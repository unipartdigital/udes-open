from datetime import datetime, timedelta

from odoo import fields, api, models


class EdiEmailNotifier(models.AbstractModel):

    _name = "edi.notifier.email"
    _inherit = "edi.notifier.model"
    _description = "Edi Notifier Email Base Model"

    def _should_notify(self, notifier, rec):
        if rec._name != notifier.template_id.model_id.model:
            return False
        return True

    @api.multi
    def _notify(self, notifier, recs):
        for rec in recs:
            notifier.template_id.send_mail(rec.id, force_send=True)

    @api.multi
    def notify(self, notifier, recs):
        """Filter records and send them for notification"""
        if not recs:
            recs = notifier.doc_type_ids
        self._notify(notifier, self.filter_records(notifier, recs))


class EdiEmailSuccessNotifier(models.AbstractModel):

    _name = "edi.notifier.email.success"
    _inherit = "edi.notifier.email"

    def _should_notify(self, notifier, rec):
        if rec.state != "done":
            return False
        return super()._should_notify(notifier, rec)


class EdiEmailFailedNotifier(models.AbstractModel):

    _name = "edi.notifier.email.failed"
    _inherit = "edi.notifier.email"

    def _should_notify(self, notifier, rec):
        if rec.state == "done":
            return False
        return super()._should_notify(notifier, rec)


class EdiEmailMissingNotifier(models.AbstractModel):

    _name = "edi.notifier.email.missing"
    _inherit = "edi.notifier.email"

    can_use_crons = True
    _timestamp_field = "x_last_not_received_notification"

    def _get_time_today(self, cron):
        time = fields.Datetime.from_string(cron.nextcall).time()
        return datetime.now().replace(
            hour=time.hour, minute=time.minute, second=0, microsecond=0,
        )

    def _get_transfers(self, rec, time_today, last_reported):

        # To account for time truncation and goal post problems
        time_today += timedelta(minutes=1)

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if last_reported is not None and last_reported > today:
            date_lower_bound = last_reported
        else:
            date_lower_bound = today

        return self.env["edi.transfer"].search(
            [
                ("create_date", ">", fields.Datetime.to_string(date_lower_bound)),
                ("create_date", "<=", fields.Datetime.to_string(time_today)),
                ("doc_ids.doc_type_id", "=", rec.id),
            ]
        )

    def _should_notify(self, notifier, rec):
        res = super()._should_notify(notifier, rec)
        if res:
            last_reported = fields.Datetime.from_string(
                getattr(rec, self._timestamp_field)
            )
            # this needed for times when the it isn't triggered by a cron
            for timeslot in notifier.cron_ids:
                time_today = self._get_time_today(timeslot)
                if last_reported is None or last_reported < time_today:
                    return not self._get_transfers(rec, time_today, last_reported)
        return False

    @api.multi
    def _notify(self, notifier, recs):
        super()._notify(notifier, recs)
        recs.write({self._timestamp_field: datetime.now()})