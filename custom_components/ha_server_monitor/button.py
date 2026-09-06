"""Button entity for HA Server Monitor: acknowledge/clear a physical device's alert."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_PHYSICAL
from .entity import physical_device_info
from .hub import HaServerMonitorHub


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: HaServerMonitorHub = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _add_physical(physical_id: str) -> None:
        async_add_entities([ClearAlertButton(hub, physical_id)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_NEW_PHYSICAL.format(entry.entry_id), _add_physical
        )
    )

    for physical_id in hub.physical_devices:
        _add_physical(physical_id)


class ClearAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "clear_alert"

    def __init__(self, hub: HaServerMonitorHub, physical_id: str) -> None:
        self._hub = hub
        self._physical_id = physical_id
        self._attr_unique_id = f"{hub.entry_id}_{physical_id}_clear_alert"

    @property
    def device_info(self):
        state = self._hub.physical_devices[self._physical_id]
        return physical_device_info(
            self._hub.entry_id, self._hub.hostname, self._physical_id, state.type
        )

    async def async_press(self) -> None:
        self._hub.clear_alert(self._physical_id)
