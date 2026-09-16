"""
Tests for run_v1/search_and_destroy.py

Focus: the overlap bid-sizing logic and the surfacing gate, and the convergence + safety
properties they guarantee.

Key rules under test:
  - Convergence (Option 1): total invested in a listing converges to
        target = max(configured across filters) + overlap_bonus
    independent of the order filters find it. Each bid is capped per-bid at max_bid_allowed
    (10% rule); a gap larger than one bid is closed by later arrivals. Trailing gaps below the
    $25 minimum can't be placed (accepted deviation).
  - Cross-filter bonus: the +bonus is earned ONLY when a filter that has not already bid the
    listing overlaps. The SAME filter re-finding its own listing earns no bonus; it may only bid
    again to finish reaching its OWN desired amount, and only if its earlier bid was clamped by
    the 10% cap.

Run from the project root:
    python3 -m unittest tests.run_v1.search_and_destroy_test
(Importing SearchAndDestroy pulls in requests/psycopg2 and config, so these tests are skipped
automatically if those runtime deps are not installed.)
"""

import itertools
import unittest

try:
    from run_v1.search_and_destroy import SearchAndDestroy
    IMPORT_ERROR = None
except Exception as e:  # requests/psycopg2/config not available in this environment
    SearchAndDestroy = None
    IMPORT_ERROR = e

MIN_BID = 25  # Prosper minimum bid amount


def _target_for(query, configured, filters_seen, highest_desired, overlap_bonus):
    """Compute the effective target for a hit using the real overlap_target rule (Option Y)."""
    distinct = set(filters_seen) | {query}
    has_multiple_filters = len(distinct) >= 2
    return SearchAndDestroy.overlap_target(has_multiple_filters, configured, highest_desired, overlap_bonus)


def simulate_listing(configured_by_filter, arrival_order, max_bid_allowed, overlap_bonus, polls=8):
    """
    Simulate repeated filter arrivals against a single listing using the REAL
    SearchAndDestroy.overlap_target + compute_overlap_bid for the math, mirroring the surrounding
    bookkeeping from thread_worker (first-bid clamp, filter tracking, $25 gate).

    Returns the total amount invested at steady state.
    """
    already_bid = None
    highest_desired = 0
    filters_seen = set()

    def one_hit(query):
        nonlocal already_bid, highest_desired
        configured = configured_by_filter[query]
        if already_bid is None:
            already_bid = min(configured, max_bid_allowed)  # first bid clamped to 10% cap
            highest_desired = configured
            filters_seen.add(query)
            return
        highest_desired = max(highest_desired, configured)
        target = _target_for(query, configured, filters_seen, highest_desired, overlap_bonus)
        _t, bid_amt_diff = SearchAndDestroy.compute_overlap_bid(target, already_bid, max_bid_allowed)
        if bid_amt_diff >= MIN_BID:
            already_bid += bid_amt_diff
            filters_seen.add(query)

    for q in arrival_order:
        one_hit(q)
    for _ in range(polls):
        for q in arrival_order:
            one_hit(q)

    return already_bid if already_bid is not None else 0


