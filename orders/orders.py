import utils.utils as utils
import log.logging as log

import datetime
import requests
import sys
import time
import math

import config.default as default
from metrics.sql_metrics import SQLMetrics

"""
This class submits the orders of loans to invest in

:param listings_list: a list of the listing_ids to be invested in
:type listings_list: List

:param filters_used_dict: A dictionary that contains the filter used as a key and a list of listing_ids as the value: {filter0: [listing_id_0, listing_id_1], filter1: [listing_id,2]}
:type filters_used_dict: Dictionary

:param amt: the dollar value to invest in the loan
:type amt: int

:param access_token: access_token to prosper
:type access_token: access_token
"""

class Orders:

    #TODO take aval cash as a param and verify have enough money. If not, submit what we have
    def __init__(self, listings_list, filters_used_dict, amt, access_token, available_cash):
        self.listings_list = listings_list
        self.filters_used_dict = filters_used_dict
        self.amt = amt
        self.access_token = access_token
        self.available_cash = math.floor(available_cash)
        self.investment_number = len(self.listings_list)
        self.request = {
            "bid_requests": []
        }
        # for l in self.listings_list:
        #     self.request['bid_requests'].append({"listing_id": l, "bid_amount": self.amt})

        self.logger = log.create_logger(log_name="app_run", logger_name="Orders_logger")

    """
    Function that only gets called when aval_amt <= 25 and investment_number > 1
    Removes listings from bid due to lack of funds when you cannot cleanly just reduce the investment bid and need to reduce the number of listings to bid on 
    """
    # Test me
    def recalculate_bid_amount(self, cash, listing_list):
        while len(listing_list) > 0:
            listing_list.pop(0)  # Remove an element since this function is only used when aval_amt <= 25 and investment_number > 1. Remove first element, since that index is highest chance of being an expired listing
            aval_bids = cash / 25
            new_listing_length = len(listing_list)
            if aval_bids >= new_listing_length:
                aval_amt = cash / new_listing_length
                return aval_amt, listing_list

    # Test me
    def handle_cash_balance(self):
        aval_amt = self.available_cash / self.investment_number
        if self.available_cash >= 25:  # min bid for a listing
            if aval_amt < self.amt:
                if aval_amt < self.available_cash:
                    if aval_amt >= 25:
                        situation_one_msg = "1: {cash} is not enough available cash for desired bid amount of {amt}, for {investment_number} listings, modifying to {new_amt}".format(
                                cash=self.available_cash, investment_number=self.investment_number, amt=self.amt, new_amt=aval_amt)
                        self.amt = aval_amt
                        print(situation_one_msg)
                        self.logger.info(situation_one_msg)
                    elif aval_amt <= 25 and self.investment_number > 1:
                        new_bid_amt, new_listing_list = self.recalculate_bid_amount(cash=self.available_cash, listing_list=self.listings_list)
                        situation_two_msg = "2: {cash} is not enough available cash for desired bid amount of {amt}, for {investment_number}  listings, modifying to bids of {new_amt} for {listing_num} listings".format(
                                cash=self.available_cash, investment_number=self.investment_number, amt=self.amt, new_amt=new_bid_amt,
                                listing_num=len(new_listing_list))
                        print(situation_two_msg)
                        self.logger.info(situation_two_msg)
                        self.amt = new_bid_amt
                        self.listings_list = new_listing_list
            else:
                normal_op_msg = f"available_cash of {self.available_cash} is enough for normal bidding submission"
                print(normal_op_msg)
                self.logger.info(normal_op_msg)

        else:
            situation_three_msg = "Your available cash of {cash} is not enough to invest in anything... Wow dude".format(cash=self.available_cash)
            print(situation_three_msg)
            self.logger.info(situation_three_msg)
            self.listings_list = []

    def build_request(self):
        for l in self.listings_list:
            self.request['bid_requests'].append({"listing_id": l, "bid_amount": round(self.amt, 2)})

    def submit_order(self):

        start_time = time.time()
        investment_number = len(self.listings_list)

        order_header = utils.http_header_build_orders(self.access_token)

        if investment_number > 0:
            self.handle_cash_balance()
            self.build_request()
            response = requests.post(default.config['prosper']['prosper_order_url'], json=self.request, headers=order_header).json()
            self.logger.info(
                'Invested in {num} orders at {time}, submit_order took {secs} seconds to run'.format(num=investment_number, time=datetime.datetime.now(), secs=time.time() - start_time))
            self.logger.info("request = {request}".format(request=self.request))
            self.logger.info("response = {response}".format(response=response))
            # TODO error handling per error code type from prosper
            if "order_id" in response:
                try:
                    sql = SQLMetrics()
                    sql.run_listing_filters_used(self.filters_used_dict)  # inserts the filters used into listings_filters_used for tracking
                    sql.run_insert_bid_request(response) #TODO add error handling. Print the error and continue
                    sql.run_insert_orders(response)
                    sql.close_connection()
                except:  # TODO make specific for now catch all errors
                    e = sys.exc_info()[0]
                    self.logger.info(e)
            if 'code' in response: # Sometimes a listing_id cannot be invested in
                # Example response {'code': 'ORD0019', 'message': 'Listing [10846973] is in status [PENDING_COMPLETION] and cannot currently accept bids.'}
                try:
                    listing_string = response['message']
                    end_index = listing_string.find("]")
                    pending_completion_listing = listing_string[9:end_index]
                    sql = SQLMetrics()
                    sql.run_insert_bid_request_pending_completion(pending_completion_listing)  # This adds the listing to bid_requests table and therefore will be excluded in the future runs
                    self.logger.info("Added {listing} to pending_completion_listings list".format(listing=pending_completion_listing))
                    sql.close_connection()
                except TypeError as type_error:
                    self.logger.info("type error: {error}".format(error=type_error))
                except:
                    e = sys.exc_info()[0]
                    self.logger.info(e)
        else:
            print("Nothing to invest, sorry bro")
            self.logger.info('I ran at {time}'.format(time=datetime.datetime.now()))

