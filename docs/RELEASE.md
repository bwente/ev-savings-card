# GitHub and HACS release checklist

## Prepared locally

- Repository name: `ev-savings-card`; intended owner: `bwente`.
- Description: Home Assistant dashboard card for EV charging cost and time of use savings.
- Suggested topics: `home-assistant`, `hacs`, `lovelace`, `custom-card`, `ev-charging`.
- Integration: `custom_components/ev_savings`, including its bundled card. Standalone card: `dist/ev-savings-card.js`.
- Existing MIT license retained. The companion integration is included.
- Tests, deterministic build, HACS workflow, and draft release workflow are included.

## Before publishing

1. Run `npm run validate` and `python -m pytest tests/integration` and inspect the complete tree for secrets and personal data before every commit or push. Keep agent instructions, credentials, and personal configurations untracked.
2. Verify the Git author is Brian Wente and the remote belongs to `bwente`. Use `main` as the default branch. Enable issues, set its description and topics.
3. Public repository publication was approved on September 17, 2026. Private repositories cannot be installed through HACS.
4. Complete the live acceptance checks below. Record exact versions and replace the prototype screenshot if the presentation changes.
5. Run the Validate workflow on the public repository. HACS must pass without ignored checks. Local unit tests do not establish that HACS validation passes.
6. Set matching versions in `package.json`, integration manifest, integration constant, and the card's `VERSION`, update the changelog, rebuild, review, and commit. Push the corresponding version tag, such as `v0.6.2`.
7. Review the workflow-created draft release and publish it with `ev-savings-card.js` attached. A tag alone does not meet submission requirements. Rerun HACS validation after publication.
8. Install the published release as a HACS custom Integration repository in a clean Home Assistant setup.
9. Only then submit `bwente/ev-savings-card` to the sorted `integration` list in `hacs/default`, using the repository owner account. No submission has been made by this preparation.

## Live acceptance checks (pending)

- Install the integration, complete Duke and OpenEI config flows, restart, and verify cached version retention.
- Confirm bundled card registration, permission checks, source/review warnings, and missing historical coverage.
- Compare the dated Duke profile against a bill with the same billing period; document excluded taxes and fees.
- Review and resolve any pending tariff updates before representing rates as current.

- Record Home Assistant, HACS, browser, phone, and desktop versions.
- Install via HACS; confirm the resource loads and card picker opens without an exception.
- Configure via editor, save, reopen, and verify advanced YAML options survive editor changes.
- Check cost, savings, kWh, previous month, current month, and rapid navigation.
- Confirm desktop and narrow mobile layouts, keyboard controls, and day information.
- Compare hourly energy and rate transitions against recorder data, including month boundaries, midnight, weekends, and DST.
- Check empty history, unavailable entities, incorrect units, malformed rates, and historical dates.
- Verify source, effective date, warnings, and selected currency are visible.
- Test ordinary non-Emporia kWh statistics. Do not claim broader charger compatibility until verified.

## Official references

- [Integration structure](https://hacs.xyz/docs/publish/integration/)
- [General repository requirements](https://hacs.xyz/docs/publish/start/)
- [HACS validation action](https://hacs.xyz/docs/publish/action/)
- [Default repository submission](https://hacs.xyz/docs/publish/include/)
