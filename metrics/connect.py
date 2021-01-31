import psycopg2

import config.default as default

"""
This class connects to the database
Offers some utility sql functions as well
"""
class Connect:

    def __init__(self):
        self.postgres_config = default.config['postgres']
        self.connection = psycopg2.connect(**self.postgres_config)

    def execute_insert_or_update(self, insert_query):
        cursor = self.connection.cursor()
        cursor.execute(insert_query)
        self.connection.commit()
        cursor.close()

    """
    returns a tuple of tuples, not a specific value
    """
    def execute_select(self, select_query):
        cursor = self.connection.cursor()
        cursor.execute(select_query)
        result = cursor.fetchall()
        cursor.close()
        return result

    def get_bid_listings(self):
        # This takes 0.0009644031524658203 seconds
        #TODO have bid requests table be sorted
        listings = []
        result = self.execute_select("select listing_id from bid_requests where created_timestamp > current_date - 7;")
        for l in result:
            listings.append(l[0])
        return listings

    def populate_list_from_single_column_sql_query(self, query):
        list_to_return = []
        result = self.execute_select(query)
        for l in result:
            list_to_return.append(l[0])
        return list_to_return

    def close_connection(self):
        self.connection.close()
