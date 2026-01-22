"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from jvcprojector.device import JvcProjectorAuthError
from jvcprojector.projector import JvcProjector, JvcProjectorConnectError, const

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NAME

_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=10)
INTERVAL_FAST = timedelta(seconds=5)
CONNECTION_TIMEOUT = 30  # seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds
RATE_LIMIT_DELAY = 0.1  # seconds between operations


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the JVC Projector integration."""

    def __init__(self, hass: HomeAssistant, device: JvcProjector) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=NAME,
            update_interval=INTERVAL_SLOW,
        )

        self.device = device
        self.unique_id = format_mac(device.mac)
        self._last_operation_time: datetime | None = None
        self._connection_lock = asyncio.Lock()
        self._update_lock = asyncio.Lock()
        self._retry_count = 0
        self._connected = False
        
        _LOGGER.debug(
            "Initialized coordinator for device %s (MAC: %s)",
            device.host,
            self.unique_id
        )

    async def _ensure_connected(self) -> None:
        """Ensure device is connected, with proper error handling."""
        if self._connected:
            return
            
        async with self._connection_lock:
            # Double-check after acquiring lock
            if self._connected:
                return
                
            _LOGGER.debug("Attempting to connect to %s", self.device.host)
            
            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    # Apply rate limiting
                    await self._apply_rate_limit()
                    
                    # Set a timeout for connection
                    await asyncio.wait_for(
                        self.device.connect(True),
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
                except JvcProjectorConnectError as err:
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
        """Safely disconnect from device."""
        if not self._connected:
            return
            
        async with self._connection_lock:
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

    async def _async_update_data(self) -> dict[str, str]:
        """Get the latest state data with proper connection management."""
        async with self._update_lock:
            _LOGGER.debug("Starting update for %s", self.device.host)
            
            try:
                # Ensure we're connected before attempting to get state
                await self._ensure_connected()
                
                # Apply rate limiting
                await self._apply_rate_limit()
                
                # Get state with timeout
                state_mapping = await asyncio.wait_for(
                    self.device.get_state(),
                    timeout=CONNECTION_TIMEOUT
                )
                
                # Only include non-None values in the final state dict
                state = {k: v for k, v in state_mapping.items() if v is not None}
                
                _LOGGER.debug(
                    "Successfully retrieved state for %s: power=%s",
                    self.device.host,
                    state.get(const.POWER, "unknown")
                )
                
                # Reset retry count on success
                self._retry_count = 0
                
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout getting state from %s", self.device.host)
                await self._disconnect_device()
                raise UpdateFailed(f"Timeout getting state from {self.device.host}")
                
            except JvcProjectorConnectError as err:
                _LOGGER.error("Connection error getting state from %s: %s", self.device.host, err)
                await self._disconnect_device()
                self._retry_count += 1
                
                if self._retry_count >= MAX_RETRY_ATTEMPTS:
                    raise UpdateFailed(f"Unable to connect to {self.device.host}: {err}")
                else:
                    # Allow retry on next update
                    raise UpdateFailed(f"Temporary connection issue with {self.device.host}")
                    
            except JvcProjectorAuthError as err:
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
            
            if state.get(const.POWER) != const.STANDBY:
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
        await self._disconnect_device()