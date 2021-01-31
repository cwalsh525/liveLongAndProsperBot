from token_gen.token_generation import TokenGeneration
from listings.listing import Listing
from orders.orders import Orders
from accounts.accounts import Accounts

import utils.utils as utils

import config.default as default
import filters.filters as filters
import log.logging as log

import time

config = default.config

logger = log.create_logger(log_name="app_run", logger_name="app_log")

# TODO Find a safe way to pass creds
access_token = TokenGeneration(
    client_id=config['prosper']['client_id'],
    client_secret=config['prosper']['client_secret'],
    ps=config['prosper']['ps'],
    username=config['prosper']['username']
).execute()

header = utils.http_header_build(access_token)
listings = Listing(header)
bid_amt = utils.get_bid_amount(starting_bid_amt=config['bid_size']['bid'],
                               starting_bid_date=config['bid_size']['starting_bid_date'],
                               implement_increasing_recurring_bid=config['bid_size']['implement_increasing_recurring_bid'],
                               increase_amt=config['bid_size']['weekly_increase_amt'])
account = Accounts(header)
cash_balance = account.get_account_response()['available_cash_balance']

#searches for new listings so program can run once new listings are posted
# listings_posted = listings.search_for_new_listings(time_to_search=240) # checks to see if new listings are posted
# I turned this off and just looped through program on 11/3/20, to see if it helps lower EXPIRED number at all.
# EXPIRED NUMBERS: 18.3% last 30 days, 22.6% last 60 days, 19.8% all time.

#TODO Make how long to run a command line param
time_to_continuously_run_submit_orders = time.time() + 330
sleep = 0.1
runs = 0

#TODO Possible low hanging fruit to reduce "EXPIRED" listings, just loop through and run program instead of checking for new listings...
# Run at 10 seconds after the hour, loop through and implement a sleep that's just enough to not get throttled..
# Update, just looping through and accepting getting throttled just run as fast as possible to avoid expire...
# Starting to think may be worth submit orders seperatly instead of after all listings are returned to speed things up.
# One possible issue with that is if listing throttle also pertains to orders (if im throttled i wont be able to submit an order) and will add to overall throttling issues
# After first minute decreases speed of run or something
# if listings_posted: # new listings, run the program a bunch (run more than once to account for late prosper batches)
# Results:
# 2020-11-3 to 2020-11-22, so this is only 12%, and to be fair, 3 out of those 4 i think i can fixed with just looping...
#------------+-------
# EXPIRED    |     4
# INVESTED   |    23
# PENDING    |     6


time.sleep(10) # Sleep 20 seconds as prosper doesn't release listings until after 20 seconds
while time.time() < time_to_continuously_run_submit_orders:
    logger.info(f"run number is {runs}")
    listings_to_invest, filters_used_dict = listings.execute_dict_threaded(filters.v2_filters_dict)
    logger.info("listings_list = : {listings_list}".format(listings_list=listings_to_invest))
    if len(listings_to_invest) > 0: # Run order class if listing/s are found
        Orders(listings_to_invest, filters_used_dict, bid_amt, access_token, cash_balance).submit_order() #TODO 20% of listings i try to invest in give me "EXPIRED" (too slow?)
        # This does not update right away so I need to instead not rely on prosper api but subtract what i bid from aval cash
        cash_balance = account.get_account_response()['available_cash_balance'] # Need to keep cash balance up to date for Orders.
    time.sleep(sleep)
    if runs == 70:
        sleep = 1
    if runs > 70:
        sleep *= 1.5
    runs += 1
