# EV Savings Card

See what your EV charging costs—and how much you save by charging at cheaper times. EV Savings combines a Home Assistant integration with a dashboard card showing monthly cost, energy charged, discount charging percentage, and savings.

Switch the calendar between **Cost**, **Savings**, and **kWh**, or tap a day to see charging broken down by rate. Use manual prices for your utility, the Duke Energy Florida RST-1 profile, or a supported OpenEI plan. It works with EV energy data supplied to Home Assistant by a charger or energy monitor; Emporia is not required.

<p>
  <img src="https://raw.githubusercontent.com/bwente/ev-savings-card/main/docs/images/ev-savings-card-cost.png" alt="Cost calendar with monthly EV charging totals" width="360">
  <img src="https://raw.githubusercontent.com/bwente/ev-savings-card/main/docs/images/ev-savings-card-savings.png" alt="Savings calendar showing the benefit of lower-rate charging" width="360">
</p>

*Screenshots show an earlier version of the card.*

## Quick start

You need **Home Assistant 2026.6.0 or later**, HACS, and an **EV-specific kWh energy sensor** with Recorder statistics enabled.

1. In **HACS → Custom repositories**, add `https://github.com/bwente/ev-savings-card` as an **Integration**. Install **EV Savings** and restart Home Assistant.
2. Open **Settings → Devices & services → Add integration → EV Savings**.
3. Choose **Manual rate entry** and enter your prices, schedule, time zone, and effective date. Enter prices in cents per kWh: **10.74** means **$0.1074/kWh**. Duke and OpenEI are also available as rate sources.
4. Select your EV energy sensor and the rate to compare charging against, such as off peak.
5. Refresh your browser, add **EV Savings Card** to a dashboard, and select the tariff entity created by the integration.

The card is bundled with the integration and registered automatically for dashboards using UI-managed resources. Change rates or the comparison period later through **EV Savings → Configure**.

[Detailed setup, YAML resources, and troubleshooting](https://github.com/bwente/ev-savings-card/blob/main/docs/CONFIGURATION.md)

## How it works

The integration reads hourly energy history from Home Assistant and applies the rate scheduled for each hour in your service location’s time zone. It adds those costs to show daily and monthly totals. **Savings** is the difference between the actual charging cost and what the same energy would have cost at your chosen comparison rate.

When charging spans two rates, the day details show the energy and cost for each portion. Dated rate versions preserve historical pricing. Manual prices stay as entered until you update them; OpenEI checks daily, while Duke profile updates arrive with integration updates.

## Limitations

- **Hourly estimates:** recent charging may take time to appear. Missing or corrected history is excluded and flagged. Day details show hourly intervals, not exact charging sessions; charging across midnight appears on both days.
- **Supported plans:** flat rates and up to three time-of-use roles—discount, off peak, and peak. Dynamic prices, tiered rates, demand charges, and half-hour boundaries are not supported. Custom manual schedules do not infer holidays.
- **Cost coverage:** include applicable variable fees and taxes in manual prices. Fixed monthly charges and minimum-bill effects are excluded. Online tariff data may omit charges; review the source and warnings against your bill.
- **Energy data required:** a power-only sensor or a session total without time history is insufficient. Broader charger compatibility and a clean HACS installation are still being tested.

This is an early public beta, available as a HACS custom repository and not yet listed in the default catalog.

[Configuration guide](https://github.com/bwente/ev-savings-card/blob/main/docs/CONFIGURATION.md) · [Changelog](https://github.com/bwente/ev-savings-card/blob/main/CHANGELOG.md) · [Report an issue](https://github.com/bwente/ev-savings-card/issues) · [MIT license](https://github.com/bwente/ev-savings-card/blob/main/LICENSE)
