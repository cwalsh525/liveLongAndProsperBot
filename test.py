import requests

import utils.utils as utils

import config.default as default
import filters.filters as filters

from token_gen.token_generation import TokenGeneration
from run_v1.search_and_destroy import SearchAndDestroy
from accounts.accounts import Accounts


example_query = 'prosper_rating=B,C&listing_term=36&listing_amount_min=4000&listing_amount_max=10000&employment_status_description=Employed&sort_by=verification_stage'
example_query1 = 'include_credit_bureau_values=transunion&listing_amount_min=4000&listing_amount_max=10000&employment_status_description=Employed&sort_by=verification_stage'
example_query2 = 'include_credit_bureau_values=transunion&at20s_min=10&listing_amount_min=4000&employment_status_description=Employed&sort_by=verification_stage'
example_query3 = 'include_credit_bureau_values=transunion&at20s_min=10&listing_amount_min=4000&employment_status_description=Employed&sort_by=verification_stage'
example_query4 = 'listing_amount_min=4000&employment_status_description=Employed&sort_by=verification_stage'
# example_query5 = 'listing_amount_min=4000&employment_status_description=Employed&at20s_min=100&sort_by=verification_stage'
example_query5 = 'listing_amount_min=4000&employment_status_description=Employed&s004s_min=1&sort_by=verification_stage'
# example_query5 = 'https://api.prosper.com/listingsvc/v2/listings/?limit=10&listing_amount_min=4000&employment_status_description=Employed&at20s_min=10&sort_by=verification_stage'
example_query5 = 'listing_amount_min=4000&employment_status_description=Employed&include_credit_bureau_values=transunion&s004s_min=1&sort_by=verification_stage'

config = default.config

access_token = TokenGeneration(
    client_id=config['prosper']['client_id'],
    client_secret=config['prosper']['client_secret'],
    ps=config['prosper']['ps'],
    username=config['prosper']['username']
).execute()

# use this to test how to pull transunion data.

header = utils.http_header_build(access_token)

query = filters.query_builder(example_query5)
# print(query)

r = requests.get(query, headers=header, timeout=30.0)
r_json = r.json()
print(r_json)

# https://api.prosper.com/listingsvc/v2/listings/?biddable=true&invested=false&limit=100&prosper_rating=B,C&listing_term=36&listing_amount_min=4000&listing_amount_max=10000&sort_by=verification_stage