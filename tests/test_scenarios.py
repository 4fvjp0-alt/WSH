"""실제로 여행 다니면서 생기는 상황들.

각 시나리오는 '이렇게 계산되어야 한다'는 합의를 코드로 고정한 것이다.
엔진을 고치다 이 중 하나라도 깨지면 사람이 납득하지 못하는 정산이 된 것이다.
"""

import unittest
from datetime import date, timedelta

from helpers import expense, ids, make_trip
from settle.engine import apply_plan, compute
from settle.invariants import cross_check_total, verify
from settle.models import (
    POT_ID, SPLIT_EXACT, SPLIT_WEIGHT, TRANSFER_POT_IN, Payment, Transfer,
)

DAY1 = date(2025, 5, 1)


class ScenarioCase(unittest.TestCase):
    def check(self, trip):
        """모든 시나리오는 폐루프 검증을 통과해야 한다."""
        result = compute(trip)
        verification = verify(result)
        self.assertTrue(verification.ok,
                        "; ".join(f"{c.code} {c.detail}" for c in verification.failures))
        self.assertTrue(cross_check_total(result).ok)
        after = apply_plan(result.rounded_net, result.plan)
        self.assertTrue(all(v == 0 for v in after.values()))
        return result

    def net(self, result, trip, name):
        return result.rounded_net[ids(trip)[name]]


