# Changelog

## 0.6.2 — Unreleased

- Register the bundled card as a Lovelace module resource, updating older integration resource URLs on startup.
- Document explicit resource registration for YAML dashboards and missing custom element troubleshooting.

## 0.6.1 — Unreleased

- Preserve editor focus and draft text during Home Assistant updates.
- Explain manual rate setup in the editor and hide legacy settings when the integration controls them.

## 0.6.0 — Unreleased

- Add graphical manual final-rate entry with flat, custom hourly and optional Duke seasonal schedules.
- Preserve historical tariff snapshots when scheduling manual rate updates.
- Add clickable calendar days with rate-split energy and cost details from hourly intervals.
- Support manual tariff currency and avoid adding tax factors to user-entered final prices.


## 0.5.2 — Unreleased

- Restore compact summary and rate columns and collapse detailed source notes.
- Keep incomplete-history and tariff notices visible without repeating full explanations.
- Add an explicit Duke cost basis including statewide gross receipts and regulatory assessment factors. Apply it consistently to actual cost, savings and rate labels.
- Preserve existing source-only totals until users opt in; mark local fees as unconfirmed until checked.


## 0.5.1 — Unreleased

- Show a neutral comparison message when savings round to zero, including tiny negative differences.


## 0.5.0 — Unreleased

- Add companion integration with graphical Duke/OpenEI setup and a bundled card.
- Add verified September 2026 Duke variable rates, seasonal hours and observed holidays.
- Calculate hourly costs in the utility time zone with dated tariff snapshots.
- Warn about missing history, stale reviews and unverified or changed OpenEI data.
- Preserve standalone YAML card support; package HACS as an integration.
- Add backend regression tests against Home Assistant 2026.6.0.


## 0.4.0 — Unreleased

- Prepare a single-file Dashboard plugin distribution for HACS.
- Add a graphical entity editor and safe card picker defaults.
- Extract tariff parsing and cost accumulation into testable functions.
- Reject invalid schedules, period mappings, missing prices, unsupported tiers, and incompatible rate units.
- Exclude energy across recorder gaps and negative corrections, with visible warnings.
- Use recorder energy consistently for cost, savings, and energy summaries; stop estimating live energy at the current rate.
- Reject tariffs whose stated validity does not cover the selected month.
- Show missing-history and tariff-freshness limitations.
- Prevent stale recorder responses from overwriting newer selections.
- Isolate styles, adapt layouts to the card width, show tariff source metadata, and honor configured currency in rate labels.
- Add build checks, regression tests, HACS validation, and a draft release workflow.
- Add seasonal rate-boundary and daylight-saving regression checks; document holiday and seasonal comparison limitations.
