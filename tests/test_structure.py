import sys
import os
from unittest.mock import MagicMock
import pytest

# Add current directory to sys.path so we can import custom_components
sys.path.append(os.getcwd())

def test_component_imports():
    """Test that the component imports JvcProjector from the correct location."""

    # 1. Mock Home Assistant dependencies
    mock_hass = MagicMock()
    sys.modules["homeassistant"] = mock_hass
    sys.modules["homeassistant.const"] = MagicMock()
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.exceptions"] = MagicMock()
    sys.modules["homeassistant.config_entries"] = MagicMock()

    # helper to mock a package
    def mock_package(name):
        m = MagicMock()
        m.__path__ = []
        sys.modules[name] = m
        return m

    mock_helpers = mock_package("homeassistant.helpers")
    sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
    sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
    sys.modules["homeassistant.helpers.entity"] = MagicMock()

    # 2. Mock jvcprojector library
    mock_jvc_pkg = MagicMock()
    sys.modules["jvcprojector"] = mock_jvc_pkg

    mock_jvc_device = MagicMock()
    sys.modules["jvcprojector.device"] = mock_jvc_device

    mock_jvc_projector_pkg = MagicMock()
    sys.modules["jvcprojector.projector"] = mock_jvc_projector_pkg

    # Set a distinct attribute to verify we got the right class
    class MockJvcProjector:
        pass

    mock_jvc_projector_pkg.JvcProjector = MockJvcProjector

    # 3. Import the component
    if "custom_components.jvc_projector" in sys.modules:
        del sys.modules["custom_components.jvc_projector"]

    # We also need to clear coordinator if it was partially loaded
    if "custom_components.jvc_projector.coordinator" in sys.modules:
        del sys.modules["custom_components.jvc_projector.coordinator"]

    import custom_components.jvc_projector as jvc_component

    # 4. Verify imports
    assert hasattr(jvc_component, "JvcProjector")
    assert jvc_component.JvcProjector is MockJvcProjector

    print("Import verification successful.")
