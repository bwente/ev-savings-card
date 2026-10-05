# Verified Duke Florida RST-1 profile

Latest review October 5, 2026; September snapshot retained unchanged. This profile estimates variable electricity charges before taxes. It does not reproduce a complete utility bill.

## Primary sources

- [Duke RST-1 tariff](https://www.duke-energy.com/-/media/pdfs/for-your-home/rates/rates-fl/pe-rates-rst-1.pdf): sheet 6.140, 41st revision, effective October 1, 2026; seasonal and holiday rules unchanged. Sheet 6.141 remains effective January 1, 2025.
- [Duke billing adjustments BA-1](https://www.duke-energy.com/-/media/pdfs/for-your-home/rates/rates-fl/pe-rates-ba-1.pdf): sheet 6.105, 115th revision, effective October 1, 2026. Sheets 6.106 and 6.107 remain unchanged.

The profile records SHA-256 hashes of the exact PDFs reviewed. These URLs are mutable; the scheduled source check fails if a PDF changes. A document hash change requires review, not an automatic numerical update.

## October 2026 update

The source monitor correctly detected changes to both PDFs. Reviewed RST-1 base prices are 5.013 / 8.263 / 11.155 cents per kWh (discount / off peak / peak); BA-1 secondary fuel factors are 4.055 / 4.387 / 5.037 cents. Other residential recovery factors remain unchanged at a combined 1.733 cents. Pre-tax totals are **10.801 / 14.383 / 17.925 cents per kWh**. The customer charge changed to $14.43 but remains excluded from charging-time savings.

A new immutable version starts October 1. The September version's data and hashes are preserved; date selection chooses the newer version from October when both are accepted. Existing installations that first receive this update after October 1 will retain October as pending under the existing backdated-update safeguard. This maintenance change does not automatically approve pending revisions or reprice saved history. Fresh installations load both versions.

The latest version's review deadline is November 5, 2026. The online source check compares the newest version's hashes with the current utility PDFs; old snapshots deliberately retain hashes of their historical documents.

## September 2026 price components

All values below are cents per kWh. JSON stores dollars per kWh as decimal strings.

| Component | Discount | Off peak | On peak |
| --- | ---: | ---: | ---: |
| Base RST-1 energy | 4.984 | 8.215 | 11.090 |
| Fuel, all other schedules / secondary | 3.539 | 3.828 | 4.395 |
| ECCR | 0.386 | 0.386 | 0.386 |
| CCR | 0.133 | 0.133 | 0.133 |
| ECRC | 0.040 | 0.040 | 0.040 |
| ASC | 0.238 | 0.238 | 0.238 |
| SPPCRC | 0.936 | 0.936 | 0.936 |
| **Total** | **10.256** | **13.776** | **17.218** |

These totals differ from the January 2025 plan shown in the supplied Emporia screenshots. At 45.4288286908208 kWh, Emporia's displayed $0.1074/kWh gives $4.88. This September profile gives $4.66 before excluded charges. That difference does not establish which application's billed total is correct: dates, billing-cycle application and covered charges must match first.

## Time rules

Service time zone: America/New_York.

- December–February discount: midnight to 3 a.m. every day.
- March–November discount: midnight to 6 a.m. every day.
- Weekday peak: 6–9 p.m. year-round; also 5–10 a.m. December–February.
- Other hours: off peak.
- Peak exceptions: New Year's Day, Memorial Day, Independence Day, Labor Day, Thanksgiving and Christmas. A Saturday holiday is observed Friday; a Sunday holiday is observed Monday.

DST uses absolute recorder timestamps converted into the service time zone. Repeated fall hours are counted separately. Missing spring hours are not invented.

## Scope and version maintenance

The source-only figures above exclude customer charges, minimum-bill effects, gross receipts and regulatory assessment fees, municipal utility taxes and franchise fees. From 0.5.2, an explicit statewide-inclusive cost basis adds the BA-1 sheet 6.106 factors of 2.5663% and 0.0871% to source energy charges; local taxes and franchise fees still require verification. Existing entries remain source-only until this option is selected. The last two can depend on municipality; a universal multiplier would be misleading. Savings compares variable costs for the same recorded energy, using the comparison period selected at setup.

Coverage starts September 1, 2026. Do not backfill earlier months from this profile. Rates are applied on calendar dates; utility billing-month application can differ.

To maintain the profile:

1. Review current utility sheets and their effective dates, schedules, riders and exclusions.
2. Add a new immutable version with source hashes and review dates; never overwrite an old version to represent a new rate.
3. Add price, effective-boundary and schedule regression tests.
4. Release the integration update before the effective date when possible. Users receive the profile through HACS updates.
5. Treat late or corrected historical versions as pending review. This beta does not offer a graphical approval/recalculation flow. Do not imply that pending versions have been applied.

The review deadline initially falls October 11, 2026. Passing that deadline triggers a visible warning; it does not establish that the utility changed prices. A daily local profile refresh only reloads installed data. It does not fetch new release content or parse utility PDFs.

## OpenEI fallback

OpenEI versions remain unverified. A successful request establishes data availability, not accuracy. Unsupported demand charges, multiple tiers, missing dates and malformed schedules are rejected. Holidays are not inferred. The integration polls by utility and follows the selected record or linked successors, retains snapshots, and warns about revisions. It never combines rates from unrelated Duke plans or assumes that the latest utility record is the customer's tariff.
