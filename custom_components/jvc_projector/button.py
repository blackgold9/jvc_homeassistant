"""Button platform for the jvc_projector integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity

async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the JVC Projector button platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([JvcProjectorManualUpdateButton(coordinator)])


class JvcProjectorManualUpdateButton(JvcProjectorEntity, ButtonEntity):
    """Representation of a manual update button."""

    _attr_translation_key = "manual_update"
    _attr_name = "Manual Update"

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}_manual_update"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_refresh()
