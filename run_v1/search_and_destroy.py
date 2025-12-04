import time
import threading
import requests
import sys
from datetime import datetime


import log.logging as logging
import config.default as default
import filters.filters as filters

from metrics.sql_metrics import SQLMetrics
from metrics.connect import Connect
from run_v1.max_requests_queue import MaxRequestsQueue

"""
This class is to create a single thread per filter that will connect to listing's API AND submit the order via the API when a listing is found
This is created as an attempt to lower the ratio of "EXPRIED" listings that are found (20%)
The thought is since currently listing's is multithreaded, but then order's is submitted as one post request, when Prosper releases listings in batch's my program is held up submitting an order when more listings are posted and missed
The "EXPIRED" listings are almost always very small loans (less than like $4000) which are historically loans I want due to decreased default factor

:param time_to_run_for: The amount of time the thread should continuously search for listings
:type time_to_run_for: int

:param filters_dict: The dictionary that contains the filter_name and the api call
:type filters_dict: dict

:param bid_amt: The amount to invest in a listing BY prosper rating. This class may modify this amount if there is not enough available cash
:type bid_amt: dict

:param min_run_time: The miniumum time a listing api call should take. This avoids me getting throttled.
:type min_run_time: float
"""


class SearchAndDestroy:


    def __init__(self, order_header, listing_header, time_to_run_for, max_request_per_second, filters_dict, bid_amt, available_cash, dry_run):
        self.order_header = order_header
        self.listing_header = listing_header
        self.filters_dict = filters_dict
        self.bid_amt = bid_amt
        self.available_cash = available_cash
        self.lock = threading.Lock()
        self.logger = logging.create_logger(logger_name="search_and_destroy", log_name="app_run")
        self.time_to_run_for = time_to_run_for
        self.time_to_continuously_run_submit_orders = time.time() + time_to_run_for
        self.connect = Connect()
        self.max_request_per_second = max_request_per_second # Prosper says its 20, but they have a bug sometimes
        self.wait_time_between_runs = 1 / max_request_per_second # To allow for equal sending over the second
        self.dry_run = dry_run
        self.wait_time_between_runs = 1 / self.max_request_per_second

    def listing_logic(self, query, query_get):
        already_invested_listings = self.connect.get_bid_listings() # Takes a fraction of a second, should be ok. Repetitive as submitted_order_listings will handle it, but perfer cutting the listing logic off if not needed
        listings_found = []
        throttled_count = 0 # Bad variable name, should be like error count. (sometimes prosper API errors and i want to ignore and re-run)
        track_filters = {} # For tracking of what filters are finding notes
        i_got_throttled = True # Sometimes get throttled, will run again if throttled
        while i_got_throttled:
            the_time = time.time()
            r = requests.get(query_get, headers=self.listing_header, timeout=30.0)
            print(f"{query} Hit API Listings at {the_time}") # For Testing
            header_json = r.headers
            if 'Retry-After' in header_json:
                # There is a bug in prosper API, it is supposed to allow 20 requests to listing api per second.
                # But sometimes they mess this up and it throttles me even though i dont send more than 20 a second.
                print("THROTTLED")
                logging.log_it_info(self.logger, "I have been Throttled by prosper API bug")
                raise Exception("Throttled by Listing API")
            query_listing = r.json()
            if 'result' in query_listing: # Can get throttled so only execute if get a result
                # if 'result' may be slow
                result_length = len(query_listing['result'])
                if result_length > 0:
                    # Handle normal non-looking further into credit_bureau_values_transunion
                    if query not in filters.transunion_add_on_filters:
                        if result_length > 0:
                            for i in range(result_length):
                                listing_number = query_listing['result'][i]['listing_number']
                                prosper_rating = query_listing['result'][i]['prosper_rating']
                                if listing_number not in already_invested_listings:
                                    self.track_filter(track_filters, listing_number,
                                                         query, prosper_rating)  # populates track_filters dict to be inserted into psql later
                                    if listing_number not in already_invested_listings:
                                        listings_found.append({"listing_number": listing_number, "prosper_rating": prosper_rating, "query": query})
                                        logging.log_it_info(self.logger, "filter {query} found listing: {listing} with prosper rating: {prosper_rating} at {current_time}".format(query=query, listing=listing_number, prosper_rating=prosper_rating, current_time=datetime.now()))

                    # i_got_throttled = False
                    # Logic for credit_bureau_values_transunion data only
                    # if query in filters.transunion_add_on_filters key
                    elif query in filters.transunion_add_on_filters:
                        listings_found_dict = self.handle_creditdata_query(query_listing, query)
                        if len(listings_found_dict) > 0:
                            for k, v in listings_found_dict.items():
                                listing_number = k
                                prosper_rating = v
                                if listing_number not in already_invested_listings:
                                    self.track_filter(track_filters, listing_number,
                                                      query,
                                                      prosper_rating)  # populates track_filters dict to be inserted into psql later
                                    if listing_number not in already_invested_listings:
                                        listings_found.append(
                                            {"listing_number": listing_number, "prosper_rating": prosper_rating, "query": query})
                                        logging.log_it_info(self.logger,
                                                            "filter {query} found listing: {listing} with prosper rating: {prosper_rating} at {current_time}".format(
                                                                query=query, listing=listing_number,
                                                                prosper_rating=prosper_rating, current_time=datetime.now()))

                i_got_throttled = False

            else:
                if 'errors' in query_listing:
                    logging.log_it_info(self.logger, "query {query} got an error, error is: {error}".format(query=query, error=query_listing))
                    throttled_count += 1
                else:
                    logging.log_it_info(self.logger, "not an errors in response, response is: {response}".format(response=query_listing))
        return listings_found, track_filters, throttled_count

    """
    listings_list = [{"listing_number": 12470793, "prosper_rating": 'A'}, {"listing_number": 12259421, "prosper_rating": 'A'}]
    """
    def order_logic(self, listing_list, bid_amt, filters_used):

        request = {
            "bid_requests": []
        }

        for l in listing_list:
            # lookup bid amt by rating
            bid_amount = bid_amt[l['prosper_rating']]
            request['bid_requests'].append({"listing_id": l['listing_number'], "bid_amount": bid_amount})
        # I think will get throttled if over 20 posts to api in one second (I'll never get this issue)

        try:
            response = requests.post(default.config['prosper']['prosper_order_url'], json=request, headers=self.order_header, timeout=30)
            response_json = response.json()
            logging.log_it_info(self.logger, "request = {request}".format(request=request))
            logging.log_it_info(self.logger, "response = {response}".format(response=response_json))
            self.handle_order_sql(response_json, filters_used)
        except:
            # except requests.exceptions.Timeout:
            e = sys.exc_info()[0]
            logging.log_it_info("Order error hit")
            logging.log_it_info(self.logger, e)
            time.sleep(5) # Assuming its the timeout error and don't need this sleep
            # Sleep for 5 seconds and post again...
            #TODO clean this up
            # For now see what kind of exceptions i get so i can properly address this
            # The issue is prosper crashes or timesout or something, somtimes. May want to implement a loop instead of one except
            logging.log_it_info("Trying order again")
            response = requests.post(default.config['prosper']['prosper_order_url'], json=request, headers=self.order_header, timeout=30)
            response_json = response.json()
            logging.log_it_info(self.logger, "request = {request}".format(request=request))
            logging.log_it_info(self.logger, "response = {response}".format(response=response_json))
            self.handle_order_sql(response_json, filters_used)

    def thread_worker(self, query, query_get, submitted_order_listings, run_dict, filter_queue):
        logging.log_it_info(self.logger, "Started running {query} at {time}".format(query=query, time=datetime.now()))
        listing_pings = 0
        order_pings = 0
        total_throttle_count = 0
        while time.time() < self.time_to_continuously_run_submit_orders:
            # This lock enforces max amount of listing requests that can be sent per second
            run_listing = False
            with self.lock:
                current_time_in_milli = time.time()
                current_time_in_seconds = int(current_time_in_milli)
                if run_dict[current_time_in_seconds]["allowed_remaining_runs"] > 0 and current_time_in_milli > run_dict[current_time_in_seconds]["latest_run_time"] and query == filter_queue[0]:
                    run_dict[current_time_in_seconds]["allowed_remaining_runs"] -= 1
                    run_dict[current_time_in_seconds]["latest_run_time"] = current_time_in_milli + self.wait_time_between_runs  # + wait_time_between_runs to allow for equal running
                    filter_queue.pop(0) # Remove from the first position
                    filter_queue.append(query) # Add to the back of the queue
                    run_listing = True

            if run_listing:
                # Submit listing request
                listings_found, filters_used, throttle_count = self.listing_logic(query=query, query_get=query_get)

                listing_pings += 1
                total_throttle_count += throttle_count
                if len(listings_found) > 0:
                    # This lock enforces no duplication on ordering when a listing is found, and aval cash is updated amongst all workers
                    with self.lock:
                        unique_listings = []
                        for listing in listings_found:
                            if listing['listing_number'] not in submitted_order_listings:
                                submitted_order_listings.append(listing['listing_number'])
                                unique_listings.append(listing)
                        listings_to_invest, new_bid_amt, new_remaining_cash = self.handle_cash_balance(logger=self.logger,available_cash=self.available_cash, bid_amt=self.bid_amt, listings_list=unique_listings)
                        self.available_cash = new_remaining_cash

                    if len(listings_to_invest) > 0:
                        logging.log_it_info(self.logger, "Listings to invest at {current_time}: {listings}".format(listings=listings_to_invest, current_time=datetime.now()))
                        if self.dry_run:
                            logging.log_it_info(self.logger, "DRY RUN IS ON. No order being placed")
                            logging.log_it_info(self.logger, "DRYRUN. This msg just for show: Listings invested at {current_time}: {listings}".format(current_time=datetime.now(), listings=listings_to_invest))

                        else:
                            self.order_logic(listing_list=listings_to_invest, bid_amt=new_bid_amt, filters_used=filters_used) # Put in order, no need to sleep if order placed since that takes time
                            logging.log_it_info(self.logger, "Listings invested at {current_time}: {listings}".format(current_time=datetime.now(), listings=listings_to_invest))
            #             # BUG (acceptable bug) Only inserting filters used if order placed... I prefer to have filters inserted if filter found something but overlaps with a previous filter will not insert...
                        order_pings += 1

        self.connect.close_connection()
        logging.log_it_info(self.logger, "Ended running {query} at {time}, with {pings} pings to the listing api, and {order_ping} order pings to the order api, and ignored {throttle_count} throttles from api".format(query=query, time=datetime.now(), pings=listing_pings, order_ping=order_pings, throttle_count=total_throttle_count))

    def execute(self):
        threads = []
        submitted_order_listings = []
        m = MaxRequestsQueue(max_request_per_second=self.max_request_per_second, filter_dict=self.filters_dict, time_to_run_for=self.time_to_run_for)
        run_allowance_dict = m.build_allowed_run_dict()
        run_list_queue = m.build_starting_filter_queue()

        for query in self.filters_dict:
            t = threading.Thread(target=self.thread_worker, args=(query, self.filters_dict[query], submitted_order_listings, run_allowance_dict, run_list_queue))
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
    def track_filter(json, listing_id, filter_used, prosper_rating):
        if listing_id in json:
            json[listing_id][0].append(filter_used)
            json[listing_id][1].append(prosper_rating)
        else:
            json[listing_id] = [filter_used], [prosper_rating]

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

    """
    RETURNS possibly modified listings_list if cash is not enough for all bid submissions, along with a modified bid_amt dict
        Possible situations
        # Less than $25, cant do anything (min $25 bid per note)
        # More than total desired bid amt in cash; operate as normal
        # Not enough for normal bids but more than $25 cash:
            # enough for at least $25 per bid and just total cash / num listings to invest in
            # Not Enough for at least $25 per bid and must drop bid/s
        # BUG (Acceptable Bug): If a listing gets submitted, but it comes back expired, it will not add that cash back to available cash.
        # The result of this bug is the available_cash variable created per run can be incorrectly lower like a bid was placed when it wasn't
        # Sparknotes: It doesn't invest all of the cash, but its not a big deal. It will do so on next run
    """
    @staticmethod
    def handle_cash_balance(logger, available_cash, bid_amt, listings_list):
        investment_number = len(listings_list)
        if investment_number == 0:  # Handles no listings
            return listings_list, bid_amt, available_cash  # [], self.bid_amt, no cash used

        else:
            desired_total_bid_amt = 0
            for l in listings_list:
                query = l['prosper_rating']['query'] #TODO Verify the other possiblites still work. Somehow my PR with this was lost and lost on local. Did this quickly, may have missed something.
                desired_total_bid_amt += bid_amt[l['prosper_rating']][query]
        if available_cash < 25:
            logging.log_it_info(logger,
                                f"Current cash of {available_cash} not enough cash for any bids... LOSER")
            return [], bid_amt, available_cash
        if available_cash >= desired_total_bid_amt:
            logging.log_it_info(logger,
                                f"Current cash of {available_cash} is enough for normal operation")
            return listings_list, bid_amt, available_cash - desired_total_bid_amt
        if available_cash >= 25 and available_cash <= desired_total_bid_amt:
            logging.log_it_info(logger,
                                f"Current cash of {available_cash} is not enough for normal operation for {investment_number} bids")
            available_per_bid = round(available_cash / investment_number, 2)
            new_total_bid_amt = available_per_bid * investment_number
            if available_per_bid >= 25:
                for v in bid_amt:
                    bid_amt[v] = available_per_bid
                situation_one_msg = "Current cash of {cash} is not enough available cash for desired bid amount, for {investment_number} listings, but enough for submit bids on all listings, modifying to {new_amt}".format(
                                                    cash=available_cash, investment_number=investment_number, new_amt=bid_amt)
                logging.log_it_info(logger, situation_one_msg)
                return listings_list, bid_amt, available_cash - new_total_bid_amt
            else:
                logging.log_it_info(logger,
                                    f"Current cash of {available_cash} is not enough cash for desired bid amount for {investment_number} listings, AND not enough for all bids, dropping bid")
                while (available_per_bid < 25):
                    logging.log_it_info(logger, "Dropping listing {listing}".format(listing=listings_list[0]))
                    listings_list.pop(0)
                    available_per_bid = round(available_cash / len(listings_list), 2)
                new_total_bid_amt = available_per_bid * len(listings_list)
                for v in bid_amt:
                    bid_amt[v] = available_per_bid
                return listings_list, bid_amt, available_cash - new_total_bid_amt

    """
    Alright, now we get confusing. Today is 12/3/25. I'm adding in the ability to query in depth Transunion data. Some Transunion data is indexed and included in the API response.
    But most of the Transunion data is not.
    This is kind of a bandaid fix to allow for this type of querying, I dont love it; but i dont want to do a full rewrite.
    This will require a dict in the filters/filter.py that adds in the additional filtering not doable straight in the API request. 
    query_listing looks like 
    {}
    """
    @staticmethod
    def handle_creditdata_query(query_listing, query):
        result_length = len(query_listing['result'])
        listings_found_dict = {}
        criteria_count = len(filters.transunion_add_on_filters[query])
        for i in range(result_length):
            criteria_hit = 0
            for x in filters.transunion_add_on_filters[query]:
                credit_bureau_value = x['credit_bureau_value']
                min_or_max_value = x['min_or_max_value']
                # credit_bureau_value = transunion_add_on_filters[query]['credit_bureau_value']
                # min_or_max_value = transunion_add_on_filters[query]['min_or_max_value']
                if x['min_or_max'] == 'min':
                    if query_listing['result'][i]['credit_bureau_values_transunion'][
                        credit_bureau_value] >= min_or_max_value:
                        criteria_hit += 1
                        listing_number = query_listing['result'][i]['listing_number']
                        prosper_rating = query_listing['result'][i]['prosper_rating']
                        if criteria_hit == criteria_count:
                            listings_found_dict[listing_number] = prosper_rating
                elif x['min_or_max'] == 'max':
                    if query_listing['result'][i]['credit_bureau_values_transunion'][
                        credit_bureau_value] <= min_or_max_value:
                        criteria_hit += 1
                        listing_number = query_listing['result'][i]['listing_number']
                        prosper_rating = query_listing['result'][i]['prosper_rating']
                        if criteria_hit == criteria_count:
                            listings_found_dict[listing_number] = prosper_rating
        return listings_found_dict



