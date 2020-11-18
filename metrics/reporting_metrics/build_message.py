from metrics.reporting_metrics.notes_metrics import NotesMetrics
from metrics.tracking_metrics import TrackingMetrics
from metrics.connect import Connect

from datetime import datetime

"""
This class builds the message to be sent to an email for tracking purposes
"""
class BuildMessage:
    def __init__(self, accounts):
        self.message = ""
        self.notes = NotesMetrics(datetime.today())
        self.accounts = accounts

    def display_default_rate_tracking(self):
        projected_default_dict, projected_default_dict_prosper, actual_default_dict, actual_default_rates_dict, actual_late_dict = self.notes.default_rate_tracking()
        total_expected_defaulted_v1 = 0
        total_expected_defaulted_prosper = 0
        total_actual_num = 0
        self.message += "\n"
        late_dict = {}
        for k in sorted(projected_default_dict):
            try:
                actual_num = actual_default_dict[k]
            except KeyError:
                actual_num = 0

            try:
                self.message += "Rating {k}: expected defaulted notes for v1 is {num}, with prosper expected of {prosper_num}, actual is {actual_num} (Including {late_num} late)".format(k=k, num=round(projected_default_dict[k], 4), prosper_num=round(projected_default_dict_prosper[k], 4), actual_num=actual_num, late_num=actual_late_dict[k])
            except KeyError:
                self.message += "Rating {k}: expected defaulted notes for v1 is {num}, with prosper expected of {prosper_num}, actual is {actual_num} (Including {late_num} late)".format(k=k, num=round(projected_default_dict[k], 4), prosper_num=round(projected_default_dict_prosper[k], 4), actual_num=actual_num, late_num=0)
            self.message += "\n"
            total_expected_defaulted_v1 += projected_default_dict[k]
            total_expected_defaulted_prosper += projected_default_dict_prosper[k]
            total_actual_num += actual_num
        self.message += "Total expected defaulted notes for v2 is {num} with prosper expected of {prosper_num}, actual is {actual_num}".format(num=round(total_expected_defaulted_v1, 4), prosper_num=round(total_expected_defaulted_prosper, 4), actual_num=total_actual_num)

    def display_note_count_by_rating(self, status):
        total_note_count = 0
        total_age_in_months = 0
        total_value = 0
        notes_data = self.notes.get_notes_by_rating_data()
        for k in sorted(notes_data[status]):
            total_value += notes_data[status][k][1] # total principal_balance_pro_rata_share remaining
        self.message += "\n{status} Note Count By Rating:\n".format(status=status)
        for k in sorted(notes_data[status]):
            self.message += "{rating}: {num}, avg_age_in_months: {age}, total value: ${total_value}, % of total: {percent}%\n".format(rating=k, num=notes_data[status][k][0], age=round(notes_data[status][k][4] / notes_data[status][k][0], 2), total_value=round(notes_data[status][k][1], 2), percent=round(notes_data[status][k][1] / total_value * 100, 2))
            total_note_count += notes_data[status][k][0]
            total_age_in_months += notes_data[status][k][4]
        self.message += "Total Note Count: {num}, avg_age_in_months: {age}, total value: ${total_value}".format(num=total_note_count, age=round(total_age_in_months / total_note_count, 2), total_value=round(total_value, 2))

    def display_bids_placed_today(self):
        self.message += "Total bids placed today: {num}".format(num=TrackingMetrics().pull_number_of_bid_requests_by_day(datetime.today()))

