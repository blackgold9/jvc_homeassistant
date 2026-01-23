"""Number platform for the jvc_projector integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from jvcprojector import command
from jvcprojector.projector import JvcProjector

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry, JvcProjectorDataUpdateCoordinator, const, capabilities
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorNumberDescription(NumberEntityDescription):
    """Describes JVC Projector number entities."""

    command: type[command.Command]


NUMBERS: Final[tuple[JvcProjectorNumberDescription, ...]] = (
    JvcProjectorNumberDescription(
        key="laser_power",
        translation_key="jvc_laser_power",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        command=command.LaserPower,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the JVC Projector number platform from a config entry."""
    coordinator = entry.runtime_data

    entities = []
    for description in NUMBERS:
        if capabilities.is_command_supported(description.command, coordinator.spec):
            entities.append(JvcProjectorNumber(coordinator, description))

    async_add_entities(entities)


class JvcProjectorNumber(JvcProjectorEntity, NumberEntity):
    """Representation of a JVC Projector number entity."""

    entity_description: JvcProjectorNumberDescription

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JvcProjectorNumberDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        # The coordinator stores values as they come from the device (strings usually)
        value = self.coordinator.data.get(self.entity_description.key)
        if value is not None:
            try:
                # Value from device is 0.0-1.0, convert to 0-100
                return int(float(value) * 100)
            except ValueError:
                return None
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # Value from UI is 0-100, convert to 0.0-1.0
        await self.device.set(self.entity_description.command, value / 100.0)
        # We might want to trigger a refresh or optimistically update
