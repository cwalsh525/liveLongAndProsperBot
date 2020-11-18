from metrics.connect import Connect
from metrics.reporting_metrics.notes_metrics import NotesMetrics

from datetime import datetime, timedelta
import config.default as default
import matplotlib.pyplot as plt


class CreateDailyMetricsTable:

    def __init__(self, start_date, path_to_save_defaults, path_to_save_annualized_returns):
        self.connect = Connect()
        self.today = datetime.today().strftime("%Y-%m-%d")
        self.table_name = "daily_notes_metrics_{date}".format(date=datetime.today().strftime("%Y-%m-%d").replace("-", "_"))
        self.start_date = start_date
        # self.path_to_save = path_to_save
        self.path_to_save_defaults = path_to_save_defaults
        self.path_to_save_annualized_returns = path_to_save_annualized_returns

    # Depreciated
    # def create_table(self):
    #     create_table_script = """
    #     create table {table_name} (
    #     date date,
    #     Realized_Gains decimal,
    #     Unrealized_Gains decimal,
    #     Unrealized_Gains_With_Oppertunity_Cost decimal,
    #     Forecasted_Returns decimal);
    #     """.format(table_name=self.table_name)
    #     self.connect.execute_insert_or_update(create_table_script)

    def build_dates_list(self):
        dates_to_run_list = []

        start_date = self.start_date
        end_date = self.today
        start_date_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        days_to_run = int((end_date_datetime - start_date_datetime).days)
        for d in range(days_to_run + 1):
            date_to_run = (end_date_datetime - timedelta(days=d)).strftime("%Y-%m-%d")
            dates_to_run_list.append(date_to_run)
        dates_to_run_list.reverse()

        return dates_to_run_list

    # Depreciated
    # def insert_daily_metrics_data(self):
    #
    #     dates_to_run = self.build_dates_list()
    #     for day in dates_to_run:
    #         print(day)
    #         notes = NotesMetrics(day)
    #         Realized_Gains = notes.realized_gains()
    #         Unrealized_Gains = notes.unrealized_gains()
    #         Unrealized_Gains_With_Oppertunity_Cost = notes.unrealized_gains_with_oppertunity_cost()
    #         Forecasted_Returns = notes.forecasted_returns()
    #
    #         insert_script = """insert into {table_name} values
    #         ('{date}', {Realized_Gains}, {Unrealized_Gains}, {Unrealized_Gains_With_Oppertunity_Cost}, {Forecasted_Returns});
    #         """.format(table_name=self.table_name,
    #             date=day,
    #             Realized_Gains=Realized_Gains,
    #                    Unrealized_Gains=Unrealized_Gains,
    #                    Unrealized_Gains_With_Oppertunity_Cost=Unrealized_Gains_With_Oppertunity_Cost,
    #                    Forecasted_Returns=Forecasted_Returns)
    #         self.connect.execute_insert_or_update(insert_script)
    #         # print(insert_script)

    # Depreciated
    # def create_line_graph_metrics_png(self):
    #
    #     dates_to_run = self.build_dates_list()
    #     realized_gains_list = []
    #     unrealized_gains_list = []
    #     unrealized_gains_with_oppertunity_cost_list = []
    #     forcasted_returns_list = []
    #     forcasted_returns_forcasted_list = []
    #
    #     for day in dates_to_run:
    #         notes = NotesMetrics(day)
    #         realized_gains_list.append(notes.realized_gains())
    #         unrealized_gains_list.append(notes.unrealized_gains())
    #         unrealized_gains_with_oppertunity_cost_list.append(notes.unrealized_gains_with_oppertunity_cost())
    #         forcasted_returns_list.append(notes.forecasted_returns())
    #         forcasted_returns_forcasted_list.append(notes.forecasted_returns_forcasted())
    #
    #     plt.figure(1)
    #     plt.plot(dates_to_run, realized_gains_list, label="realized_gains")
    #     plt.plot(dates_to_run, unrealized_gains_list, label="unrealized_gains")
    #     plt.plot(dates_to_run, unrealized_gains_with_oppertunity_cost_list, label="unrealized_gains_w_opc")
    #     plt.plot(dates_to_run, forcasted_returns_list, label="forcasted_returns")
    #     plt.plot(dates_to_run, forcasted_returns_forcasted_list, label="forcasted_returns_forcasted")
    #     plt.legend()
    #     plt.title("Gains Over Time {start_date} - {end_date}".format(start_date=self.start_date, end_date=self.today))
    #     plt.xlabel("Date")
    #     plt.ylabel("Percent Return")
    #
    #     plt.savefig(self.path_to_save)


    def create_default_tracking_line_graph_png(self):

        dates_to_run = self.build_dates_list()
        projected_default = []
        projected_default_prosper = []
        actual_default = []

        def total_defaults(default_dict):
            defaults = 0
            for k in default_dict:
                defaults += default_dict[k]
            return defaults

        for day in dates_to_run:
            notes = NotesMetrics(day)
            projected_default_dict, projected_default_dict_prosper, actual_default_dict, _, _ = notes.default_rate_tracking()
            projected_default.append(total_defaults(projected_default_dict))
            projected_default_prosper.append(total_defaults(projected_default_dict_prosper))
            actual_default.append(total_defaults(actual_default_dict))

        plt.figure(2)
        plt.plot(dates_to_run, projected_default, label="projected_defaults")
        plt.plot(dates_to_run, projected_default_prosper, label="projected_defaults_prosper")
        plt.plot(dates_to_run, actual_default, label="actual_defaults")
        plt.title("Defaults Over Time {start_date} - {end_date}".format(start_date=self.start_date, end_date=self.today))
        plt.xlabel("Date")
        plt.ylabel("Number of Defaults")
        plt.legend()

        plt.savefig(self.path_to_save_defaults)

    def create_annualized_returns_line_graph(self):
        query = "select * from daily_annualized_returns;"
        results = self.connect.execute_select(query)

        dates = []
        annualized_returns = []
        annualized_returns_late_equals_default = []
        for t in results:
            dates.append(t[0])
            annualized_returns.append(t[1])
            annualized_returns_late_equals_default.append(t[2])

        plt.figure(3)
        plt.plot(dates, annualized_returns, label="annualized_returns")
        plt.plot(dates, annualized_returns_late_equals_default, label="annualized_returns_late_equals_default")
        plt.title("annualized_returns Over Time {start_date} - {end_date}".format(start_date=dates[0], end_date=dates[-1]))
        plt.xlabel("Date")
        plt.ylabel("annualized_returns %")
        plt.legend()

        plt.savefig(self.path_to_save_annualized_returns)


    # def execute_table(self):
    #     self.create_table()
    #     self.insert_daily_metrics_data()
