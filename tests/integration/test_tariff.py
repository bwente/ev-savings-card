"""Regression coverage for delivered prices, dates, DST and source revisions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest
from custom_components.ev_savings.tariff import (
    TariffError, calculate_month, merge_versions, month_bounds, price, role_at, version_at,
)
from custom_components.ev_savings.openei import convert

PROFILE = json.loads(Path('custom_components/ev_savings/profiles/duke_fl_rst1.json').read_text())["versions"][0]


def test_verified_prices_and_emporia_comparison():
    assert [price(PROFILE, r) for r in ('discount', 'off_peak', 'peak')] == [Decimal('.10256'), Decimal('.13776'), Decimal('.17218')]
    energy = Decimal('45.4288286908208')
    assert (energy * Decimal('.1074')).quantize(Decimal('.01')) == Decimal('4.88')
    assert (energy * price(PROFILE, 'discount')).quantize(Decimal('.01')) == Decimal('4.66')


@pytest.mark.parametrize('stamp,expected', [
    ('2026-09-11T05:59:59-04:00','discount'), ('2026-09-11T06:00:00-04:00','off_peak'),
    ('2026-09-11T18:00:00-04:00','peak'), ('2026-09-11T21:00:00-04:00','off_peak'),
    ('2026-12-01T02:59:59-05:00','discount'), ('2026-12-01T03:00:00-05:00','off_peak'),
    ('2026-12-01T05:00:00-05:00','peak'), ('2026-12-01T10:00:00-05:00','off_peak'),
    ('2026-09-12T18:00:00-04:00','off_peak'), ('2026-09-07T18:00:00-04:00','off_peak'),
    ('2026-07-03T18:00:00-04:00','off_peak'), ('2027-12-24T06:00:00-05:00','off_peak'),
    ('2026-11-26T18:00:00-05:00','off_peak'), ('2027-05-31T18:00:00-04:00','off_peak')])
def test_seasons_weekends_and_observed_holidays(stamp, expected):
    assert role_at(PROFILE, stamp) == expected


def rows_for(start, hours):
    return [{"start": start + timedelta(hours=i), "sum": i + 1} for i in range(-1, hours)]


@pytest.mark.parametrize('month,hours', [(3,743), (11,721)])
def test_dst_and_hourly_costs(month, hours):
    profile = deepcopy(PROFILE)
    profile['effective_from'] = '2026-01-01'
    start, end = month_bounds(2026, month, 'America/New_York')
    assert (end-start).total_seconds()/3600 == hours
    result = calculate_month(rows_for(start, hours), [profile], 2026, month, 'America/New_York', now=end)
    assert result['totals']['kwh'] == hours
    assert result['coverage'] == {'hours': hours, 'expected': hours}
    assert sum(day['kwh'] for day in result['days'].values()) == hours
    assert result['days'][f'2026-{month:02}-' + ('08' if month == 3 else '01')]['kwh'] == (23 if month == 3 else 25)


def test_midmonth_version_change_preserves_old_charges():
    second = deepcopy(PROFILE)
    second['id'] = 'new'
    second['effective_from'] = '2026-09-02'
    second['rates']['discount']['base'] = '.14984'
    start, _ = month_bounds(2026, 9, 'America/New_York')
    result = calculate_month(rows_for(start, 30), [PROFILE, second], 2026, 9, 'America/New_York', now=start+timedelta(hours=30))
    assert result['days']['2026-09-01']['actualCost'] == pytest.approx(6*.10256 + 15*.13776 + 3*.17218)
    assert result['days']['2026-09-02']['actualCost'] == pytest.approx(6*.20256)
    assert len(result['tariff']['versions_used']) == 2


def test_missing_history_and_invalid_statistics():
    with pytest.raises(TariffError, match='No tariff version'):
        version_at([PROFILE], '2026-08-31T23:59:59-04:00')
    start, _ = month_bounds(2026, 9, 'America/New_York')
    rows = rows_for(start, 5)
    rows[2]['sum'] = None
    rows[-1]['sum'] = -1
    result = calculate_month(rows, [PROFILE], 2026, 9, 'America/New_York', now=start+timedelta(hours=5))
    assert result['totals']['kwh'] == 2
    assert any('incomplete' in text for text in result['warnings'])


def test_revision_freezing_and_future_effective_dates():
    changed = deepcopy(PROFILE)
    changed['rates']['discount']['base'] = '.20'
    kept, pending = merge_versions([PROFILE], [changed], '2026-09-11')
    assert kept == [PROFILE] and pending == [changed]
    changed['id'] = 'new'
    kept, pending = merge_versions([PROFILE], [changed], '2026-09-11')
    assert pending == [changed]
    changed['effective_from'] = '2026-10-01'
    kept, pending = merge_versions([PROFILE], [changed], '2026-09-11')
    assert len(kept) == 2 and not pending
    assert version_at(kept, '2026-09-30T23:00:00-04:00')['id'] == PROFILE['id']
    assert version_at(kept, '2026-10-01T00:00:00-04:00')['id'] == 'new'


def test_openei_explicit_mapping_and_reject_tiers():
    record = {'label':'test', 'name':'TOU', 'utility':'Example', 'startdate':1735689600,
              'energyratestructure':[[{'rate':.11,'adj':.06,'unit':'kWh'}], [{'rate':.08,'adj':.05,'unit':'kWh'}], [{'rate':.04,'adj':.03,'unit':'kWh'}]],
              'energyweekdayschedule':[[2]*6+[1]*12+[0]*3+[1]*3]*12,
              'energyweekendschedule':[[2]*6+[1]*18]*12}
    roles = {'discount':2,'off_peak':1,'peak':0}
    v = convert(record, 'America/New_York', roles)
    assert not v['verified'] and price(v,'discount') == Decimal('.07')
    assert role_at(v, '2026-09-11T04:00:00-04:00') == 'discount'
    record['energyratestructure'][0].append({'rate':.2, 'unit':'kWh'})
    with pytest.raises(TariffError, match='Tiered'):
        convert(record, 'America/New_York', roles)


def test_statewide_billing_applies_equally_to_cost_savings_and_display_rates():
    from custom_components.ev_savings.billing import billed_price
    billing = {'cost_basis':'total', 'local_charges':'unknown'}
    assert billed_price(PROFILE, 'discount', billing) == Decimal('.10528132704')
    start, _ = month_bounds(2026, 9, 'America/New_York')
    result = calculate_month(rows_for(start, 1), [PROFILE], 2026, 9, 'America/New_York', now=start+timedelta(hours=1), billing=billing)
    assert result['totals']['actualCost'] == pytest.approx(.10256 * 1.026534)
    assert result['totals']['comparisonCost'] == pytest.approx(.13776 * 1.026534)
    assert result['totals']['savings'] == pytest.approx((.13776-.10256) * 1.026534)
    assert result['tariff']['rates']['discount'] == result['totals']['actualCost']
    assert any('not yet an all-in total' in w for w in result['warnings'])
    assert price(PROFILE,'discount') == Decimal('.10256')  # Stored energy version is unchanged.


def test_total_billing_does_not_assume_other_utilities_share_duke_taxes():
    from custom_components.ev_savings.billing import billed_price
    other = deepcopy(PROFILE)
    other['schedule_kind'] = 'monthly'
    with pytest.raises(TariffError, match='not yet defined'):
        billed_price(other, 'discount', {'cost_basis':'total'})
    assert billed_price(other,'discount',{'cost_basis':'energy'}) == Decimal('.10256')
