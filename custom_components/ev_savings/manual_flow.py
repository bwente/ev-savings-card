"""Shared graphical manual-rate wizard for setup and options."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import voluptuous as vol
from homeassistant.helpers import selector
from .manual import make_version


def choose(options, multiple=False):
    return selector.SelectSelector(selector.SelectSelectorConfig(options=options, multiple=multiple, mode=selector.SelectSelectorMode.DROPDOWN))


class ManualFlow:
    async def async_step_manual(self, user_input=None):
        errors={}
        if user_input:
            try:
                self.manual_data=user_input
                self.manual_rules=[]
                self.manual_version=make_version(user_input, [])
                if getattr(self,'manual_update',False):
                    current={**self.config_entry.data, **self.config_entry.options}
                    today=datetime.now(ZoneInfo(current['time_zone'])).date().isoformat()
                    if user_input['time_zone'] != current['time_zone'] or user_input['currency'].upper() != current.get('currency','USD') or user_input['effective_from'] <= today:
                        raise ValueError('Updates must start on a future local date and preserve time zone and currency')
                if user_input['schedule']=='custom':
                    return await self.async_step_manual_rule()
                return await self.finish_manual()
            except (ValueError, KeyError, TypeError):
                errors['base']='invalid_manual'
        current = {**self.config_entry.data, **self.config_entry.options} if getattr(self,'manual_update',False) else {}
        zone=current.get('time_zone',self.hass.config.time_zone)
        default_date=(datetime.now(ZoneInfo(zone)).date()+timedelta(days=1 if getattr(self,'manual_update',False) else 0)).isoformat()
        return self.async_show_form(step_id='manual',errors=errors,data_schema=vol.Schema({
            vol.Required('utility'):str, vol.Required('name'):str,
            vol.Required('currency',default=current.get('currency','USD')):str,
            vol.Required('time_zone',default=zone):str,
            vol.Required('effective_from',default=default_date):selector.DateSelector(),
            vol.Required('discount'):vol.All(vol.Coerce(float),vol.Range(min=0)),
            vol.Required('off_peak'):vol.All(vol.Coerce(float),vol.Range(min=0)),
            vol.Required('peak'):vol.All(vol.Coerce(float),vol.Range(min=0)),
            vol.Required('schedule',default='custom'):choose([
                {'value':'flat','label':'Flat rate — uses the discount price all day'},
                {'value':'custom','label':'Custom time-of-use schedule'},
                {'value':'duke_fl_rst1','label':'Duke Florida RST-1 seasonal hours and holidays'}])}))

    async def async_step_manual_rule(self,user_input=None):
        errors={}
        if user_input:
            try:
                if not user_input['months'] or not user_input['days']:
                    raise ValueError('Select months and days')
                candidate=[*self.manual_rules,user_input]
                version=make_version(self.manual_data,candidate)
                self.manual_rules=candidate
                self.manual_version=version
                if not user_input['add_another']:
                    return await self.finish_manual()
            except (ValueError,KeyError,TypeError):
                errors['base']='invalid_schedule'
        return self.async_show_form(step_id='manual_rule',errors=errors,data_schema=vol.Schema({
            vol.Required('months',default=[str(m) for m in range(1,13)]):choose([str(m) for m in range(1,13)],True),
            vol.Required('days',default=['weekday','weekend']):choose(['weekday','weekend'],True),
            vol.Required('role',default='discount'):choose(['discount','peak']),
            vol.Required('start',default=0):vol.All(vol.Coerce(float),vol.In(list(range(24))),vol.Coerce(int)),
            vol.Required('end',default=6):vol.All(vol.Coerce(float),vol.In(list(range(1,25))),vol.Coerce(int)),
            vol.Required('add_another',default=False):bool}))

    async def finish_manual(self):
        if getattr(self,'manual_update',False):
            options={**self.config_entry.options, **self.pending_options,
                     'provider':'manual','currency':self.manual_version['currency'],
                     'manual_versions':[*self.config_entry.options.get('manual_versions',[]),self.manual_version]}
            return self.async_create_entry(title='',data=options)
        self.selection.update({'provider':'manual','initial_version':self.manual_version,
                               'time_zone':self.manual_version['time_zone'],'currency':self.manual_version['currency']})
        return await self.async_step_energy()
