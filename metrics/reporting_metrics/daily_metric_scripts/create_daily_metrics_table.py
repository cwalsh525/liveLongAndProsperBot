from metrics.connect import Connect
from metrics.reporting_metrics.notes_metrics import NotesMetrics

from datetime import datetime, timedelta
import matplotlib.pyplot as plt


class CreateDailyMetricsTable:

    def __init__(self, start_date, path_to_save_defaults):
        self.connect = Connect()
        self.today = datetime.today().strftime("%Y-%m-%d")
        self.table_name = "daily_notes_metrics_{date}".format(date=datetime.today().strftime("%Y-%m-%d").replace("-", "_"))
        self.start_date = start_date
        self.path_to_save_defaults = path_to_save_defaults

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
            projected_default_dict, projected_default_dict_prosper, actual_default_dict, _ = notes.default_rate_tracking()
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
        print("saved")
