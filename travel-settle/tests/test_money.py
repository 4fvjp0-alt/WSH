import unittest
from decimal import Decimal

from helpers import *  # noqa: F401,F403  (sys.path 설정)
from settle.money import (
    allocate, convert, format_money, from_minor, round_preserving_sum,
    round_to_unit, to_minor,
)


class TestAllocate(unittest.TestCase):
    def test_sum_is_exact_for_indivisible_amounts(self):
        for total in range(0, 200):
            for parts in range(1, 8):
                shares = allocate(total, [1] * parts)
                self.assertEqual(sum(shares), total, f"{total}/{parts}")
                self.assertLessEqual(max(shares) - min(shares), 1)

    def test_weighted_split(self):
        self.assertEqual(allocate(300, [1, 2]), [100, 200])
        self.assertEqual(sum(allocate(1000, [0.5, 1, 1.5])), 1000)

    def test_zero_weight_gets_nothing(self):
        self.assertEqual(allocate(100, [1, 0, 1]), [50, 0, 50])

    def test_negative_total_keeps_sum(self):
        for total in range(-100, 0):
            shares = allocate(total, [1, 1, 1])
            self.assertEqual(sum(shares), total)
            self.assertTrue(all(s <= 0 for s in shares))

    def test_seed_rotates_remainder(self):
        # 나머지 1원이 항상 같은 사람에게 가지 않아야 한다
        winners = {allocate(10, [1, 1, 1], seed=s).index(4) for s in range(3)}
        self.assertGreater(len(winners), 1)

    def test_rejects_negative_or_zero_weights(self):
        with self.assertRaises(ValueError):
            allocate(100, [1, -1])
        with self.assertRaises(ValueError):
            allocate(100, [0, 0])

    def test_empty_only_allowed_for_zero(self):
        self.assertEqual(allocate(0, []), [])
        with self.assertRaises(ValueError):
            allocate(1, [])


class TestParsingAndFormatting(unittest.TestCase):
    def test_to_minor(self):
        self.assertEqual(to_minor("12,500원", "KRW"), 12500)
        self.assertEqual(to_minor("12.34", "USD"), 1234)
        self.assertEqual(to_minor(Decimal("0.005"), "USD"), 1)  # 반올림
        self.assertEqual(to_minor(1500, "JPY"), 1500)
        with self.assertRaises(ValueError):
            to_minor("사천원", "KRW")

    def test_from_minor_roundtrip(self):
        self.assertEqual(from_minor(1234, "USD"), Decimal("12.34"))
        self.assertEqual(from_minor(1234, "KRW"), Decimal(1234))

    def test_format(self):
        self.assertEqual(format_money(1234567, "KRW"), "1,234,567원")
        self.assertEqual(format_money(-1234, "USD"), "-$12.34")
        self.assertEqual(format_money(500, "JPY"), "500엔")
        self.assertEqual(format_money(1000, "THB"), "10.00 THB")


class TestRounding(unittest.TestCase):
    def test_round_to_unit(self):
        self.assertEqual(round_to_unit(1250, 100), 1300)
        self.assertEqual(round_to_unit(1249, 100), 1200)
        self.assertEqual(round_to_unit(-1250, 100), -1300)

    def test_round_preserving_sum_keeps_zero(self):
        for values in ([3333, -1234, -2099], [1, -1], [99, 1, -100], [0, 0]):
            for unit in (10, 100, 1000):
                rounded = round_preserving_sum(values, unit)
                self.assertEqual(sum(rounded), sum(values))
                self.assertTrue(all(v % unit == 0 for v in rounded))

    def test_rejects_when_sum_not_multiple(self):
        with self.assertRaises(ValueError):
            round_preserving_sum([5, 0], 100)


class TestConvert(unittest.TestCase):
    def test_same_currency_is_identity(self):
        self.assertEqual(convert(1000, "KRW", "KRW", None), 1000)

    def test_jpy_to_krw(self):
        self.assertEqual(convert(10000, "JPY", "KRW", 9.1), 91000)

    def test_usd_cents_to_krw(self):
        self.assertEqual(convert(1234, "USD", "KRW", 1300), 16042)

    def test_negative_amount(self):
        self.assertEqual(convert(-1000, "JPY", "KRW", 9.5), -9500)

    def test_missing_rate(self):
        with self.assertRaises(ValueError):
            convert(100, "JPY", "KRW", None)


if __name__ == "__main__":
    unittest.main()
