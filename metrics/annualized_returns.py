from metrics.connect import Connect
from accounts.accounts import Accounts
from notes.notes import Notes

from datetime import datetime

from datetime import date

class AnnualizedReturns(Connect):

    def __init__(self, header):
        self.date = datetime.today()
        self.header = header
        Connect.__init__(self) # Initialize connection

    def calculate_annualized_returns(self):
        money_in = 0
        avg_age_of_money = 0
        monies = self.execute_select("select transaction_date, amount from deposits_and_withdrawls;")
        for a in monies:
            money_in += a[1]
        for a in monies:
            days_old = (date.today() - a[0]).days
            proportion_of_total_money = a[1] / money_in
            avg_age_of_money += (proportion_of_total_money * days_old)

        accounts = Accounts(header=self.header).get_account_response()
        cash = accounts['available_cash_balance']
        pending = accounts['pending_investments_primary_market']
        notes = Notes()
        principal_with_late, principal = notes.get_account_value()
        total_monies = principal + pending + cash
        total_monies_with_late = principal_with_late + pending + cash

        account_value_change = total_monies - float(money_in)
        account_value_percent_change = account_value_change / float(money_in)
        account_value_change_with_late = total_monies_with_late - float(money_in)
        account_value_percent_change_with_late = account_value_change_with_late / float(money_in)

        annualized_returns = account_value_percent_change ** float((avg_age_of_money / 365))
        annualized_returns_with_late = account_value_percent_change_with_late ** float((avg_age_of_money / 365))
        return round(annualized_returns * 100, 4), round(annualized_returns_with_late * 100, 4)

    def update_annualized_returns_table(self):
        annualized_returns, annualized_returns_with_late = self.calculate_annualized_returns()
        insert_query = """insert into daily_annualized_returns
        ("date", annualized_return, annualized_return_late_equals_default)
        values
        ('{date}', {annualized_returns}, {annualized_returns_with_late});""".format(date=self.date, annualized_returns=annualized_returns, annualized_returns_with_late=annualized_returns_with_late)
        self.execute_insert_or_update(insert_query)
