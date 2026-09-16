import copy
import math
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

    def __init__(self, order_header, listing_header, time_to_run_for, max_request_per_second, filters_dict, bid_amt, available_cash, dry_run, overlap_extra_bid_amt):
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
        self.overlap_extra_bid_amt = overlap_extra_bid_amt
        self.wait_time_between_runs = 1 / self.max_request_per_second

    def listing_logic(self, query, query_get, bid_amt, submitted_order_listings_desired, submitted_order_listings_filters):
        already_invested_listings = self.connect.get_bid_listings_with_bid_amount() # Takes a fraction of a second, should be ok. Repetitive as submitted_order_listings will handle it, but perfer cutting the listing logic off if not needed
        # Frozen snapshot for this call, indexed for O(1) membership + amount lookups (built once, not per listing).
        invested_by_id = {d["listing_number"]: d["bidded_amount"] for d in already_invested_listings}
        listings_found = []
        throttled_count = 0 # Bad variable name, should be like error count. (sometimes prosper API errors and i want to ignore and re-run)
        track_filters = {} # For tracking of what filters are finding notes
        i_got_throttled = True # Sometimes get throttled, will run again if throttled
        while i_got_throttled:
            the_time = time.time()
            r = requests.get(query_get, headers=self.listing_header, timeout=30.0)
            # print(f"{query} Hit API Listings at {datetime.now()}") # For Testing
            # logging.log_it_info(self.logger, f"{query} Hit API Listings at {datetime.now()}") # For testing
            status_code = r.status_code
            # Entering the valley of if statements...Clean this up.
            # Check for a valid 200 status code.
            if status_code == 200:
                # logging.log_it_info(self.logger, f"{query} Hit API Listings at {the_time}")
                header_json = r.headers
                if 'Retry-After' in header_json:
                    # There is a bug in prosper API, it is supposed to allow 20 requests to listing api per second.
                    # But sometimes they mess this up and it throttles me even though i dont send more than 20 a second.
                    print("THROTTLED")
                    logging.log_it_info(self.logger, "I have been Throttled by prosper API bug")
                    raise Exception("Throttled by Listing API")
                try:
                    query_listing = r.json()
                except ValueError as e:
                    print(e)
                    # print(r.status_code)
                    logging.log_it_info(self.logger, f"VALUE ERROR: {e}")
                    # This is where it seems we get hit if the API throttles.
                if 'result' in query_listing: # Can get throttled so only execute if get a result
                    # if 'result' may be slow
                    result_length = len(query_listing['result'])
                    if result_length > 0:
                        # Handle normal non-looking further into credit_bureau_values_transunion
                        if query not in filters.transunion_add_on_filters:
                            for i in range(result_length):
                                if 'occupation' in query_listing['result'][i]:  # Really dirty band-aid way to ignore no occupation.
                                    #TODO Add in error logic for key error.
                                    listing_number = query_listing['result'][i]['listing_number']
                                    prosper_rating = query_listing['result'][i]['prosper_rating']
                                    listing_amount = query_listing['result'][i]['listing_amount']
                                    max_bid_amt = math.floor(listing_amount * .1)
                                    amt_to_bid = bid_amt[prosper_rating][query]
                                    if max_bid_amt < amt_to_bid:
                                        amt_to_bid = max_bid_amt

                                    # Checks to verify this listing wasn't already invested in.
                                    # With a lot of overlap between filters, it would be nice to check to see if when a listing was already invested,
                                    # if it was a smaller bid_amt to add another order to the amt of this filter since many times it can be larger. This would require a good amount of re-work though.

                                    if listing_number not in invested_by_id:
                                        self.track_filter(track_filters, listing_number,
                                                             query, prosper_rating)  # populates track_filters dict to be inserted into psql later
                                        listings_found.append(
                                            {"listing_number": listing_number, "prosper_rating": prosper_rating,
                                             "query": query, "max_bid_amt": max_bid_amt})
                                        logging.log_it_info(self.logger, "filter {query} found listing: {listing} with prosper rating: {prosper_rating} at {current_time}".format(query=query, listing=listing_number, prosper_rating=prosper_rating, current_time=datetime.now()))
                                    elif listing_number in invested_by_id:  # if listing_number has already been bidded.
                                        already_invested_amount = invested_by_id.get(listing_number)
                                        # Target-aware surfacing. The +bonus is earned once a listing has 2+ DISTINCT
                                        # filters (including this one); a single filter re-finding its own listing does not
                                        # earn it and only tops up toward its own desired (i.e. if earlier bid was 10%-clamped).
                                        # thread_worker is the authoritative dedup/sizing; this gate just avoids blocking real top-ups.
                                        distinct_filters = set(submitted_order_listings_filters.get(listing_number, [])) | {query}
                                        has_multiple_filters = len(distinct_filters) >= 2
                                        highest_desired = max(bid_amt[prosper_rating][query], submitted_order_listings_desired.get(listing_number, 0))
                                        target_total = self.overlap_target(has_multiple_filters, bid_amt[prosper_rating][query], highest_desired, self.overlap_extra_bid_amt)
                                        if self.should_surface_invested_listing(already_invested_amount, target_total):
                                            logging.log_it_info(self.logger, f"*Listing Logic Method* Another filter: {query} found listing: {listing_number}, room toward target; already invested {already_invested_amount}, highest desired {highest_desired}")
                                            self.track_filter(track_filters, listing_number,
                                                              query,
                                                              prosper_rating)  # populates track_filters dict to be inserted into psql later
                                            listings_found.append(
                                                {"listing_number": listing_number, "prosper_rating": prosper_rating,
                                                 "query": query, "max_bid_amt": max_bid_amt})
                                            logging.log_it_info(self.logger,
                                                                "filter {query} found listing: {listing} with prosper rating: {prosper_rating} at {current_time}".format(
                                                                    query=query, listing=listing_number,
                                                                    prosper_rating=prosper_rating,
                                                                    current_time=datetime.now()))
                                # else:
                                #     logging.log_it_info(self.logger, f"WARNING; blocking bid occupation key does not exist")


                        # i_got_throttled = False
                        # Logic for credit_bureau_values_transunion data only
                        # if query in filters.transunion_add_on_filters key
                        elif query in filters.transunion_add_on_filters:
                            # logging.log_it_info(self.logger, "include transunion hit")  # Testing
                            listings_found_dict, listings_found_dict_listing_amt = self.handle_creditdata_query(query_listing, query)
                            if len(listings_found_dict) > 0:
                                for k, v in listings_found_dict.items():
                                    listing_number = k
                                    prosper_rating = v
                                    listing_amount = listings_found_dict_listing_amt[listing_number]
                                    max_bid_amt = math.floor(listing_amount * .1)
                                    amt_to_bid = bid_amt[prosper_rating][query]
                                    if max_bid_amt < amt_to_bid:
                                        amt_to_bid = max_bid_amt

                                    if listing_number not in invested_by_id:
                                        self.track_filter(track_filters, listing_number,
                                                          query,
                                                          prosper_rating)  # populates track_filters dict to be inserted into psql later
                                        listings_found.append(
                                            {"listing_number": listing_number, "prosper_rating": prosper_rating,
                                             "query": query, "max_bid_amt": max_bid_amt})
                                        logging.log_it_info(self.logger,
                                                            "filter {query} found listing: {listing} with prosper rating: {prosper_rating} at {current_time}".format(
                                                                query=query, listing=listing_number,
                                                                prosper_rating=prosper_rating, current_time=datetime.now()))
                                    elif listing_number in invested_by_id:  # if listing_number has already been bidded.
                                        already_invested_amount = invested_by_id.get(listing_number)
                                        # Target-aware surfacing (see normal path above for rationale).
                                        distinct_filters = set(submitted_order_listings_filters.get(listing_number, [])) | {query}
                                        has_multiple_filters = len(distinct_filters) >= 2
                                        highest_desired = max(bid_amt[prosper_rating][query], submitted_order_listings_desired.get(listing_number, 0))
                                        target_total = self.overlap_target(has_multiple_filters, bid_amt[prosper_rating][query], highest_desired, self.overlap_extra_bid_amt)
                                        if self.should_surface_invested_listing(already_invested_amount, target_total):
                                            logging.log_it_info(self.logger,
                                                                f"*Listing Logic Method* Another filter: {query} found listing: {listing_number}, room toward target; already invested {already_invested_amount}, highest desired {highest_desired}")
                                            self.track_filter(track_filters, listing_number,
                                                              query,
                                                              prosper_rating)  # populates track_filters dict to be inserted into psql later
                                            listings_found.append(
                                                {"listing_number": listing_number, "prosper_rating": prosper_rating,
                                                 "query": query, "max_bid_amt": max_bid_amt})
                                            logging.log_it_info(self.logger,
                                                                "filter {query} found listing: {listing} with prosper rating: {prosper_rating} at {current_time}".format(
                                                                    query=query, listing=listing_number,
                                                                    prosper_rating=prosper_rating,
                                                                    current_time=datetime.now()))

                    i_got_throttled = False

                else:
                    if 'errors' in query_listing:
                        logging.log_it_info(self.logger, "query {query} got an error, error is: {error}".format(query=query, error=query_listing))
                        throttled_count += 1
                    else:
                        logging.log_it_info(self.logger, "not an errors in response, response is: {response}".format(response=query_listing))
            else:
                print(f"status code is {status_code}, not 200. Sleeping for 2 seconds.")
                logging.log_it_info(self.logger, f"status code is {status_code}, not 200. Sleeping for 2 seconds.")
                time.sleep(2)
        return listings_found, track_filters, throttled_count

    """
    listings_list = [{"listing_number": 12470793, "prosper_rating": 'A'}, {"listing_number": 12259421, "prosper_rating": 'A'}]
    """
    def order_logic(self, listing_list, bid_amt, filters_used):

        request = {
            "bid_requests": []
        }

        for l in listing_list:
            bid_amount = l['bid_amount']
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

    def thread_worker(self, query, query_get, submitted_order_listings, submitted_order_listings_filters, submitted_order_listings_desired, run_dict, filter_queue):
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
                # Check if this filter is next in queue and we have capacity this second
                if run_dict[current_time_in_seconds]["allowed_remaining_runs"] > 0 and query == filter_queue[0]:
                    # Only check latest_run_time if it's been set (not 0)
                    if run_dict[current_time_in_seconds]["latest_run_time"] == 0 or current_time_in_milli >= run_dict[current_time_in_seconds]["latest_run_time"]:
                        run_dict[current_time_in_seconds]["allowed_remaining_runs"] -= 1
                        run_dict[current_time_in_seconds]["latest_run_time"] = current_time_in_milli + self.wait_time_between_runs  # + wait_time_between_runs to allow for equal running
                        filter_queue.popleft()  # O(1) operation with deque
                        filter_queue.append(query)  # Add to the back of the queue
                        run_listing = True

            if run_listing:
                # Submit listing request
                listings_found, filters_used, throttle_count = self.listing_logic(query=query, query_get=query_get, bid_amt=self.bid_amt, submitted_order_listings_desired=submitted_order_listings_desired, submitted_order_listings_filters=submitted_order_listings_filters) # pass back max bid amt

                listing_pings += 1
                total_throttle_count += throttle_count
                if len(listings_found) > 0:
                    # This lock enforces no duplication on ordering when a listing is found, and aval cash is updated amongst all workers
                    with self.lock:
                        overlap_bid_amt = copy.deepcopy(self.bid_amt)  # To make the bid dict unique everytime to account for rare bug if the same proper rating filter finds multiple lsitings, the bid amt dict needs to not be modified. 
                        unique_listings = []
                        for listing in listings_found:
                            listing_number = listing['listing_number']
                            rating = listing['prosper_rating']
                            max_bid_allowed = listing['max_bid_amt']
                            configured_desired_bid_amt = overlap_bid_amt[rating][query]  # This filter's desired amount BEFORE the 10%-per-bid clamp. Used to track highest demand across filters.
                            desired_bid_amt = overlap_bid_amt[rating][query]
                            if desired_bid_amt > max_bid_allowed: # if my bid is more than 10% of listing amount.
                                overlap_bid_amt[rating][query] = max_bid_allowed
                                desired_bid_amt = max_bid_allowed
                                logging.log_it_info(self.logger, f"listing {listing_number} with filter {query}, with bid amt of: {desired_bid_amt}, is too large for listing, changed to max of {max_bid_allowed}")
                            # Find if the dictionary with this key already exists in the list
                            existing = next((d for d in submitted_order_listings if listing_number in d), None)
                            if existing:
                                # Track the highest configured (pre-clamp) demand seen for this listing across all filters.
                                # The 10% cap is per-bid only (Option B), so overlaps fill the gap between what's already bid
                                # and the highest desired amount, rather than measuring against this filter's own (often smaller) config.
                                highest_desired = max(submitted_order_listings_desired.get(listing_number, 0), configured_desired_bid_amt)
                                submitted_order_listings_desired[listing_number] = highest_desired
                                # The +bonus is earned once a listing has 2+ DISTINCT filters (including this one).
                                # A single filter re-finding its own listing never earns it.
                                distinct_filters = set(submitted_order_listings_filters[listing_number]) | {query}
                                has_multiple_filters = len(distinct_filters) >= 2
                                target_total = self.overlap_target(has_multiple_filters, configured_desired_bid_amt, highest_desired, self.overlap_extra_bid_amt)
                                target_total, bid_amt_diff = self.compute_overlap_bid(
                                    target_total=target_total,
                                    already_bid=existing[listing_number],
                                    max_bid_allowed=max_bid_allowed)
                                # Bid only if there is still room to the (filter-appropriate) target.
                                if bid_amt_diff > 0:
                                    logging.log_it_info(self.logger, f"listing {listing_number} already ordered on")
                                    if bid_amt_diff >= 25:  # 25 min order amt; anything under 25 is skipped (never submitted).
                                        logging.log_it_info(self.logger, f"OVERLAP; listing {listing_number} already ordered on, topping up by {bid_amt_diff} toward target total of {target_total} (currently {existing[listing_number]})")
                                        existing[listing_number] += bid_amt_diff  # Handle cash balance can introude bug..
                                        if query not in submitted_order_listings_filters[listing_number]:
                                            submitted_order_listings_filters[listing_number].append(query)
                                        overlap_bid_amt[rating][query] = bid_amt_diff  # Replaces existing bid_amt dict with the new amount to bid based on overlap
                                        listing['bid_amount'] = bid_amt_diff
                                        unique_listings.append(listing)

                            else:
                                submitted_order_listings.append({listing_number: desired_bid_amt})  # Add if new
                                submitted_order_listings_filters[listing_number] = [query] # Add if new, this is a dict, List for filter tracking since multiple.
                                submitted_order_listings_desired[listing_number] = configured_desired_bid_amt  # Track highest desired (pre-clamp) so later overlaps can fill remaining demand toward it
                                listing['bid_amount'] = desired_bid_amt
                                unique_listings.append(listing)
                        listings_to_invest, new_bid_amt, new_remaining_cash = self.handle_cash_balance(logger=self.logger,available_cash=self.available_cash, bid_amt=overlap_bid_amt, listings_list=unique_listings)
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
            else:
                # Reduce lock contention by sleeping briefly when we can't run
                # This prevents busy-waiting and allows other threads to acquire the lock
                time.sleep(0.001)  # 1ms sleep - small enough to not impact throughput

        self.connect.close_connection()
        logging.log_it_info(self.logger, "Ended running {query} at {time}, with {pings} pings to the listing api, and {order_ping} order pings to the order api, and ignored {throttle_count} throttles from api".format(query=query, time=datetime.now(), pings=listing_pings, order_ping=order_pings, throttle_count=total_throttle_count))

    """
    If a filter is overlapped w/ another filter that means all those criteria apply.
    We know these filters have a much lower default rate, ie; an average filter with another slighty better filter is now much stronger and deserves a larger bid amt higher than simply the better filter that found it.
    To avoid pre calculating all the different possibilities, and the expensive search that would require when time is of the essence.
    Simply add a pre determined extra bid amt to add.
    """
    def determine_overlap(self, bid_amt, max_bid_amt):
        if bid_amt != max_bid_amt:  # Check if already using max bid.
            bid_amt += self.overlap_extra_bid_amt
            if bid_amt > max_bid_amt and (max_bid_amt - bid_amt) < 25:
                bid_amt = max_bid_amt
            else:
                bid_amt = max_bid_amt - bid_amt
        return bid_amt
    def execute(self):
        threads = []
        # Seed tracking dicts from the DB so a restart continues from prior-run bids (7-day window)
        # rather than re-bidding already-invested listings in full.
        submitted_order_listings, submitted_order_listings_filters, submitted_order_listings_desired = self.seed_from_db()
        logging.log_it_info(self.logger, "Seeded {n} previously-bid listings from DB at startup".format(n=len(submitted_order_listings)))
        m = MaxRequestsQueue(max_request_per_second=self.max_request_per_second, filter_dict=self.filters_dict, time_to_run_for=self.time_to_run_for)
        run_allowance_dict = m.build_allowed_run_dict()
        run_list_queue = m.build_starting_filter_queue()

        for query in self.filters_dict:
            t = threading.Thread(target=self.thread_worker, args=(query, self.filters_dict[query], submitted_order_listings, submitted_order_listings_filters, submitted_order_listings_desired, run_allowance_dict, run_list_queue))
            threads.append(t)
            t.start()
        for thread in threads:
            thread.join()

    """
    Pure bid-sizing helper for the overlap case (listing already bid on by another/same filter).

    Model (Option 1): the total invested in a single listing converges to
        target_total = highest_desired + overlap_extra_bid_amt
    where highest_desired is the largest configured (pre-10%-clamp) bid amt across all
    filters that matched the listing. The overlap bonus is part of the target (added once),
    NOT per bid, so repeated top-up bids across successive filter arrivals converge to the
    same total regardless of the order filters find the listing.

    Each individual bid is capped at max_bid_allowed (the per-bid 10% rule); when the gap to
    the target exceeds one bid, later arrivals close the remainder.

    Returns (target_total, bid_amt_diff) where bid_amt_diff is the amount to top up by on THIS
    bid (capped, and never negative). The caller still enforces the $25 minimum before placing.
    """
    @staticmethod
    def compute_overlap_bid(target_total, already_bid, max_bid_allowed):
        bid_amt_diff = target_total - already_bid
        if bid_amt_diff < 0:
            bid_amt_diff = 0  # already at/above target; nothing to add
        if bid_amt_diff > max_bid_allowed:
            bid_amt_diff = max_bid_allowed  # per-bid 10% cap; remaining gap closed by later arrivals
        return target_total, bid_amt_diff

    """
    Computes the effective target total for a listing that has already been bid on.

    The overlap bonus is a CROSS-FILTER signal, earned only once a listing has been matched by 2+
    DISTINCT filters (more distinct filters == higher conviction). The deciding state is whether the
    listing has ever had multiple distinct filters, NOT whether this specific re-find is a new filter.
    This resolves two requirements together:
      - A single filter re-finding its own listing never conjures a bonus (target = its own desired),
        so it only bids again to finish reaching its own desired amount (i.e. when its earlier bid was
        clamped by the per-bid 10% cap). If already at its desired, nothing more is placed.
      - Once a genuine cross-filter overlap has occurred, the listing has a FIXED target of
        highest_desired + bonus, and any filter (including ones that already bid) may top up toward it
        on later polls. This keeps the total order-independent and lets a gap larger than one 10%-capped
        bid converge across multiple polls.

    :param has_multiple_filters: True if 2+ distinct filters have matched this listing
    :param this_filter_desired: this filter's own configured desire (pre-10%-clamp)
    :param highest_desired: highest configured desire across all filters that matched the listing
    :param overlap_extra_bid_amt: the flat cross-filter bonus
    """
    @staticmethod
    def overlap_target(has_multiple_filters, this_filter_desired, highest_desired, overlap_extra_bid_amt):
        if has_multiple_filters:
            return highest_desired + overlap_extra_bid_amt
        # Only one distinct filter has ever matched: no bonus, just its own desired amount.
        return this_filter_desired

    """
    Target-aware decision for whether listing_logic should SURFACE an already-invested listing again.

    This mirrors compute_overlap_bid's target so the cheap per-poll surfacing gate agrees with the
    authoritative locked bid-sizing in thread_worker. Previously the gate compared a single filter's
    amt_to_bid against the summed already-invested amount, which prematurely blocked top-ups once the
    running total exceeded any one filter's amount (e.g. listing stuck at 339 instead of 375).

    Surface iff there is still at least the $25 minimum of room toward target_total (computed by the
    caller via overlap_target: highest_desired + bonus for a new filter, or this filter's own desired
    amount for the same filter re-finding its listing).
    The per-bid 10% cap does NOT gate surfacing (thread_worker clips each bid and later polls top up).

    Termination: once already_invested_amount >= target_total, the remaining gap drops below $25 and
    this returns False, so a listing cannot be surfaced (and re-bid) forever.

    :return: True if the listing should be surfaced for a (top-up) bid, else False.
    """
    @staticmethod
    def should_surface_invested_listing(already_invested_amount, target_total, min_bid=25):
        remaining = target_total - already_invested_amount
        return remaining >= min_bid

    """
    Reconstructs the highest ORIGINAL configured desire per listing from the filters that bid on it.

    The DB only stores the amount actually bid (bid_requests.bid_amount), not the pre-10%-clamp
    configured desire. But listings_filters_used records which (filter, rating) bid on each listing,
    and the configured desire is deterministic: bid_amt[rating][filter]. So the highest desire for a
    listing is max(bid_amt[rating][filter]) over every filter that bid on it.

    :param filters_used_rows: list of {"listing_number", "filter", "prosper_rating"} from the DB
    :param bid_amt: the configured bid_amt dict (rating -> filter -> amount)
    :param bidded_by_listing: {listing_number: total_bidded} fallback when config can't reconstruct a desire
    :return: {listing_number: highest_desired}
    """
    @staticmethod
    def reconstruct_highest_desired(filters_used_rows, bid_amt, bidded_by_listing):
        highest_desired = {}
        for row in filters_used_rows:
            listing_number = row["listing_number"]
            rating = row["prosper_rating"]
            query = row["filter"]
            # A filter/rating that no longer exists in the current config can't be reconstructed; skip it.
            configured = bid_amt.get(rating, {}).get(query)
            if configured is None:
                continue
            if configured > highest_desired.get(listing_number, 0):
                highest_desired[listing_number] = configured
        # Fallback: any listing we couldn't reconstruct a desire for falls back to what was actually bid,
        # so its target never drops below the amount already invested. Live filters re-raise it via max(...).
        for listing_number, bidded in bidded_by_listing.items():
            if listing_number not in highest_desired:
                highest_desired[listing_number] = bidded
        return highest_desired

    """
    Seeds the in-memory tracking structures from the DB so a restart continues from prior-run bids
    instead of treating already-bid listings as brand new (which would re-bid them in full).
    Uses the same 7-day window as get_bid_listings_with_bid_amount() so listing_logic's surfacing
    gate and thread_worker's in-memory 'existing' lookup agree.
    """
    def seed_from_db(self):
        bidded = self.connect.get_bid_listings_with_bid_amount()  # [{"listing_number", "bidded_amount"}]
        filters_used_rows = self.connect.get_filters_used_for_recent_bids()

        submitted_order_listings = []
        submitted_order_listings_filters = {}
        bidded_by_listing = {}
        for row in bidded:
            listing_number = row["listing_number"]
            bidded_by_listing[listing_number] = row["bidded_amount"]
            submitted_order_listings.append({listing_number: row["bidded_amount"]})
            submitted_order_listings_filters[listing_number] = []

        # Record which filters have already bid, so a same-filter re-find is treated as a repeat.
        for row in filters_used_rows:
            listing_number = row["listing_number"]
            if listing_number in submitted_order_listings_filters and row["filter"] not in submitted_order_listings_filters[listing_number]:
                submitted_order_listings_filters[listing_number].append(row["filter"])

        submitted_order_listings_desired = self.reconstruct_highest_desired(
            filters_used_rows, self.bid_amt, bidded_by_listing)

        return submitted_order_listings, submitted_order_listings_filters, submitted_order_listings_desired

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
                sql.run_insert_bid_request(response)  # This is giving me error bc listing_id is the primary key and now i can have multipe bids for same listing, need to fix this.
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
                desired_total_bid_amt += l['bid_amount']
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
                for l in listings_list:
                    l['bid_amount'] = available_per_bid
                situation_one_msg = "Current cash of {cash} is not enough available cash for desired bid amount, for {investment_number} listings, but enough for submit bids on all listings, modifying to {new_amt} per bid".format(
                                                    cash=available_cash, investment_number=investment_number, new_amt=available_per_bid)
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
                for l in listings_list:
                    l['bid_amount'] = available_per_bid

                return listings_list, bid_amt, available_cash - new_total_bid_amt

    """
    Alright, now we get confusing. Today is 12/3/25. I'm adding in the ability to query in depth Transunion data. Some Transunion data is indexed and included in the API response.
    But most of the Transunion data is not.
    This is kind of a bandaid fix to allow for this type of querying, I dont love it; but i dont want to do a full rewrite.
    This will require a dict in the filters/filter.py that adds in the additional filtering not doable straight in the API request. 
    query_listing looks like 
    {}
    """

    def handle_creditdata_query(self, query_listing, query):
        results = query_listing['result']
        listings_found_dict = {}
        listings_found_dict_listing_amt = {}
        criteria_list = filters.transunion_add_on_filters[query]
        criteria_count = len(criteria_list)
        for result in results:
            if 'occupation' not in result:  # Really dirty band-aid way to ignore no occupation.
                continue

            # A missing transunion block means we can't evaluate this listing; skip it (not the whole batch).
            transunion = result.get('credit_bureau_values_transunion')
            if transunion is None:
                continue

            criteria_hit = 0
            for x in criteria_list:
                credit_bureau_value = x['credit_bureau_value']
                try:
                    value = transunion[credit_bureau_value]
                except KeyError as e:
                    logging.log_it_info(self.logger, f"key error for transunion data: {e}")
                    break  # Skip just this listing, keep processing the rest of the batch.

                min_or_max = x['min_or_max']
                if min_or_max == 'min':
                    passed = value >= x['min_or_max_value']
                elif min_or_max == 'max':
                    passed = value <= x['min_or_max_value']
                elif min_or_max == 'between':
                    passed = x['min_value'] <= value <= x['max_value']
                else:
                    passed = False

                if not passed:
                    break  # All criteria are required; no point checking the rest.
                criteria_hit += 1

            # Only record the listing if every criterion matched.
            if criteria_hit == criteria_count:
                listing_number = result['listing_number']
                listings_found_dict[listing_number] = result['prosper_rating']
                listings_found_dict_listing_amt[listing_number] = result['listing_amount']
            # else:
            #     logging.log_it_info(self.logger,
            #                         f"WARNING; blocking TRANSUNION bid occupation key does not exist")

        return listings_found_dict, listings_found_dict_listing_amt