class TestEverydayScenarios(ScenarioCase):
    def test_01_one_person_pays_everything(self):
        """총무 한 명이 전부 결제하고 나중에 걷는다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense(f"e{i}", 30000, m["민수"]) for i in range(5)]
        result = self.check(trip)
        self.assertEqual(self.net(result, trip, "민수"), 100000)
        self.assertEqual(len(result.plan), 2)
        self.assertTrue(all(t.to_id == m["민수"] for t in result.plan))

    def test_02_everyone_pays_something(self):
        """각자 다른 걸 결제해 우연히 딱 맞는 경우 — 송금 0회."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense(f"e{i}", 30000, mid) for i, mid in enumerate(m.values())]
        result = self.check(trip)
        self.assertEqual(result.plan, [])

    def test_03_one_bill_split_across_two_cards(self):
        """한 계산서를 카드 두 장으로 나눠 긁었다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense(
            "e1", 90000, [Payment(m["민수"], 50000), Payment(m["지영"], 40000)])]
        result = self.check(trip)
        self.assertEqual(result.balances[m["민수"]].paid, 50000)
        self.assertEqual(result.balances[m["지영"]].paid, 40000)
        self.assertEqual(self.net(result, trip, "현우"), -30000)

    def test_04_non_drinker_excluded_from_alcohol(self):
        """술 안 마시는 사람은 술값에서 빠진다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [
            expense("e1", 60000, m["민수"], category="식비"),
            expense("e2", 40000, m["지영"], category="주류",
                    participants=[m["민수"], m["지영"]]),
        ]
        result = self.check(trip)
        self.assertEqual(result.balances[m["현우"]].owed, 20000)

    def test_05_child_counts_as_half(self):
        """아이는 0.5인분."""
        trip = make_trip(("엄마", "아빠", "아이"))
        trip.members[2].weight = 0.5
        m = ids(trip)
        trip.expenses = [expense("e1", 50000, m["엄마"], split_method=SPLIT_WEIGHT)]
        result = self.check(trip)
        self.assertEqual(result.balances[m["아이"]].owed, 10000)
        self.assertEqual(result.balances[m["아빠"]].owed, 20000)

    def test_06_late_join_and_early_leave(self):
        """중간 합류자와 조기 귀가자는 그 기간 지출에만 참여한다."""
        trip = make_trip()
        trip.members[2].joined = DAY1 + timedelta(days=2)   # 3일차 합류
        trip.members[0].left = DAY1 + timedelta(days=1)     # 2일차까지만
        m = ids(trip)
        trip.expenses = [
            expense("e1", 20000, m["지영"], day=DAY1),
            expense("e2", 20000, m["지영"], day=DAY1 + timedelta(days=3)),
        ]
        result = self.check(trip)
        self.assertEqual(result.balances[m["현우"]].owed, 10000)
        self.assertEqual(result.balances[m["민수"]].owed, 10000)
        self.assertEqual(result.balances[m["지영"]].owed, 20000)

    def test_07_room_assignment_with_exact_amounts(self):
        """숙소 방 배정에 따라 금액이 다르다."""
        trip = make_trip(("민수", "지영", "현우", "서연"))
        m = ids(trip)
        trip.expenses = [expense(
            "e1", 400000, m["민수"], split_method=SPLIT_EXACT,
            split_values={m["민수"]: 150000, m["지영"]: 150000,
                          m["현우"]: 50000, m["서연"]: 50000})]
        result = self.check(trip)
        self.assertEqual(result.balances[m["현우"]].owed, 50000)
        self.assertEqual(result.balances[m["민수"]].owed, 150000)

    def test_08_mid_trip_transfer_is_credited(self):
        """여행 중 이미 보낸 돈은 최종 정산에서 빠진다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense("e1", 30000, m["민수"])]
        trip.transfers = [Transfer(id="t1", from_id=m["지영"], to_id=m["민수"],
                                   amount=10000, day=DAY1)]
        result = self.check(trip)
        self.assertEqual(self.net(result, trip, "지영"), 0)
        self.assertEqual(len(result.plan), 1)

    def test_09_personal_purchase_excluded(self):
        """기념품 같은 개인 지출은 통계엔 남고 정산에선 빠진다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [
            expense("e1", 30000, m["민수"]),
            expense("e2", 88000, m["지영"], category="쇼핑", exclude_from_settlement=True),
        ]
        result = self.check(trip)
        self.assertEqual(result.total, 30000)
        self.assertEqual(result.personal_total, 88000)
        self.assertEqual(self.net(result, trip, "지영"), -10000)

    def test_10_prepaid_deposit_before_the_trip(self):
        """여행 전에 미리 낸 예약금도 그대로 정산에 들어간다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense("e1", 300000, m["민수"],
                                 day=DAY1 - timedelta(days=30), category="숙박")]
        result = self.check(trip)
        self.assertEqual(result.balances[m["현우"]].owed, 100000)

    def test_11_refund_reduces_everyone(self):
        """취소·환불은 음수 지출로 넣으면 모두에게 되돌아간다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [
            expense("e1", 90000, m["민수"], category="숙박"),
            expense("e2", -30000, m["민수"], category="숙박", title="숙박 일부 환불"),
        ]
        result = self.check(trip)
        self.assertEqual(result.total, 60000)
        self.assertEqual(result.balances[m["현우"]].owed, 20000)

    def test_12_multi_currency_trip(self):
        """엔화 결제와 원화 결제가 섞인 해외여행."""
        trip = make_trip(rates={"JPY": 9.2})
        m = ids(trip)
        trip.expenses = [
            expense("e1", 30000, m["민수"], currency="JPY"),
            expense("e2", 60000, m["지영"]),
        ]
        result = self.check(trip)
        self.assertEqual(result.total, 30000 * 92 // 10 + 60000)
        self.assertEqual(result.by_currency["JPY"], 30000)

    def test_13_shared_pot(self):
        """각자 회비를 걷어 공금으로 쓰고 남은 돈은 돌려받는다."""
        trip = make_trip()
        m = ids(trip)
        trip.transfers = [
            Transfer(id=f"p{i}", from_id=mid, to_id=POT_ID, amount=100000,
                     kind=TRANSFER_POT_IN, day=DAY1)
            for i, mid in enumerate(m.values())
        ]
        trip.expenses = [expense("e1", 210000, POT_ID)]
        result = self.check(trip)
        self.assertEqual(result.pot.balance, 90000)
        refunds = sorted(t.amount for t in result.plan if t.from_id == POT_ID)
        self.assertEqual(refunds, [30000, 30000, 30000])

    def test_14_remainder_is_shared_over_many_expenses(self):
        """1원 나머지가 한 사람에게만 몰리지 않아야 한다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense(f"e{i}", 10000, m["민수"]) for i in range(30)]
        result = self.check(trip)
        owed = [result.balances[mid].owed for mid in m.values()]
        self.assertEqual(sum(owed), 300000)
        self.assertLess(max(owed) - min(owed), 10,
                        f"나머지 배분이 한쪽으로 쏠렸습니다: {owed}")

    def test_15_someone_pays_extra_on_purpose(self):
        """'내가 좀 더 낼게' 를 반영하고 나머지를 나눈다."""
        trip = make_trip()
        m = ids(trip)
        trip.expenses = [expense("e1", 100000, m["지영"],
                                 adjustments={m["민수"]: 40000})]
        result = self.check(trip)
        self.assertEqual(result.balances[m["민수"]].owed, 60000)
        self.assertEqual(result.balances[m["지영"]].owed, 20000)
        self.assertEqual(result.balances[m["현우"]].owed, 20000)

    def test_16_couple_counted_as_two(self):
        """커플이 한 사람 이름으로 2인분 참여."""
        trip = make_trip(("민수", "지영커플", "현우"))
        trip.members[1].weight = 2
        m = ids(trip)
        trip.expenses = [expense("e1", 40000, m["민수"], split_method=SPLIT_WEIGHT)]
        result = self.check(trip)
        self.assertEqual(result.balances[m["지영커플"]].owed, 20000)

    def test_17_rounding_to_thousand(self):
        """잔돈 없이 천원 단위로 송금하고 싶다."""
        trip = make_trip(rounding_unit=1000)
        m = ids(trip)
        trip.expenses = [expense("e1", 100000, m["민수"]), expense("e2", 33333, m["지영"])]
        result = self.check(trip)
        self.assertTrue(all(t.amount % 1000 == 0 for t in result.plan))

    def test_18_nothing_to_settle(self):
        """지출이 없으면 송금도 없다."""
        trip = make_trip()
        result = self.check(trip)
        self.assertEqual(result.plan, [])
        self.assertEqual(result.total, 0)

    def test_19_everything_at_once(self):
        """위 상황이 한 여행에 전부 섞여 있어도 맞아야 한다."""
        trip = make_trip(("민수", "지영", "현우", "서연"), rates={"JPY": 9.2},
                         rounding_unit=100)
        trip.members[3].joined = DAY1 + timedelta(days=1)
        trip.members[2].weight = 0.5
        m = ids(trip)
        trip.transfers = [
            Transfer(id="p1", from_id=m["민수"], to_id=POT_ID, amount=200000,
                     kind=TRANSFER_POT_IN, day=DAY1),
            Transfer(id="p2", from_id=m["지영"], to_id=POT_ID, amount=200000,
                     kind=TRANSFER_POT_IN, day=DAY1),
            Transfer(id="t1", from_id=m["서연"], to_id=m["민수"], amount=50000,
                     day=DAY1 + timedelta(days=1)),
        ]
        trip.expenses = [
            expense("e1", 300000, m["민수"], day=DAY1, category="항공/기차",
                    participants=list(m.values())),
            expense("e2", 50000, POT_ID, currency="JPY", day=DAY1, category="숙박",
                    split_method=SPLIT_WEIGHT),
            expense("e3", 12000, [Payment(m["지영"], 8000), Payment(m["현우"], 4000)],
                    currency="JPY", day=DAY1 + timedelta(days=1), category="주류",
                    adjustments={m["현우"]: 3000}),
            expense("e4", -4000, POT_ID, currency="JPY",
                    day=DAY1 + timedelta(days=2), category="숙박"),
            expense("e5", 30000, m["서연"], day=DAY1 + timedelta(days=2),
                    category="쇼핑", exclude_from_settlement=True),
            expense("e6", 24000, m["서연"], currency="JPY",
                    day=DAY1 + timedelta(days=2), category="관광/입장료",
                    split_method=SPLIT_EXACT,
                    split_values={m["민수"]: 6000, m["지영"]: 6000,
                                  m["현우"]: 6000, m["서연"]: 6000}),
        ]
        result = self.check(trip)
        self.assertGreater(result.total, 0)
        self.assertEqual(result.personal_total, 30000)
        self.assertLessEqual(len(result.plan), 4)


if __name__ == "__main__":
    unittest.main()
