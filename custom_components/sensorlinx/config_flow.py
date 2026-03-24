from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from sensorlinx import SensorLinxClient
from sensorlinx.exceptions import AuthError, SensorLinxError

from .const import DOMAIN

_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _authenticate(hass: HomeAssistant, email: str, password: str) -> str:
    """Validate credentials and return JWT token. Raises on failure."""
    client = SensorLinxClient()
    try:
        return await hass.async_add_executor_job(client.login, email, password)
    finally:
        await hass.async_add_executor_job(client.close)


class SensorLinxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HBX SensorLinx."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                token = await _authenticate(
                    self.hass,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except SensorLinxError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        "token": token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_SCHEMA,
            errors=errors,
        )
