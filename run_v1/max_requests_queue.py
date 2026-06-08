import time
from collections import deque, defaultdict

class MaxRequestsQueue:
    """
    Queue that allows for max amount of requests to be sent to Prosper's Listing API.
    This is needed as they only allow 20 per second.
    BUT, this is really needed because they have a bug that allows for significantly less than 20 per second.
    I have this parameterized for easy changing if needed.
    
    Optimized to use deque for O(1) operations and sliding window for memory efficiency.
    """

    def __init__(self, max_request_per_second, filter_dict, time_to_run_for):
        self.max_request_per_second = max_request_per_second
        self.filter_dict = filter_dict
        self.time_to_run_for = time_to_run_for

    def build_allowed_run_dict(self):
        """
        Returns a defaultdict that dynamically creates entries as needed.
        This avoids pre-allocating thousands of entries and allows automatic cleanup.
        """
        def create_entry():
            return {"allowed_remaining_runs": self.max_request_per_second, "latest_run_time": 0}
        
        return defaultdict(create_entry)

    def build_starting_filter_queue(self):
        """
        Returns a deque for O(1) popleft() and append() operations.
        This is the key optimization - list.pop(0) is O(n), deque.popleft() is O(1).
        """
        return deque(self.filter_dict.keys())
