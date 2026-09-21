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
                print(response_object['order_status'])
                self.execute_insert_or_update(self.update_order_table_query(response_object['order_id'], response_object['order_status']))

    def update_bid_requests_query(self, order_id, listing_id, bid_status, bid_result):
        return """
        update bid_requests
            set 
                bid_status = '{bid_status}',
                bid_result = '{bid_result}',
                modified_timestamp = '{modified_timestamp}'
            where listing_id = {listing_id} and order_id = '{order_id}';
        """.format(order_id=order_id, bid_status=bid_status, bid_result=bid_result, listing_id=listing_id, modified_timestamp=datetime.datetime.now())

    def get_invested_listing_ids(self, response_object):
        # Read-only: which listing_ids in this order response are INVESTED (no DB writes).
        return [l['listing_id'] for l in response_object['bid_requests'] if l['bid_status'] == 'INVESTED']

    def update_bid_requests_table(self, order_id, response_object):
        listing_ids = []
        for l in response_object['bid_requests']:
            if l['bid_status'] != 'PENDING':
                self.execute_insert_or_update(self.update_bid_requests_query(order_id, l['listing_id'], l['bid_status'], l['bid_result']))
                if l['bid_status'] == 'INVESTED':
                    listing_ids.append(l['listing_id'])
        return listing_ids

    def get_url_get_request_notes(self, offset, limit):
        status_code = 0
        # Re hit api if bad request.
        while status_code != 200:
            response = requests.get("{base_url}/notes/?offset={offset}&limit={limit}&sort_by=origination_date desc".format(base_url=self.config['prosper']['prosper_base_url'], offset=offset, limit=str(limit)), headers=self.header, timeout=30.0)
            status_code = response.status_code
        return response.json()

    def get_response_note(self, https_request):
        response = requests.get(https_request, headers=self.header, timeout=30.0)
        return response

    def insert_note_record(self, response_object, effective_start_date):
        self.execute_insert_or_update(sql_query_utils.insert_notes_query(response_object, effective_start_date, self.logger))

    def fetch_notes_for_listings(self, listing_ids, limit):
        """
        Pages through the Prosper notes API and returns {listing_id: note_object} for every requested
        listing whose note currently EXISTS. Listings whose note has not been created yet by Prosper
        (the known lag between INVESTED and note availability) simply won't appear in the returned map.

        The caller uses this to gate finalization: an order is only finalized when ALL of its INVESTED
        listings' notes are present here. Does NOT write anything.
        """
        remaining = set(listing_ids)
        found = {}
        if not remaining:
            return found
        offset = 0
        response_object = self.get_url_get_request_notes(offset, limit)
        while remaining and response_object.get('result'):
            for l in response_object['result']:
                listing_number = l['listing_number']
                if listing_number in remaining:
                    found[listing_number] = l
                    remaining.discard(listing_number)
            if not remaining:
                break
            offset += limit
            response_object = self.get_url_get_request_notes(offset, limit)
        if remaining:
            self.logger.debug(
                f"Notes not yet available for listings (order will not be finalized this run): {sorted(remaining)}")
        return found

    def insert_new_note_records(self, listing_ids, limit):
        listing_ids.sort(reverse=True)
        offset = 0
        response_object = self.get_url_get_request_notes(offset, limit)
        total_objects = response_object['total_count']
        while len(listing_ids) > 0:
            # print(listing_ids)
            for l in response_object['result']:
                listing_number = l['listing_number']
                if listing_number in listing_ids:
                    self.insert_note_record(l, l['origination_date'])
                    listing_ids.remove(listing_number)
            offset += limit # Preparing for next get request
            response_object = self.get_url_get_request_notes(offset, limit)
            # response_object = requests.get(self.get_url_get_request_notes(offset, limit), headers=self.header, timeout=30.0).json()
            # print(response_object)
            if response_object['result'] is None:
                if len(listing_ids) > 0:
                    self.logger.debug(
                        f"WARNING: these listing_ids were never found in notes API and not inserted: {listing_ids}")
                    #TODO I think there is a bug on Prosper's side where the note does not exist yet even though bid request is "INVESTED"
                    # Testing this here. If it doesn't find it, i should not update the bid_request to invested, need to solve for it.
                    # The bid request and order table updates really should be a transaction included with the notes table stuff and done at the same time,
                    # This way i can check the notes API and not update the orders and bids if the note does not exist yet.
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

    #TODO add error handling!
    #TODO clean this stuff up
    def execute(self):
        # Option 1a (per-order, all-or-nothing): an order is only finalized (order status + bid_requests
        # + note inserts) once ALL of its INVESTED listings that need a NEW note are actually retrievable
        # from Prosper's notes API. Prosper lags between marking a bid INVESTED and creating the note, so
        # finalizing before the note exists silently loses the note (the order/bid drop out of the
        # IN_PROGRESS/PENDING re-scan window). If any required note is missing, we skip ALL writes for
        # that order this run, leaving it IN_PROGRESS/PENDING so the next run retries.
        limit = 20
        order_ids = self.build_order_ids_to_get()  # order_ids that aren't complete
        print(order_ids)
        listing_ids = self.build_pending_listing_ids()  # pending listings (candidates for a NEW note)
        listing_ids_deduped = set(listing_ids)  # dedupe: can have multiple bid requests with same listing

        # ---- Pass 1: read-only. Fetch each order and compute its INVESTED listings. No DB writes. ----
        orders_pending_finalize = []  # (order_id, response_object, invested_listing_ids)
        all_required_note_listings = set()  # union of INVESTED listings needing a new note, across orders
        for order in order_ids:
            status_code = 0
            while status_code != 200:
                # To handle for a problem w/ prosper api.
                order_response = self.get_order_response_by_order_id(order)
                status_code = order_response.status_code
                print(status_code)
            order_response_object = order_response.json()
            print(order_response_object)
            invested_listing_ids = self.get_invested_listing_ids(order_response_object)
            orders_pending_finalize.append((order, order_response_object, invested_listing_ids))
            # Only INVESTED listings that are currently PENDING in bid_requests need a brand-new note.
            all_required_note_listings.update(l for l in invested_listing_ids if l in listing_ids_deduped)

        # ---- Fetch notes once for the union of required listings (no writes). ----
        found_notes = self.fetch_notes_for_listings(all_required_note_listings, limit)

        # ---- Pass 2: writes. Finalize only orders whose required notes are ALL present. ----
        for order, order_response_object, invested_listing_ids in orders_pending_finalize:
            required_notes = {l for l in invested_listing_ids if l in listing_ids_deduped}
            missing = required_notes - set(found_notes.keys())
            if missing:
                self.logger.debug(
                    "Skipping order {order} this run; notes not yet available for {missing} (staying IN_PROGRESS/PENDING)".format(
                        order=order, missing=sorted(missing)))
                continue

            # All required notes are present: finalize the order end-to-end.
            self.update_order_table(order_response_object)
            self.logger.debug("order being updated: {order}".format(order=order))
            listing_ids_updated = self.update_bid_requests_table(order, order_response_object)
            self.logger.debug("lising_ids updated: {listings}".format(listings=listing_ids_updated))
            # Insert the brand-new note records for this order's required listings.
            for l in required_notes:
                note = found_notes[l]
                self.insert_note_record(note, note['origination_date'])
                self.logger.debug("inserted new note for listing {listing}".format(listing=l))

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

    def pull_bid_requests_listing_ids(self, date):
        select_query = "select listing_id from bid_requests where created_timestamp::date = '{date}';".format(
            date=date)
        results = self.execute_select(select_query)
        return results