def simulate_listing_with_gate(configured_by_filter, arrival_order, max_bid_allowed, overlap_bonus, polls=8):
    """
    End-to-end simulation modeling BOTH layers of the real flow:
      1. listing_logic's surfacing gate (should_surface_invested_listing), then
      2. thread_worker's bid sizing (overlap_target + compute_overlap_bid).

    Both layers use the same filter-aware target. Returns (total_invested, num_bids) so tests can
    also assert termination (no runaway re-bidding).
    """
    already_bid = None
    highest_desired = 0
    filters_seen = set()
    num_bids = 0

    def one_hit(query):
        nonlocal already_bid, highest_desired, num_bids
        configured = configured_by_filter[query]
        if already_bid is None:
            already_bid = min(configured, max_bid_allowed)
            highest_desired = configured
            filters_seen.add(query)
            num_bids += 1
            return
        highest_desired = max(highest_desired, configured)
        target = _target_for(query, configured, filters_seen, highest_desired, overlap_bonus)
        # Layer 1: surfacing gate.
        if not SearchAndDestroy.should_surface_invested_listing(already_bid, target):
            return
        # Layer 2: sizing.
        _t, bid_amt_diff = SearchAndDestroy.compute_overlap_bid(target, already_bid, max_bid_allowed)
        if bid_amt_diff >= MIN_BID:
            already_bid += bid_amt_diff
            filters_seen.add(query)
            num_bids += 1

    for q in arrival_order:
        one_hit(q)
    for _ in range(polls):
        for q in arrival_order:
            one_hit(q)

    return (already_bid if already_bid is not None else 0), num_bids


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class OverlapTargetTest(unittest.TestCase):
    """
    The filter-aware target (Option Y). First arg = has_multiple_filters (2+ distinct filters ever
    matched the listing). True -> highest_desired + bonus; False -> this filter's own desired (no bonus).
    """

    BONUS = 75

    def test_multiple_filters_earn_bonus(self):
        # 2+ distinct filters, highest_desired 300 -> 300 + 75
        self.assertEqual(SearchAndDestroy.overlap_target(True, 90, 300, self.BONUS), 375)

    def test_single_filter_targets_own_desired_no_bonus(self):
        # only one distinct filter, its own desired 156 -> 156 (NO bonus)
        self.assertEqual(SearchAndDestroy.overlap_target(False, 156, 156, self.BONUS), 156)

    def test_single_filter_clamped_can_still_reach_own_desired(self):
        # single filter desired 300 but only 200 bid so far -> target 300 (no bonus), room 100
        self.assertEqual(SearchAndDestroy.overlap_target(False, 300, 300, self.BONUS), 300)


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class ComputeOverlapBidTest(unittest.TestCase):
    """Unit tests for the pure bid-sizing helper (takes a target directly)."""

    def test_reaches_target_when_gap_fits_under_cap(self):
        # target 375, already 200, cap 200 -> gap 175 fits under cap.
        target, diff = SearchAndDestroy.compute_overlap_bid(375, 200, 200)
        self.assertEqual(target, 375)
        self.assertEqual(diff, 175)

    def test_gap_larger_than_cap_is_clamped(self):
        # target 375, already 90, cap 200 -> gap 285 clamped to 200.
        _target, diff = SearchAndDestroy.compute_overlap_bid(375, 90, 200)
        self.assertEqual(diff, 200)

    def test_already_at_target_returns_zero(self):
        _target, diff = SearchAndDestroy.compute_overlap_bid(375, 375, 200)
        self.assertEqual(diff, 0)

    def test_already_above_target_never_negative(self):
        _target, diff = SearchAndDestroy.compute_overlap_bid(375, 500, 200)
        self.assertEqual(diff, 0)


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class SameFilterNoBonusRegressionTest(unittest.TestCase):
    """
    Regression for listing 14139305: query_AI_8_2 bid its full desired (156, cap 604 not binding),
    then re-found its own listing and MUST NOT bid another 75. The same filter earns no bonus.
    """

    BONUS = 75

    def test_same_filter_full_desired_no_second_bid(self):
        # First bid 156 = desired (cap 604 not binding). Same filter re-finds: target = own desired 156.
        target = SearchAndDestroy.overlap_target(has_multiple_filters=False, this_filter_desired=156,
                                                 highest_desired=156, overlap_extra_bid_amt=self.BONUS)
        _t, diff = SearchAndDestroy.compute_overlap_bid(target, already_bid=156, max_bid_allowed=604)
        self.assertEqual(diff, 0)  # no second bid

    def test_same_filter_does_not_surface(self):
        # Gate must also refuse to surface it (target 156, already 156, gap 0).
        target = SearchAndDestroy.overlap_target(False, 156, 156, self.BONUS)
        self.assertFalse(SearchAndDestroy.should_surface_invested_listing(156, target))

    def test_end_to_end_same_filter_single_bid(self):
        # Full two-layer simulation: one filter, many polls -> exactly one bid, total = its desired.
        total, num_bids = simulate_listing_with_gate(
            {"query_AI_8_2": 156}, ["query_AI_8_2"], max_bid_allowed=604, overlap_bonus=self.BONUS, polls=50)
        self.assertEqual(total, 156)
        self.assertEqual(num_bids, 1)

    def test_same_filter_clamped_tops_up_to_own_desired_no_bonus(self):
        # Same filter desired 300 on a small listing (cap 120): first bid 120 (clamped), re-find tops
        # up toward its OWN 300 (no bonus), capped 120 each -> 120, 120, 60 = 300. Never 375.
        total, _num = simulate_listing_with_gate(
            {"solo": 300}, ["solo"], max_bid_allowed=120, overlap_bonus=self.BONUS, polls=50)
        self.assertEqual(total, 300)  # own desired, NOT 300 + 75


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class SecondFilterOverlapRulesTest(unittest.TestCase):
    """
    Two overlap rules for a SECOND (distinct) filter (10% cap not binding):
      Rule 1: 2nd filter's config <= 1st filter's bid -> 2nd bid = bonus (75)
      Rule 2: 2nd filter's config  > 1st filter's bid -> 2nd bid = diff + bonus
    """

    BONUS = 75
    BIG_CAP = 10_000

    def _second_bid(self, first_bid, second_config):
        highest_desired = max(first_bid, second_config)
        target = SearchAndDestroy.overlap_target(True, second_config, highest_desired, self.BONUS)
        _t, diff = SearchAndDestroy.compute_overlap_bid(target, first_bid, self.BIG_CAP)
        return diff

    def test_second_filter_lower_bids_only_bonus(self):
        self.assertEqual(self._second_bid(first_bid=200, second_config=90), 75)

    def test_second_filter_equal_bids_only_bonus(self):
        self.assertEqual(self._second_bid(first_bid=200, second_config=200), 75)

    def test_second_filter_higher_bids_diff_plus_bonus(self):
        self.assertEqual(self._second_bid(first_bid=90, second_config=300), 210 + 75)

    def test_second_filter_slightly_higher_bids_diff_plus_bonus(self):
        self.assertEqual(self._second_bid(first_bid=200, second_config=252), 52 + 75)


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class TenPercentCapClipTest(unittest.TestCase):
    """Per-bid 10% cap clips an individual overlap bid; later polls close the remainder."""

    BONUS = 75

    def test_overlap_bid_clipped_to_cap(self):
        # new filter, target 375, already 90, cap 200 -> clipped to 200.
        target = SearchAndDestroy.overlap_target(True, 300, 300, self.BONUS)
        _t, diff = SearchAndDestroy.compute_overlap_bid(target, 90, 200)
        self.assertEqual(diff, 200)

    def test_clipped_then_converges(self):
        target = SearchAndDestroy.overlap_target(True, 300, 300, self.BONUS)
        _t, diff = SearchAndDestroy.compute_overlap_bid(target, 290, 200)
        self.assertEqual(diff, 85)

    def test_first_bid_clipped_reported_case(self):
        # f1 config 300 on 2000 listing clipped to 200 first bid, f2 config 90 tops up 175 -> 375.
        total = simulate_listing(
            {"query_AI_28": 300, "query_v1_5_2": 90}, ["query_AI_28", "query_v1_5_2"],
            max_bid_allowed=200, overlap_bonus=self.BONUS)
        self.assertEqual(total, 375)


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class OverlapConvergenceTest(unittest.TestCase):
    """Total converges to max(config) + bonus regardless of arrival order (distinct filters)."""

    def _assert_order_independent(self, configured_by_filter, max_bid_allowed, overlap_bonus):
        expected = max(configured_by_filter.values()) + overlap_bonus
        for perm in set(itertools.permutations(configured_by_filter.keys())):
            total = simulate_listing(configured_by_filter, list(perm), max_bid_allowed, overlap_bonus)
            self.assertEqual(total, expected, msg=f"order {list(perm)} gave {total}, expected {expected}")

    def test_reported_two_filter_case(self):
        self._assert_order_independent({"query_AI_28": 300, "query_v1_5_2": 90}, 200, 75)

    def test_gap_exceeds_single_bid_cap(self):
        self._assert_order_independent({"query_small": 60, "query_big": 300}, 200, 75)

    def test_three_overlapping_filters(self):
        self._assert_order_independent({"f_a": 300, "f_b": 90, "f_c": 198}, 200, 75)

    def test_twenty_five_minimum_edge_leaves_small_gap(self):
        total = simulate_listing({"f_a": 300, "f_b": 90}, ["f_a", "f_b"], max_bid_allowed=40, overlap_bonus=75)
        target = 300 + 75
        self.assertLess(total, target)
        self.assertGreaterEqual(target - total, 0)
        self.assertLess(target - total, MIN_BID)


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class ReconstructHighestDesiredTest(unittest.TestCase):
    """Startup seeding: reconstruct highest configured desire per listing from filters that bid."""

    BID_AMT = {
        "E": {"query_AI_28": 300, "query_v1_5_2": 90},
        "A": {"query_AI_34": 252},
    }

    def test_highest_across_multiple_filters(self):
        rows = [
            {"listing_number": 14304682, "filter": "query_AI_28", "prosper_rating": "E"},
            {"listing_number": 14304682, "filter": "query_v1_5_2", "prosper_rating": "E"},
        ]
        result = SearchAndDestroy.reconstruct_highest_desired(rows, self.BID_AMT, {14304682: 200})
        self.assertEqual(result[14304682], 300)

    def test_single_filter_uses_its_config(self):
        rows = [{"listing_number": 999, "filter": "query_v1_5_2", "prosper_rating": "E"}]
        result = SearchAndDestroy.reconstruct_highest_desired(rows, self.BID_AMT, {999: 90})
        self.assertEqual(result[999], 90)

    def test_missing_config_key_falls_back_to_bidded(self):
        rows = [{"listing_number": 555, "filter": "query_deleted", "prosper_rating": "E"}]
        result = SearchAndDestroy.reconstruct_highest_desired(rows, self.BID_AMT, {555: 120})
        self.assertEqual(result[555], 120)

    def test_listing_with_no_filter_rows_falls_back_to_bidded(self):
        result = SearchAndDestroy.reconstruct_highest_desired([], self.BID_AMT, {777: 150})
        self.assertEqual(result[777], 150)

    def test_restart_topup_not_full_rebid(self):
        # Restart: reconstruct desired=300 for a listing bid to 200 (clamped). A NEW filter overlap
        # tops up 175 toward 375, not a full 300 re-bid.
        seeded = SearchAndDestroy.reconstruct_highest_desired(
            [{"listing_number": 1, "filter": "query_AI_28", "prosper_rating": "E"}], self.BID_AMT, {1: 200})
        target = SearchAndDestroy.overlap_target(True, 90, seeded[1], 75)
        _t, topup = SearchAndDestroy.compute_overlap_bid(target, 200, 200)
        self.assertEqual(topup, 175)
        self.assertNotEqual(topup, 300)


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class ShouldSurfaceInvestedListingTest(unittest.TestCase):
    """Surfacing gate: surface while target - already_invested >= $25 (takes target directly)."""

    def test_surfaces_when_gap_at_least_25(self):
        self.assertTrue(SearchAndDestroy.should_surface_invested_listing(339, 375))

    def test_does_not_surface_when_gap_below_25(self):
        self.assertFalse(SearchAndDestroy.should_surface_invested_listing(355, 375))

    def test_does_not_surface_at_target(self):
        self.assertFalse(SearchAndDestroy.should_surface_invested_listing(375, 375))

    def test_does_not_surface_above_target(self):
        self.assertFalse(SearchAndDestroy.should_surface_invested_listing(400, 375))

    def test_surfaces_exactly_at_25_gap(self):
        self.assertTrue(SearchAndDestroy.should_surface_invested_listing(350, 375))


