import sys
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# Mock Home Assistant modules before importing the component
mock_hass = MagicMock()
sys.modules["homeassistant"] = mock_hass
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.exceptions"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()

# Mock DataUpdateCoordinator
class MockDataUpdateCoordinator:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = MockDataUpdateCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = Exception

# Mock jvcprojector structure
mock_jvc = MagicMock()
mock_jvc.__path__ = []
sys.modules["jvcprojector"] = mock_jvc

mock_command_pkg = MagicMock()
mock_command_pkg.__path__ = []
sys.modules["jvcprojector.command"] = mock_command_pkg

# Mock jvcprojector.command.base
mock_command_base = MagicMock()
sys.modules["jvcprojector.command.base"] = mock_command_base
mock_command_base.Command = MagicMock
mock_command_base.Spec = MagicMock
mock_command_base.Parameter = MagicMock
mock_command_base.LIMP_MODE = MagicMock
mock_command_base.MapParameter = MagicMock

# Mock jvcprojector.command.command
mock_command_command = MagicMock()
sys.modules["jvcprojector.command.command"] = mock_command_command
mock_command_command.SPECIFICATIONS = []

mock_error = MagicMock()
class JvcProjectorError(Exception): pass
class JvcProjectorAuthError(JvcProjectorError): pass
mock_error.JvcProjectorError = JvcProjectorError
mock_error.JvcProjectorAuthError = JvcProjectorAuthError
sys.modules["jvcprojector.error"] = mock_error

mock_projector = MagicMock()
sys.modules["jvcprojector.projector"] = mock_projector

# Ensure we can import the module
import custom_components.jvc_projector.coordinator as coord_module

@pytest.mark.asyncio
async def test_shutdown_timeout():
    """Test that async_shutdown proceeds even if lock is held."""

    # Setup mock device
    mock_device = AsyncMock()
    mock_device.host = "1.2.3.4"
    mock_device.disconnect = AsyncMock()

    # Setup coordinator
    hass = MagicMock()
    coordinator = coord_module.JvcProjectorDataUpdateCoordinator(
        hass, mock_device, "AA:BB:CC:DD:EE:FF", "ModelX", "1.0"
    )
    coordinator._connected = True # Ensure disconnect is attempted

    # Simulate the lock being held by a stuck update/connect task
    await coordinator._lock.acquire()

    # We expect async_shutdown to NOT hang forever.
    # It should timeout internally (e.g. 2s) and force disconnect.
    # We set a test timeout slightly larger than expected internal timeout.

    start_time = asyncio.get_running_loop().time()

    try:
        # If fix works, this should return in ~2-3 seconds
        # If fix is missing, this will raise TimeoutError after 5s
        await asyncio.wait_for(coordinator.async_shutdown(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("async_shutdown hung waiting for lock (fix not implemented?)")

    end_time = asyncio.get_running_loop().time()
    duration = end_time - start_time

    # Verify disconnect was called
    mock_device.disconnect.assert_called_once()

    # Cleanup lock for test sanity
    coordinator._lock.release()

@pytest.mark.asyncio
async def test_shutdown_normal():
    """Test that async_shutdown works normally when lock is free."""

    mock_device = AsyncMock()
    mock_device.host = "1.2.3.4"
    hass = MagicMock()
    coordinator = coord_module.JvcProjectorDataUpdateCoordinator(
        hass, mock_device, "AA:BB:CC:DD:EE:FF", "ModelX", "1.0"
    )
    coordinator._connected = True # Ensure disconnect is attempted

    # Lock is free
    await coordinator.async_shutdown()

    mock_device.disconnect.assert_called_once()
