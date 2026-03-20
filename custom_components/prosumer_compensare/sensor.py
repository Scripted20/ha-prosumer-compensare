"""Sensor platform for Prosumer Compensare integration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.components.recorder.statistics import (
    statistics_during_period,
)
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

from .const import (
    DOMAIN,
    CONF_TOTAL_IMPORT,
    CONF_TOTAL_EXPORT,
    CONF_TODAY_IMPORT,
    CONF_TODAY_EXPORT,
    CONF_GRID_POWER,
    CONF_PRET_IMPORT,
    CONF_PRET_EXPORT,
    CONF_RAPORT,
    CONF_DATA_INSTALARE,
    CONF_DATA_CICLU,
    DEFAULT_PRET_IMPORT,
    DEFAULT_PRET_EXPORT,
    DEFAULT_RAPORT,
)

_LOGGER = logging.getLogger(__name__)


async def _get_baseline_at_date(
    hass: HomeAssistant, entity_id: str, date_str: str
) -> float | None:
    """Get the sensor value at a specific date from recorder statistics."""
    if not date_str:
        return None

    try:
        dt = datetime.fromisoformat(date_str)
        start = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=23, minutes=59, seconds=59)

        stats = await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            start,
            end,
            {entity_id},
            "hour",
            None,
            {"state"},
        )

        entity_stats = stats.get(entity_id)
        if entity_stats and len(entity_stats) > 0:
            return entity_stats[0].get("state")
    except Exception:
        _LOGGER.warning(
            "Could not read baseline at %s for %s from recorder",
            date_str, entity_id
        )

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prosumer Compensare sensors from a config entry."""
    config = hass.data[DOMAIN][entry.entry_id]

    # Read baselines from recorder for both dates
    data_ciclu = config.get(CONF_DATA_CICLU)
    data_instalare = config.get(CONF_DATA_INSTALARE)

    ciclu_import = await _get_baseline_at_date(
        hass, config[CONF_TOTAL_IMPORT], data_ciclu
    )
    ciclu_export = await _get_baseline_at_date(
        hass, config[CONF_TOTAL_EXPORT], data_ciclu
    )

    instalare_import = None
    instalare_export = None
    if data_instalare:
        instalare_import = await _get_baseline_at_date(
            hass, config[CONF_TOTAL_IMPORT], data_instalare
        )
        instalare_export = await _get_baseline_at_date(
            hass, config[CONF_TOTAL_EXPORT], data_instalare
        )

    _LOGGER.info(
        "Prosumer baselines — ciclu(%s): imp=%s exp=%s | instalare(%s): imp=%s exp=%s",
        data_ciclu, ciclu_import, ciclu_export,
        data_instalare, instalare_import, instalare_export,
    )

    baselines = {
        "ciclu_import": ciclu_import,
        "ciclu_export": ciclu_export,
        "instalare_import": instalare_import,
        "instalare_export": instalare_export,
    }

    entities: list[SensorEntity] = [
        # Ciclu sensors (from selected cycle date)
        ProsumerCreditKwhSensor(hass, entry, config, baselines, "ciclu"),
        ProsumerCreditRonSensor(hass, entry, config, baselines, "ciclu"),
        ProsumerProcentCompensareSensor(hass, entry, config, baselines, "ciclu"),
    ]

    # Total sensors (from install date) — only if install date is set
    if data_instalare:
        entities.extend([
            ProsumerCreditKwhSensor(hass, entry, config, baselines, "total"),
            ProsumerCreditRonSensor(hass, entry, config, baselines, "total"),
            ProsumerProcentCompensareSensor(hass, entry, config, baselines, "total"),
        ])

    if config.get(CONF_TODAY_IMPORT) and config.get(CONF_TODAY_EXPORT):
        entities.append(ProsumerBalantaAziSensor(hass, entry, config))

    if config.get(CONF_GRID_POWER):
        entities.append(GridDirectieSensor(hass, entry, config))

    async_add_entities(entities)


