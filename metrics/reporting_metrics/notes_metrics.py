import psycopg2
import psycopg2.extras
import decimal
from datetime import datetime, timedelta
import math

from metrics.connect import Connect

"""
This class holds the funcitons for calculating the metrics
"""


# TODO There is a lot of cleanup to be done here. A lot of copy paste code. Make into functions
# TODO Change name as this is now really just for default rate tracking since gains stuff was pulled out
class NotesMetrics:
    def __init__(self, date):
        self.date = date
        self.notes_data = self.pull_notes_table()  # An array of tuples (a tuple per row)
        # These default rates are high as analysis was done 2010 - 2019, but CURRENT notes were thrown away in analysis (so past 3 years defaults were analzyed but not notes that were still current)
        self.total_chance_of_default_v1_deprecated = {
            "B": .1058, # Warning Deprecated. Here for reference ~ 2 - 2.3 Avg notes per day
                                      "C": .1336,
                                      "D": .1717,
                                      "E": .2519,
                                      "HR": .2847
                                    }
        # self.total_chance_of_default_v2 = { # ~ X Avg notes per day depr 20201207
        #     "B": .1068, # Stronger than Prosper A's 56% of baseline
        #       "C": .1325, # Close to Propser A's, Stronger than prosper B's 48% of baseline (lower % of baseline is best)
        #       "D": .1834, # Equal to Prosper B's # 53% of baseline
        #       "E": .2548, # Better than prosper C's 68% of baseline
        #       "HR": .2875 # Better than Prosper D's, ~ prosper C 74% of baseline
        #       } # added 2 more filters for more c, d , e
        # self.total_chance_of_default_v2 = { # ~ X Avg notes per day # depr 20201210
        #     "B": .1068, # Stronger than Prosper A's 56% of baseline
        #       "C": .1351, # Close to Propser A's, Stronger than prosper B's 49% of baseline (lower % of baseline is best)
        #       "D": .1857, # Equal to Prosper B's # 54% of baseline
        #       "E": .2524, # Better than prosper C's 68% of baseline
        #       "HR": .2875 # Better than Prosper D's, ~ prosper C 74% of baseline
        #       }
        self.total_chance_of_default_v2 = { # ~ X Avg notes per day
            "B": .1063, # Stronger than Prosper A's 56% of baseline
              "C": .1351, # Close to Propser A's, Stronger than prosper B's 49% of baseline (lower % of baseline is best)
              "D": .1888, # Equal to Prosper B's # 55% of baseline
              "E": .2541, # Better than prosper C's 68% of baseline
              "HR": .2875 # Better than Prosper D's, ~ prosper C 74% of baseline
              }
        self.total_chance_of_default_prosper = {"AA": .0566,
                                      "A": .1184,
                                      "B": .1903,
                                      "C": .2767,
                                      "D": .3448,
                                      "E": .3731,
                                      "HR": .3882
                                      }

    """Pulls the notes data"""
    def pull_notes_table(self):
        connect = Connect()
        cursor = connect.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Pulling in extra muscle with DictCursor
        # cursor.execute("select * from notes where '{date}' between effective_start_date and effective_end_date;".format(date=self.date))
        cursor.execute("select note_status_description, principal_balance_pro_rata_share, principal_paid_pro_rata_share, interest_paid_pro_rata_share, age_in_months, payment_received, note_ownership_amount, ownership_start_date, prosper_rating, note_ownership_amount, lender_yield, days_past_due, term "
                       "from notes where '{date}' between effective_start_date and effective_end_date;".format(date=self.date))
        notes_data = cursor.fetchall()
        return notes_data

    def number_of_notes(self):
        return len(self.notes_data)

    def calculate_age_in_months(self, ownership_start_date, actual_date):
        # start_date_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        # end_date_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        # days_to_run = int((end_date_datetime - start_date_datetime).days)
        # actual_date.split(" ")
        # actual_date[-1] = actual_date[-1][:4]
        # actual_date = " ".join(actual_date)
        # if len(str(ownership_start_date)) != 10:
        #     print("yikes {date}".format(date=ownership_start_date))
        if len(str(actual_date)) != 10:
            # print("yikes {date}".format(date=actual_date))
        #TODO Explore this bug. Looks like current_date is running many many times
            actual_date = str(actual_date)[:10]
        end_date = datetime.strptime(str(actual_date), "%Y-%m-%d")
        start_date = datetime.strptime(str(ownership_start_date), "%Y-%m-%d")
        age_in_days = int((end_date - start_date).days)
        age_in_months = age_in_days / 30
        if age_in_months > 36: #TODO needs to change if term changes
            age_in_months = 36
        return math.floor(age_in_months)

    """
    Returns {STATUS: {"prosper_rating": [count, principal owed, principal paid, interest paid, age_in_months_sum, payment_received, note_ownership_amount, calculated_age_in_months]}
    """
    def get_notes_by_rating_data(self):

        metrics_to_track = ["total_count", "principal_owed", "principal_paid", "interest_paid", "age_in_months_sum", "payment_received", "note_ownership_amount", "calculated_age_in_months", "term_percent_complete_sum"]
        note_statues = ["CURRENT", "COMPLETED", "DEFAULTED", "CHARGEOFF", "LATE", "PROSPERBUYBACKBUG", "CANCELLED"]
        prosper_ratings = ["B", "C", "D", "E", "HR"]
        note_status_description_dict = {}
        # Build note_status_description_dict
        for status in note_statues:
            note_status_description_dict[status] = {}
            for rating in prosper_ratings:
                note_status_description_dict[status][rating] = {}
                for metric in metrics_to_track:
                    note_status_description_dict[status][rating][metric] = 0

        # Below is structure for note_status_description_dict
        # note_status_description_dict = \
        #     {
        #     "CURRENT": {
        #         "B": {"total_count": 0,
        #               "principal_owed": 0,
        #               "principal_paid": 0,
        #               "interest_paid": 0,
        #               "age_in_months_sum": 0,
        #               "payment_received": 0,
        #               "note_ownership_amount": 0,
        #               "calculated_age_in_months": 0
        #         },
        #         "C": {"total_count": 0,
        #               "principal_owed": 0,
        #               "principal_paid": 0,
        #               "interest_paid": 0,
        #               "age_in_months_sum": 0,
        #               "payment_received": 0,
        #               "note_ownership_amount": 0,
        #               "calculated_age_in_months": 0
        #               }
        #     },
        #     "COMPLETED": {
        #         "B": {"total_count": 0,
        #               "principal_owed": 0,
        #               "principal_paid": 0,
        #               "interest_paid": 0,
        #               "age_in_months_sum": 0,
        #               "payment_received": 0,
        #               "note_ownership_amount": 0,
        #               "calculated_age_in_months": 0
        #               }
        #         }
        #     }
        # Create note_status_description_dict
        for note in self.notes_data:
            if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 0:
                note_status_description = "LATE"
            else:
                note_status_description = note['note_status_description']
            prosper_rating = note['prosper_rating']
            note_status_description_dict[note_status_description][prosper_rating]["total_count"] += 1
            note_status_description_dict[note_status_description][prosper_rating]["principal_owed"] += note['principal_balance_pro_rata_share']
            note_status_description_dict[note_status_description][prosper_rating]["principal_paid"] += note['principal_paid_pro_rata_share']
            note_status_description_dict[note_status_description][prosper_rating]["interest_paid"] += note['interest_paid_pro_rata_share']
            note_status_description_dict[note_status_description][prosper_rating]["age_in_months_sum"] += note['age_in_months']
            note_status_description_dict[note_status_description][prosper_rating]["payment_received"] += note['payment_received']
            note_status_description_dict[note_status_description][prosper_rating]["note_ownership_amount"] += note['note_ownership_amount']
            note_status_description_dict[note_status_description][prosper_rating]["calculated_age_in_months"] += self.calculate_age_in_months(ownership_start_date=note['ownership_start_date'], actual_date=self.date)
            note_status_description_dict[note_status_description][prosper_rating]["term_percent_complete_sum"] += note['age_in_months'] / note['term']

        return note_status_description_dict


    """
    Chance of defualt is hardcoded.
    total_chance_of_default_v1 is my filters chance of defualt vs total_chance_of_default_prosper which is prosper average
    Returns three dictionaries projected_default_dict_v1, projected_default_dict_prosper, actual_default_dict_v1
    
    projected_default_dict_v1: projected number of notes that should have defaulted
    projected_default_dict_prosper: projected number of notes that should have defaulted prosper
    actual_default_dict_v1: actual number of defaulted loans (includes late)
    """
    # I would think this should change everytime a note is added(?) but it only changes like twice a month??
    # But when notes are added they have age_in_months of 0, so it makes no difference in the calculation.
    def default_rate_tracking(self):
        # ME HR .00777777777 * age_in_months * cnt
        # Prosper HR .01078333333 * age_in_months * cnt
        notes_data = self.get_notes_by_rating_data()

        #TODO Make better
        # As of 20200801 we are using complete age in months not calc
        # For default rates, we will use caluclated age_in_months for non current
        # calculated age in months should be used for default rating. If a note or completes before term, its expected age_in_months should be used not the age_in_months it got closed at.

        projected_default_dict = {}
        projected_default_dict_prosper = {}
        actual_default_dict = {}
        actual_late_dict = {}

        # Builds actual defaulted notes
        # Build a dict that is defaulted (chargeoff and default) as well as late notes to be counted as such for forcasting

        for k in notes_data['DEFAULTED']:
            actual_default_dict[k] = notes_data['DEFAULTED'][k]['total_count']
        for k in notes_data['CHARGEOFF']:
            actual_default_dict[k] += notes_data['CHARGEOFF'][k]['total_count']
        for k in notes_data['LATE']:
            actual_default_dict[k] += notes_data['LATE'][k]['total_count']
        # Builds actual_late_dict
        for k in notes_data['LATE']:
            actual_late_dict[k] = notes_data['LATE'][k]['total_count']

        def get_total_value_from_notes_by_rating(prosper_rating, value_needed):
            return_value = 0
            for k in notes_data:
                return_value += notes_data[k][prosper_rating][value_needed]
            return return_value

        # #TODO Should I calculate age_in_months for completed note (up to 36) to factor it into defualt rate chances? or keep the stale age_in_months?
        ratings = ['B', 'C', 'D', 'E', 'HR']
        for rating in ratings:
            projected_default_dict[rating] = get_total_value_from_notes_by_rating(rating, "term_percent_complete_sum") * self.total_chance_of_default_v2[rating]
            projected_default_dict_prosper[rating] = get_total_value_from_notes_by_rating(rating, "term_percent_complete_sum") * self.total_chance_of_default_prosper[rating]

        return projected_default_dict, projected_default_dict_prosper, actual_default_dict, actual_late_dict


    def get_note_status_description(self):
        status_description_count = {}
        for note in self.notes_data:
            if note['note_status_description'] == 'CURRENT' and note['days_past_due'] > 0:
                try:
                    status_description_count['LATE'] += 1
                except KeyError:
                    status_description_count['LATE'] = 1
            else:
                try:
                    status_description_count[note['note_status_description']] += 1
                except KeyError:
                    status_description_count[note['note_status_description']] = 1
        return status_description_count
