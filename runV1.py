import math

import utils.utils as utils

import config.default as default
import filters.filters as filters

from token_gen.token_generation import TokenGeneration
from run_v1.search_and_destroy import SearchAndDestroy
from accounts.accounts import Accounts


config = default.config

access_token = TokenGeneration(
    client_id=config['prosper']['client_id'],
    client_secret=config['prosper']['client_secret'],
    ps=config['prosper']['ps'],
    username=config['prosper']['username']
).execute()

header = utils.http_header_build(access_token)
order_header = utils.http_header_build_orders(access_token)

account = Accounts(header)
cash_balance = math.floor(account.get_account_response()['available_cash_balance'])

# time.sleep(10) # Typically takes ~ 20, 25 seconds to post, but there are outliers. Running a loop seems more effective at getting the most amount of listings vs searhcing for new listings and then running.

# Started on 11/23/20. Very first note found was expired... a 4K E rated note... So looks like i may not be able to speed up my proccess enough to get all notes...
# Still worthwhile to see if SearchAndDestroy gets better results.
# Turning off min_run_time on 12/16/2020 to see if expired due to demand decreases.
# 11/23/20 - 12/16/2020 was 5.63% expired due to demand (4 out of 71)
# Started no min_run_time and just let get throttled on 12/17/20 beg of day
# Turned min_run_time back on for 1/12/21. 12/17/20 - 1/11/21 was 8 / 81 was expired due to demand 9.8%...
# 1/12/21 - 1/26/21 had 4/61 expired due to demand 6.5%
# On 1/27/21 turned off all 5 HR filters to see if reduced expired finds.
# 1/27/21 - 3/30/21 so far is 7/230 or 3% expired due to demand.. so it does decrease expired number... But, if HR is more than 7 or 8 over that time, it's worth it?
# seemed to be working vwell. added diff prosper bif amt by rating on 2/2.
# 3/31/21 turning back on HR. If i get more than 7 or 8 HR's per 2 months it's worth having the filters on?? I think so
# Turning HR back off on 8/15/21 as no HR bids in past 30 days
SearchAndDestroy(order_header=order_header,
                 listing_header=header,
                 time_to_run_for=60 * 4,
                 filters_dict=filters.v2_filters_dict,
                 bid_amt=config['bid_amt'],
                 available_cash=cash_balance,
                 min_run_time=(len(filters.v2_filters_dict) / 20) + .03
                 ).execute()
# Added query_v2_1 back into filters on 12/7. See if it gets anything and is worth it.
