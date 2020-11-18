example_query = 'prosper_rating=B,C&listing_term=36&listing_amount_min=4000&listing_amount_max=10000&sort_by=verification_stage'

base_path = "https://api.prosper.com/listingsvc/v2/listings/?"
default_query = base_path + "biddable=true&invested=false&limit=100"

default_v1 = "prosper_rating=B,C,D,E&listing_term=36"

def query_builder(filter: str) -> str:
    return default_query + "&" + filter

homeowner = "&has_mortgage=true"

# Filters used simply to find listings for testing
query_test_0 = default_v1
query_test_1 = default_v1 + "&listing_amount_max=10000"
query_test_2 = default_v1 + homeowner

test_filters_list = [query_test_0, query_test_1, query_test_2]

test_filters_list_concat = []
for query in test_filters_list:
    test_filters_list_concat.append(query_builder(query))

test_filters_dict = {
    "query_test_0": query_builder(query_test_0),
    "query_test_1": query_builder(query_test_1),
    "query_test_2": query_builder(query_test_2)
}
