from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date


class AccountLoanRate(models.Model):
    _name = 'account.loan.rate'
    _description = 'Loan Rate Change'
    _order = 'loan_id, date, id'

    loan_id = fields.Many2one('account.loan', string='Loan', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='loan_id.company_id', store=True, index=True)
    date = fields.Date(string='From', required=True, help="The first day of the new rate.")
    rate = fields.Float(string='Annual Rate (%)', digits=(16, 4), required=True)

    _unique_date = models.Constraint('UNIQUE(loan_id, date)', 'A loan has one rate change a day.')
    _positive_rate = models.Constraint('CHECK(rate >= 0)', 'The interest rate cannot be negative.')

    @api.constrains('date', 'loan_id')
    def _check_after_paid(self):
        """ A rate cannot change in the periods already paid: their interest is booked. """
        for change in self:
            paid = change.loan_id.line_ids.filtered(lambda line: line.state == 'posted')
            last = max(paid.mapped('date'), default=None)
            if last and change.date <= last:
                raise ValidationError(self.env._(
                    'The loan %(loan)s is paid up to %(date)s: a rate change applies from a later date.',
                    loan=change.loan_id.display_name, date=format_date(self.env, last)))

    @api.model_create_multi
    def create(self, vals_list):
        changes = super().create(vals_list)
        changes._regenerate(min(changes.mapped('date'), default=None))
        return changes

    def write(self, vals):
        dates = self.mapped('date')
        res = super().write(vals)
        self._regenerate(min(dates + self.mapped('date'), default=None))
        return res

    def unlink(self):
        loans = self.loan_id
        dates = self.mapped('date')
        res = super().unlink()
        loans._regenerate_from(min(dates, default=None))
        return res

    def _regenerate(self, date_from):
        self.loan_id._regenerate_from(date_from)