class ProsumerBaseSensor(SensorEntity):
    """Base class for prosumer sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict,
        baselines: dict | None = None,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._config = config
        self._baselines = baselines or {}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Prosumer Compensare",
            "manufacturer": "Community",
            "model": "Compensare Energie Romania",
        }

    def _get_pret_import(self) -> float:
        return self._entry.options.get(
            CONF_PRET_IMPORT,
            self._config.get(CONF_PRET_IMPORT, DEFAULT_PRET_IMPORT),
        )

    def _get_pret_export(self) -> float:
        return self._entry.options.get(
            CONF_PRET_EXPORT,
            self._config.get(CONF_PRET_EXPORT, DEFAULT_PRET_EXPORT),
        )

    def _get_raport(self) -> float:
        return self._entry.options.get(
            CONF_RAPORT,
            self._config.get(CONF_RAPORT, DEFAULT_RAPORT),
        )

    def _get_float(self, entity_id: str | None) -> float:
        if not entity_id:
            return 0.0
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0

    def _get_since(self, entity_id: str, baseline_key: str) -> float:
        """Get value accumulated since a baseline date."""
        current = self._get_float(entity_id)
        baseline = self._baselines.get(baseline_key)
        if baseline is None:
            return 0.0
        return max(0.0, current - baseline)


class ProsumerCreditKwhSensor(ProsumerBaseSensor):
    """Sensor showing free kWh credit — for ciclu or total period."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, baselines, period: str):
        super().__init__(hass, entry, config, baselines)
        self._period = period
        if period == "total":
            self._attr_name = "Credit Total"
            self._attr_unique_id = f"{entry.entry_id}_credit_total_kwh"
        else:
            self._attr_name = "Credit Ciclu"
            self._attr_unique_id = f"{entry.entry_id}_credit_ciclu_kwh"

    @property
    def _import_key(self) -> str:
        return f"{self._period}_import"

    @property
    def _export_key(self) -> str:
        return f"{self._period}_export"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._config[CONF_TOTAL_IMPORT], self._config[CONF_TOTAL_EXPORT]],
                self._handle_update,
            )
        )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        exported = self._get_since(self._config[CONF_TOTAL_EXPORT], self._export_key)
        imported = self._get_since(self._config[CONF_TOTAL_IMPORT], self._import_key)
        raport = self._get_raport()
        credit = (exported / raport) - imported if raport > 0 else 0
        self._attr_native_value = round(credit, 1)
        self._attr_icon = (
            "mdi:battery-plus-variant" if credit >= 0
            else "mdi:battery-minus-variant"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        exported = self._get_since(self._config[CONF_TOTAL_EXPORT], self._export_key)
        imported = self._get_since(self._config[CONF_TOTAL_IMPORT], self._import_key)
        raport = self._get_raport()
        date_key = CONF_DATA_INSTALARE if self._period == "total" else CONF_DATA_CICLU
        return {
            "perioada": self._period,
            "data_start": self._config.get(date_key, "N/A"),
            "exportat": round(exported, 1),
            "importat": round(imported, 1),
            "echivalent_gratuit": round(exported / raport, 1) if raport > 0 else 0,
            "raport": raport,
            "status": self._get_status(),
        }

    def _get_status(self) -> str:
        val = self._attr_native_value or 0
        if val > 10:
            return "Ai credit bun!"
        if val > 0:
            return "Credit pozitiv"
        if val > -10:
            return "Aproape echilibru"
        return "Depasit - platesti diferenta"


class ProsumerCreditRonSensor(ProsumerBaseSensor):
    """Sensor showing monetary balance in RON — for ciclu or total."""

    _attr_native_unit_of_measurement = "RON"
    _attr_icon = "mdi:cash-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, baselines, period: str):
        super().__init__(hass, entry, config, baselines)
        self._period = period
        if period == "total":
            self._attr_name = "Credit Total RON"
            self._attr_unique_id = f"{entry.entry_id}_credit_total_ron"
        else:
            self._attr_name = "Credit Ciclu RON"
            self._attr_unique_id = f"{entry.entry_id}_credit_ciclu_ron"

    @property
    def _import_key(self) -> str:
        return f"{self._period}_import"

    @property
    def _export_key(self) -> str:
        return f"{self._period}_export"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._config[CONF_TOTAL_IMPORT], self._config[CONF_TOTAL_EXPORT]],
                self._handle_update,
            )
        )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        exported = self._get_since(self._config[CONF_TOTAL_EXPORT], self._export_key)
        imported = self._get_since(self._config[CONF_TOTAL_IMPORT], self._import_key)
        balance = (exported * self._get_pret_export()) - (imported * self._get_pret_import())
        self._attr_native_value = round(balance, 2)


class ProsumerProcentCompensareSensor(ProsumerBaseSensor):
    """Sensor showing what % of import is covered — for ciclu or total."""

    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:percent"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, baselines, period: str):
        super().__init__(hass, entry, config, baselines)
        self._period = period
        if period == "total":
            self._attr_name = "Compensare Total"
            self._attr_unique_id = f"{entry.entry_id}_procent_total"
        else:
            self._attr_name = "Compensare Ciclu"
            self._attr_unique_id = f"{entry.entry_id}_procent_ciclu"

    @property
    def _import_key(self) -> str:
        return f"{self._period}_import"

    @property
    def _export_key(self) -> str:
        return f"{self._period}_export"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._config[CONF_TOTAL_IMPORT], self._config[CONF_TOTAL_EXPORT]],
                self._handle_update,
            )
        )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        exported = self._get_since(self._config[CONF_TOTAL_EXPORT], self._export_key)
        imported = self._get_since(self._config[CONF_TOTAL_IMPORT], self._import_key)
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
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_balanta_azi"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        entities = [e for e in [
            self._config.get(CONF_TODAY_IMPORT),
            self._config.get(CONF_TODAY_EXPORT),
        ] if e]
        if entities:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, entities, self._handle_update
                )
            )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
        exported = self._get_float(self._config.get(CONF_TODAY_EXPORT))
        imported = self._get_float(self._config.get(CONF_TODAY_IMPORT))
        raport = self._get_raport()
        self._attr_native_value = round(
            (exported / raport) - imported if raport > 0 else 0, 2
        )


class GridDirectieSensor(ProsumerBaseSensor):
    """Sensor showing current grid direction."""

    _attr_name = "Grid Directie"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, hass, entry, config):
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_grid_directie"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        grid = self._config.get(CONF_GRID_POWER)
        if grid:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [grid], self._handle_update
                )
            )
        self._update_value()

    @callback
    def _handle_update(self, event: Event) -> None:
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self) -> None:
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
