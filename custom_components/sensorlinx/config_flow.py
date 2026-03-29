from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from pysensorlinx import InvalidCredentialsError, LoginError, Sensorlinx

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MAX_TIMEOUT,
    MIN_SCAN_INTERVAL,
    MIN_TIMEOUT,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _authenticate(hass: HomeAssistant, email: str, password: str) -> None:
    """Validate credentials against the SensorLinx API. Raises on failure."""
    client = Sensorlinx()
    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await client.login(username=email, password=password)
    finally:
        await client.close()


class SensorLinxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HBX SensorLinx."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SensorLinxOptionsFlowHandler:
        """Return the options flow handler."""
        return SensorLinxOptionsFlowHandler()

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial user configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _authenticate(
                    self.hass,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except (LoginError, RuntimeError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication when credentials become invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show re-authentication form and update the entry on success."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            try:
                await _authenticate(self.hass, email, password)
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except (LoginError, RuntimeError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                _LOGGER.debug("Re-authentication successful for %s", email)
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL,
                        default=reauth_entry.data.get(CONF_EMAIL, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"email": reauth_entry.data.get(CONF_EMAIL, "")},
        )


class SensorLinxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SensorLinx options (scan interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the options form."""
        if user_input is not None:
            # NumberSelector submits floats from the UI; coerce to int so
            # entry.options always contains integers regardless of input source.
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
                },
            )

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, SCAN_INTERVAL
        )
        current_timeout = self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(CONF_TIMEOUT, default=current_timeout): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_TIMEOUT,
                            max=MAX_TIMEOUT,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
