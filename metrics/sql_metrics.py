import psycopg2

import datetime

import config.default as default

"""
This class provides sql functions the bot uses to track listings and notes
"""
class SQLMetrics:
    def __init__(self):
        self.config = default.config['postgres']
        self.connection = psycopg2.connect(**self.config)

    def listing_filters_used(self, listing_id, filter):
        cursor = self.connection.cursor()
        """
        :param listing_id:
        :param filter:
        :return:
        """
        insert_query = """
        insert into listings_filters_used values ({listing_id}, '{filter}');
        """.format(listing_id=listing_id, filter=filter)

        cursor.execute(insert_query)
        self.connection.commit()
        cursor.close()

    def run_listing_filters_used(self, listing_filters_dict):
        for key in listing_filters_dict:
            for l in listing_filters_dict[key]:
                self.listing_filters_used(key, l)

    def insert_bid_request(self, order_id, listing_id, amt, status):
        insert_query = """
        insert into bid_requests values
        ('{order_id}', {listing_id}, {bid_amount}, '{bid_status}', null, '{created_ts}', null)
        """.format(order_id=order_id, listing_id=listing_id, bid_amount=amt, bid_status=status, created_ts=datetime.datetime.now())
        return insert_query

    def run_insert_bid_request(self, response_object):
        cursor = self.connection.cursor()
        for j in response_object['bid_requests']:
            cursor.execute(self.insert_bid_request(response_object['order_id'], j['listing_id'], j['bid_amount'], j['bid_status']))
            #TODO add if bid_status = invested add record in notes table (may not need this as may not be possible to start with invested)
            self.connection.commit()
        cursor.close()

    def run_insert_bid_request_pending_completion(self, listing_id):
        cursor = self.connection.cursor()
        cursor.execute(self.insert_bid_request("NA: Listing not aval", listing_id, "0", "NA: Listing not aval"))
        self.connection.commit()
        cursor.close()

    def run_insert_orders(self, response_object):
        cursor = self.connection.cursor()
        insert_query = """
        insert into orders values
        ('{order_id}', '{order_status}', '{order_source}', '{order_date}', '{created_ts}', null)
        """.format(order_id=response_object['order_id'], order_status=response_object['order_status'], order_source=response_object['source'], order_date=response_object['order_date'], created_ts=datetime.datetime.now())
        cursor.execute(insert_query)
        self.connection.commit()
        cursor.close()

    def close_connection(self):
        self.connection.close()
