import requests
# import psycopg2
import psycopg2.extras
import datetime

from token_gen.token_generation import TokenGeneration
from metrics.connect import Connect

import config.default as default
import utils.utils as utils
import notes.note_utils as note_util
from utils import sql_query_utils
import log.logging as log


class UpdateNotes:

    def __init__(self):
        self.config = default.config
        self.access_token = access_token = TokenGeneration(
            client_id=self.config['prosper']['client_id'],
            client_secret=self.config['prosper']['client_secret'],
            ps=self.config['prosper']['ps'],
            username=self.config['prosper']['username']
        ).execute()
        self.header = utils.http_header_build(access_token)
        self.connect = Connect()
        self.logger = log.create_logger(log_name="metrics_app", logger_name="update_notes_logger")

    """
    This function checks if any value in the database for a note differs from api
    """
    def check_if_note_needs_update(self, api_record, database_record):
        #Sloppy and inefficient, but gets the job done.
        # If the db record shows note has been sold...
        # Never update the record again. It's done, over.
        missing_keys = self.check_for_missing_api_keys(api_record, database_record)
        for d in database_record:
            if (d['is_sold']
            # Bug, i think Propser updates their notes before payment verifciation, so if final payment for COMPLETED doesn't go through this record would get locked incorrectly. This would be a very small amt to be fair though, most likely.
            #         or d['note_status_description'] == "COMPLETED"
                    or d['note_status_description'] == "DEFAULTED"
                #TODO Add in something like ( d['note_status_description'] == "COMPLETED" and current_date > effective_start_date - 10 )
            ):
                return False, {}
        # final_return = False
        for k in api_record:
            for n in database_record: # Still need to loop even though only one record
                # Sometimes a record will update months or years later because of one col.
                # if n['is_sold']:
                #     return False
                # This every value!
                # Create a locked column so the record for sure never gets updated again once the note is completed or charged off?
                if (n['note_status_description'] == "COMPLETED" and k == "age_in_months")\
                        or (n['note_status_description'] == "CHARGEOFF" and k == "age_in_months")\
                        or (n['note_status_description'] == "CHARGEOFF" and k == "days_past_due") \
                        or (n['note_status_description'] == "DEFAULTED" and k == "age_in_months") \
                        or (n['note_status_description'] == "DEFAULTED" and k == "days_past_due") \
                        or (n['note_status_description'] == "PROSPERBUYBACKBUG") \
                        :
                    return False, {}
                # Ignore COMPLETED loans if its just updating the age_in_months
                # Ignore PROSPERBUYBACKBUG as prosper bought those back and keeps chaning to CURRENT
                else:
                    if k != "accrued_interest": # Ignore accrued_interest since it changes daily.
                        if str(api_record[k]) != str(n[k]):  # cast to string to make the same
                            msg = "NOT Equal value, with key: {key}, propser response value of {r_val}, database value of {db_val} of loan_note_id of {loan_note_id}"\
                                .format(key=k, r_val=api_record[k], db_val=n[k], loan_note_id=api_record['loan_note_id'])
                            # print(msg)
                            # self.logger.debug(msg)
                            return True, missing_keys # If database value does not equal prosper api value return True to flag for update
        # return final_return
        return False, {}

    def check_for_missing_api_keys(self, api_record, database_record):
        # Convert keys to sets and subtract
        missing_set = set(database_record[0].keys()) - set(api_record.keys())
        # Remove my internal cols, which of course are missing
        missing = missing_set - {'latest_record_flag', 'created_ts', 'effective_end_date', 'effective_start_date', 'modified_ts', 'id'}

        # print(f"Keys missing: {missing}")
        return missing

    """
    builds list of notes that differ in the database compared to the api
    This notes need to be updated
    """
    #TODO, this seems inefficeint, instead of pulling all notes via api and checking to DB to see if update is needed, perhaps do it the other way.
    def build_notes_to_update_query(self):
        list_of_notes_to_update = []
        insert_query = ""
        first_insert_record = True
        offset = 0
        limit = 25
        response = ""
        while response != None:
            #TODO Update this min_date at least. Check DB to see most recent still active note.
            #TODO Update this min_date at least. Check DB to see most recent still active note. As of 11/5/25 this min date is 2022-07-05, but used jun 1 to be safe. This failed??
            # response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2019-11-25", limit), headers=self.header, timeout=30.0).json()['result']
            # response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2021-12-31", limit), headers=self.header, timeout=30.0).json()['result']
            response_api = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2022-10-01", limit), headers=self.header, timeout=30.0)
            print(f"Hit API, offset is: {offset}, api status code is {response_api.status_code}")
            if response_api.status_code == 200:
                response = response_api.json()['result']
                # 2022-10-18 is min(ownership_start_date) for current.
                if response != None:
                    # print(response)
                    for r in response:
                        cursor = self.connect.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Pulling in extra muscle with DictCursor
                        cursor.execute("select * from notes where loan_note_id = '{loan_note_id}' and latest_record_flag='t';"
                                       .format(loan_note_id=r['loan_note_id']))
                        note_record = cursor.fetchall() # fetchall is for more than 1 record, shouldnt i use fetchone()?
                        if len(note_record) > 0: #TODO raise error flag if len(note_record) == 0
                            needs_update, missing_keys = self.check_if_note_needs_update(api_record=r, database_record=note_record)
                            # if len(missing_keys) > 0:
                            #     print(missing_keys)
                            api_dict_with_old_cols_added = r.copy()
                            for k in missing_keys:
                                # print(note_record[0][k])
                                api_dict_with_old_cols_added[k] = note_record[0][k]  # Prosper API BUG(?) they aren't including all keys, so if missing keys, use most recent database value for thatkey instead of null which is wrong for existing records.
                            # print(api_dict_with_old_cols_added)
                            if needs_update:
                                if first_insert_record:
                                    if r['note_status_description'] != "CANCELLED":  # Temp to check something. Prosper API is giving me a garbage cancelled
                                        insert_query += sql_query_utils.insert_notes_query(response_object=api_dict_with_old_cols_added,
                                                                           effective_start_date=datetime.date.today(), logger=self.logger)
                                        first_insert_record = False
                                else:
                                    insert_query += sql_query_utils.insert_notes_addational_value(response_object=api_dict_with_old_cols_added,
                                                                                                  effective_start_date=datetime.date.today(), logger=self.logger)
                                    # print(insert_query) # Testing.
                                # print(f"loan note identified to be updated: {r['loan_note_id']}")
                                list_of_notes_to_update.append(r['loan_note_id'])
                offset += limit
        update_query = sql_query_utils.update_notes_query(list_of_notes_to_update)
        print("{num} notes to update".format(num=len(list_of_notes_to_update)))
        self.logger.debug("{num} notes to update".format(num=len(list_of_notes_to_update)))
        return update_query, insert_query

    def build_transaction(self):
        update_query, insert_query = self.build_notes_to_update_query()
        # print(update_query)
        # print(insert_query)
        return """ BEGIN TRANSACTION;
        {update_query}
        {insert_query};
        END TRANSACTION;
        """.format(update_query=update_query, insert_query=insert_query)

    def execute(self):
        self.connect.execute_insert_or_update(self.build_transaction())
        self.connect.close_connection()
        # TODO bug, age_in_months updates after a note is charged off when the debt is sold (make a final column?, use is sold) (check for sold off defaulted records and update the age_in_months to the min when defaulted or charged off)
        # The effect of bug is all chargeoff loans are basically 1 month older than should be bc thats when they get sold off.
