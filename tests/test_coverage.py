"""Targeted tests for previously uncovered code paths."""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from pysensorlinx import InvalidCredentialsError, LoginError

from .conftest import CONF_DATA
from .conftest import ha_device_id as _ha_device_id

# ---------------------------------------------------------------------------
# async_setup_entry — login error paths  (__init__.py lines 44-51)
# ---------------------------------------------------------------------------


async def test_setup_login_timeout_gives_setup_retry(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """TimeoutError during login → ConfigEntryNotReady (SETUP_RETRY)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    client.login.side_effect = asyncio.TimeoutError()

    entry = MockConfigEntry(
        domain="sensorlinx", data=CONF_DATA, entry_id="test_login_timeout"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_credentials_gives_setup_error(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """InvalidCredentialsError during login → ConfigEntryAuthFailed (SETUP_ERROR)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    client.login.side_effect = InvalidCredentialsError("wrong password")

    entry = MockConfigEntry(
        domain="sensorlinx", data=CONF_DATA, entry_id="test_login_invalid_creds"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_login_error_gives_setup_retry(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """LoginError during login → ConfigEntryNotReady (SETUP_RETRY)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    client.login.side_effect = LoginError("service unavailable")

    entry = MockConfigEntry(
        domain="sensorlinx", data=CONF_DATA, entry_id="test_login_error"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


# ---------------------------------------------------------------------------
# async_remove_config_entry_device — no coordinator data (__init__.py line 107)
# ---------------------------------------------------------------------------


async def test_remove_device_allowed_when_coordinator_data_empty(
    hass, setup_integration
):
    """Returns True immediately when coordinator has no data (empty dict)."""
    from unittest.mock import MagicMock

    from custom_components.sensorlinx import async_remove_config_entry_device

    entry, coordinator = setup_integration
    coordinator.data.clear()  # make coordinator.data falsy

    fake_device = MagicMock()
    fake_device.identifiers = {("sensorlinx", "ABC123")}

    result = await async_remove_config_entry_device(hass, entry, fake_device)
    assert result is True


# ---------------------------------------------------------------------------
# _sync_code_from_device_id — device not a SensorLinx device (services.py:63)
# ---------------------------------------------------------------------------


async def test_service_raises_for_non_sensorlinx_device(hass, setup_integration):
    """ServiceValidationError when the device_id belongs to a non-SensorLinx device."""
    entry, _ = setup_integration
    dev_reg = dr.async_get(hass)
    other_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_integration", "xyz")},
    )

    with pytest.raises(Exception) as exc_info:
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": other_device.id, "mode": "heat"},
            blocking=True,
        )
    assert "not a SensorLinx device" in str(exc_info.value)


# ---------------------------------------------------------------------------
# _find_device — coordinator empty + device not found (services.py:81, 96)
# ---------------------------------------------------------------------------


async def test_service_raises_when_sync_code_not_in_coordinator(
    hass, setup_integration
):
    """ServiceValidationError when sync_code exists in registry but not coordinator data."""
    entry, coordinator = setup_integration
    dev_reg = dr.async_get(hass)

    # Register a SensorLinx device whose sync_code is absent from coordinator data
    ghost_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("sensorlinx", "GHOST99")},
    )

    with pytest.raises(Exception) as exc_info:
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": ghost_device.id, "mode": "heat"},
            blocking=True,
        )
    assert "GHOST99" in str(exc_info.value)


async def test_service_raises_when_coordinator_has_no_data(hass, setup_integration):
    """ServiceValidationError when coordinator data is empty (hits the continue branch)."""
    entry, coordinator = setup_integration
    coordinator.data.clear()  # coordinator.data is now falsy → hits continue

    with pytest.raises(Exception):
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": _ha_device_id(hass, "ABC123"), "mode": "heat"},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# _call_with_reauth — TimeoutError (services.py:129)
# ---------------------------------------------------------------------------


async def test_service_call_timeout_raises_service_validation_error(
    hass, setup_integration, mock_sensorlinx
):
    """TimeoutError from set_device_parameter → ServiceValidationError with 'timed out'."""
    _, client = mock_sensorlinx
    client.set_device_parameter.side_effect = asyncio.TimeoutError()

    with pytest.raises(Exception) as exc_info:
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": _ha_device_id(hass, "ABC123"), "mode": "heat"},
            blocking=True,
        )
    assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# SensorLinxBaseEntity.device_info — KeyError path (entity.py:52-53)
# ---------------------------------------------------------------------------


async def test_entity_device_info_returns_none_when_data_gone(hass, setup_integration):
    """device_info returns None when coordinator data no longer contains the device."""
    from custom_components.sensorlinx.entity import SensorLinxBaseEntity

    _, coordinator = setup_integration

    entity = SensorLinxBaseEntity(coordinator, "bld-1", "ABC123")
    assert entity.device_info is not None  # sanity check

    coordinator.data.clear()
    assert entity.device_info is None
