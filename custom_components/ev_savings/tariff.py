"""Pure tariff validation, version selection and hourly accounting.

Times are absolute instants until converted to the service location's IANA zone.
Money is accumulated with Decimal; rounding is a presentation concern.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

ROLES = ("discount", "off_peak", "peak")


class TariffError(ValueError):
    """No trustworthy calculation can be made for the requested data."""


def decimal(value):
    if value is None or isinstance(value, bool):
        raise TariffError("Missing or invalid numeric value")
    try:
        number = Decimal(str(value))
    except InvalidOperation as err:
        raise TariffError("Invalid numeric value") from err
    if not number.is_finite():
        raise TariffError("Non-finite numeric value")
    return number


def instant(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, (float, int)):
        result = datetime.fromtimestamp(value / 1000 if value > 1e12 else value, timezone.utc)
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise TariffError("A statistic timestamp must include its time zone")
    return result.astimezone(timezone.utc)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_version(v):
    ZoneInfo(v["time_zone"])
    start = date.fromisoformat(v["effective_from"])
    if v.get("effective_to") and date.fromisoformat(v["effective_to"]) <= start:
        raise TariffError("Invalid tariff date range")
    if not v.get("source") or not v.get("id"):
        raise TariffError("Tariff source and version are required")
    if set(v["rates"]) != set(ROLES):
        raise TariffError("Three explicit period prices are required")
    for components in v["rates"].values():
        if not components:
            raise TariffError("Missing price components")
        for amount in components.values():
            decimal(amount)
    if v["schedule_kind"] == "duke_fl_rst1":
        if v["time_zone"] != "America/New_York":
            raise TariffError("Duke Florida profile requires America/New_York")
    elif v["schedule_kind"] == "monthly":
        for key in ("weekday", "weekend"):
            schedule = v[key]
            if len(schedule) != 12 or any(len(month) != 24 or any(role not in ROLES for role in month) for month in schedule):
                raise TariffError("Schedules require 12 months of 24 period roles")
    else:
        raise TariffError("Unsupported schedule")
    return v


def price(v, role):
    return sum((decimal(x) for x in v["rates"][role].values()), Decimal(0))


def duke_holidays(year):
    """Named holidays plus Friday/Monday observance, including adjacent years."""
    holidays = set()
    for y in (year - 1, year, year + 1):
        fixed = [date(y, 1, 1), date(y, 7, 4), date(y, 12, 25)]
        holidays.update(fixed)
        for day in fixed:
            if day.weekday() == 5:
                holidays.add(day - timedelta(days=1))
            elif day.weekday() == 6:
                holidays.add(day + timedelta(days=1))
        last_may = date(y, 5, 31)
        holidays.add(last_may - timedelta(days=last_may.weekday()))
        first_sep = date(y, 9, 1)
        holidays.add(first_sep + timedelta(days=(-first_sep.weekday()) % 7))
        first_nov = date(y, 11, 1)
        holidays.add(first_nov + timedelta(days=(3 - first_nov.weekday()) % 7 + 21))
    return holidays


def role_at(v, timestamp):
    local = instant(timestamp).astimezone(ZoneInfo(v["time_zone"]))
    if v["schedule_kind"] == "duke_fl_rst1":
        winter = local.month in (12, 1, 2)
        if local.hour < (3 if winter else 6):
            return "discount"
        if local.weekday() < 5 and local.date() not in duke_holidays(local.year):
            if 18 <= local.hour < 21 or (winter and 5 <= local.hour < 10):
                return "peak"
        return "off_peak"
    return v["weekend" if local.weekday() >= 5 else "weekday"][local.month - 1][local.hour]


def version_at(versions, timestamp):
    eligible = []
    for v in versions:
        day = instant(timestamp).astimezone(ZoneInfo(v["time_zone"])).date().isoformat()
        if v["effective_from"] <= day and (not v.get("effective_to") or day < v["effective_to"]):
            eligible.append(v)
    if not eligible:
        raise TariffError("No tariff version covers this date. Historical prices will not be inferred from a newer tariff.")
    newest = max(v["effective_from"] for v in eligible)
    matches = [v for v in eligible if v["effective_from"] == newest]
    if len(matches) != 1:
        raise TariffError("Conflicting tariff versions require review")
    return matches[0]


def merge_versions(existing, incoming, observed_day):
    """Never replace a stored version or silently backdate a newly seen change."""
    accepted = list(existing)
    pending = []
    for v in incoming:
        validate_version(v)
        prior = next((old for old in accepted if old["id"] == v["id"]), None)
        if prior:
            if digest(prior) != digest(v):
                pending.append(v)
            continue
        if existing and v["effective_from"] < observed_day:
            pending.append(v)
            continue
        if any(old["effective_from"] == v["effective_from"] for old in accepted):
            pending.append(v)
            continue
        accepted.append(v)
    return accepted, pending


def month_bounds(year, month, zone):
    tz = ZoneInfo(zone)
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def calculate_month(rows, versions, year, month, zone, comparison="off_peak", now=None, billing=None):
    from .billing import billed_price, billing_description, SOURCE as BILLING_SOURCE

    if comparison not in ROLES:
        raise TariffError("Invalid comparison period")
    now = instant(now or datetime.now(timezone.utc))
    start, end = month_bounds(year, month, zone)
    if start > now:
        raise TariffError("Future months cannot be calculated")
    # Require a known opening version even when energy is zero.
    version_at(versions, start)
    warnings = {"Hourly recorder estimates; recent charging may not appear yet."}
    points = []
    for row in rows:
        try:
            points.append((instant(row["start"]), decimal(row["sum"])))
        except (KeyError, ValueError, TypeError, OverflowError):
            warnings.add("Invalid recorder statistics were excluded; totals may be incomplete.")
    points.sort(key=lambda p: p[0])
    last_complete = min(end, now.replace(minute=0, second=0, microsecond=0))
    expected = int((last_complete - start).total_seconds() // 3600)
    covered = set()
    days = {}
    used = {}
    previous = None
    for stamp, total in points:
        if previous and start <= stamp < last_complete:
            prev_time, prev_total = previous
            if (stamp - prev_time).total_seconds() != 3600 or total < prev_total:
                warnings.add("Missing or corrected recorder intervals were excluded; totals are incomplete.")
            elif stamp not in covered:
                covered.add(stamp)
                energy = total - prev_total
                v = version_at(versions, stamp)
                used[v["id"]] = v
                role = role_at(v, stamp)
                # Hourly statistics cannot exactly price a tariff transition inside the hour.
                if role_at(v, stamp + timedelta(minutes=59, seconds=59)) != role:
                    raise TariffError("A tariff boundary falls inside an hourly statistic")
                key = stamp.astimezone(ZoneInfo(zone)).date().isoformat()
                rec = days.setdefault(key, {"kwh": Decimal(0), "actualCost": Decimal(0), "comparisonCost": Decimal(0), "savings": Decimal(0), "discountKwh": Decimal(0), "offPeakKwh": Decimal(0), "peakKwh": Decimal(0), "periodKwh": {r: Decimal(0) for r in ROLES}, "segments": []})
                rec["kwh"] += energy
                rec["actualCost"] += energy * billed_price(v, role, billing)
                rec["comparisonCost"] += energy * billed_price(v, comparison, billing)
                rec[{"discount": "discountKwh", "off_peak": "offPeakKwh", "peak": "peakKwh"}[role]] += energy
                rec["periodKwh"][role] += energy
                rec["savings"] = rec["comparisonCost"] - rec["actualCost"]
                if energy > 0:
                    unit_price = billed_price(v, role, billing)
                    finish = stamp + timedelta(hours=1)
                    segments = rec["segments"]
                    if segments and segments[-1]["end"] == stamp.isoformat() and segments[-1]["role"] == role and segments[-1]["rate"] == unit_price:
                        segment = segments[-1]
                        segment["end"] = finish.isoformat()
                        segment["kwh"] += energy
                        segment["cost"] += energy * unit_price
                    else:
                        segments.append({"start": stamp.isoformat(), "end": finish.isoformat(), "role": role,
                                         "rate": unit_price, "kwh": energy, "cost": energy * unit_price})
        previous = (stamp, total)
    if len(covered) < expected:
        warnings.add(f"Recorder coverage is incomplete: {len(covered)} of {expected} completed hours.")
    if not covered:
        warnings.add("No usable hourly history; zero totals do not establish zero charging.")
    display = version_at(versions, min(end - timedelta(microseconds=1), now))
    used.setdefault(display["id"], display)
    for v in used.values():
        if v.get("manual"):
            warnings.add("Manual rates supplied by the user; accuracy and included charges depend on the values entered.")
        elif not v.get("verified"):
            warnings.add("Unverified OpenEI tariff: schedules, holidays and price components have not been checked against utility documents.")
        if v.get("review_after") and now.date().isoformat() > v["review_after"]:
            warnings.add("Maintained tariff review is overdue. Install available integration updates before trusting current estimates.")
        if v.get("manual") or not billing or billing.get("cost_basis", "energy") == "energy":
            warnings.add(v.get("scope", "Price coverage is defined by the tariff source."))
    if billing and billing.get("cost_basis") == "total" and any(not v.get("manual") for v in used.values()):
        warnings.add(billing_description(billing))
        warnings.add("Calendar-date estimates may differ from utility billing-month application.")
    if len(used) > 1:
        warnings.add("Multiple dated tariffs applied; rate labels show the final applicable version.")
    totals = {key: sum((rec[key] for rec in days.values()), Decimal(0)) for key in ("kwh", "actualCost", "comparisonCost", "savings", "discountKwh", "offPeakKwh", "peakKwh")}
    totals["discountPercent"] = totals["discountKwh"] / totals["kwh"] * 100 if totals["kwh"] else Decimal(0)
    def serial(value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, list):
            return [serial(v) for v in value]
        if isinstance(value, dict):
            return {k: serial(v) for k, v in value.items()}
        return value
    return {"year": year, "month": month, "time_zone": zone, "days": serial(days), "totals": serial(totals), "warnings": sorted(warnings), "coverage": {"hours": len(covered), "expected": expected}, "comparison": comparison, "cost_basis": "manual" if display.get("manual") else (billing or {}).get("cost_basis", "energy"), "local_charges": (billing or {}).get("local_charges", "unknown"), "tariff": {"id": display["id"], "currency": display.get("currency", "USD"), "name": display["name"], "utility": display["utility"], "source": display["source"] + ("; " + BILLING_SOURCE if billing and billing.get("cost_basis") == "total" and not display.get("manual") else ""), "effective_from": display["effective_from"], "verified": all(v.get("verified", False) for v in used.values()), "scope": billing_description(billing) if billing and billing.get("cost_basis") == "total" and not display.get("manual") else display.get("scope", ""), "rates": {role: float(billed_price(display, role, billing)) for role in ROLES}, "components": display["rates"], "versions_used": list(used)}}
