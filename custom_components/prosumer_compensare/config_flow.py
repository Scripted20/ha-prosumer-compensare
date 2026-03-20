"""Config flow for Prosumer Compensare integration."""
from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DateSelector,
    DateSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_TOTAL_IMPORT,
    CONF_TOTAL_EXPORT,
    CONF_TODAY_IMPORT,
    CONF_TODAY_EXPORT,
    CONF_GRID_POWER,
    CONF_PV_POWER,
    CONF_BATTERY_SOC,
    CONF_PRET_IMPORT,
    CONF_PRET_EXPORT,
    CONF_RAPORT,
    CONF_DATA_INSTALARE,
    CONF_DATA_CICLU,
    DEFAULT_PRET_IMPORT,
    DEFAULT_PRET_EXPORT,
    DEFAULT_RAPORT,
)

SENSOR_SELECTOR = EntitySelector(EntitySelectorConfig(domain="sensor"))
DATE_SELECTOR = DateSelector(DateSelectorConfig())


async def _detect_from_energy(hass) -> dict:
    """Auto-detect sensors and prices from HA Energy configuration."""
    detected = {}

    try:
        prefs = await hass.async_add_executor_job(
            lambda: hass.data.get("energy_manager")
        )
        if prefs is None:
            # Try WebSocket approach
            prefs_data = await hass.services.async_call(
                "energy", "get_prefs", blocking=True
            )
    except Exception:
        pass

    # Use websocket to get energy prefs
    try:
        from homeassistant.components.energy import async_get_manager
        manager = await async_get_manager(hass)
        prefs_data = manager.data
    except Exception:
        return detected

    if not prefs_data:
        return detected

    sources = prefs_data.get("energy_sources", [])

    for source in sources:
        if source.get("type") == "grid":
            # Import (flow_from)
            flow_from = source.get("flow_from", [])
            if flow_from:
                today_import = flow_from[0].get("stat_energy_from", "")
                detected[CONF_TODAY_IMPORT] = today_import
                # Try to find the total variant
                total_import = today_import.replace("today_", "total_")
                if hass.states.get(total_import):
                    detected[CONF_TOTAL_IMPORT] = total_import
                # Get price
                price = flow_from[0].get("number_energy_price")
                if price:
                    detected[CONF_PRET_IMPORT] = price

            # Export (flow_to)
            flow_to = source.get("flow_to", [])
            if flow_to:
                today_export = flow_to[0].get("stat_energy_to", "")
                detected[CONF_TODAY_EXPORT] = today_export
                total_export = today_export.replace("today_", "total_")
                if hass.states.get(total_export):
                    detected[CONF_TOTAL_EXPORT] = total_export
                price = flow_to[0].get("number_energy_price")
                if price:
                    detected[CONF_PRET_EXPORT] = price

        elif source.get("type") == "solar":
            solar_entity = source.get("stat_energy_from", "")
            # Derive PV power and grid power from the entity prefix
            prefix = solar_entity.rsplit("_today_", 1)[0] if "_today_" in solar_entity else ""
            if prefix:
                pv = f"{prefix}_pv_power"
                if hass.states.get(pv):
                    detected[CONF_PV_POWER] = pv
                grid = f"{prefix}_grid_power"
                if hass.states.get(grid):
                    detected[CONF_GRID_POWER] = grid
                battery = f"{prefix}_battery"
                if hass.states.get(battery):
                    detected[CONF_BATTERY_SOC] = battery

    return detected


def _sensor_schema(defaults: dict | None = None) -> vol.Schema:
    """Build sensor selection schema with optional defaults."""
    d = defaults or {}
    schema = {}

    for key in (CONF_TOTAL_IMPORT, CONF_TOTAL_EXPORT):
        if key in d:
            schema[vol.Required(key, default=d[key])] = SENSOR_SELECTOR
        else:
            schema[vol.Required(key)] = SENSOR_SELECTOR

    for key in (CONF_TODAY_IMPORT, CONF_TODAY_EXPORT, CONF_GRID_POWER, CONF_PV_POWER, CONF_BATTERY_SOC):
        if key in d and d[key]:
            schema[vol.Optional(key, default=d[key])] = SENSOR_SELECTOR
        else:
            schema[vol.Optional(key)] = SENSOR_SELECTOR

    return vol.Schema(schema)


