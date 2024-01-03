import time


class MaxRequestsQueue:

    def __init__(self, max_request_per_second, filter_dict, time_to_run_for):
        self.max_request_per_second = max_request_per_second
        self.filter_dict = filter_dict
        self.time_to_run_for = time_to_run_for

    def build_allowed_run_dict(self):
        # {1699543285: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543285}, 1699543286: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543286}, 1699543287: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543287}, 1699543288: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543288}, 1699543289: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543289}, 1699543290: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543290}, 1699543291: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543291}, 1699543292: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543292}, 1699543293: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543293}, 1699543294: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543294}, 1699543295: {'allowed_remaining_runs': 5, 'latest_run_time': 1699543295}}
        current_time_in_milli = time.time()
        current_time_in_seconds = int(current_time_in_milli)
        run_allowance_dict = {}

        for i in range(self.time_to_run_for + 10): # 10 extra seconds just to be safe
            the_second = current_time_in_seconds + i
            run_allowance_dict[the_second] = { "allowed_remaining_runs": self.max_request_per_second, "latest_run_time": the_second}
            # Using latest_run_time as the_second as this will be the floor to start running
        return run_allowance_dict

    def build_starting_filter_queue(self):
        # ['filter_1', 'filter_2', 'filter_3', 'filter_4']
        run_list = []
        for key in self.filter_dict:
            run_list.append(key)
        return run_list
