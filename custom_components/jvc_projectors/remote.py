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

# Rate limiting for commands
COMMAND_RATE_LIMIT = 0.1  # seconds between commands
POWER_COMMAND_DELAY = 2.0  # longer delay after power commands


async def async_setup_entry(
    hass: HomeAssistant, entry: JVCConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([JvcProjectorRemote(coordinator)], True)


class JvcProjectorRemote(JvcProjectorEntity, RemoteEntity):
    """Representation of a JVC Projector device."""

    _attr_name = None
    
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the remote."""
        super().__init__(*args, **kwargs)
        self._last_command_time: datetime | None = None
        self._command_lock = asyncio.Lock()

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        # Check against command.Power constants
        return self.coordinator.data.get("power", command.Power.STANDBY) in [command.Power.ON, command.Power.WARMING]

    async def _apply_command_rate_limit(self, is_power_command: bool = False) -> None:
        """Apply rate limiting between commands."""
        if self._last_command_time:
            elapsed = (datetime.now() - self._last_command_time).total_seconds()
            required_delay = POWER_COMMAND_DELAY if is_power_command else COMMAND_RATE_LIMIT
            
            if elapsed < required_delay:
                delay = required_delay - elapsed
                _LOGGER.debug(
                    "Rate limiting command for %s: waiting %.2f seconds",
                    self.device.host,
                    delay
                )
                await asyncio.sleep(delay)
        
        self._last_command_time = datetime.now()

    async def _execute_command_with_retry(
        self,
        command_fn,
        command_name: str,
        max_retries: int = 2
    ) -> None:
        """Execute a command with retry logic and error handling."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Ensure we're connected via coordinator
                await self.coordinator._ensure_connected()
                
                # Execute the command
                await command_fn()
                
                _LOGGER.debug(
                    "Successfully executed %s command for %s",
                    command_name,
                    self.device.host
                )
                return
                
            except error.JvcProjectorError as err:
                last_error = err
                _LOGGER.warning(
                    "Connection error executing %s for %s (attempt %d/%d): %s",
                    command_name,
                    self.device.host,
                    attempt + 1,
                    max_retries + 1,
                    err
                )
                
                # Disconnect to force reconnection on next attempt
                await self.coordinator._disconnect_device()
                
                if attempt < max_retries:
                    await asyncio.sleep(2 * (attempt + 1))
                    
            except Exception as err:
                last_error = err
                _LOGGER.error(
                    "Unexpected error executing %s for %s: %s",
                    command_name,
                    self.device.host,
                    err,
                    exc_info=True
                )
                break
        
        # All retries failed
        raise last_error or Exception(f"Failed to execute {command_name}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on with proper error handling."""
        async with self._command_lock:
            _LOGGER.debug("Turning on JVC Projector at %s", self.device.host)
            
            await self._apply_command_rate_limit(is_power_command=True)
            
            try:
                await self._execute_command_with_retry(
                    lambda: self.device.set(command.Power, command.Power.ON),
                    "power_on"
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
        async with self._command_lock:
            _LOGGER.debug("Turning off JVC Projector at %s", self.device.host)
            
            await self._apply_command_rate_limit(is_power_command=True)
            
            try:
                await self._execute_command_with_retry(
                    lambda: self.device.set(command.Power, command.Power.OFF),
                    "power_off"
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
        async with self._command_lock:
            _LOGGER.debug("Sending commands '%s' to %s", command, self.device.host)

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

                await self._apply_command_rate_limit()

                try:
                    if cmd_name == "remote":
                        if value not in REMOTE_COMMANDS:
                            _LOGGER.error("Unknown remote command: %s", value)
                            raise ValueError(f"Unknown remote command: {value}")
                            
                        await self._execute_command_with_retry(
                            lambda: self.device.remote(REMOTE_COMMANDS[value]),
                            f"remote_{value}"
                        )
                    else:
                        # Check if it's a known command class
                        if cmd_name in COMMANDS:
                            cmd_cls = COMMANDS[cmd_name]
                            await self._execute_command_with_retry(
                                lambda: self.device.set(cmd_cls, value),
                                f"{cmd_name}_{value}"
                            )
                        else:
                             _LOGGER.error("Unknown command: %s", cmd_name)
                             raise ValueError(f"Unknown command: {cmd_name}")
                        
                except Exception as err:
                    _LOGGER.error(
                        "Failed to send command %s to %s: %s",
                        cmd,
                        self.device.host,
                        err
                    )
                    raise