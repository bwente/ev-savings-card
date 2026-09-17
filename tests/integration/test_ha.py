"""Exercise adapters against the supported Home Assistant version."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from custom_components.ev_savings import TariffCache, websocket_month
from custom_components.ev_savings.config_flow import ConfigFlow
from custom_components.ev_savings.sensor import TariffSensor
from custom_components.ev_savings.const import DUKE_PROFILE


@pytest.mark.asyncio
async def test_config_flow_forms():
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(time_zone='America/New_York'))
    result = await flow.async_step_user()
    assert result['step_id'] == 'user'
    result = await flow.async_step_user({'provider':DUKE_PROFILE})
    assert result['step_id'] == 'energy'
    flow.hass.states = SimpleNamespace(get=lambda _:None)
    result = await flow.async_step_energy({'energy_entity':'sensor.invalid', 'comparison':'off_peak'})
    assert result['errors'] == {'base':'invalid_energy'}


@pytest.mark.asyncio
async def test_cache_reload_and_status_do_not_expose_credentials():
    hass = SimpleNamespace(bus=SimpleNamespace(async_fire=Mock()))
    async def executor(fn):
        return fn()
    hass.async_add_executor_job = executor
    entry = SimpleNamespace(entry_id='example', title='Example', options={}, data={'provider':DUKE_PROFILE,
        'time_zone':'America/New_York', 'energy_entity':'sensor.ev', 'api_key':'must-not-leak'})
    # Avoid requiring HA's filesystem storage manager in this isolated test.
    cache = object.__new__(TariffCache)
    cache.hass, cache.entry = hass, entry
    cache.store = SimpleNamespace(async_save=AsyncMock())
    cache.versions, cache.pending = [], []
    cache.warning, cache.last_checked = None, None
    entry.runtime_data = cache
    await cache.refresh()
    assert len(cache.versions) == 1 and cache.warning is None
    await cache.refresh()
    assert len(cache.versions) == 1 and not cache.pending
    assert 'must-not-leak' not in str(TariffSensor(entry).extra_state_attributes)
    assert cache.store.async_save.await_count == 2


@pytest.mark.asyncio
async def test_websocket_denies_energy_without_read_permission():
    from inspect import unwrap
    entry = SimpleNamespace(domain='ev_savings', options={}, runtime_data=object(), data={'energy_entity':'sensor.private'})
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_get_entry=lambda _:entry))
    connection = SimpleNamespace(user=SimpleNamespace(permissions=SimpleNamespace(check_entity=Mock(return_value=False))), send_error=Mock())
    await unwrap(websocket_month)(hass, connection, {'id':1,'entry_id':'entry'})
    connection.send_error.assert_called_once_with(1,'unauthorized','Energy entity access denied')


@pytest.mark.asyncio
async def test_websocket_uses_recorder_and_backend_prices(monkeypatch):
    from inspect import unwrap
    import json
    from pathlib import Path
    import custom_components.ev_savings as integration
    profile = json.loads(Path('custom_components/ev_savings/profiles/duke_fl_rst1.json').read_text())['versions']
    entry = SimpleNamespace(domain='ev_savings', options={}, runtime_data=SimpleNamespace(versions=profile, warning=None),
                            data={'energy_entity':'sensor.ev','time_zone':'America/New_York','comparison':'off_peak'})
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_get_entry=lambda _:entry))
    async def executor(job):
        assert job.args[5] == {'energy':'kWh'}
        start = job.args[1]
        from datetime import timedelta
        return {'sensor.ev':[{'start':start,'sum':0},{'start':start+timedelta(hours=1),'sum':10}]}
    monkeypatch.setattr(integration,'get_instance',lambda _:SimpleNamespace(async_add_executor_job=executor))
    connection = SimpleNamespace(user=SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda *_:True)),send_result=Mock(),send_error=Mock())
    await unwrap(websocket_month)(hass, connection, {'id':1,'entry_id':'entry','month_offset':0})
    assert not connection.send_error.called
    result = connection.send_result.call_args.args[1]
    assert result['totals']['kwh'] == 10
    assert result['totals']['actualCost'] == 1.0256


@pytest.mark.asyncio
async def test_manual_wizard_selects_rates_then_collects_hourly_windows():
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(time_zone='America/New_York'))
    result = await flow.async_step_user({'provider':'manual'})
    assert result['step_id']=='manual'
    data={'utility':'Example','name':'TOU','currency':'USD','time_zone':'America/New_York','effective_from':'2026-09-01',
          'discount':10.74,'off_peak':14.28,'peak':17.79,'schedule':'custom'}
    result=await flow.async_step_manual(data)
    assert result['step_id']=='manual_rule'
    result=await flow.async_step_manual_rule({'months':['9'],'days':['weekday','weekend'],'role':'discount','start':0,'end':6,'add_another':False})
    assert result['step_id']=='energy'
    assert flow.selection['initial_version']['rates']['discount']['entered_total']=='0.1074'
