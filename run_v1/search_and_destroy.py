import time
import threading
import requests
import sys
from datetime import datetime


import log.logging as logging
import config.default as default

from metrics.sql_metrics import SQLMetrics
from metrics.connect import Connect

"""
This class is to create a single thread per filter that will connect to listing's API AND submit the order via the API when a listing is found
This is created as an attempt to lower the ratio of "EXPRIED" listings that are found (20%)
The thought is since currently listing's is multithreaded, but then order's is submitted as one post request, when Prosper releases listings in batch's my program is held up submitting an order when more listings are posted and missed
The "EXPIRED" listings are almost always very small loans (less than like $4000) which are historically loans I want due to decreased default factor

:param time_to_run_for: The amount of time the thread should continuously search for listings
:type time_to_run_for: int

:param filters_dict: The dictionary that contains the filter_name and the api call
:type filters_dict: dict

:param bid_amt: The amount to invest in a listing. This class may modify this amount if there is not enough available cash
:type bid_amt: float

:param min_run_time: The miniumum time a listing api call should take. This avoids me getting throttled.
:type min_run_time: float
"""


class SearchAndDestroy:


    def __init__(self, order_header, listing_header, time_to_run_for, filters_dict, bid_amt, available_cash, min_run_time):
        self.order_header = order_header
        self.listing_header = listing_header
        self.filters_dict = filters_dict
        self.bid_amt = bid_amt
        self.remaining_cash = available_cash # Renamed variable to avoid confusion as this is being updated with orders
        self.lock = threading.Lock()
        self.min_run_time = min_run_time
        self.logger = logging.create_logger(logger_name="search_and_destroy", log_name="app_run")
        self.time_to_continuously_run_submit_orders = time.time() + time_to_run_for
        self.connect = Connect()

    def listing_logic(self, query, query_get):
        already_invested_listings = self.connect.get_bid_listings() # Takes a fraction of a second, should be ok. Repetitive as submitted_order_listings will handle it, but perfer cutting the listing logic off if not needed
        listings_found = []
        track_filters = {} # For tracking of what filters are finding notes
        i_got_throttled = True # Sometimes get throttled, will run again if throttled
        while i_got_throttled:
            r = requests.get(query_get, headers=self.listing_header, timeout=30.0)
            query_listing = r.json()
            if 'result' in query_listing: # Can get throttled so only execute if get a result
                # if 'result' may be slow
                result_length = len(query_listing['result'])
                if result_length > 0:
                    for i in range(result_length):
                        listing_number = query_listing['result'][i]['listing_number']
                        if listing_number not in already_invested_listings:
                            self.track_filter(track_filters, listing_number,
                                                 query)  # populates track_filters dict to be inserted into psql later
                            if listing_number not in already_invested_listings:
                                listings_found.append(listing_number)
                                logging.log_it_info(self.logger, "filter {query} found listing: {listing} at {current_time}".format(query=query, listing=listing_number, current_time=datetime.now()))

                i_got_throttled = False
            else:
                if 'errors' in query_listing:
                    logging.log_it_info(self.logger, "query {query} got an error, error is: {error}".format(query=query, error=query_listing))
                else:
                    logging.log_it_info(self.logger, "not an errors in response, response is: {response}".format(response=query_listing))
        return listings_found, track_filters

    def order_logic(self, listing_list, bid_amt, filters_used):
        request = {
            "bid_requests": []
        }
        for l in listing_list:
            request['bid_requests'].append({"listing_id": l, "bid_amount": round(bid_amt, 2)})
            # TODO What happens if i get throttled!? Is Prosper API post / get throttled different or the same?? Monitor and modify if need error handling like in listing logic
        response = requests.post(default.config['prosper']['prosper_order_url'], json=request, headers=self.order_header).json()
        logging.log_it_info(self.logger, "request = {request}".format(request=request))
        logging.log_it_info(self.logger, "response = {response}".format(response=response))
        self.handle_order_sql(response, filters_used)

    def thread_worker(self, query, query_get, submitted_order_listings):
        logging.log_it_info(self.logger, "Started running {query} at {time}".format(query=query, time=datetime.now()))
        listing_pings = 0
        order_pings = 0
        while time.time() < self.time_to_continuously_run_submit_orders:
            start_time = time.time()
            listings_found, filters_used = self.listing_logic(query=query, query_get=query_get)
            listing_pings += 1
            if len(listings_found) > 0:
                with self.lock:
                    unique_listings = []
                    for listing in listings_found:
                        if listing not in submitted_order_listings:
                            submitted_order_listings.append(listing)
                            unique_listings.append(listing)
                    listings_to_invest, new_bid_amt, cash_used = self.handle_cash_balance(self.remaining_cash, unique_listings)
                    self.remaining_cash -= cash_used # Will count cash used towards an expired listing. Calculate cash on fly because get cash from prosper api not always quick enough
                if len(listings_to_invest) > 0:
                    logging.log_it_info(self.logger, "Listings to invest at {current_time}: {listings}".format(listings=listings_to_invest, current_time=datetime.now()))
                    self.order_logic(listing_list=listings_to_invest, bid_amt=new_bid_amt, filters_used=filters_used) # Put in order, no need to sleep if order placed since that takes time
                    # BUG Only inserting filters used if order placed... I prefer to have filters inserted if filter found something but overlaps with a previous filter will not insert... This was not a proble with run.py
                    order_pings += 1
                else:
                    self.wait_for_throttle_cap(start_time, self.min_run_time)
            else:
                self.wait_for_throttle_cap(start_time, self.min_run_time)

        self.connect.close_connection()
        logging.log_it_info(self.logger, "Ended running {query} at {time}, with {pings} pings to the listing api, and {order_ping} order pings to the order api".format(query=query, time=datetime.now(), pings=listing_pings, order_ping=order_pings))

    @staticmethod
    def wait_for_throttle_cap(start_time, min_run_time):
        diff = time.time() - start_time
        if diff < min_run_time:
            time.sleep(min_run_time - diff)


    def execute(self):
        threads = []
        submitted_order_listings = []

        for query in self.filters_dict:
            t = threading.Thread(target=self.thread_worker, args=(query, self.filters_dict[query], submitted_order_listings))
            threads.append(t)
            t.start()
        for thread in threads:
            thread.join()

    """
    Utility function to track filters
    track filters looks like:
    {11762017: ['example_query1'], 11636219: ['example_query1'], 11830273: ['example_query1'], 11641319: ['example_query1'], 11642054: ['example_query1'], 11834419: ['example_query1']}
    """

    @staticmethod
    def track_filter(json, listing_id, filter_used):
        if listing_id in json:
            json[listing_id].append(filter_used)
        else:
            json[listing_id] = [filter_used]

    def handle_order_sql(self, response, filters_used_dict):
        # TODO error handling per error code type from prosper
        if "order_id" in response:
            try:
                sql = SQLMetrics()
                sql.run_listing_filters_used(filters_used_dict)  # inserts the filters used into listings_filters_used for tracking
                sql.run_insert_bid_request(response)  # TODO add error handling. Print the error and continue
                sql.run_insert_orders(response)
                sql.close_connection()
            except:  # TODO make specific for now catch all errors
                e = sys.exc_info()[0]
                logging.log_it_info(self.logger, e)
        if 'code' in response:  # Sometimes a listing_id cannot be invested in
            # Example response {'code': 'ORD0019', 'message': 'Listing [10846973] is in status [PENDING_COMPLETION] and cannot currently accept bids.'}
            try:
                listing_string = response['message']
                end_index = listing_string.find("]")
                pending_completion_listing = listing_string[9:end_index]
                sql = SQLMetrics()
                sql.run_insert_bid_request_pending_completion(
                    pending_completion_listing)  # This adds the listing to bid_requests table and therefore will be excluded in the future runs
                logging.log_it_info(self.logger,
                    "Added {listing} to pending_completion_listings list".format(listing=pending_completion_listing))
                sql.close_connection()
            except TypeError as type_error:
                logging.log_it_info(self.logger, "type error: {error}".format(error=type_error))
            except:
                e = sys.exc_info()[0]
                logging.log_it_info(self.logger, e)

    def recalculate_bid_amount(self, cash, listing_list):
        while len(listing_list) > 0:
            listing_list.pop(0)  # Remove an element since this function is only used when aval_amt <= 25 and investment_number > 1. Remove first element, since that index is highest chance of being an expired listing
            aval_bids = cash / 25
            new_listing_length = len(listing_list)
            if aval_bids >= new_listing_length:
                aval_amt = cash / new_listing_length
                return aval_amt, listing_list

    # Add to testing suite
    def handle_cash_balance(self, available_cash, listings_list):
        investment_number = len(listings_list)
        if investment_number == 0: # Handles no listings
            return listings_list, self.bid_amt, 0 # [], self.bid_amt, no cash used
        else:
            new_listing_list = listings_list
            new_amt = self.bid_amt
            aval_amt = available_cash / investment_number
            if available_cash >= 25:  # min bid for a listing
                if aval_amt < self.bid_amt:
                    if aval_amt < available_cash:
                        if aval_amt >= 25:
                            situation_one_msg = "1: {cash} is not enough available cash for desired bid amount of {amt}, for {investment_number} listings, modifying to {new_amt}".format(
                                    cash=available_cash, investment_number=investment_number, amt=self.bid_amt, new_amt=aval_amt)
                            # self.amt = aval_amt
                            new_amt = aval_amt
                            logging.log_it_info(self.logger, situation_one_msg)
                        elif aval_amt <= 25 and investment_number > 1:
                            new_amt, new_listing_list = self.recalculate_bid_amount(cash=available_cash, listing_list=listings_list)
                            situation_two_msg = "2: {cash} is not enough available cash for desired bid amount of {amt}, for {investment_number}  listings, modifying to bids of {new_amt} for {listing_num} listings".format(
                                    cash=available_cash, investment_number=investment_number, amt=self.bid_amt, new_amt=new_amt,
                                    listing_num=len(new_listing_list))
                            logging.log_it_info(self.logger, situation_two_msg)
                            # self.amt = new_bid_amt
                            # self.listings_list = new_listing_list

                else:
                    normal_op_msg = f"available_cash of {available_cash} is enough for normal bidding submission"
                    logging.log_it_info(self.logger, normal_op_msg)

            else:
                situation_three_msg = "Your available cash of {cash} is not enough to invest in anything... Wow dude".format(cash=available_cash)
                logging.log_it_info(self.logger, situation_three_msg)
                new_listing_list = []
                # self.listings_list = []
            return new_listing_list, new_amt, len(new_listing_list) * new_amt # May be the same as original