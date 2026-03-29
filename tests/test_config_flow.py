"""Tests for the SensorLinx config flow and options flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType
from pysensorlinx import InvalidCredentialsError, LoginError

from .conftest import CONF_DATA


def _patch_auth(side_effect=None):
    mock = AsyncMock(side_effect=side_effect)
    return patch("custom_components.sensorlinx.config_flow._authenticate", mock)


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


async def test_config_flow_success(hass, enable_custom_integrations, mock_sensorlinx):
    """Valid credentials complete the flow and create an entry."""
    with _patch_auth():
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == CONF_DATA[CONF_EMAIL]
    assert result["data"][CONF_EMAIL] == CONF_DATA[CONF_EMAIL]
    assert result["data"][CONF_PASSWORD] == CONF_DATA[CONF_PASSWORD]
    assert "token" not in result["data"]


async def test_config_flow_invalid_credentials(
    hass, enable_custom_integrations, mock_sensorlinx
):
    with _patch_auth(side_effect=InvalidCredentialsError("bad password")):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_config_flow_login_error(
    hass, enable_custom_integrations, mock_sensorlinx
):
    with _patch_auth(side_effect=LoginError("timeout")):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_runtime_error(
    hass, enable_custom_integrations, mock_sensorlinx
):
    with _patch_auth(side_effect=RuntimeError("network down")):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_timeout_shows_cannot_connect(
    hass, enable_custom_integrations, mock_sensorlinx
):
    """A TimeoutError during login is reported as cannot_connect, not an unhandled exception."""
    with _patch_auth(side_effect=TimeoutError()):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_duplicate_aborts(
    hass, enable_custom_integrations, mock_sensorlinx
):
    with _patch_auth():
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    with _patch_auth():
        result = await hass.config_entries.flow.async_init(
            "sensorlinx", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


async def test_reauth_form_prefills_email(hass, setup_integration):
    """Reauth confirm form includes the current email as a description placeholder."""
    entry, _ = setup_integration

    result = await hass.config_entries.flow.async_init(
        "sensorlinx",
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["email"] == entry.data[CONF_EMAIL]


async def test_options_flow_default_interval(hass, setup_integration):
    """Options form shows default scan interval."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert "scan_interval" in schema_keys


async def test_options_flow_sets_interval(hass, setup_integration):
    """Submitting options saves both scan_interval and timeout."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 120, "timeout": 45}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 120
    assert entry.options["timeout"] == 45


async def test_options_flow_rejects_out_of_range(hass, setup_integration):
    """Scan interval outside 30–3600 is rejected."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)

    import voluptuous as vol

    with pytest.raises((vol.Invalid, Exception)):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 5}
        )
