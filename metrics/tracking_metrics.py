from metrics.connect import Connect

import requests
import datetime

import utils.utils as utils

import config.default as default
from utils import sql_query_utils
import notes.note_utils as note_util
import log.logging as log

from token_gen.token_generation import TokenGeneration
from notes.update_notes import UpdateNotes
from accounts.accounts import Accounts
from metrics.annualized_returns import AnnualizedReturns

"""
This class handles all inserts and updates to the backend tracking database
"""
class TrackingMetrics(Connect):

    def __init__(self):
        self.config = default.config
        self.access_token = access_token = TokenGeneration(
            client_id=self.config['prosper']['client_id'],
            client_secret=self.config['prosper']['client_secret'],
            ps=self.config['prosper']['ps'],
            username=self.config['prosper']['username']
        ).execute()
        self.header = utils.http_header_build(access_token)
        Connect.__init__(self) # Initialize connection
        self.logger = log.create_logger(log_name="metrics_app", logger_name="tracking_metrics_logger")

    def get_url_get_request(self, order_id):
        return "{base_url}/orders/{order_id}".format(base_url=self.config['prosper']['prosper_base_url'], order_id=order_id)

    def get_order_response_by_order_id(self, order_id):
        return requests.get(self.get_url_get_request(order_id), headers=self.header, timeout=30.0)

    def build_order_ids_to_get(self):
        order_ids = []
        select_query = "select order_id from orders where order_status = 'IN_PROGRESS';"
        results = self.execute_select(select_query)
        for t in results:
            order_ids.append(t[0]) # [0] because only returning one row
        return order_ids

    def build_pending_listing_ids(self):
        listing_ids = []
        select_query = "select listing_id from bid_requests where bid_status = 'PENDING';"
        results = self.execute_select(select_query)
        for t in results:
            listing_ids.append(t[0]) # [0] because only returning one row
        return listing_ids

    def update_order_table_query(self, order_id, order_status):
        return """
        update orders
            set 
                order_status = '{order_status}',
                modified_timestamp = '{modified_timestamp}'
            where
                order_id = '{order_id}'
            ;
            """.format(order_status=order_status, order_id=order_id, modified_timestamp=datetime.datetime.now())

    def update_order_table(self, response_object):
        if len(response_object) > 0:
            if response_object['order_status'] != "IN_PROGRESS":
                self.execute_insert_or_update(self.update_order_table_query(response_object['order_id'], response_object['order_status']))

    def update_bid_requests_query(self, listing_id, bid_status, bid_result):
        return """
        update bid_requests
            set 
                bid_status = '{bid_status}',
                bid_result = '{bid_result}',
                modified_timestamp = '{modified_timestamp}'
            where listing_id = {listing_id};
        """.format(bid_status=bid_status, bid_result=bid_result, listing_id=listing_id, modified_timestamp=datetime.datetime.now())

    def update_bid_requests_table(self, response_object):
        listing_ids = []
        for l in response_object['bid_requests']:
            if l['bid_status'] != 'PENDING':
                self.execute_insert_or_update(self.update_bid_requests_query(l['listing_id'], l['bid_status'], l['bid_result']))
                if l['bid_status'] == 'INVESTED':
                    listing_ids.append(l['listing_id'])
        return listing_ids

    def get_url_get_request_notes(self, offset, limit):
        return "{base_url}/notes/?offset={offset}&limit={limit}&sort_by=origination_date desc".format(base_url=self.config['prosper']['prosper_base_url'], offset=offset, limit=str(limit))

    def get_response_note(self, https_request):
        response = requests.get(https_request, headers=self.header, timeout=30.0)
        return response

    def insert_note_record(self, response_object, effective_start_date):
        self.execute_insert_or_update(sql_query_utils.insert_notes_query(response_object, effective_start_date))

    def insert_new_note_records(self, listing_ids, limit):
        listing_ids.sort(reverse=True)
        offset = 0
        response_object = requests.get(self.get_url_get_request_notes(offset, limit), headers=self.header, timeout=30.0).json()
        total_objects = response_object['total_count']
        while len(listing_ids) > 0:
            for l in response_object['result']:
                listing_number = l['listing_number']
                if listing_number in listing_ids:
                    self.insert_note_record(l, l['origination_date'])
                    listing_ids.remove(listing_number)
            offset += limit # Preparing for next get request
            response_object = requests.get(self.get_url_get_request_notes(offset, limit), headers=self.header, timeout=30.0).json()
            if response_object['result'] is None:
                break

    # DEPRECATED.Prosper updates frequently, this is not enough. Using Update_notes class now
    # def build_note_ids_to_update_list(self):
    #     select_query = """
    #     select loan_note_id
    #           from notes
    #          where ( (DATE_PART('year', current_date) - DATE_PART('year', origination_date::date)) * 12 +
    #           (DATE_PART('month', current_date::date) - DATE_PART('month', origination_date::date)) > age_in_months
    #             or ( next_payment_due_date < current_date and created_ts < current_date - 2 ) -- run if next_payment_date OR to avoid late notes from updating everyday, will check late notes every 3 days
    #             )
    #           and effective_end_date = '2099-12-31'
    #           and note_status_description not in ('CHARGEOFF', 'DEFAULTED', 'COMPLETED', 'CANCELLED');
    #     """
    #     note_ids = self.populate_list_from_single_column_sql_query(select_query)
    #     return note_ids

    #TODO make its own class?
    def update_deposits_and_withdrawls_table(self):
        account = Accounts(self.header)
        account_response = account.get_account_response()
        deposit_query = "select amount, transaction_date from deposits_and_withdrawls where id = (select max(id) from deposits_and_withdrawls where amount > 0);"
        withdrawl_query = "select amount, transaction_date from deposits_and_withdrawls where id = (select max(id) from deposits_and_withdrawls where amount < 0);"
        deposit_results = self.execute_select(deposit_query)
        withdrawl_results = self.execute_select(withdrawl_query)
        last_deposit_date_from_prosper = datetime.datetime.strptime(account_response['last_deposit_date'][0:10], "%Y-%m-%d").date()
        last_deposit_amount = deposit_results[0][0]
        last_deposit_date = deposit_results[0][1]

        last_withdrawl_date_from_prosper = datetime.datetime.strptime(account_response['last_withdraw_date'][0:10], "%Y-%m-%d").date()
        last_withdraw_amount = withdrawl_results[0][0]
        last_withdrawl_date = withdrawl_results[0][1]

        if float(last_deposit_amount) != account_response['last_deposit_amount'] or last_deposit_date != last_deposit_date_from_prosper:
            self.logger.info("inserting new deposit record of {dep} on {date} ".format(dep=account_response['last_deposit_amount'], date=last_deposit_date_from_prosper))
            self.execute_insert_or_update("insert into deposits_and_withdrawls (transaction_date, amount, created_ts, modified_ts) values ('{date}', {amt}, '{time}' ,null)"
                                          .format(date=last_deposit_date_from_prosper, amt=account_response['last_deposit_amount'], time=datetime.datetime.today()))
        else:
            print("We good bro")

        if last_withdraw_amount != (account_response['last_withdraw_amount'] * -1) or last_withdrawl_date != last_withdrawl_date_from_prosper:
            self.logger.info("inserting new withdrawl record of {dep} on {date} ".format(dep=account_response['last_withdraw_amount'], date=last_withdrawl_date_from_prosper))
            self.execute_insert_or_update("insert into deposits_and_withdrawls (transaction_date, amount, created_ts, modified_ts) values ('{date}', {amt}, '{time}' ,null)"
                                          .format(date=account_response['last_withdraw_date'][0:10], amt=account_response['last_withdraw_amount'] * -1, time=datetime.datetime.today()))
        else:
            print("We good bro")

    #TODO add error handling!
    #TODO clean this stuff up
    def execute(self):
        self.update_deposits_and_withdrawls_table() # updates deposits_and_withdrawls_table table KNOWN BUG, can only handle 1 daily withdrawl and 1 daily deposit
        annual_returns = AnnualizedReturns(header=self.header)
        annual_returns.update_annualized_returns_table() # calculates and updates the annualized_returns_table for today

        order_ids = self.build_order_ids_to_get() # list of order_ids that aren't complete
        listing_ids = self.build_pending_listing_ids() # list of pending listings
        new_listings_to_insert_note_records = [] # New records to insert to notes table
        for order in order_ids:
            order_response = self.get_order_response_by_order_id(order)
            order_response_object = order_response.json()
            self.update_order_table(order_response_object)
            self.logger.debug("order being updated: {order}".format(order=order))
            listing_ids_updated = self.update_bid_requests_table(order_response_object)
            self.logger.debug("lising_ids updated: {listings}".format(listings=listing_ids_updated)) #TODO Check this for error if ran more than once daily
            for l in listing_ids_updated:
                if l in listing_ids:
                    new_listings_to_insert_note_records.append(l)
                    self.logger.debug("listings that need to be inserted to notes {listings}".format(listings=new_listings_to_insert_note_records))
        # This inserts new note records to notes table that have never existed in the notes table
        self.insert_new_note_records(new_listings_to_insert_note_records, 20)

        # This updates existing note records and inserts a new record for those existing records (type 2 dim)
        UpdateNotes().execute()
        self.logger.debug("tracking metrics ran at {time}".format(time=datetime.datetime.now()))

    """util function to pull a note for testing and ad-hoc analysis
        Not used in automated program
    """
    def pull_note_response(self, note_id):
        note_response = self.get_response_note(note_util.get_url_get_request_note(note_id)).json()  # returns just json
        print(note_response)

    def pull_number_of_bid_requests_by_day(self, date):
        select_query = "select count(*) from bid_requests where created_timestamp::date = '{date}';".format(date=date)
        results = self.execute_select(select_query)
        return results[0][0]  # Only one record returned

    def pull_bid_requests_by_day(self, date):
        select_query = "select bid_status, count(*) from bid_requests where created_timestamp::date = '{date}' group by 1;".format(
            date=date)
        results = self.execute_select(select_query)
        return results  # Only one record returned


