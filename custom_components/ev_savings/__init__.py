"""EV Savings integration: private tariff cache and server-side accounting."""
from datetime import datetime, timedelta, timezone
from functools import partial
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import DOMAIN, DUKE_PROFILE
from .frontend import async_register_card
from .openei import fetch, convert
from .tariff import TariffError, calculate_month, merge_versions, month_bounds


class TariffCache:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.versions = []
        self.pending = []
        self.warning = None
        self.last_checked = None

    async def refresh(self, _now=None):
        config = {**self.entry.data, **self.entry.options}
        try:
            if config["provider"] == "manual":
                incoming = config.get("manual_versions", [])
            elif config["provider"] == DUKE_PROFILE:
                path = Path(__file__).parent / "profiles" / "duke_fl_rst1.json"
                payload = await self.hass.async_add_executor_job(path.read_text)
                incoming = json.loads(payload)["versions"]
            else:
                records = await fetch(async_get_clientsession(self.hass), config["api_key"],
                                      ratesforutility=config["utility"], sector="Residential")
                # A utility can have many unrelated plans. Never select simply by newest date.
                known = {config["tariff"], *(v["id"] for v in self.versions)}
                matching = []
                # Follow a lineage across multiple updates, never all same-utility plans.
                for _ in range(len(records) + 1):
                    batch = [r for r in records if r not in matching and
                             (r.get("label") in known or (r.get("name") == config["tariff_name"] and r.get("supersedes") in known))]
                    if not batch:
                        break
                    matching.extend(batch)
                    known.update(r["label"] for r in batch)
                if not matching:
                    raise TariffError("Selected tariff was not returned")
                incoming = [convert(r, config["time_zone"], config["roles"]) for r in matching]
            today = datetime.now(ZoneInfo(config["time_zone"])).date().isoformat()
            self.versions, self.pending = merge_versions(self.versions, incoming, today)
            self.warning = "Changed or backdated tariff needs review; cached rates retained." if self.pending else None
            self.last_checked = datetime.now(timezone.utc).isoformat()
            await self.save()
        except Exception:
            # Never log request exceptions: URLs can contain API keys.
            self.warning = "Tariff refresh failed. Cached rates may be stale."
        self.hass.bus.async_fire(f"{DOMAIN}_updated", {"entry_id": self.entry.entry_id})

    async def save(self):
        await self.store.async_save({"versions": self.versions, "pending": self.pending, "last_checked": self.last_checked})


async def async_setup(hass, config):
    await hass.http.async_register_static_paths([StaticPathConfig(
        f"/{DOMAIN}/ev-savings-card.js", str(Path(__file__).parent / "www" / "ev-savings-card.js"), False)])
    await async_register_card(hass)
    websocket_api.async_register_command(hass, websocket_month)
    return True


async def async_setup_entry(hass, entry):
    cache = TariffCache(hass, entry)
    stored = await cache.store.async_load()
    if stored:
        cache.versions = stored.get("versions", [])
        cache.pending = stored.get("pending", [])
        cache.last_checked = stored.get("last_checked")
    elif entry.data.get("initial_version"):
        cache.versions = [entry.data["initial_version"]]
    entry.runtime_data = cache
    await cache.refresh()
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    entry.async_on_unload(async_track_time_interval(hass, cache.refresh, timedelta(days=1)))
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])


@websocket_api.websocket_command({vol.Required("type"): "ev_savings/month",
                                  vol.Required("entry_id"): str,
                                  vol.Optional("month_offset", default=0): vol.All(int, vol.Range(min=-120, max=0))})
@websocket_api.async_response
async def websocket_month(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if not entry or entry.domain != DOMAIN or not getattr(entry, "runtime_data", None):
        connection.send_error(msg["id"], "not_found", "EV Savings integration is not loaded")
        return
    settings = {**entry.data, **entry.options}
    entity = settings["energy_entity"]
    if not connection.user.permissions.check_entity(entity, "read"):
        connection.send_error(msg["id"], "unauthorized", "Energy entity access denied")
        return
    cache = entry.runtime_data
    try:
        zone = settings["time_zone"]
        now = datetime.now(ZoneInfo(zone))
        month_index = now.year * 12 + now.month - 1 + msg["month_offset"]
        year, month = month_index // 12, month_index % 12 + 1
        start, end = month_bounds(year, month, zone)
        records = await get_instance(hass).async_add_executor_job(partial(
            statistics_during_period, hass, start - timedelta(hours=1), min(end, now),
            {entity}, "hour", {"energy": "kWh"}, {"sum"}))
        result = calculate_month(records.get(entity, []), cache.versions, year, month, zone,
                                 settings["comparison"], now, billing=settings)
        if cache.warning:
            result["warnings"].append(cache.warning)
        connection.send_result(msg["id"], result)
    except TariffError as err:
        connection.send_error(msg["id"], "tariff_unavailable", str(err))
    except Exception:
        connection.send_error(msg["id"], "calculation_failed", "Could not calculate costs; check energy recorder statistics and tariff configuration")
