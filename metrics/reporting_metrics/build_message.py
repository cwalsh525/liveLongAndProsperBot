from metrics.reporting_metrics.notes_metrics import NotesMetrics
from metrics.tracking_metrics import TrackingMetrics
from metrics.connect import Connect

from datetime import datetime, timedelta
from texttable import Texttable

"""
This class builds the message to be sent to an email for tracking purposes
"""
class BuildMessage:
    def __init__(self, accounts, listing):
        self.message = ""
        self.notes = NotesMetrics(datetime.today())
        self.accounts = accounts
        self.listing = listing

    def display_default_rate_tracking(self):
        table = Texttable()
        table.add_row(["Rating", "Expected", "BL", "Actual", "% +/-", "Diff", "Diff BL", "Late"])
        projected_default_dict, projected_default_dict_prosper, actual_default_dict, actual_default_rates_dict, actual_late_dict = self.notes.default_rate_tracking()
        total_expected_defaulted_v1 = 0
        total_expected_defaulted_prosper = 0
        total_actual_num = 0
        total_late = 0
        self.message += "\n"
        late_dict = {}
        for k in sorted(projected_default_dict):
            try:
                actual_num = actual_default_dict[k]
            except KeyError:
                actual_num = 0

            try:
                # self.message += "Rating {k}: expected defaulted notes for v1 is {num}, with prosper expected of {prosper_num}, actual is {actual_num} (Including {late_num} late)".format(k=k, num=round(projected_default_dict[k], 4), prosper_num=round(projected_default_dict_prosper[k], 4), actual_num=actual_num, late_num=actual_late_dict[k])
                table.add_row([k,
                               round(projected_default_dict[k], 4),
                               round(projected_default_dict_prosper[k], 4),
                               actual_num,
                               str(round(((projected_default_dict[k] - actual_num)/ projected_default_dict[k]) * 100, 2)) + "%",
                               # "actual is {actual_num} (Including {late_num} late)".format(actual_num=actual_num, late_num=actual_late_dict[k]),
                               round(projected_default_dict[k], 4) - actual_num,
                               round(projected_default_dict_prosper[k], 4) - actual_num,
                               actual_late_dict[k]
                               ])
                total_late += actual_late_dict[k]
            except KeyError:
                # self.message += "Rating {k}: expected defaulted notes for v1 is {num}, with prosper expected of {prosper_num}, actual is {actual_num} (Including {late_num} late)".format(k=k, num=round(projected_default_dict[k], 4), prosper_num=round(projected_default_dict_prosper[k], 4), actual_num=actual_num, late_num=0)
                table.add_row([k,
                               round(projected_default_dict[k], 4),
                               round(projected_default_dict_prosper[k], 4),
                               actual_num,
                               str(round(((projected_default_dict[k] - actual_num)/ projected_default_dict[k]) * 100, 2)) + "%",
                               # "actual is {actual_num} (Including {late_num} late)".format(actual_num=actual_num, late_num=0),
                               round(projected_default_dict[k], 4) - actual_num,
                               round(projected_default_dict_prosper[k], 4) - actual_num,
                               0
                               ])
            # self.message += "\n"
            total_expected_defaulted_v1 += projected_default_dict[k]
            total_expected_defaulted_prosper += projected_default_dict_prosper[k]
            total_actual_num += actual_num
        table.add_row(["Total",
                       round(total_expected_defaulted_v1, 4),
                       round(total_expected_defaulted_prosper, 4),
                       total_actual_num,
                       str(round(((total_expected_defaulted_v1 - total_actual_num) / total_expected_defaulted_v1) * 100, 2)) + "%",
                       round(total_expected_defaulted_v1, 4) - total_actual_num,
                       round(total_expected_defaulted_prosper, 4) - total_actual_num,
                       total_late
                       ])
        self.message += "Default And Late Rate Tracking:\n"
        self.message += table.draw()
        self.message += "\n"
        # self.message += "Total expected defaulted notes for v2 is {num} with prosper expected of {prosper_num}, actual is {actual_num}".format(num=round(total_expected_defaulted_v1, 4), prosper_num=round(total_expected_defaulted_prosper, 4), actual_num=total_actual_num)

    def display_note_count_by_rating(self, status):
        table = Texttable()
        table.add_row(["Rating", "Count", "% of Total", "Total Value", "Avg Age Months"])
        total_note_count = 0
        total_age_in_months = 0
        total_value = 0
        notes_data = self.notes.get_notes_by_rating_data()
        for k in sorted(notes_data[status]):
            total_value += notes_data[status][k][1] # total principal_balance_pro_rata_share remaining
        self.message += "\n{status} Note Count By Rating:\n".format(status=status)
        for k in sorted(notes_data[status]):
            table.add_row([k, notes_data[status][k][0], round(notes_data[status][k][1] / total_value * 100, 2), round(notes_data[status][k][1], 2), round(notes_data[status][k][4] / notes_data[status][k][0], 2)])
            total_note_count += notes_data[status][k][0]
            total_age_in_months += notes_data[status][k][4]
        table.add_row(["Total", total_note_count, 100, round(total_value, 2), round(total_age_in_months / total_note_count, 2)])
        self.message += table.draw()

    def display_bids_placed_today(self):
        self.message += "Total bids placed today: {num}".format(num=TrackingMetrics().pull_number_of_bid_requests_by_day(datetime.today()))

    def display_note_count_total(self):
        self.message += "\nTotal notes by status: {status_dict}".format(status_dict=self.notes.get_note_status_description())

    def display_average_notes_purchased_last_X_days(self, days_to_query):
        query = "select count(*) from notes where ownership_start_date between current_date - {days_to_query} AND current_date AND latest_record_flag='t'".format(days_to_query=days_to_query)
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
        select lfu.prosper_rating, count(*)
        from bid_requests br
        join listings_filters_used lfu
        on br.listing_id = lfu.listing_id
        where br.created_timestamp::date = '{date}'
        group by 1;
        """.format(date=datetime.today())
        msg = "Bids placed today by prosper rating:\n"
        bids = Connect().execute_select(query)
        for b in bids:
            msg += "{prosper_rating}: {count}\n".format(prosper_rating=b[0], count=b[1])
        self.message += "\n{bids}".format(bids=msg)

    def display_bids_placed_today_by_rating(self):
        msg = "\nTotal bids by rating:\n"
        bids = TrackingMetrics().pull_bid_requests_by_day(datetime.today())
        # listings = TrackingMetrics.pull_bid_requests_listing_ids("2020-07-13")
        # listings_list = []
        # for l in listings:
        #     listings_list.append(l[0])


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
        total_principal_91_20_late = 0
        note_ownership = 0
        note_count = 0
        for note in notes_data:
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] == 0:
                total_principal += note['principal_balance_pro_rata_share']
                note_ownership += note['note_ownership_amount']
                note_count += 1
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 90:
                total_principal_91_20_late += note['principal_balance_pro_rata_share']
        for note in notes_data:
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] == 0:
                outstanding_yield += (note['principal_balance_pro_rata_share'] / total_principal) * note['lender_yield']

        estimated_interest = round(
            ((float(outstanding_yield) + 1)**(1/12) - 1)
            * float(total_principal), 2)
        interest_minus_cost = estimated_interest - float(total_principal_91_20_late)
        estimated_annualized_return = round(((((interest_minus_cost / float(total_principal)) + 1) ** 12) - 1) * 100, 2)

        # This is for IF defaults what %
        current_date = datetime.today()
        last_month_date = (current_date - timedelta(days=(current_date.day)))

        notes_today = NotesMetrics(current_date)
        projected_default_dict_this_month, _, _, _, _ = notes_today.default_rate_tracking()

        notes_last_month = NotesMetrics(last_month_date)
        projected_default_dict_last_month, _, _, _, _ = notes_last_month.default_rate_tracking()

        default_count_this_month = 0
        default_count_last_month = 0

        for k in projected_default_dict_this_month:
            default_count_this_month += projected_default_dict_this_month[k]

        for k in projected_default_dict_last_month:
            default_count_last_month += projected_default_dict_last_month[k]

        increase_in_defaults = default_count_this_month - default_count_last_month
        what_if_loss = increase_in_defaults * (float(total_principal) / note_count)
        what_if_annualized_return = round(((((estimated_interest - float(what_if_loss)) / float(total_principal) + 1) ** 12) - 1) * 100, 2)


        # principal_charged_off = Connect().execute_select( # This result may be incorrect if defaulted / charged off notes get a new record after they have already defaulted for some reason
        #     "select sum(payment_received - note_ownership_amount) from notes where effective_start_date >= current_date - 30 and latest_record_flag='t' and note_status_description in ('CHARGEOFF', 'DEFAULTED');"
        # )[0][0] # One record
        # if principal_charged_off is None:
        #     principal_charged_off = 0
        self.message += "\nAverage outstanding yield is {the_yield}%".format(the_yield=round(outstanding_yield * 100, 2))
        self.message += "\nEstimated next month annualized return is {estimated_annualized_return}%".format(estimated_annualized_return=estimated_annualized_return)
        self.message += "\nEstimated monthly interest is {interest}".format(interest=estimated_interest)
        self.message += "\nPrincipal to be charged off in next 30 days: {late_over_90}".format(late_over_90=round(total_principal_91_20_late,2))
        self.message += "\nEstimated monthly interest minus charegoffs is {interest}".format(interest=round(interest_minus_cost, 2))
        self.message += "\nEstimated monthly interest minus chargeoffs must be {value} to get 15% return".format(value=round(0.01171491691 * float(total_principal), 2))
        # 0.01171491691 is (1.15 ^ (1 / 12 ) ) - 1 (its 15% annual return adjusted for month)
        self.message += "\nAverage note ownership amount is {note_amt}".format(note_amt=round(note_ownership / note_count, 2))
        self.message += "\nAverage note outstanding principal is {prin_amt}".format(prin_amt=round(total_principal / note_count, 2))
        self.message += "\nIF expected defaults for last month happened with current outstanding principal, annualized return would be: {ann_return}%".format(ann_return=what_if_annualized_return)
        self.message += "\n"
    # weight the yield on prinpical balance outstanding.

    def display_late_info(self):
        late_cats = ["1 - 15", "16 - 30", "31 - 60", "61 - 90", "91 - 120"]
        # create dict
        late_dict = {}
        current_count = 0
        total_late_count = 0
        for cat in late_cats:
            late_dict[cat] = {"count": 0,
                              "outstanding principal": 0,
                              "ratings": []}
        # {'1 - 15': {'count': 0, 'outstanding principal': 0, 'ratings': []},
        #  '16 - 30': {'count': 0, 'outstanding principal': 0, 'ratings': []},
        #  '31 - 60': {'count': 0, 'outstanding principal': 0, 'ratings': []},
        #  '61 - 90': {'count': 0, 'outstanding principal': 0, 'ratings': []},
        #  '91 - 120': {'count': 0, 'outstanding principal': 0, 'ratings': []}}

        notes_data = self.notes.pull_notes_table()
        for note in notes_data:
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] == 0:
                current_count += 1
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 0 and note['days_past_due'] < 16:
                late_dict["1 - 15"]["count"] += 1
                late_dict["1 - 15"]["outstanding principal"] += note['principal_balance_pro_rata_share']
                late_dict["1 - 15"]["ratings"].append(note['prosper_rating'])
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 15  and note['days_past_due'] < 31:
                late_dict["16 - 30"]["count"] += 1
                late_dict["16 - 30"]["outstanding principal"] += note['principal_balance_pro_rata_share']
                late_dict["16 - 30"]["ratings"].append(note['prosper_rating'])
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 30 and note['days_past_due'] < 61:
                late_dict["31 - 60"]["count"] += 1
                late_dict["31 - 60"]["outstanding principal"] += note['principal_balance_pro_rata_share']
                late_dict["31 - 60"]["ratings"].append(note['prosper_rating'])
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 60 and  note['days_past_due'] < 91:
                late_dict["61 - 90"]["count"] += 1
                late_dict["61 - 90"]["outstanding principal"] += note['principal_balance_pro_rata_share']
                late_dict["61 - 90"]["ratings"].append(note['prosper_rating'])
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 90:
                late_dict["91 - 120"]["count"] += 1
                late_dict["91 - 120"]["outstanding principal"] += note['principal_balance_pro_rata_share']
                late_dict["91 - 120"]["ratings"].append(note['prosper_rating'])
        table = Texttable()
        table.add_row(["Late Category", "Count", "Outstanding Principal", "Comprised Notes"])
        for d in late_dict:
            table.add_row([d,
                           late_dict[d]["count"],
                           late_dict[d]["outstanding principal"],
                           late_dict[d]["ratings"]
                           ])
            total_late_count += late_dict[d]["count"]
        self.message += "\nLate Note Data:"
        self.message += "\nCurrent notes late is {num}% of all notes\n".format(num=round((total_late_count / (total_late_count + current_count) * 100), 2))
        self.message += table.draw()
        self.message += "\n"


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
        self.display_average_notes_purchased_last_X_days(30)
        self.display_notes_purchased_last_X_days_by_rating(30)
        self.display_note_count_by_rating("CURRENT")
        self.display_note_count_total()
        self.display_average_yield()
        self.display_current_annualized_return()
        self.display_default_rate_tracking()
        self.display_late_info()
        self.display_available_cash_balance()
        return self.message
