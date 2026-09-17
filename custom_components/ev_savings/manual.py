"""User-entered final kWh prices and explicit hourly schedules."""
from datetime import date
from zoneinfo import ZoneInfo
from .tariff import TariffError, decimal, digest, validate_version


def make_version(data, rules):
    ZoneInfo(data['time_zone'])
    date.fromisoformat(data['effective_from'])
    currency = data['currency'].upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise TariffError('Use a three-letter currency code')
    rates = {}
    for role in ('discount', 'off_peak', 'peak'):
        cents = decimal(data['discount'] if data['schedule'] == 'flat' else data[role])
        if cents < 0:
            raise TariffError('Rates must be nonnegative')
        rates[role] = {'entered_total': str(cents / 100)}
    version = {'name':data['name'], 'utility':data['utility'], 'time_zone':data['time_zone'],
               'currency':currency, 'effective_from':data['effective_from'], 'effective_to':None,
               'manual':True, 'verified':False, 'source':'Manual entry — '+data['utility'],
               'scope':'User-entered final variable kWh prices; no extra taxes or multipliers added. Fixed household charges excluded.',
               'rates':rates, 'schedule_kind':'monthly'}
    if data['schedule'] == 'duke_fl_rst1':
        version['schedule_kind'] = 'duke_fl_rst1'
    else:
        base = 'discount' if data['schedule'] == 'flat' else 'off_peak'
        version.update({key:[[base]*24 for _ in range(12)] for key in ('weekday','weekend')})
        occupied = set()
        for rule in rules:
            if decimal(rule['start']) % 1 or decimal(rule['end']) % 1:
                raise TariffError('Schedules require whole hours with hourly statistics')
            start, end = int(rule['start']), int(rule['end'])
            if not 0 <= start < end <= 24:
                raise TariffError('Use increasing whole-hour boundaries; split overnight windows into two rules')
            for month in rule['months']:
                for day in rule['days']:
                    for hour in range(start,end):
                        cell=(int(month)-1,day,hour)
                        if cell in occupied:
                            raise TariffError('Schedule rules overlap')
                        occupied.add(cell)
                        version[day][int(month)-1][hour]=rule['role']
    version['id']='manual-'+digest(version)[:20]
    return validate_version(version)
