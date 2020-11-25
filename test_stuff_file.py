from notes.update_notes import UpdateNotes
import config.default as default
from datetime import datetime
from notes.update_missing_notes import UpdateMissingNotes
from notes.notes import Notes
from accounts.accounts import Accounts
from token_gen.token_generation import TokenGeneration
import log.logging as log
import config.default as default
import utils.utils as utils
from metrics.connect import Connect

from orders.orders import Orders

from metrics.annualized_returns import AnnualizedReturns
from metrics.tracking_metrics import TrackingMetrics
from metrics.reporting_metrics.notes_metrics import NotesMetrics
from metrics.reporting_metrics.daily_metric_scripts.create_daily_metrics_table import CreateDailyMetricsTable
import logging

# update_notes = UpdateNotes()
# update_notes.build_notes_to_update_query()

# n0 = NotesMetrics("2020-07-17")
# n1 = NotesMetrics("2020-07-18")
# n = NotesMetrics("2020-11-02")
# # print(n.default_rate_tracking())
# projected_default_dict, projected_default_dict_prosper, actual_default_dict, actual_default_rates_dict, actual_late_dict = n.default_rate_tracking()
# print(actual_default_dict)
# print(actual_late_dict)
# #
# print(n0.default_rate_tracking())

# print(n0.default_rate_tracking())
# print(n1.default_rate_tracking())





# print(n.default_rate_tracking())
# n.forecasted_returns()
# 335

#
# # print(update_notes.build_transaction())
#
# update_notes.execute()

# logger_metrics = log.create_logger(log_name="app_metrics", logger_name="test0")
# logger_app = log.create_logger(log_name="app_run", logger_name="test1")
# logger_test = log.create_logger(log_name="app_run", logger_name="test2")
#
# logger_metrics.info("logger_metrics")
# logger_app.info("logger_app")
# logger_test.info("me too")


# path_to_save = default.base_path + '/log/daily_metrics.png'
# path_to_save_defaults = default.base_path + '/log/daily_defaults.png'
# path_to_save_annualized_returns = default.base_path + '/log/daily_annualized_returns.png'
# c = CreateDailyMetricsTable(start_date="2020-03-02", path_to_save=path_to_save, path_to_save_defaults=path_to_save_defaults, path_to_save_annualized_returns=path_to_save_annualized_returns)
# c.create_annualized_returns_line_graph()
# c.create_line_graph_metrics_png()
# c.create_default_tracking_line_graph_png()

# n = UpdateMissingNotes()

# n = Notes()
# print(n.get_account_value())

config = default.config
access_token = TokenGeneration(
    client_id=config['prosper']['client_id'],
    client_secret=config['prosper']['client_secret'],
    ps=config['prosper']['ps'],
    username=config['prosper']['username']
).execute()

header = utils.http_header_build(access_token)
# # #
# #
a = Accounts(header)
print(a.get_account_response())
# # for i in range(10):
#     # a = Accounts(header).get_account_response()
# print(a.get_account_response())
# print(a)
#
# tm = TrackingMetrics()
# tm.update_deposits_and_withdrawls_table()

# ar = AnnualizedReturns(header)
# ar.update_annualized_returns_table()
# print(ar.calculate_annualized_returns())

# from metrics.reporting_metrics.build_message import BuildMessage
# b = BuildMessage(a)
# b.display_average_yield()

# o = Orders(access_token=access_token, amt=25, available_cash=75, filters_used_dict={}, listings_list=["123", "231", "444"])
# o.handle_cash_balance()


# already_invested_listings = Connect().get_bid_listings()  # Takes a fraction of a second, should be ok. Repetitive as submitted_order_listings will handle it, but perfer cutting the listing logic off if not needed


