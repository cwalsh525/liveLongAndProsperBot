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
        for k in api_record:
            for n in database_record: # Still need to loop even though only one record
                # This every value!
                # Create a locked column so the record for sure never gets updated again once the note is completed or charged off?
                if (n['note_status_description'] == "COMPLETED" and k == "age_in_months")\
                        or (n['note_status_description'] == "CHARGEOFF" and k == "age_in_months")\
                        or (n['note_status_description'] == "CHARGEOFF" and k == "days_past_due") \
                        or (n['note_status_description'] == "DEFAULTED" and k == "age_in_months") \
                        or (n['note_status_description'] == "DEFAULTED" and k == "days_past_due") \
                        :
                    return False
                # Ignore COMPLETED loans if its just updating the age_in_months
                else:
                    if k != "accrued_interest": # Ignore accrued_interest since it changes daily.
                        if str(api_record[k]) != str(n[k]):  # cast to string to make the same
                            msg = "NOT Equal value, with key: {key}, propser response value of {r_val}, database value of {db_val} of loan_note_id of {loan_note_id}"\
                                .format(key=k, r_val=api_record[k], db_val=n[k], loan_note_id=api_record['loan_note_id'])
                            # print(msg)
                            # self.logger.debug(msg)
                            return True # If database value does not equal prosper api value return True to flag for update
        return False

    """
    builds list of notes that differ in the database compared to the api
    This notes need to be updated
    """
    def build_notes_to_update_query(self):
        list_of_notes_to_update = []
        insert_query = ""
        first_insert_record = True
        offset = 0
        limit = 25
        response = ""
        while response != None:
            response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2019-11-25", limit), headers=self.header, timeout=30.0).json()['result']
            if response != None:
                # print(response)
                for r in response:
                    cursor = self.connect.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Pulling in extra muscle with DictCursor
                    cursor.execute("select * from notes where loan_note_id = '{loan_note_id}' and latest_record_flag='t';"
                                   .format(loan_note_id=r['loan_note_id']))
                    note_record = cursor.fetchall()
                    if len(note_record) > 0: #TODO raise error flag if len(note_record) == 0
                        if self.check_if_note_needs_update(api_record=r, database_record=note_record):
                            if first_insert_record:
                                insert_query += sql_query_utils.insert_notes_query(response_object=r,
                                                                   effective_start_date=datetime.date.today())
                                first_insert_record = False
                            else:
                                insert_query += sql_query_utils.insert_notes_addational_value(response_object=r,
                                                                                              effective_start_date=datetime.date.today())
                            list_of_notes_to_update.append(r['loan_note_id'])
            offset += limit
        update_query = sql_query_utils.update_notes_query(list_of_notes_to_update)
        print("{num} notes to update".format(num=len(list_of_notes_to_update)))
        self.logger.debug("{num} notes to update".format(num=len(list_of_notes_to_update)))
        return update_query, insert_query

    def build_transaction(self):
        update_query, insert_query = self.build_notes_to_update_query()
        return """ BEGIN TRANSACTION;
        {update_query}
        {insert_query};
        END TRANSACTION;
        """.format(update_query=update_query, insert_query=insert_query)

    def execute(self):
        self.connect.execute_insert_or_update(self.build_transaction())