# Depreciated
#     def display_gains(self):
#         self.message += """\n
# Realized Gains: {r_gains}%
# Unrealized Gains: {ur}%
# Unrealized Gains With Oppertunity Cost: {uro}%
# Forecasted Returns: {fr}%
# Forcasted Returns Forcasted: {frf}%
#         """.format(r_gains=self.notes.realized_gains(),
#                    ur=self.notes.unrealized_gains(),
#                    uro=self.notes.unrealized_gains_with_oppertunity_cost(),
#                    fr=self.notes.forecasted_returns(),
#                    frf=self.notes.forecasted_returns_forcasted()
#                    )

    def display_note_count_total(self):
        self.message += "\nTotal notes by status: {status_dict}".format(status_dict=self.notes.get_note_status_description())

    def display_average_notes_purchased_last_X_days(self, days_to_query):
        query = "select count(*) from notes where ownership_start_date > current_date - {days_to_query} AND latest_record_flag='t'".format(days_to_query=days_to_query)
        number_of_new_loans = Connect().execute_select(query)[0][0]
        if number_of_new_loans != 0:
            avg_daily_notes_purchased = round(number_of_new_loans / days_to_query, 2)
        else:
            avg_daily_notes_purchased = 0
        self.message += "\nAn average of {avg} notes have been purchased per day for the past {days} days".format(avg=avg_daily_notes_purchased, days=days_to_query)

    def display_notes_purchased_last_X_days_by_rating(self, days_to_query):
        query = "select prosper_rating,count(*) from notes where ownership_start_date > current_date - {days_to_query} and latest_record_flag = 't' group by 1 order by 1 asc;".format(days_to_query=days_to_query)
        loans = Connect().execute_select(query)
        msg = "Notes purchased over the past {days} days:\n".format(days=days_to_query)
        for r in loans:
            msg += "{prosper_rating}: {count}\n".format(prosper_rating=r[0], count=r[1])
        self.message += "\n{loans}".format(loans=msg)

    def display_bids_placed_today_by_prosper_rating(self):
        query = """
        select n.prosper_rating, count(*)
        from bid_requests br
        join notes n 
        on br.listing_id = n.listing_number
        where br.created_timestamp::date = '{date}'
        group by 1;
        """.format(date=datetime.today())
        msg = "Bids INVESTED today by prosper rating:\n"
        bids = Connect().execute_select(query)
        for b in bids:
            msg += "{prosper_rating}: {count}\n".format(prosper_rating=b[0], count=b[1])
        self.message += "\n{bids}".format(bids=msg)

    def display_bids_placed_today_by_rating(self):
        msg = "\nTotal bids by rating:\n"
        bids = TrackingMetrics().pull_bid_requests_by_day(datetime.today())
        for b in bids:
            msg += "{bid_status}: {count}\n".format(bid_status=b[0], count=b[1])
        self.message += "{bids}".format(bids=msg)

    def display_available_cash_balance(self):
        cash_balance = round(self.accounts.get_account_response()['available_cash_balance'], 2)
        self.message += "\nAvailable cash balance is ${cash}".format(cash=cash_balance)

    def display_average_yield(self):
        notes_data = self.notes.pull_notes_table()
        total_principal = 0
        outstanding_yield = 0
        for note in notes_data:
            if note['note_status_description'] == "CURRENT":
                total_principal += note['principal_balance_pro_rata_share']
        for note in notes_data:
            if note['note_status_description'] == "CURRENT":
                outstanding_yield += (note['principal_balance_pro_rata_share'] / total_principal) * note['lender_yield']
        self.message += "\nAverage outstanding yield is {the_yield}%".format(the_yield=round(outstanding_yield * 100, 2))
    # weight the yield on prinpical balance outstanding.

    def display_current_annualized_return(self):
        query = "select annualized_return, annualized_return_late_equals_default from daily_annualized_returns where date in (select max(date) from daily_annualized_returns);"
        results = Connect().execute_select(query)
        for r in results:
            self.message += """
Current annualized_return: {annualized_return}%
annualized_return_minus_late: {annualized_return_late_equals_default}%
""".format(annualized_return=r[0], annualized_return_late_equals_default=r[1])

    def build_complete_message(self):
        self.display_bids_placed_today()
        self.display_bids_placed_today_by_rating()
        self.display_bids_placed_today_by_prosper_rating()
        self.display_note_count_by_rating("CURRENT")
        self.display_note_count_total()
        self.display_average_yield()
        self.display_current_annualized_return()
        # self.display_gains() # Depreciated
        self.display_default_rate_tracking()
        self.message += "\n"
        self.display_average_notes_purchased_last_X_days(30)
        self.display_notes_purchased_last_X_days_by_rating(30)
        self.display_available_cash_balance()
        return self.message
