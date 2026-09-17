"""Explicit cost basis layered over immutable energy tariff snapshots.

Duke BA-1 sheet 6.106 (effective February 1, 2026) specifies factors of
2.5663% gross receipts tax and 0.0871% regulatory assessment fee on sales.
Local taxes and franchise fees are not inferred from a service time zone.
"""
from decimal import Decimal
from .tariff import TariffError, price

SOURCE = 'Duke BA-1 sheet 6.106, effective February 1, 2026'
SOURCE_URL = 'https://www.duke-energy.com/-/media/pdfs/for-your-home/rates/rates-fl/pe-rates-ba-1.pdf'


def billed_price(version, role, settings=None):
    settings = settings or {}
    base = price(version, role)
    if settings.get('cost_basis', 'energy') not in ('energy', 'total'):
        raise TariffError('Invalid cost basis')
    if version.get('manual') or settings.get('cost_basis', 'energy') == 'energy':
        return base
    if version['schedule_kind'] != 'duke_fl_rst1':
        raise TariffError('Inclusive pricing is not yet defined for this provider. Use source rates until its included taxes are verified.')
    if version['effective_from'] < '2026-02-01':
        raise TariffError('Statewide billing factors are not verified for this tariff version')
    return base * (Decimal(1) + Decimal('0.025663') + Decimal('0.000871'))


def billing_description(settings=None):
    settings = settings or {}
    if settings.get('cost_basis', 'energy') != 'total':
        return 'Source energy rates; additional taxes and local fees excluded.'
    return ('Includes fuel, recovery charges, 2.5663% gross receipts tax and 0.0871% regulatory assessment fee. '
            'Fixed household charges and minimum-bill effects are excluded from EV charging costs. '
            + ('No additional local charges, as confirmed in configuration.' if settings.get('local_charges') == 'none'
               else 'Local taxes and franchise fees are unconfirmed and not included; this is not yet an all-in total.'))
