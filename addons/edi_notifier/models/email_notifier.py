from datetime import datetime, timedelta

from odoo import fields, api, models


class EdiEmailNotifier(models.AbstractModel):

    _name = "edi.notifier.email"
    _inherit = "edi.notifier.model"
    _description = "EDI Notifier Email Base Model"

    def get_email_model(self):
        return self.env.ref("edi.model_edi_document")

    def _should_notify(self, notifier, rec):
        return rec._name == notifier.template_id.model_id.model

    @api.multi
    def _notify(self, notifier, recs):
        for rec in recs:
            template =  notifier.template_id
            if notifier.include_issues:
                template = template.with_context(issues=self._get_issues(rec))
            if notifier.include_notes:
                template = template.with_context(notes=self._get_notes(rec))
            template.send_mail(rec.id, force_send=True)

    @api.multi
    def notify(self, notifier, recs):
        """Filter records and send them for notification"""
        if not recs:
            recs = notifier.doc_type_ids
        self._notify(notifier, self.filter_records(notifier, recs))


class EdiEmailStateNotifier(models.AbstractModel):

    _name = "edi.notifier.email.state"
    _inherit = "edi.notifier.email"

    def _should_notify(self, notifier, rec):
        return super()._should_notify(notifier, rec) and self._check_state(rec)

    def _check_state(self, rec):
        raise NotImplementedError


class EdiEmailSuccessNotifier(models.AbstractModel):

    _name = "edi.notifier.email.success"
    _inherit = "edi.notifier.email.state"

    def _check_state(self, rec):
        return rec.state == "done"


class EdiEmailFailedNotifier(models.AbstractModel):

    _name = "edi.notifier.email.failed"
    _inherit = "edi.notifier.email.state"

    def _check_state(self, rec):
        return rec.state != "done"


class EdiEmailMissingNotifier(models.AbstractModel):

    _name = "edi.notifier.email.missing"
    _inherit = "edi.notifier.email"

    def get_email_model(self):
        return self.env.ref("edi.model_edi_document_type")

    can_use_crons = True
    _timestamp_field = "x_last_checked_not_received"

    def _get_time_today(self, cron):
        time = fields.Datetime.from_string(cron.nextcall).time()
        return datetime.now().replace(
            hour=time.hour, minute=time.minute, second=0, microsecond=0,
        )

    def _start_of_day(self):
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def _get_last_checked(self, rec):
        return fields.Datetime.from_string(getattr(rec, self._timestamp_field))

    def _get_date_lower_bound(self, _notifier, _cron, rec):
        """Gets when it was lasted checked or the start of the day """
        start_of_day = self._start_of_day()
        date_lower_bound = self._get_last_checked(rec)
        if not date_lower_bound or start_of_day < start_of_day:
            date_lower_bound = start_of_day
        return date_lower_bound

    def _get_transfers(self, lower_bound, upper_bound, rec):
        # To account for time truncation and goal post problems
        return self.env["edi.transfer"].search(
            [
                ("create_date", ">", fields.Datetime.to_string(lower_bound)),
                ("create_date", "<=", fields.Datetime.to_string(upper_bound)),
                ("doc_ids.doc_type_id", "=", rec.id),
            ]
        )

    def _should_notify(self, notifier, rec):
        res = super()._should_notify(notifier, rec)
        if res:
            last_checked = self._get_last_checked(rec)
            # this needed for times when it isn't triggered by a cron
            for timeslot in notifier.cron_ids:
                time_today = self._get_time_today(timeslot)
                if last_checked is None or last_checked < time_today:
                    return not self._get_transfers(
                        self._get_date_lower_bound(notifier, timeslot, rec),
                        time_today + timedelta(minutes=1),  # for goal post errors
                        rec,
                    )
        return False

    @api.multi
    def _notify(self, notifier, recs):
        super()._notify(notifier, recs)
        recs.write({self._timestamp_field: datetime.now()})


class EdiEmailMissingInRangeNotifier(models.AbstractModel):

    _name = "edi.notifier.email.missing.in.range"
    _inherit = "edi.notifier.email.missing"

    can_use_crons = True

    def _get_date_lower_bound(self, notifier, cron, _rec):
        return self._get_time_today(cron) - timedelta(hours=notifier.lookback_hours)

