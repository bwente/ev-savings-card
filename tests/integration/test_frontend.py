"""Exercise dashboard registration with Home Assistant's resource collection."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection, ResourceYAMLCollection

from custom_components.ev_savings.frontend import async_register_card, CARD_URL


@pytest.mark.asyncio
@pytest.mark.parametrize('existing', [[], [
    {'id': 'card', 'url': '/ev_savings/ev-savings-card.js?v=0.6.1', 'type': 'js'},
    {'id': 'other', 'url': '/local/another-card.js', 'type': 'module'},
]])
async def test_storage_resource_loaded_updated_and_idempotent(tmp_path, existing):
    hass = HomeAssistant(str(tmp_path))
    resources = ResourceStorageCollection(hass, Mock())
    resources.store.async_load = AsyncMock(return_value={'items': existing})
    resources.store.async_delay_save = Mock()
    hass.data[LOVELACE_DATA] = SimpleNamespace(resource_mode='storage', resources=resources)
    await async_register_card(hass)
    first = list(resources.async_items())
    await async_register_card(hass)
    assert resources.async_items() == first
    cards = [item for item in first if item['url'] == CARD_URL]
    assert len(cards) == 1
    assert cards[0]['type'] == 'module'
    resources.store.async_load.assert_awaited_once()
    if existing:
        assert cards[0]['id'] == 'card'
        assert next(item for item in first if item['id'] == 'other') == existing[1]


@pytest.mark.asyncio
async def test_yaml_resources_remain_user_owned(monkeypatch, caplog):
    from custom_components.ev_savings import frontend as module
    items = [{'url': '/local/another-card.js', 'type': 'module'}]
    resources = ResourceYAMLCollection(items.copy())
    hass = SimpleNamespace(data={LOVELACE_DATA: SimpleNamespace(resource_mode='yaml', resources=resources)})
    extra = Mock()
    monkeypatch.setattr(module.frontend, 'add_extra_js_url', extra)
    await async_register_card(hass)
    assert resources.async_items() == items
    extra.assert_called_once_with(hass, CARD_URL)
    assert CARD_URL in caplog.text