@unittest.skipUnless(SearchAndDestroy is not None, f"SearchAndDestroy import failed: {IMPORT_ERROR}")
class GateAndSizingEndToEndTest(unittest.TestCase):
    """Both layers together: the reported cross-filter case reaches 375 and terminates."""

    BONUS = 75

    def test_reported_14138534_reaches_375(self):
        total, _ = simulate_listing_with_gate(
            {"query_AI_5_2": 120, "query_v1_5_2": 300}, ["query_AI_5_2", "query_v1_5_2"],
            max_bid_allowed=219, overlap_bonus=self.BONUS)
        self.assertEqual(total, 375)

    def test_reported_case_terminates(self):
        total, num_bids = simulate_listing_with_gate(
            {"query_AI_5_2": 120, "query_v1_5_2": 300}, ["query_AI_5_2", "query_v1_5_2"],
            max_bid_allowed=219, overlap_bonus=self.BONUS, polls=100)
        self.assertEqual(total, 375)
        # 120, then clipped overlap 219 (total 339), then final top-up 36 (375) = 3 bids.
        self.assertEqual(num_bids, 3)

    def test_gate_aware_convergence_order_independent(self):
        cfg = {"query_AI_5_2": 120, "query_v1_5_2": 300}
        for perm in set(itertools.permutations(cfg.keys())):
            total, _ = simulate_listing_with_gate(cfg, list(perm), max_bid_allowed=219, overlap_bonus=self.BONUS)
            self.assertEqual(total, max(cfg.values()) + self.BONUS, msg=f"order {list(perm)}")


if __name__ == "__main__":
    unittest.main()
