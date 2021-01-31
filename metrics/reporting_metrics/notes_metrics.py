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
        cursor.execute("select * from notes where '{date}' between effective_start_date and effective_end_date;".format(date=self.date))
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
        if age_in_months > 36:
            age_in_months = 36
        return math.floor(age_in_months)

    """
    Returns {STATUS: {"prosper_rating": [count, principal owed, principal paid, interest paid, age_in_months_sum, payment_received, note_ownership_amount, calculated_age_in_months]}
    """
    def get_notes_by_rating_data(self):
        # notes_dict = {"prosper_rating": [count, principal owed, principal paid, interest paid, age_in_months_sum, payment_received, note_ownership_amount, calculated_age_in_months]}
        # calculated age in months should be used for default rating. If a note or completes before term, its expected age_in_months should be used not the age_in_months it got closed at.
        current__notes_dict = {}
        completed_notes_dict = {}
        defaulted_notes_dict = {}
        chargeoff_notes_dict = {}
        late_notes_dict = {}
        note_status_description_dict = {"CURRENT": current__notes_dict,
                                        "COMPLETED": completed_notes_dict,
                                        "DEFAULTED": defaulted_notes_dict,
                                        "CHARGEOFF": chargeoff_notes_dict,
                                        "LATE": late_notes_dict
                                        }
        for k in note_status_description_dict:
            for note in self.notes_data:
                if note['note_status_description'] == k:
                    if note['note_status_description'] == "CURRENT" and note['days_past_due'] > 0:
                        try: # TODO make all dicts
                            get_list = note_status_description_dict["LATE"][note['prosper_rating']]
                            get_list[0] += 1
                            get_list[1] += note['principal_balance_pro_rata_share']
                            get_list[2] += note['principal_paid_pro_rata_share']
                            get_list[3] += note['interest_paid_pro_rata_share']
                            get_list[4] += note['age_in_months']
                            get_list[5] += note['payment_received']
                            get_list[6] += note['note_ownership_amount']
                            get_list[7] += note['age_in_months']

                        except KeyError:
                            note_status_description_dict["LATE"][note['prosper_rating']] = [1, note['principal_balance_pro_rata_share'], note['principal_paid_pro_rata_share'], note['interest_paid_pro_rata_share'], note['age_in_months'], note['payment_received'], note['note_ownership_amount'], note['age_in_months']]
                        except Exception:
                            raise
                    else:
                        try:
                            get_list = note_status_description_dict[k][note['prosper_rating']]
                            get_list[0] += 1
                            get_list[1] += note['principal_balance_pro_rata_share']
                            get_list[2] += note['principal_paid_pro_rata_share']
                            get_list[3] += note['interest_paid_pro_rata_share']
                            get_list[4] += note['age_in_months']
                            get_list[5] += note['payment_received']
                            get_list[6] += note['note_ownership_amount']
                            get_list[7] += self.calculate_age_in_months(ownership_start_date=note['ownership_start_date'], actual_date=self.date)

                        except KeyError:
                            note_status_description_dict[k][note['prosper_rating']] = [1, note[
                                'principal_balance_pro_rata_share'], note['principal_paid_pro_rata_share'], note[
                                                                                           'interest_paid_pro_rata_share'],
                                                                                       note['age_in_months'], note['payment_received'], note['note_ownership_amount'], self.calculate_age_in_months(ownership_start_date=note['ownership_start_date'], actual_date=self.date)]
                        except Exception:
                            raise

        return note_status_description_dict

    # Utility function for this class
    def calculate_annual_return(self, sum_age_in_months, sum_payments_received, sum_note_ownership_amt, note_count):
        avg_age_in_months = sum_age_in_months / note_count
        exponent_value = 12 / avg_age_in_months
        dollar_gain = sum_payments_received - sum_note_ownership_amt
        percent_gain = float(dollar_gain) / float(sum_note_ownership_amt) + 1
        weighted_percent_gain = (percent_gain ** exponent_value - 1) * 100
        annual_return = round(weighted_percent_gain, 4)

        # print("payments_received: {payments_received}".format(payments_received=sum_payments_received))
        # print("note_ownership_amt: {note_ownership_amt}".format(note_ownership_amt=sum_note_ownership_amt))
        # print("avg_age_in_months: {avg_age_in_months}".format(avg_age_in_months=avg_age_in_months))
        # print("note_count: {note_count}".format(note_count=note_count))
        # print("exponent_value: {exponent_value}".format(exponent_value=exponent_value))
        # print("dollar_gain: {dollar_gain}".format(dollar_gain=dollar_gain))
        # print("percent_gain: {percent_gain}".format(percent_gain=percent_gain))
        # print("weighted_percent_gain: {weighted_percent_gain}".format(weighted_percent_gain=weighted_percent_gain))

        return annual_return

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
        # {STATUS: {"prosper_rating": [count, principal owed, principal paid, interest paid, age_in_months_sum]}}
        all_notes = {}
        current = notes_data['CURRENT']
        complete = notes_data['COMPLETED']
        defaulted = notes_data['DEFAULTED']
        chargeoff = notes_data['CHARGEOFF']
        late = notes_data['LATE']

        #TODO Make better
        # As of 20200801 we are using complete age in months not calc
        # For default rates, we will use caluclated age_in_months for non current
        # calculated age in months should be used for default rating. If a note or completes before term, its expected age_in_months should be used not the age_in_months it got closed at.

        # Adds all notes data together.
        for k in current:
            all_notes[k] = current[k]
        for k in late:
            for i in range(len(late[k])):
                all_notes[k][i] += late[k][i]  # Add current and complete together
        for k in complete:
            # complete[k][4] = complete[k][7] # Use calculated age_in_months instead of age_in_months
            for i in range(len(complete[k])):
                all_notes[k][i] += complete[k][i]  # Add current and complete together
        for k in defaulted:
            # defaulted[k][4] = defaulted[k][7] # Use calculated age_in_months instead of age_in_months
            for i in range(len(defaulted[k])):
                all_notes[k][i] += defaulted[k][i]  # Add current and complete together
        for k in chargeoff:
            # chargeoff[k][4] = chargeoff[k][7] # Use calculated age_in_months instead of age_in_months
            for i in range(len(chargeoff[k])):
                all_notes[k][i] += chargeoff[k][i]  # Add current and complete together

        projected_default_dict = {}
        projected_default_dict_prosper = {}
        actual_default_dict = {}
        actual_default_rates_dict = {}
        actual_late_dict = {}

        # Builds actual defaulted notes
        for k in defaulted:
            try:
                actual_default_dict[k] += defaulted[k][0]
            except KeyError:
                actual_default_dict[k] = defaulted[k][0]
        for k in chargeoff:
            try:
                actual_default_dict[k] += chargeoff[k][0]
            except KeyError:
                actual_default_dict[k] = chargeoff[k][0]
        for k in late:
            try:
                actual_default_dict[k] += late[k][0]
            except KeyError:
                actual_default_dict[k] = late[k][0]
        for k in late:
            try:
                actual_late_dict[k] += late[k][0]
            except KeyError:
                actual_late_dict[k] = late[k][0]


        #TODO Should I calculate age_in_months for completed note (up to 36) to factor it into defualt rate chances? or keep the stale age_in_months?
        for k in all_notes:       # all_notes = {STATUS: {"prosper_rating": [count, principal owed, principal paid, interest paid, age_in_months_sum]} }
            average_ave = all_notes[k][4] / all_notes[k][0]
            projected_default_dict[k] = all_notes[k][4] * self.total_chance_of_default_v2[k] / 36  # cnt of notes * avg_age_in_months * default chance per month. Gives number of nots that should be defaulted
            projected_default_dict_prosper[k] = all_notes[k][4] * self.total_chance_of_default_prosper[k] / 36  # cnt of notes * avg_age_in_months * default chance per month. Gives number of nots that should be defaulted
            try:
                actual_default_rates_dict[k] = ((actual_default_dict[k] * 36 ) / all_notes[k][0]) / average_ave
            except KeyError:
                actual_default_rates_dict[k] = ((0 * 36) / all_notes[k][0]) / average_ave
            # actual_default_rate = ((default_rate * 36) / total_count ) / average_ave



        return projected_default_dict, projected_default_dict_prosper, actual_default_dict, actual_default_rates_dict, actual_late_dict


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
