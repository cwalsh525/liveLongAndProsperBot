from datetime import datetime
import math

def http_header_build(access_token):
    bearer = "bearer {access_token}".format(access_token=access_token)
    return {'accept': "application/json", 'Authorization': bearer}

def http_header_build_orders(access_token):
    bearer = "bearer {access_token}".format(access_token=access_token)
    return {'accept': "application/json", 'content-type': "application/json", 'Authorization': bearer}


def get_bid_amount(starting_bid_amt, starting_bid_date, implement_increasing_recurring_bid, increase_amt):
    amt_to_bid = starting_bid_amt
    if implement_increasing_recurring_bid:
        get_weeks_since_start = math.floor((((datetime.today() - datetime.strptime(starting_bid_date, '%Y-%m-%d')).days) / 7) * increase_amt)
        amt_to_bid = starting_bid_amt + get_weeks_since_start
    return amt_to_bid
