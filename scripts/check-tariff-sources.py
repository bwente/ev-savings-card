"""Fail when a maintained utility PDF changes, prompting human rate review."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

profile = json.loads(Path('custom_components/ev_savings/profiles/duke_fl_rst1.json').read_text())
latest = max(profile['versions'], key=lambda v: v['effective_from'])
for source in latest['sources']:
    request = Request(source['url'], headers={'User-Agent': 'EV-Savings tariff source review'})
    with urlopen(request, timeout=60) as response:
        actual = hashlib.sha256(response.read()).hexdigest()
    if actual != source['sha256']:
        raise SystemExit(f"Duke sheet {source['sheet']} document changed. Review tariff text before updating the profile.")
print('Source PDF hashes match the reviewed profile.')
