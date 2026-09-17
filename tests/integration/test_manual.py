from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import pytest
from custom_components.ev_savings.manual import make_version
from custom_components.ev_savings.tariff import calculate_month, month_bounds, version_at, TariffError
from custom_components.ev_savings.billing import billed_price

DATA={'utility':'Example Electric','name':'My plan','currency':'USD','time_zone':'America/New_York',
      'effective_from':'2026-09-01','discount':10.74,'off_peak':14.28,'peak':17.79,'schedule':'custom'}
RULE={'months':[str(m) for m in range(1,13)],'days':['weekday','weekend'],'role':'discount','start':0,'end':6}


def test_manual_final_price_no_tax_double_count_and_flat_plan():
    v=make_version(DATA,[RULE])
    assert billed_price(v,'discount',{'cost_basis':'total'}) == Decimal('.1074')
    assert round(float(billed_price(v,'discount'))*45.4288286908208,2)==4.88
    flat=make_version({**DATA,'schedule':'flat'},[])
    assert billed_price(flat,'off_peak') == billed_price(flat,'discount')


def test_cross_rate_charging_has_two_cost_segments():
    v=make_version(DATA,[RULE])
    start,_=month_bounds(2026,9,'America/New_York')
    rows=[{'start':start+timedelta(hours=h),'sum':s} for h,s in [(4,0),(5,10),(6,20),(7,20)]]
    r=calculate_month(rows,[v],2026,9,'America/New_York',now=start+timedelta(hours=8))
    day=r['days']['2026-09-01']
    assert day['actualCost']==pytest.approx(2.502)
    assert day['savings']==pytest.approx(.354)
    assert [s['role'] for s in day['segments']]==['discount','off_peak']
    assert sum(s['cost'] for s in day['segments'])==pytest.approx(day['actualCost'])
    assert r['cost_basis']=='manual'
    assert not any('OpenEI' in w for w in r['warnings'])


def test_manual_updates_select_dated_prices_and_reject_overlapping_or_fractional_hours():
    old=make_version(DATA,[RULE]); new=make_version({**DATA,'discount':12,'effective_from':'2026-10-01'},[RULE])
    assert version_at([old,new],'2026-09-30T23:00:00-04:00')['id']==old['id']
    assert version_at([old,new],'2026-10-01T00:00:00-04:00')['id']==new['id']
    with pytest.raises(TariffError,match='overlap'):make_version(DATA,[RULE,RULE])
    with pytest.raises(TariffError,match='whole hours'):make_version(DATA,[{**RULE,'start':.5}])
    with pytest.raises(TariffError):make_version({**DATA,'discount':float('nan')},[RULE])
