"""Register the bundled card with the dashboard resource loader."""
import logging
from urllib.parse import urlsplit

from homeassistant.components import frontend
from homeassistant.components.lovelace.const import LOVELACE_DATA

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)
CARD_PATH = f"/{DOMAIN}/ev-savings-card.js"
CARD_URL = f"{CARD_PATH}?v={VERSION}"


async def async_register_card(hass):
    """Persist a module resource so dashboard loading includes the card."""
    lovelace = hass.data[LOVELACE_DATA]
    resources = lovelace.resources
    if lovelace.resource_mode != "storage":
        # YAML remains user-owned. Keep the prior frontend fallback available.
        frontend.add_extra_js_url(hass, CARD_URL)
        _LOGGER.warning(
            "For reliable EV Savings card loading, add %s with type: module "
            "to your Lovelace YAML resources", CARD_URL
        )
        return

    # Public info access loads the resource collection before inspecting entries.
    await resources.async_get_info()
    matches = [item for item in resources.async_items()
               if urlsplit(item["url"]).path == CARD_PATH]
    if not matches:
        await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
        return
    # Reuse existing registrations, including manually added older versions.
    for item in matches:
        if item["url"] != CARD_URL or item["type"] != "module":
            await resources.async_update_item(item["id"], {"url": CARD_URL, "res_type": "module"})
