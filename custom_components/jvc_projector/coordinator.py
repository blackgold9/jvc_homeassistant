"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from jvcprojector import command, error
from jvcprojector.projector import JvcProjector

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const, capabilities

_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=10)
INTERVAL_FAST = timedelta(seconds=5)
CONNECTION_TIMEOUT = 30  # seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds
RATE_LIMIT_DELAY = 0.1  # seconds between operations


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the JVC Projector integration."""

    def __init__(self, hass: HomeAssistant, device: JvcProjector, mac: str, model: str | None = None, version: str | None = None) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=const.NAME,
            update_interval=INTERVAL_SLOW,
        )

        self.device = device
        self.mac = mac
        self.model = model
        self.spec = capabilities.get_spec(model)
        self.version = version
        self.unique_id = format_mac(mac)
        self._last_operation_time: datetime | None = None
        self._lock = asyncio.Lock()
        self._retry_count = 0
        self._connected = False
        
        _LOGGER.debug(
            "Initialized coordinator for device %s (MAC: %s)",
            device.host,
            self.unique_id
        )

    async def _ensure_connected(self) -> None:
        """Ensure device is connected, with proper error handling.

        Must be called with _lock acquired.
        """
        if self._connected:
            return
            
        _LOGGER.debug("Attempting to connect to %s", self.device.host)

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                # Apply rate limiting
                await self._apply_rate_limit()
                
                # Set a timeout for connection
                await asyncio.wait_for(
                    self.device.connect(),
                    timeout=CONNECTION_TIMEOUT
                )
                self._connected = True
                self._retry_count = 0
                _LOGGER.debug("Successfully connected to %s", self.device.host)
                return
                
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Connection timeout to %s (attempt %d/%d)",
                    self.device.host,
                    attempt + 1,
                    MAX_RETRY_ATTEMPTS
                )
            except error.JvcProjectorError as err:
                _LOGGER.warning(
                    "Connection failed to %s (attempt %d/%d): %s",
                    self.device.host,
                    attempt + 1,
                    MAX_RETRY_ATTEMPTS,
                    err
                )
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error connecting to %s: %s",
                    self.device.host,
                    err,
                    exc_info=True
                )
            
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        # All attempts failed
        raise UpdateFailed(f"Unable to connect to {self.device.host} after {MAX_RETRY_ATTEMPTS} attempts")

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting to prevent overwhelming the device."""
        if self._last_operation_time:
            elapsed = (datetime.now() - self._last_operation_time).total_seconds()
            if elapsed < RATE_LIMIT_DELAY:
                delay = RATE_LIMIT_DELAY - elapsed
                _LOGGER.debug("Rate limiting: waiting %.2f seconds", delay)
                await asyncio.sleep(delay)
        
        self._last_operation_time = datetime.now()

    async def _disconnect_device(self) -> None:
        """Safely disconnect from device.

        Must be called with _lock acquired.
        """
        if not self._connected:
            return
            
        try:
            _LOGGER.debug("Disconnecting from %s", self.device.host)
            await self.device.disconnect()
            self._connected = False
            _LOGGER.debug("Disconnected from %s", self.device.host)
        except Exception as err:
            _LOGGER.error(
                "Error disconnecting from %s: %s",
                self.device.host,
                err,
                exc_info=True
            )
            # Mark as disconnected anyway to allow reconnection
            self._connected = False

    async def async_execute_command(
        self,
        command_fn: Callable[[], Awaitable[Any]],
        retry: bool = True
    ) -> Any:
        """Execute a command with centralized locking, rate limiting, and retry logic.

        Args:
            command_fn: The async function to execute.
            retry: Whether to retry on failure.

        Returns:
            The result of command_fn.

        Raises:
            HomeAssistantError: If the command fails after retries.
        """
        async with self._lock:
            last_error = None
            max_retries = MAX_RETRY_ATTEMPTS if retry else 0

            for attempt in range(max_retries + 1):
                try:
                    await self._ensure_connected()
                    await self._apply_rate_limit()

                    result = await command_fn()
                    return result

                except (error.JvcProjectorError, asyncio.TimeoutError) as err:
                    last_error = err
                    _LOGGER.warning(
                        "Error executing command on %s (attempt %d/%d): %s",
                        self.device.host,
                        attempt + 1,
                        max_retries + 1,
                        err
                    )

                    # Disconnect to force reconnection on next attempt
                    await self._disconnect_device()

                    if attempt < max_retries:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))

                except Exception as err:
                    _LOGGER.error(
                        "Unexpected error executing command on %s: %s",
                        self.device.host,
                        err,
                        exc_info=True
                    )
                    await self._disconnect_device()
                    raise HomeAssistantError(f"Unexpected error: {err}") from err

            # If we get here, all retries failed
            msg = f"Failed to execute command after {max_retries + 1} attempts: {last_error}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg) from last_error

    async def _async_update_data(self) -> dict[str, str]:
        """Get the latest state data with proper connection management."""
        async with self._lock:
            _LOGGER.debug("Starting update for %s", self.device.host)
            
            try:
                # Ensure we're connected before attempting to get state
                await self._ensure_connected()
                
                # Apply rate limiting
                await self._apply_rate_limit()
                
                state = {}
                # Fetch all monitored attributes
                for key, cmd_class in const.COMMANDS.items():
                    if not capabilities.is_command_supported(cmd_class, self.spec):
                        continue

                    try:
                        # Fetch individual attribute
                        val = await self.device.get(cmd_class)
                        state[key] = val
                    except error.JvcProjectorError as e:
                         # Some commands might fail if not supported or during startup
                        _LOGGER.debug("Failed to get %s: %s", key, e)
                    except Exception as e:
                        _LOGGER.debug("Unexpected error getting %s: %s", key, e)

                _LOGGER.debug(
                    "Successfully retrieved state for %s: power=%s",
                    self.device.host,
                    state.get("power", "unknown")
                )
                
                # Reset retry count on success
                self._retry_count = 0
                
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout getting state from %s", self.device.host)
                await self._disconnect_device()
                raise UpdateFailed(f"Timeout getting state from {self.device.host}")
                
            except error.JvcProjectorError as err:
                _LOGGER.error("Connection error getting state from %s: %s", self.device.host, err)
                await self._disconnect_device()
                self._retry_count += 1
                
                if self._retry_count >= MAX_RETRY_ATTEMPTS:
                    raise UpdateFailed(f"Unable to connect to {self.device.host}: {err}")
                else:
                    # Allow retry on next update
                    raise UpdateFailed(f"Temporary connection issue with {self.device.host}")
                    
            except error.JvcProjectorAuthError as err:
                _LOGGER.error("Authentication error with %s", self.device.host)
                await self._disconnect_device()
                raise ConfigEntryAuthFailed("Password authentication failed") from err
                
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error getting state from %s: %s",
                    self.device.host,
                    err,
                    exc_info=True
                )
                await self._disconnect_device()
                raise UpdateFailed(f"Unexpected error: {err}")

            # Update polling interval based on power state
            old_interval = self.update_interval
            
            # Check power state properly using command.Power constants if possible,
            # but here state values are strings. const.VAL_POWER has the values.
            # Assuming "standby" is the value for standby.
            power_state = state.get("power")
            # We can use command.Power.STANDBY if we want to be precise, but string check is safer if we know the string

            if power_state and power_state != command.Power.STANDBY:
                self.update_interval = INTERVAL_FAST
            else:
                self.update_interval = INTERVAL_SLOW
            
            if self.update_interval != old_interval:
                _LOGGER.debug(
                    "Changed update interval for %s to %s",
                    self.device.host,
                    self.update_interval
                )

            return state

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and cleanup resources."""
        _LOGGER.debug("Shutting down coordinator for %s", self.device.host)
        # We need to acquire lock to safely disconnect
        async with self._lock:
            await self._disconnect_device()
