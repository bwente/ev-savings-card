# Supplied RST-1 tariff audit — September 11, 2026

Compared the supplied tariff attributes with Duke Florida's filed RST-1 sheet 6.140, marked effective January 1, 2026: [filing, PDF page 63](https://www.psc.state.fl.us/library/FILINGS/2025/14875-2025/14875-2025.pdf#page=63). The linked live Duke PDF and OpenEI record could not be retrieved during this audit, so this is not certification of the latest delivered prices.

## Schedule discrepancy

All 576 weekday/weekend hour entries were compared with the filed ordinary-day schedule. Exactly 18 entries differ: hours 0, 1, and 2 in January, February, and December, in both schedules. The supplied values are period 1 (off peak); the filing specifies period 2 (discount). All remaining entries match the filed ordinary weekday/weekend schedule.

The correction is to change the first three entries in monthly arrays 0, 1, and 11 to 2 in both `energyweekdayschedule` and `energyweekendschedule`. Do this in the source tariff configuration so a subsequent refresh does not erase the correction. Do not automatically alter arbitrary OpenEI records in the dashboard card.

With the supplied adjustments, the off-peak/discount difference is $0.03551 per kWh. If the example multiplier 1.03586 is still active, the difference is $0.0367833886 per kWh. Thus 10 kWh charged during those winter discount hours would have its cost overstated and savings understated by approximately $0.37; discount energy would also be undercounted.

## Effective date conflict

The supplied `startdate` is `1735714800`, or January 1, 2025 at 07:00 UTC (02:00 in America/New_York). The three base rates match the filed sheet marked January 1, 2026. This is conflicting version metadata, not proof that the correct repair is simply to change the year. Preserve historical versions and verify the upstream record and rate effective dates before pricing older charging data. Also distinguish utility calendar dates from UTC timestamp encoding; 02:00 is not local midnight.

## Price arithmetic

| Role | Base | Adjustment | Sum, $/kWh | With example multiplier 1.03586 |
| --- | --- | --- | --- | --- |
| Peak | 0.11032 | 0.06257 | 0.17289 | 0.17908984 |
| Off peak | 0.08172 | 0.05699 | 0.13871 | 0.14368414 |
| Discount | 0.04958 | 0.05362 | 0.10320 | 0.10690075 |

These calculations reproduce the screenshot's displayed rates after rounding. They do not validate the adjustment components, their applicable dates, or the multiplier. The tariff references additional billing-adjustment sheets; those components must be reconciled before claiming delivered-cost accuracy. Fixed monthly charges remain excluded from scheduling savings.

## Other unresolved accuracy issues

- The card lacks named-holiday and observed-weekday handling. A 12-by-24 weekday/weekend schedule cannot encode those date exceptions by itself.
- The card supports seasonal hour changes and has DST boundary tests, but those tests cannot detect incorrect upstream tariff content.
- A 2025 effective date with 2026-matching rates will bypass a simple date-bound check. Structural validation alone does not establish historical correctness.
- Actual monthly corrections require hourly charging data; the size of a household's error cannot be inferred from tariff attributes alone.

## Utility-wide response follow-up

The supplied utility-wide JSON contains 40 records, including 11 RST-1 records (some historical names include “Closed Rate”). The newest RST-1 by declared start date is still `678abac33d12e18b730b0663`; no newer-starting RST-1 appears in this response. The newer 2026 record is RS-1, a different plan, and must not replace RST-1.

The raw RST-1 response repeats the missing winter discount hours, locating that discrepancy upstream of the Home Assistant sensor. It also contains `supersedes: 651386944021932a7c02360b` and a final revision timestamp of `1771323277` (February 17, 2026 UTC), despite retaining a January 2025 start date. This supports the possibility of an existing record being edited later; it does not identify which fields changed or when their values became effective.

Its `energycomments` lists Fuel Cost Recovery, Energy Conservation Cost Recovery, Capacity Cost Recovery, Environmental Cost Recovery, Asset Securitization Charge, and Storm Protection Plan Surcharge as adjustment components. Those categories correspond to the categories displayed by Emporia, but the adjustment totals differ. The discrepancy therefore cannot be explained merely by assuming OpenEI excludes all those fees.

Onboarding should persist the selected plan identity and discover its versions using utility-wide results and available supersession metadata. Refresh should also detect changes within the same label, retain snapshots, and distinguish record edit timestamps from tariff effective dates. A label and start date alone are insufficient historical version identifiers.
