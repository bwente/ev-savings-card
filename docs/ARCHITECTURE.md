# Architecture

## Legacy standalone mode

```text
OpenEI REST sensor
        |
        v
Home Assistant tariff entity
        |
        + energyratestructure
        + energyweekdayschedule
        + energyweekendschedule
        |
        v
EV Savings Card
        ^
        |
daily EV energy history
monthly EV energy sensor
```

The frontend currently performs both tariff interpretation and presentation. That is acceptable for the prototype, but it is not the preferred public architecture.

## Integration mode (0.5.0)

```text
OpenEI
  |
  v
EV Savings integration
  |
  + tariff discovery
  + tariff cache
  + rate period mapping
  + historical tariff versions
  + cost calculations
  + savings calculations
  + derived sensors
  |
  v
Home Assistant entities
  |
  v
EV Savings Card
```

## Why move calculations into the integration

The frontend should not hold API keys or depend on remote network access.

Moving calculations into the integration gives safer API key storage, better caching, consistent history, reusable sensors, easier testing, cleaner card code, and better error reporting.

## Historical accuracy

Historical charging must be calculated using the tariff that was effective when the energy was consumed.

A future tariff update must not silently change prior month savings. Stored versions are immutable; a changed or backdated incoming record is retained as pending. No historical rate is inferred before the first known effective date.

## Savings definition

Default comparison:

```text
cost if the same charging energy had occurred at the off peak rate
minus
actual time of use charging cost
```

The comparison period should remain configurable.

Fixed monthly customer charges are excluded because they are not affected by charging time.

## Calendar

Each day exposes total kWh, actual cost, savings, discount kWh, off peak kWh and on peak kWh. Session timing is not currently derived from hourly statistics.

The status sensor exposes an entry ID and refresh status. The authenticated `ev_savings/month` WebSocket endpoint checks read permission on the configured energy entity, retrieves hourly Recorder sums, and returns a calendar summary. API credentials remain server-side. No cost sensors or live-session estimates are provided in this beta.

## Provider and equipment independence

The product must be adaptable to any utility or user-supplied tariff and any charger or energy monitor with suitable Home Assistant data. Supporting a particular company must not require changes to the calendar or introduce a dependency on a charger brand.

Keep three separate responsibilities:

1. **Energy source:** obtain timestamped energy from Home Assistant and normalize units. Identify support through entity metadata and statistics availability, not manufacturer names. Disclose missing history and measurement resolution.
2. **Tariff provider:** discover or accept rates, normalize dated prices and schedules, supply service time zone and currency, and identify included charges and verification status. OpenEI, maintained utility profiles and manually supplied rates should feed the same calculation interface.
3. **Accounting and presentation:** apply the applicable dated price to each energy interval and the chosen comparison scenario. Return provider-independent calendar data to the card.

The existing implementation begins this separation but is not yet a universal tariff engine. Duke's schedule resolver is currently an explicit branch, and the normalized schema currently requires three period roles. Generalization must replace those assumptions with arbitrary period identifiers and separate optional display roles. A flat-rate plan should naturally show zero scheduling savings against the same price. Dynamic and tiered rates need explicit comparison semantics and sufficient history; demand charges need a separate calculation model. Do not flatten these plans into three prices.

Next extension work should add a provider interface and profile registry, graphical manual-rate setup, provider-defined currency and service time zone, and arbitrary period counts. Keep existing Duke and OpenEI configurations compatible. New providers need source-specific validation and regression fixtures; a provider failure must not disable other configured utilities.

Duke's verified profile remains an optional reference implementation. Its holidays, fee components and time zone must never become defaults for other utilities. Charger brand must never determine tariff selection.
