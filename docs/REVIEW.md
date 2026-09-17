# Release preparation review

## Public repository preparation — 2026-09-17

- Version 0.6.2 includes manual rate entry, compact presentation, hourly rate breakdowns, editor focus preservation, and dashboard resource registration.
- The user confirmed that dashboard resource registration resolved the observed intermittent missing-card error on a live installation.
- The local regression suite has 21 frontend and 34 backend tests.
- Hosted HACS and Hassfest checks and clean HACS installation remain separate acceptance checks.
- The sections below are historical review records; later sections supersede earlier findings.

## Initial review — 2026-09-11

## Resolved

- Empty card-picker configuration threw before setup. Added a safe stub and graphical editor.
- Missing or malformed prices could silently become zero; invalid role indexes could silently fall back. Added explicit validation and rejected unsupported tariff tiers and units.
- Live daily energy was assigned to the current tariff hour without reliable timing. Removed this estimate and made all summaries use recorded energy consistently.
- Recorder gaps could assign several hours of energy to one rate. Excluded nonconsecutive intervals and corrections with warnings.
- Older asynchronous requests could replace a newly selected month. Added request ownership checks and removed stale totals during loading/errors.
- A new tariff could silently reprice historical months. Enforced declared date bounds and disclosed freshness/history limitations.
- Global CSS could affect other cards. Isolated rendering with a shadow root.
- Narrow cards in wide dashboards retained desktop spacing. Switched responsive rules to card-width container queries.
- Rate labels always used dollars, and tariff source was parsed but absent from the footer. Applied configured currency and rendered escaped source metadata.
- Added HACS and release workflows, regression tests, installation/configuration documentation, issue templates, and release checklist.

## Verification

- `npm run validate`: build, syntax checks, and 15 regression tests pass.
- Local in-app browser fixture with synthetic recorder data: inspected 650px and 320px card widths, graphical editor fields, Cost/Savings/kWh modes, and previous-month navigation.
- Supplied Cost and Savings screenshots moved into `docs/images` without changing bytes or dimensions. README displays their native pixel dimensions and links to the originals. They show v0.3.2, not the revised build.
- Pattern-based secret scan of the working tree found no credential matches. This is not a guarantee against all secret formats.
- Local Git initialized on `main` with Brian Wente's configured identity. No commit, remote, push, or public submission made.

## Remaining publication gates

- Public repository approval, hosted HACS validation, a published release, and clean HACS installation are pending.
- Live Home Assistant acceptance testing and a verified minimum version are pending; 2026.6.0 is a retained declaration, not a tested compatibility claim.
- Browser and Home Assistant time zones must match; cross-time-zone presentation needs a future implementation.
- Calendar day details remain hover text; touch-friendly day interaction and historical tariff discovery remain future work.

See [release checklist](RELEASE.md) for the submission sequence.

## Seasonal timing review

Seasonal month/hour selection and exact discount/peak boundaries now have regression coverage. New York DST fixtures confirm that a spring transition contains 23 recorded hours and a fall transition contains 25, counting both occurrences of the repeated hour. These tests use synthetic prices; they do not verify a household tariff entity or bill.

Duke Florida RST-1's filed sheet 6.140, effective January 1, 2026, specifies prevailing local clock time, seasonal discount hours, winter morning peaks, and named holiday/observance exceptions. Source: [Duke filing, PDF page 63](https://www.psc.state.fl.us/library/FILINGS/2025/14875-2025/14875-2025.pdf#page=63).

Remaining accuracy gates:

- Holiday and observed-day exceptions are not represented by the current weekday/weekend selector. Do not claim full Duke RST-1 accuracy until this is implemented and validated.
- Verify the actual tariff entity's 12 monthly schedules and delivered price components against the applicable utility sheets for each historical period.
- Global role mapping assumes the same comparison period index remains appropriate across seasons. Tariffs with distinct seasonal price indexes need season-specific comparison mapping before they can be claimed supported.
- Browser time-zone mismatch is blocked, not automatically converted. The Home Assistant zone must also match the service location's tariff clock.
- Calendar months differ from utility billing cycles; compare matching intervals when reconciling against bills.

## Integration review — 0.5.0

This section supersedes the earlier prototype-only limitations where integration mode is used.

- Added the companion integration, graphical setup, private tariff cache, authenticated monthly accounting endpoint, and bundled card registration.
- Added utility-verified September 2026 Duke price components and named holiday/observance rules. See VERIFIED-TARIFFS.md for scope and source hashes.
- Backend calculations use America/New_York for Duke regardless of browser location. Legacy standalone mode retains its time-zone restriction.
- Node regression suite: 16 tests pass. Python suite: 25 tests pass against Home Assistant 2026.6.0 imports and adapters. This is not a full Home Assistant installation test.
- Source-check script successfully fetched both Duke PDFs and matched their reviewed SHA-256 hashes.
- HACS packaging now uses the integration category, with a local brand icon and bundled JavaScript. No hosted HACS validation has run.
- OpenEI support is deliberately limited to three-period, untiered residential plans. Utility entry requires its exact OpenEI name; this is not yet a location-based utility picker.
- Pending revisions have a visible warning and remain unapplied; graphical revision approval and historical correction workflows remain future work.
- Live installation, browser verification of the new integration path, and bill reconciliation remain publication gates. The existing screenshots retain original pixels and show the earlier card version.
