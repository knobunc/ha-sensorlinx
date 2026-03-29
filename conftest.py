"""Root conftest — registers pytest-homeassistant-custom-component plugin."""

import sys
from pathlib import Path

# Ensure the project root (where custom_components/ lives) is on sys.path
# so HA's loader can `import custom_components` and discover our integration.
sys.path.insert(0, str(Path(__file__).parent))

# Pre-import the integration package so that mock.patch("custom_components.sensorlinx.*")
# can resolve the attribute path on the namespace package.
import custom_components.sensorlinx  # noqa: E402, F401

pytest_plugins = "pytest_homeassistant_custom_component"
