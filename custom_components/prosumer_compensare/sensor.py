"""Sensor platform for Prosumer Compensare integration."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    CONF_TOTAL_IMPORT,
    CONF_TOTAL_EXPORT,
    CONF_TODAY_IMPORT,
    CONF_TODAY_EXPORT,
    CONF_GRID_POWER,
    CONF_PRET_IMPORT,
    CONF_PRET_EXPORT,
    CONF_RAPORT,
    DEFAULT_PRET_IMPORT,
    DEFAULT_PRET_EXPORT,
    DEFAULT_RAPORT,
    CYCLE_START_MONTH,
    CYCLE_START_DAY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prosumer Compensare sensors from a config entry."""
    config = hass.data[DOMAIN][entry.entry_id]

    # Load persisted baselines (March 1 values)
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    stored = await store.async_load() or {}

    entities: list[SensorEntity] = [
        ProsumerCreditKwhSensor(hass, entry, config, store, stored),
        ProsumerCreditRonSensor(hass, entry, config, store, stored),
        ProsumerProcentCompensareSensor(hass, entry, config, store, stored),
    ]

    # Optional sensors based on config
    if config.get(CONF_TODAY_IMPORT) and config.get(CONF_TODAY_EXPORT):
        entities.append(ProsumerBalantaAziSensor(hass, entry, config))

    if config.get(CONF_GRID_POWER):
        entities.append(GridDirectieSensor(hass, entry, config))

    async_add_entities(entities)


