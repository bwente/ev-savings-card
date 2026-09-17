"""OpenEI discovery and conservative conversion; never claims verification."""
from datetime import datetime, timezone
from .tariff import TariffError, decimal, digest, validate_version

API = "https://api.openei.org/utility_rates"


async def fetch(session, api_key, **query):
    params = {"version": "7", "format": "json", "detail": "full", "api_key": api_key, **query}
    items = []
    for offset in range(0, 10000, 500):
        async with session.get(API, params={**params, "limit": 500, "offset": offset}, timeout=30) as response:
            if response.status != 200:
                raise TariffError("OpenEI request failed; check credentials and service availability")
            data = await response.json()
        if data.get("errors") or not isinstance(data.get("items"), list):
            raise TariffError("OpenEI did not return valid tariff records")
        page = data["items"]
        items.extend(page)
        if len(page) < 500:
            return items
    raise TariffError("Too many utility records; narrow the utility selection")


def convert(record, zone, roles):
    """Only simple, three-period kWh plans are supported in this beta."""
    if record.get("demandratestructure") or record.get("flatdemandstructure"):
        raise TariffError("Demand charges are not supported")
    structure = record.get("energyratestructure", [])
    if len(structure) != 3 or set(roles.values()) != {0, 1, 2}:
        raise TariffError("Select three distinct period indexes for a three-period tariff")
    rates = {}
    for role, index in roles.items():
        tiers = structure[index]
        if len(tiers) != 1 or tiers[0].get("max") is not None or tiers[0].get("unit") != "kWh":
            raise TariffError("Tiered and non-kWh tariffs are not supported")
        tier = tiers[0]
        rates[role] = {"energy": str(decimal(tier.get("rate"))), "adjustments": str(decimal(tier.get("adj", 0)))}
    by_index = {index: role for role, index in roles.items()}
    def schedule(key):
        try:
            return [[by_index[index] for index in month] for month in record[key]]
        except (KeyError, TypeError) as err:
            raise TariffError("Unsupported OpenEI schedule") from err
    def day(key):
        value = record.get(key)
        # URDB dates represent nominal tariff dates, not local charging instants.
        return datetime.fromtimestamp(float(value), timezone.utc).date().isoformat() if value else None
    if not day("startdate"):
        raise TariffError("Tariff effective date is missing")
    v = {"id": record["label"], "name": record["name"], "utility": record["utility"],
         "time_zone": zone, "effective_from": day("startdate"), "effective_to": day("enddate"),
         "verified": False, "source": record.get("source") or record.get("uri") or "OpenEI URDB",
         "schedule_kind": "monthly", "weekday": schedule("energyweekdayschedule"),
         "weekend": schedule("energyweekendschedule"), "rates": rates,
         "scope": "OpenEI energy rate plus adjustment only; completeness, holidays and taxes are unverified."}
    # Detect a changed record without exposing credentials or unrelated API metadata.
    v["revision"] = digest(v)
    return validate_version(v)
