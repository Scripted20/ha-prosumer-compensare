"""Config flow for Prosumer Compensare integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.selector import (
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
    DEFAULT_PRET_IMPORT,
    DEFAULT_PRET_EXPORT,
    DEFAULT_RAPORT,
)


class ProsumerCompensareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Prosumer Compensare."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._sensor_data: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Select energy sensor entities."""
        errors = {}

        if user_input is not None:
            # Validate that required sensors exist
            total_import = user_input.get(CONF_TOTAL_IMPORT)
            total_export = user_input.get(CONF_TOTAL_EXPORT)

            if not total_import or not total_export:
                errors["base"] = "missing_required"
            else:
                state_import = self.hass.states.get(total_import)
                state_export = self.hass.states.get(total_export)

                if state_import is None:
                    errors[CONF_TOTAL_IMPORT] = "entity_not_found"
                elif state_export is None:
                    errors[CONF_TOTAL_EXPORT] = "entity_not_found"
                else:
                    self._sensor_data = user_input
                    return await self.async_step_prices()

        sensor_selector = EntitySelector(
            EntitySelectorConfig(domain="sensor")
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOTAL_IMPORT): sensor_selector,
                    vol.Required(CONF_TOTAL_EXPORT): sensor_selector,
                    vol.Optional(CONF_TODAY_IMPORT): sensor_selector,
                    vol.Optional(CONF_TODAY_EXPORT): sensor_selector,
                    vol.Optional(CONF_GRID_POWER): sensor_selector,
                    vol.Optional(CONF_PV_POWER): sensor_selector,
                    vol.Optional(CONF_BATTERY_SOC): sensor_selector,
                }
            ),
            errors=errors,
        )

    async def async_step_prices(self, user_input=None):
        """Step 2: Configure prices and compensation ratio."""
        if user_input is not None:
            # Merge sensor data with price data
            data = {**self._sensor_data, **user_input}

            # Set unique ID based on the import sensor to prevent duplicates
            await self.async_set_unique_id(
                f"prosumer_{self._sensor_data[CONF_TOTAL_IMPORT]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Prosumer Compensare",
                data=data,
            )

        return self.async_show_form(
            step_id="prices",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRET_IMPORT, default=DEFAULT_PRET_IMPORT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=5.0,
                            step=0.001,
                            unit_of_measurement="RON/kWh",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_PRET_EXPORT, default=DEFAULT_PRET_EXPORT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=3.0,
                            step=0.001,
                            unit_of_measurement="RON/kWh",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_RAPORT, default=DEFAULT_RAPORT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1.0,
                            max=5.0,
                            step=0.1,
                            unit_of_measurement="x",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ProsumerCompensareOptionsFlow(config_entry)


class ProsumerCompensareOptionsFlow(OptionsFlow):
    """Handle options flow for Prosumer Compensare."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRET_IMPORT,
                        default=current.get(CONF_PRET_IMPORT, DEFAULT_PRET_IMPORT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=5.0,
                            step=0.001,
                            unit_of_measurement="RON/kWh",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_PRET_EXPORT,
                        default=current.get(CONF_PRET_EXPORT, DEFAULT_PRET_EXPORT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=3.0,
                            step=0.001,
                            unit_of_measurement="RON/kWh",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_RAPORT,
                        default=current.get(CONF_RAPORT, DEFAULT_RAPORT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1.0,
                            max=5.0,
                            step=0.1,
                            unit_of_measurement="x",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