class ProsumerBaseSensor(SensorEntity):
    """Base class for prosumer sensors with March baseline tracking."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict,
        store: Store | None = None,
        stored: dict | None = None,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self._entry = entry
        self._config = config
        self._store = store
        self._stored = stored or {}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Prosumer Compensare",
            "manufacturer": "Community",
            "model": "Compensare Energie Romania",
        }

    def _get_pret_import(self) -> float:
        """Get import price from options or config."""
        return self._entry.options.get(
            CONF_PRET_IMPORT,
            self._config.get(CONF_PRET_IMPORT, DEFAULT_PRET_IMPORT),
        )

    def _get_pret_export(self) -> float:
        """Get export price from options or config."""
        return self._entry.options.get(
            CONF_PRET_EXPORT,
            self._config.get(CONF_PRET_EXPORT, DEFAULT_PRET_EXPORT),
        )

    def _get_raport(self) -> float:
        """Get compensation ratio from options or config."""
        return self._entry.options.get(
            CONF_RAPORT,
            self._config.get(CONF_RAPORT, DEFAULT_RAPORT),
        )

    def _get_float(self, entity_id: str | None) -> float:
        """Get float value from an entity state."""
        if not entity_id:
            return 0.0
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0

    def _get_since_march(self, entity_id: str, baseline_key: str) -> float:
        """Get value accumulated since March 1."""
        current = self._get_float(entity_id)
        baseline = self._stored.get(baseline_key, 0.0)

        today = date.today()
        # Check if we need to reset baseline (it's March 1 or later in a new cycle)
        if today.month == CYCLE_START_MONTH and today.day == CYCLE_START_DAY:
            if self._stored.get(f"{baseline_key}_year") != today.year:
                # New cycle — save current value as baseline
                self._stored[baseline_key] = current
                self._stored[f"{baseline_key}_year"] = today.year
                baseline = current
                if self._store:
                    self.hass.async_create_task(
                        self._store.async_save(self._stored)
                    )

        # If no baseline stored yet, use current (starts from 0)
        if baseline_key not in self._stored:
            self._stored[baseline_key] = current
            if self._store:
                self.hass.async_create_task(
                    self._store.async_save(self._stored)
                )
            return 0.0

        return max(0.0, current - baseline)


class ProsumerCreditKwhSensor(ProsumerBaseSensor):
    """Sensor showing free kWh credit available."""

    _attr_name = "Credit Gratuit"
    _attr_unique_id_suffix = "credit_kwh"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, store, stored):
        """Initialize."""
        super().__init__(hass, entry, config, store, stored)
        self._attr_unique_id = f"{entry.entry_id}_credit_kwh"

    async def async_added_to_hass(self) -> None:
        """Track source entity state changes."""
        await super().async_added_to_hass()

        entities_to_track = [
            self._config[CONF_TOTAL_IMPORT],
            self._config[CONF_TOTAL_EXPORT],
        ]
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entities_to_track, self._handle_update
            )
        )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        """Handle source sensor state change."""
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        """Recalculate credit."""
        exported = self._get_since_march(
            self._config[CONF_TOTAL_EXPORT], "baseline_export"
        )
        imported = self._get_since_march(
            self._config[CONF_TOTAL_IMPORT], "baseline_import"
        )
        raport = self._get_raport()

        credit = (exported / raport) - imported if raport > 0 else 0
        self._attr_native_value = round(credit, 1)

        # Set icon based on credit
        self._attr_icon = (
            "mdi:battery-plus-variant" if credit >= 0
            else "mdi:battery-minus-variant"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        exported = self._get_since_march(
            self._config[CONF_TOTAL_EXPORT], "baseline_export"
        )
        imported = self._get_since_march(
            self._config[CONF_TOTAL_IMPORT], "baseline_import"
        )
        raport = self._get_raport()

        return {
            "exported_din_martie": round(exported, 1),
            "imported_din_martie": round(imported, 1),
            "echivalent_gratuit": round(exported / raport, 1) if raport > 0 else 0,
            "raport": raport,
            "status": self._get_status(),
        }

    def _get_status(self) -> str:
        """Get human-readable status."""
        val = self._attr_native_value or 0
        if val > 10:
            return "Ai credit bun!"
        if val > 0:
            return "Credit pozitiv"
        if val > -10:
            return "Aproape echilibru"
        return "Depasit - platesti diferenta"


class ProsumerCreditRonSensor(ProsumerBaseSensor):
    """Sensor showing monetary balance in RON."""

    _attr_name = "Credit Gratuit RON"
    _attr_native_unit_of_measurement = "RON"
    _attr_icon = "mdi:cash-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, store, stored):
        """Initialize."""
        super().__init__(hass, entry, config, store, stored)
        self._attr_unique_id = f"{entry.entry_id}_credit_ron"

    async def async_added_to_hass(self) -> None:
        """Track source entity state changes."""
        await super().async_added_to_hass()

        entities_to_track = [
            self._config[CONF_TOTAL_IMPORT],
            self._config[CONF_TOTAL_EXPORT],
        ]
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entities_to_track, self._handle_update
            )
        )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        """Handle source sensor state change."""
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        """Recalculate monetary balance."""
        exported = self._get_since_march(
            self._config[CONF_TOTAL_EXPORT], "baseline_export"
        )
        imported = self._get_since_march(
            self._config[CONF_TOTAL_IMPORT], "baseline_import"
        )
        pret_export = self._get_pret_export()
        pret_import = self._get_pret_import()

        balance = (exported * pret_export) - (imported * pret_import)
        self._attr_native_value = round(balance, 2)


class ProsumerProcentCompensareSensor(ProsumerBaseSensor):
    """Sensor showing what % of import is covered by export."""

    _attr_name = "Procent Compensare"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:percent"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, store, stored):
        """Initialize."""
        super().__init__(hass, entry, config, store, stored)
        self._attr_unique_id = f"{entry.entry_id}_procent"

    async def async_added_to_hass(self) -> None:
        """Track source entity state changes."""
        await super().async_added_to_hass()

        entities_to_track = [
            self._config[CONF_TOTAL_IMPORT],
            self._config[CONF_TOTAL_EXPORT],
        ]
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entities_to_track, self._handle_update
            )
        )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        """Handle source sensor state change."""
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        """Recalculate compensation percentage."""
        exported = self._get_since_march(
            self._config[CONF_TOTAL_EXPORT], "baseline_export"
        )
        imported = self._get_since_march(
            self._config[CONF_TOTAL_IMPORT], "baseline_import"
        )
        raport = self._get_raport()
        credit_kwh = exported / raport if raport > 0 else 0

        if imported > 0:
            self._attr_native_value = round((credit_kwh / imported) * 100, 1)
        elif credit_kwh > 0:
            self._attr_native_value = 100.0
        else:
            self._attr_native_value = 0.0


class ProsumerBalantaAziSensor(ProsumerBaseSensor):
    """Sensor showing today's balance."""

    _attr_name = "Balanta Azi"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:scale-balance"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config):
        """Initialize."""
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_balanta_azi"

    async def async_added_to_hass(self) -> None:
        """Track source entity state changes."""
        await super().async_added_to_hass()

        entities_to_track = []
        if self._config.get(CONF_TODAY_IMPORT):
            entities_to_track.append(self._config[CONF_TODAY_IMPORT])
        if self._config.get(CONF_TODAY_EXPORT):
            entities_to_track.append(self._config[CONF_TODAY_EXPORT])

        if entities_to_track:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, entities_to_track, self._handle_update
                )
            )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        """Handle source sensor state change."""
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        """Recalculate today's balance."""
        exported = self._get_float(self._config.get(CONF_TODAY_EXPORT))
        imported = self._get_float(self._config.get(CONF_TODAY_IMPORT))
        raport = self._get_raport()

        balance = (exported / raport) - imported if raport > 0 else 0
        self._attr_native_value = round(balance, 2)


class GridDirectieSensor(ProsumerBaseSensor):
    """Sensor showing current grid direction (import/export/balanced)."""

    _attr_name = "Grid Directie"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, hass, entry, config):
        """Initialize."""
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_grid_directie"

    async def async_added_to_hass(self) -> None:
        """Track grid power state changes."""
        await super().async_added_to_hass()

        grid_entity = self._config.get(CONF_GRID_POWER)
        if grid_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [grid_entity], self._handle_update
                )
            )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        """Handle grid power state change."""
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        """Update grid direction."""
        grid = self._get_float(self._config.get(CONF_GRID_POWER))

        if grid > 50:
            self._attr_native_value = f"Import {round(grid)}W"
            self._attr_icon = "mdi:transmission-tower-import"
        elif grid < -50:
            self._attr_native_value = f"Export {round(abs(grid))}W"
            self._attr_icon = "mdi:transmission-tower-export"
        else:
            self._attr_native_value = "Echilibru"
            self._attr_icon = "mdi:transmission-tower"