def _prices_schema(defaults: dict | None = None) -> vol.Schema:
    """Build prices + dates schema."""
    d = defaults or {}
    today = date.today()
    default_ciclu = d.get(CONF_DATA_CICLU, f"{today.year}-03-01")
    default_instalare = d.get(CONF_DATA_INSTALARE, "")

    schema = {
        vol.Required(
            CONF_PRET_IMPORT,
            default=d.get(CONF_PRET_IMPORT, DEFAULT_PRET_IMPORT),
        ): NumberSelector(
            NumberSelectorConfig(
                min=0.1, max=5.0, step=0.001,
                unit_of_measurement="RON/kWh",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_PRET_EXPORT,
            default=d.get(CONF_PRET_EXPORT, DEFAULT_PRET_EXPORT),
        ): NumberSelector(
            NumberSelectorConfig(
                min=0.1, max=3.0, step=0.001,
                unit_of_measurement="RON/kWh",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_RAPORT,
            default=d.get(CONF_RAPORT, DEFAULT_RAPORT),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1.0, max=5.0, step=0.1,
                unit_of_measurement="x",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_DATA_CICLU,
            default=default_ciclu,
        ): DATE_SELECTOR,
    }

    if default_instalare:
        schema[vol.Optional(CONF_DATA_INSTALARE, default=default_instalare)] = DATE_SELECTOR
    else:
        schema[vol.Optional(CONF_DATA_INSTALARE)] = DATE_SELECTOR

    return vol.Schema(schema)


class ProsumerCompensareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Prosumer Compensare."""

    VERSION = 1

    def __init__(self) -> None:
        self._sensor_data: dict = {}
        self._detected: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Select energy sensor entities (pre-filled from Energy config)."""
        errors = {}

        # Auto-detect on first load
        if not self._detected:
            self._detected = await _detect_from_energy(self.hass)

        if user_input is not None:
            total_import = user_input.get(CONF_TOTAL_IMPORT)
            total_export = user_input.get(CONF_TOTAL_EXPORT)

            if not total_import or not total_export:
                errors["base"] = "missing_required"
            else:
                if self.hass.states.get(total_import) is None:
                    errors[CONF_TOTAL_IMPORT] = "entity_not_found"
                elif self.hass.states.get(total_export) is None:
                    errors[CONF_TOTAL_EXPORT] = "entity_not_found"
                else:
                    self._sensor_data = user_input
                    return await self.async_step_prices()

        return self.async_show_form(
            step_id="user",
            data_schema=_sensor_schema(self._detected),
            errors=errors,
        )

    async def async_step_prices(self, user_input=None):
        """Step 2: Configure prices, ratio, and dates."""
        if user_input is not None:
            data = {**self._sensor_data, **user_input}

            await self.async_set_unique_id(
                f"prosumer_{self._sensor_data[CONF_TOTAL_IMPORT]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Prosumer Compensare",
                data=data,
            )

        # Merge detected prices into defaults
        defaults = dict(self._detected)
        return self.async_show_form(
            step_id="prices",
            data_schema=_prices_schema(defaults),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ProsumerCompensareOptionsFlow(config_entry)


class ProsumerCompensareOptionsFlow(OptionsFlow):
    """Handle options flow — menu with sensors, prices, and dates."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["sensors", "prices"],
        )

    async def async_step_sensors(self, user_input=None):
        if user_input is not None:
            new_data = dict(self._config_entry.data)
            new_data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="sensors",
            data_schema=_sensor_schema(dict(self._config_entry.data)),
        )

    async def async_step_prices(self, user_input=None):
        if user_input is not None:
            new_data = dict(self._config_entry.data)
            new_data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="prices",
            data_schema=_prices_schema(dict(self._config_entry.data)),
        )
