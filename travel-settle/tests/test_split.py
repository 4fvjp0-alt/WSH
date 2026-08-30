import unittest
from datetime import date

from helpers import expense, ids, make_trip
from settle.models import (
    POT_ID, SPLIT_EXACT, SPLIT_PERCENT, SPLIT_WEIGHT, Expense, Payment,
)
from settle.split import SettleError, split_expense


class TestEqualSplit(unittest.TestCase):
    def test_basic(self):
        trip = make_trip()
        m = ids(trip)
        result = split_expense(trip, expense("e1", 30000, m["민수"]))
        self.assertEqual(result.owed, {m["민수"]: 10000, m["지영"]: 10000, m["현우"]: 10000})
        self.assertEqual(result.paid, {m["민수"]: 30000})

    def test_indivisible_amount_sums_exactly(self):
        trip = make_trip()
        m = ids(trip)
        result = split_expense(trip, expense("e1", 10000, m["민수"]))
        self.assertEqual(sum(result.owed.values()), 10000)
        self.assertEqual(sorted(result.owed.values()), [3333, 3333, 3334])

    def test_explicit_participants(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 20000, m["민수"], participants=[m["민수"], m["지영"]])
        result = split_expense(trip, e)
        self.assertEqual(result.owed, {m["민수"]: 10000, m["지영"]: 10000})


class TestAdjustments(unittest.TestCase):
    def test_extra_payer_takes_adjustment_then_equal_rest(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 100000, m["민수"], adjustments={m["민수"]: 20000})
        result = split_expense(trip, e)
        self.assertEqual(sum(result.owed.values()), 100000)
        self.assertEqual(result.owed[m["민수"]], 20000 + result.owed[m["지영"]] + 1)
        self.assertEqual(result.owed[m["지영"]] + result.owed[m["현우"]]
                         + (result.owed[m["민수"]] - 20000), 80000)

    def test_adjustment_makes_non_participant_a_participant(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 30000, m["민수"], participants=[m["지영"]],
                    adjustments={m["현우"]: 10000})
        result = split_expense(trip, e)
        self.assertIn(m["현우"], result.owed)
        self.assertEqual(sum(result.owed.values()), 30000)

    def test_adjustment_larger_than_total_is_rejected(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 10000, m["민수"], adjustments={m["민수"]: 20000})
        with self.assertRaises(SettleError):
            split_expense(trip, e)


class TestWeightAndPercent(unittest.TestCase):
    def test_member_default_weight_used(self):
        trip = make_trip()
        trip.members[2].weight = 0.5
        m = ids(trip)
        e = expense("e1", 25000, m["민수"], split_method=SPLIT_WEIGHT)
        result = split_expense(trip, e)
        self.assertEqual(result.owed[m["민수"]], 10000)
        self.assertEqual(result.owed[m["현우"]], 5000)

    def test_percent_must_total_100(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 10000, m["민수"], split_method=SPLIT_PERCENT,
                    split_values={m["민수"]: 50, m["지영"]: 40})
        with self.assertRaises(SettleError):
            split_expense(trip, e)

    def test_percent_split(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 100000, m["민수"], split_method=SPLIT_PERCENT,
                    split_values={m["민수"]: 50, m["지영"]: 30, m["현우"]: 20})
        result = split_expense(trip, e)
        self.assertEqual(result.owed[m["민수"]], 50000)
        self.assertEqual(result.owed[m["현우"]], 20000)

    def test_split_values_imply_participation(self):
        trip = make_trip()
        m = ids(trip)
        trip.members[2].joined = date(2025, 5, 3)  # 나중 합류
        e = expense("e1", 30000, m["민수"], day=date(2025, 5, 1),
                    split_method=SPLIT_WEIGHT, split_values={m["현우"]: 1})
        result = split_expense(trip, e)
        self.assertIn(m["현우"], result.owed)


