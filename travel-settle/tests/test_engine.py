import random
import unittest
from datetime import date
from itertools import combinations

from helpers import expense, ids, make_trip
from settle.engine import (
    _optimal_groups, apply_plan, compute, minimal_transfers,
)
from settle.models import POT_ID, TRANSFER_POT_IN, Payment, Transfer
from settle.invariants import verify


def brute_force_max_groups(values: list[int]) -> int:
    """합이 0인 그룹으로 나눌 수 있는 최대 개수 (완전 탐색). DP 검증용."""
    n = len(values)
    memo: dict[int, int] = {}

    def solve(mask: int) -> int:
        if mask == 0:
            return 0
        if mask in memo:
            return memo[mask]
        low = (mask & -mask).bit_length() - 1
        rest = [i for i in range(n) if mask >> i & 1 and i != low]
        best = -1
        for size in range(len(rest) + 1):
            for extra in combinations(rest, size):
                group = (1 << low) | sum(1 << i for i in extra)
                if sum(values[i] for i in range(n) if group >> i & 1) != 0:
                    continue
                sub = solve(mask ^ group)
                if sub >= 0:
                    best = max(best, sub + 1)
        memo[mask] = best
        return best

    return solve((1 << n) - 1)


class TestMinimalTransfers(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(minimal_transfers({}), [])
        self.assertEqual(minimal_transfers({"a": 0, "b": 0}), [])

    def test_simple_pair(self):
        plan = minimal_transfers({"a": 1000, "b": -1000})
        self.assertEqual(len(plan), 1)
        self.assertEqual((plan[0].from_id, plan[0].to_id, plan[0].amount), ("b", "a", 1000))

    def test_plan_always_zeroes_out(self):
        rng = random.Random(7)
        for _ in range(400):
            size = rng.randint(2, 8)
            values = [rng.randint(-50, 50) * 100 for _ in range(size - 1)]
            values.append(-sum(values))
            nets = {f"m{i}": v for i, v in enumerate(values)}
            plan = minimal_transfers(nets)
            after = apply_plan(nets, plan)
            self.assertTrue(all(v == 0 for v in after.values()))
            nonzero = sum(1 for v in nets.values() if v != 0)
            self.assertLessEqual(len(plan), max(0, nonzero - 1))
            self.assertTrue(all(t.amount > 0 for t in plan))

    def test_grouping_matches_brute_force(self):
        rng = random.Random(11)
        for _ in range(120):
            size = rng.randint(2, 7)
            values = [rng.randint(-5, 5) for _ in range(size - 1)]
            values.append(-sum(values))
            items = [(f"m{i}", v) for i, v in enumerate(values) if v != 0]
            if not items:
                continue
            groups = _optimal_groups(items)
            self.assertEqual(
                len(groups), brute_force_max_groups([v for _, v in items]),
                f"values={values}",
            )
            # 그룹은 서로소이고 각 그룹의 합은 0이어야 한다
            seen = set()
            for group in groups:
                self.assertEqual(sum(v for _, v in group), 0)
                for name, _ in group:
                    self.assertNotIn(name, seen)
                    seen.add(name)

    def test_no_one_both_sends_and_receives(self):
        rng = random.Random(3)
        for _ in range(200):
            values = [rng.randint(-30, 30) for _ in range(5)]
            values.append(-sum(values))
            nets = {f"m{i}": v for i, v in enumerate(values)}
            plan = minimal_transfers(nets)
            senders = {t.from_id for t in plan}
            receivers = {t.to_id for t in plan}
            self.assertFalse(senders & receivers)


class TestCompute(unittest.TestCase):
    def test_balances(self):
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense("e1", 30000, m["민수"]), expense("e2", 60000, m["지영"])]
        result = compute(trip)
        self.assertEqual(result.total, 90000)
        self.assertEqual(result.balances[m["민수"]].paid, 30000)
        self.assertEqual(result.balances[m["민수"]].owed, 30000)
        self.assertEqual(result.balances[m["현우"]].net, -30000)

    def test_existing_transfer_reduces_debt(self):
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense("e1", 30000, m["민수"])]
        trip.transfers = [Transfer(id="t1", from_id=m["현우"], to_id=m["민수"], amount=10000)]
        result = compute(trip)
        self.assertEqual(result.balances[m["현우"]].net, 0)
        self.assertEqual(result.balances[m["민수"]].net, 10000)

    def test_personal_expense_excluded(self):
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [
            expense("e1", 30000, m["민수"]),
            expense("e2", 50000, m["지영"], exclude_from_settlement=True),
        ]
        result = compute(trip)
        self.assertEqual(result.total, 30000)
        self.assertEqual(result.personal_total, 50000)
        self.assertEqual(result.balances[m["지영"]].paid, 0)
        self.assertEqual(result.balances[m["지영"]].personal, 50000)

    def test_rounding_unit_applies_to_plan(self):
        trip = make_trip(rounding_unit=1000)
        m = ids(trip)
        trip.expenses = [expense("e1", 10000, m["민수"])]
        result = compute(trip)
        self.assertTrue(all(t.amount % 1000 == 0 for t in result.plan))
        self.assertEqual(sum(result.rounded_net.values()), 0)
        self.assertTrue(verify(result).ok)

    def test_by_category_and_day(self):
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [
            expense("e1", 30000, m["민수"], category="식비", day=date(2025, 5, 1)),
            expense("e2", 20000, m["지영"], category="식비", day=date(2025, 5, 2)),
            expense("e3", 10000, m["현우"], category="교통", day=date(2025, 5, 2)),
        ]
        result = compute(trip)
        self.assertEqual(result.by_category["식비"], 50000)
        self.assertEqual(result.by_day["2025-05-02"], 30000)


class TestPot(unittest.TestCase):
    def _pot_trip(self):
        trip = make_trip()
        m = ids(trip)
        trip.transfers = [
            Transfer(id=f"p{i}", from_id=mid, to_id=POT_ID, amount=100000,
                     kind=TRANSFER_POT_IN)
            for i, mid in enumerate(m.values())
        ]
        return trip, m

    def test_leftover_is_refunded(self):
        trip, m = self._pot_trip()
        trip.expenses = [expense("e1", 150000, POT_ID)]
        result = compute(trip)
        self.assertEqual(result.pot.contributed, 300000)
        self.assertEqual(result.pot.spent, 150000)
        self.assertEqual(result.pot.balance, 150000)
        # 남은 공금은 각자에게 5만원씩 돌아간다
        refunds = {t.to_id: t.amount for t in result.plan if t.from_id == POT_ID}
        self.assertEqual(sorted(refunds.values()), [50000, 50000, 50000])
        self.assertTrue(verify(result).ok)

    def test_overspent_pot_is_warned(self):
        trip, m = self._pot_trip()
        trip.expenses = [expense("e1", 400000, POT_ID)]
        result = compute(trip)
        self.assertEqual(result.pot.balance, -100000)
        self.assertTrue(any("공금" in w for w in result.warnings))
        self.assertTrue(verify(result).ok)

    def test_mixed_pot_and_personal_cards(self):
        trip, m = self._pot_trip()
        trip.expenses = [
            expense("e1", 90000, POT_ID),
            expense("e2", 60000, m["민수"]),
        ]
        result = compute(trip)
        self.assertTrue(verify(result).ok)
        after = apply_plan(result.rounded_net, result.plan)
        self.assertTrue(all(v == 0 for v in after.values()))


if __name__ == "__main__":
    unittest.main()
