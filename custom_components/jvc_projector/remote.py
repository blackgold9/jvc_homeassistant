"""Remote platform for the jvc_projector integration."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime
import logging
from typing import Any

from jvcprojector import command, error

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry
from .const import REMOTE_COMMANDS, COMMANDS
from .entity import JvcProjectorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: JVCConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([JvcProjectorRemote(coordinator)], True)


class JvcProjectorRemote(JvcProjectorEntity, RemoteEntity):
    """Representation of a JVC Projector device."""

    _attr_name = None
    _attr_translation_key = "power"

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the remote."""
        super().__init__(*args, **kwargs)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        # Check against command.Power constants
        return self.coordinator.data.get("power", command.Power.STANDBY) in [command.Power.ON, command.Power.WARMING]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on with proper error handling."""
        _LOGGER.debug("Turning on JVC Projector at %s", self.device.host)

        try:
            await self.coordinator.async_execute_command(
                lambda: self.device.set(command.Power, command.Power.ON)
            )
            
            # Wait a bit before refreshing to allow projector to process
            await asyncio.sleep(1)
            
            # Force a refresh but don't fail if it errors
            try:
                await self.coordinator.async_refresh()
            except Exception as err:
                _LOGGER.debug(
                    "Failed to refresh after power on for %s: %s",
                    self.device.host,
                    err
                )

        except Exception as err:
            _LOGGER.error(
                "Failed to turn on %s: %s",
                self.device.host,
                err
            )
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off with proper error handling."""
        _LOGGER.debug("Turning off JVC Projector at %s", self.device.host)

        try:
            await self.coordinator.async_execute_command(
                lambda: self.device.set(command.Power, command.Power.OFF)
            )
            
            # Wait a bit before refreshing to allow projector to process
            await asyncio.sleep(1)
            
            # Force a refresh but don't fail if it errors
            try:
                await self.coordinator.async_refresh()
            except Exception as err:
                _LOGGER.debug(
                    "Failed to refresh after power off for %s: %s",
                    self.device.host,
                    err
                )

        except Exception as err:
            _LOGGER.error(
                "Failed to turn off %s: %s",
                self.device.host,
                err
            )
            raise

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send remote commands to the device with proper error handling."""
        _LOGGER.debug("Sending commands '%s' to %s", command, self.device.host)

        command_fns = []

        for cmd in command:
            _LOGGER.debug("Processing command '%s'", cmd)

            # Split command and value
            parts = cmd.split(",", 1)
            if len(parts) != 2:
                _LOGGER.error("Invalid command format: %s", cmd)
                raise ValueError(f"Invalid command format: {cmd}")

            cmd_name, value = parts
            cmd_name = cmd_name.strip().lower()
            value = value.strip()

            if cmd_name == "remote":
                if value not in REMOTE_COMMANDS:
                    _LOGGER.error("Unknown remote command: %s", value)
                    raise ValueError(f"Unknown remote command: {value}")

                command_fns.append(
                    lambda v=value: self.device.remote(REMOTE_COMMANDS[v])
                )
            elif cmd_name in COMMANDS:
                cmd_cls = COMMANDS[cmd_name]
                command_fns.append(
                    lambda c=cmd_cls, v=value: self.device.set(c, v)
                )
            else:
                _LOGGER.error("Unknown command: %s", cmd_name)
                raise ValueError(f"Unknown command: {cmd_name}")

        try:
            await self.coordinator.async_execute_batch(command_fns)
        except Exception as err:
            _LOGGER.error(
                "Failed to send commands %s to %s: %s",
                command,
                self.device.host,
                err
            )
            raise