class TestExact(unittest.TestCase):
    def test_exact_values(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 100000, m["민수"], split_method=SPLIT_EXACT,
                    split_values={m["민수"]: 50000, m["지영"]: 30000, m["현우"]: 20000})
        result = split_expense(trip, e)
        self.assertEqual(result.owed[m["지영"]], 30000)

    def test_exact_must_match_total(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 100000, m["민수"], split_method=SPLIT_EXACT,
                    split_values={m["민수"]: 50000, m["지영"]: 30000})
        with self.assertRaises(SettleError):
            split_expense(trip, e)

    def test_exact_rejects_adjustments(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 100000, m["민수"], split_method=SPLIT_EXACT,
                    split_values={m["민수"]: 100000}, adjustments={m["지영"]: 1000})
        with self.assertRaises(SettleError):
            split_expense(trip, e)


class TestPayments(unittest.TestCase):
    def test_multiple_payers(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 90000, [Payment(m["민수"], 60000), Payment(m["지영"], 30000)])
        result = split_expense(trip, e)
        self.assertEqual(result.paid, {m["민수"]: 60000, m["지영"]: 30000})

    def test_payment_sum_must_match(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 90000, [Payment(m["민수"], 60000)])
        e.amount = 90000
        e.payments = [Payment(m["민수"], 60000)]
        with self.assertRaises(SettleError):
            split_expense(trip, e)

    def test_missing_payer(self):
        trip = make_trip()
        e = Expense(id="e1", title="x", amount=1000, payments=[])
        with self.assertRaises(SettleError):
            split_expense(trip, e)

    def test_pot_cannot_pay_personal_expense(self):
        trip = make_trip()
        e = expense("e1", 10000, POT_ID, exclude_from_settlement=True)
        with self.assertRaises(SettleError):
            split_expense(trip, e)

    def test_pot_cannot_be_participant(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", 10000, m["민수"], participants=[POT_ID])
        with self.assertRaises(SettleError):
            split_expense(trip, e)


class TestRefunds(unittest.TestCase):
    def test_negative_amount_splits_negatively(self):
        trip = make_trip()
        m = ids(trip)
        result = split_expense(trip, expense("e1", -30000, m["민수"]))
        self.assertEqual(sum(result.owed.values()), -30000)
        self.assertTrue(all(v < 0 for v in result.owed.values()))

    def test_refund_with_multiple_payers(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", -9000, [Payment(m["민수"], -6000), Payment(m["지영"], -3000)])
        result = split_expense(trip, e)
        self.assertEqual(sum(result.paid.values()), -9000)

    def test_refund_rejects_adjustment(self):
        trip = make_trip()
        m = ids(trip)
        e = expense("e1", -10000, m["민수"], adjustments={m["민수"]: 1000})
        with self.assertRaises(SettleError):
            split_expense(trip, e)


class TestCurrency(unittest.TestCase):
    def test_converts_with_trip_rate(self):
        trip = make_trip()
        trip.rates["JPY"] = 9.2
        m = ids(trip)
        result = split_expense(trip, expense("e1", 10000, m["민수"], currency="JPY"))
        self.assertEqual(result.base_total, 92000)
        self.assertEqual(sum(result.owed.values()), 92000)

    def test_per_expense_rate_overrides(self):
        trip = make_trip()
        trip.rates["JPY"] = 9.2
        m = ids(trip)
        result = split_expense(trip, expense("e1", 10000, m["민수"], currency="JPY", rate=10.0))
        self.assertEqual(result.base_total, 100000)

    def test_missing_rate_is_an_error(self):
        trip = make_trip()
        m = ids(trip)
        with self.assertRaises(SettleError):
            split_expense(trip, expense("e1", 10000, m["민수"], currency="JPY"))


class TestPartialAttendance(unittest.TestCase):
    def test_late_joiner_excluded_from_earlier_days(self):
        trip = make_trip()
        trip.members[2].joined = date(2025, 5, 3)
        m = ids(trip)
        early = split_expense(trip, expense("e1", 20000, m["민수"], day=date(2025, 5, 1)))
        later = split_expense(trip, expense("e2", 30000, m["민수"], day=date(2025, 5, 3)))
        self.assertNotIn(m["현우"], early.owed)
        self.assertIn(m["현우"], later.owed)

    def test_early_leaver_excluded_from_later_days(self):
        trip = make_trip()
        trip.members[0].left = date(2025, 5, 2)
        m = ids(trip)
        later = split_expense(trip, expense("e1", 20000, m["지영"], day=date(2025, 5, 4)))
        self.assertNotIn(m["민수"], later.owed)


if __name__ == "__main__":
    unittest.main()
