import requests
import time
import threading

from _datetime import datetime, timezone, timedelta

from metrics.connect import Connect
import filters.filters as filters
import log.logging as log

"""
This class handles interacting with the listing api, finds listings to invest in
"""
class Listing:

    lock = threading.Lock()

    def __init__(self, header):
        self.header = header
        self.logger = log.create_logger(log_name="app_run", logger_name="Listing_logger")

    """
    A simple request that gets the most recent note listing
    """
    def get_newest_listing(self):
        response = requests.get("https://api.prosper.com/listingsvc/v2/listings/?limit=1&sort_by=listing_start_date desc", headers=self.header, timeout=30.0)
        return response.json()
    """
    Uses above function to see if a new note listing has been posted in past timedelta amount of time
    :param: time: timedelta
    """
    def _new_listings_posted(self, time):
        response = self.get_newest_listing()
        if response['total_count'] == 0:
            return False
        else:
            time_to_check = response['result'][0]['listing_start_date']
            datetime_time_to_check = datetime.strptime(time_to_check, '%Y-%m-%d %H:%M:%S %z')
            if datetime_time_to_check > datetime.now(timezone.utc) - time:
                return True
            else:
                return False

    """
    Gets listings based on a dict of query name and actual post request query
    
    """
    def execute_dict_sequential(self, filters_dict):
        start_time = time.time()
        listings_list = []
        track_filters = {}
        already_invested_listings = Connect().get_bid_listings() #TODO put this function in a proper location
        for query in filters_dict:
            r = requests.get(filters_dict[query], headers=self.header, timeout=30.0)
            query_listing = r.json()
            result_length = len(query_listing['result'])
            if result_length > 0:
                for i in range(result_length):
                    listing_number = query_listing['result'][i]['listing_number']
                    if listing_number not in already_invested_listings:
                        self.track_filter(track_filters, listing_number, query) # populates track_filters dict to be inserted into psql later
                        if listing_number not in listings_list:
                            listings_list.append(listing_number)
            print("Ran: {query}, found {result_length} listings".format(query=query, result_length=result_length))
        print("Totally elapsed time to run: {time} seconds".format(time=time.time() - start_time))
        return listings_list, track_filters

    """
    This is what the worker will be doing.
    Very similar to above function
    thread_worker takes a get request, gets the listing_number and adds it to the master listings_list provided
    The listing_list will later be used to submit a post request to invest in those listings
    I believe Prosper's Listing API throttles at around 15 requests a second, and i typically get throttled on my second loop of listing requests, so thread_worker re-runs if throttled
    """
    def thread_worker(self, query, query_get, listings_list, already_invested_listings, track_filters):
        i_got_throttled = True # Sometimes get throttled, will run again if throttled
        while i_got_throttled:
            r = requests.get(query_get, headers=self.header, timeout=30.0) # Check if this is what takes bulk of time when listings found OR if its my logic
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
                            with self.lock:
                                if listing_number not in listings_list:
                                    listings_list.append(listing_number)
                i_got_throttled = False
            else:
                if 'errors' in query_listing:
                    msg ="query {query} got an error, error is: {error}".format(query=query, error=query_listing)
                    # print(msg)
                    self.logger.warning(msg)
                else:
                    self.logger.warning("not an errors in response, response is: {response}".format(response=query_listing))
    """
    Add multi-threading get listings (run all get listings at same time to increase speed)
    Creates a thread for every get request filter (query)
    
    :return:
        listings_list: a list of listings to be invested in
         track_filters: a dict {filter0: [listing_id_0, listing_id_1], filter1: [listing_id,2]} that gets past in for the sole purpose of tracking filters used for reporting metrics
    """
    def execute_dict_threaded(self, filters_dict):
        start_time = time.time()
        listings_list = []
        track_filters = {}
        threads = []
        already_invested_listings = Connect().get_bid_listings() #TODO put this function in a proper location
        for query in filters_dict:
            t = threading.Thread(target=self.thread_worker, args=(query, filters_dict[query], listings_list, already_invested_listings, track_filters))
            threads.append(t)
            t.start()
        for thread in threads:
            thread.join()  # Waits for all threads to complete or else will hit return value before threads are complete

        # print("Total elapsed time to run: {time} seconds".format(time=time.time() - start_time))
        self.logger.info("Run time: {run_time}, Total elapsed time to run execute_dict_threaded in Listing: {time} seconds".format(run_time=datetime.now(), time=time.time() - start_time))
        return listings_list, track_filters

    """
    Utility function to track filters
    """
    @staticmethod
    def track_filter(json, listing_id, filter_used):
        if listing_id in json:
            json[listing_id].append(filter_used)
        else:
            json[listing_id] = [filter_used]

    def search_for_new_listings(self, time_to_search):
        listings_posted = False
        timeout_to_search_for_listings = time.time() + time_to_search
        self.logger.info("Started searching for new listings at {time}".format(time=datetime.now()))
        while listings_posted is False and time.time() < timeout_to_search_for_listings:
            listings_posted = self._new_listings_posted(time=timedelta(hours=2))
        if listings_posted is True:
            self.logger.info("New listings found at {time}".format(time=datetime.now()))
        else:
            self.logger.info("Warning, no new listings found! :(")
        return listings_posted

    def testing(self):
        r = requests.get(filters.query_builder(filters.example_query), headers=self.header, timeout=30.0)
        listings = r.json()
        for i in range(len(listings['result'])):
            listing_number = listings['result'][i]['listing_number']
            print(listing_number)
