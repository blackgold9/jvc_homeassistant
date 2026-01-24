import sys
import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import importlib

# --- Mocking Infrastructure ---

# Mock Home Assistant
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

# Mock jvcprojector
mock_jvc = MagicMock()
mock_jvc.__path__ = []
sys.modules["jvcprojector"] = mock_jvc

# Mock command classes
class MockCommand:
    pass

class MockPower(MockCommand): name = "power"
class MockInput(MockCommand): name = "input"
class MockPictureMode(MockCommand): name = "picture_mode"
class MockSignal(MockCommand): name = "signal"
class MockLampTime(MockCommand): name = "lamp_time"
class MockLaserPower(MockCommand): name = "laser_power"

# Setup nested module structure for jvcprojector.command
mock_command_pkg = MagicMock()
mock_command_pkg.__path__ = []
sys.modules["jvcprojector.command"] = mock_command_pkg
# IMPORTANT: Link the package to the parent mock so 'from jvcprojector import command' works as expected
mock_jvc.command = mock_command_pkg

# Mock jvcprojector.command.base
mock_command_base = MagicMock()
sys.modules["jvcprojector.command.base"] = mock_command_base
mock_command_base.Command = MockCommand
mock_command_base.Spec = MagicMock
mock_command_base.Parameter = MagicMock
mock_command_base.LIMP_MODE = MagicMock
mock_command_base.MapParameter = MagicMock
mock_command_base.SPECIFICATIONS = []

# Mock jvcprojector.command.command (if needed by capabilities or others)
mock_command_module = MagicMock()
sys.modules["jvcprojector.command.command"] = mock_command_module
mock_command_module.SPECIFICATIONS = []

# Attach mock classes to the command package so const can find them
mock_command_pkg.Power = MockPower
mock_command_pkg.Input = MockInput
mock_command_pkg.PictureMode = MockPictureMode
mock_command_pkg.Signal = MockSignal
mock_command_pkg.LightTime = MockLampTime
mock_command_pkg.LaserPower = MockLaserPower
mock_command_pkg.Power.STANDBY = "standby"
mock_command_pkg.Power.ON = "on"
mock_command_pkg.Power.OFF = "off"

# Mock jvcprojector.error
mock_error = MagicMock()
class JvcProjectorError(Exception): pass
class JvcProjectorAuthError(JvcProjectorError): pass
mock_error.JvcProjectorError = JvcProjectorError
mock_error.JvcProjectorAuthError = JvcProjectorAuthError
sys.modules["jvcprojector.error"] = mock_error
sys.modules["jvcprojector.projector"] = MagicMock()

# --- Imports after mocking ---
import custom_components.jvc_projector.coordinator as coord_module
from custom_components.jvc_projector import const, capabilities

# Reload modules to ensure they use OUR mocks, not stale ones from other tests
importlib.reload(const)
importlib.reload(capabilities)
importlib.reload(coord_module)

# Patching COMMANDS and capabilities for predictable testing
# We'll use a smaller set of commands for testing to make counting easier
TEST_COMMANDS = {
    "power": MockPower,
    "input": MockInput,
    "picture_mode": MockPictureMode,
    "signal": MockSignal,
    "lamp_time": MockLampTime,
    "laser_power": MockLaserPower,
}

@pytest.fixture
def mock_device():
    device = AsyncMock()
    device.host = "1.2.3.4"
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    return device

@pytest.fixture
def coordinator(mock_device):
    coord = coord_module.JvcProjectorDataUpdateCoordinator(
        MagicMock(), mock_device, "AA:BB:CC", "ModelX", "1.0"
    )
    return coord

@pytest.fixture(autouse=True)
def patch_deps():
    with patch("custom_components.jvc_projector.capabilities.is_command_supported", return_value=True), \
         patch.dict(const.COMMANDS, TEST_COMMANDS, clear=True):
        yield

@pytest.mark.asyncio
async def test_smart_polling_standby(coordinator, mock_device):
    """Test polling in standby mode."""
    # Setup: Power returns STANDBY
    mock_device.get.side_effect = lambda cmd: "standby" if cmd == MockPower else "other"

    await coordinator._async_update_data()

    # Verify only Power was fetched
    # We expect 1 call to get(Power)
    assert mock_device.get.call_count == 1
    mock_device.get.assert_called_with(MockPower)

    # Verify interval is FAST (2s) to ensure quick wake-up detection
    assert coordinator.update_interval == timedelta(seconds=2)
    assert coordinator._poll_count == 0

@pytest.mark.asyncio
async def test_smart_polling_active_fast(coordinator, mock_device):
    """Test polling in active mode (Fast cycle)."""
    # Setup: Power returns ON
    mock_device.get.side_effect = lambda cmd: "on" if cmd == MockPower else "some_val"

    await coordinator._async_update_data()

    # Verify FAST keys were fetched
    # FAST keys: power, input, picture_mode, signal
    # Power is fetched first explicitly
    # Then loop fetches others
    # Total calls: 4 (assuming all are in TEST_COMMANDS)

    # Check calls
    called_commands = [call.args[0] for call in mock_device.get.call_args_list]
    assert MockPower in called_commands
    assert MockInput in called_commands
    assert MockPictureMode in called_commands
    assert MockSignal in called_commands

    # Ensure Slow keys were NOT fetched
    assert MockLampTime not in called_commands
    assert MockLaserPower not in called_commands

    # Verify interval is FAST (2s)
    assert coordinator.update_interval == timedelta(seconds=2)
    assert coordinator._poll_count == 1

@pytest.mark.asyncio
async def test_smart_polling_active_slow(coordinator, mock_device):
    """Test polling in active mode (Slow cycle trigger)."""
    # Setup: Power returns ON
    mock_device.get.return_value = "on"

    # Force poll count to 29 (next one is 30, triggering full update)
    coordinator._poll_count = 29

    await coordinator._async_update_data()

    # Verify ALL keys were fetched
    called_commands = [call.args[0] for call in mock_device.get.call_args_list]

    assert MockPower in called_commands
    assert MockInput in called_commands
    assert MockLampTime in called_commands
    assert MockLaserPower in called_commands

    # Verify counter reset
    assert coordinator._poll_count == 0
