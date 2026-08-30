"""폐루프 검증 — 무작위 여행 수천 건에 대해 불변식이 깨지는지 본다.

시나리오 테스트는 '사람이 생각해낸 상황'만 덮는다. 사람이 생각 못 한 조합
(환불 + 다중 결제자 + 부분 참여 + 반올림이 동시에 겹치는 경우 같은)은
여기서 잡는다. 실패하면 출력된 시드로 그대로 재현된다.

건수는 TRAVEL_SETTLE_FUZZ 환경변수로 조절한다 (기본 1500).
"""

import os
import unittest

from helpers import *  # noqa: F401,F403  (sys.path 설정)
from settle.engine import apply_plan, compute
from settle.fuzz import random_trip
from settle.invariants import cross_check_total, verify

COUNT = int(os.environ.get("TRAVEL_SETTLE_FUZZ", "1500"))


class TestInvariantsUnderRandomTrips(unittest.TestCase):
    def test_random_trips_hold_all_invariants(self):
        failures = []
        for seed in range(COUNT):
            trip = random_trip(seed)
            try:
                result = compute(trip)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"seed={seed} 계산 실패: {type(exc).__name__}: {exc}")
                continue
            verification = verify(result)
            if not verification.ok:
                failures.append(
                    f"seed={seed} " + "; ".join(
                        f"{c.code}({c.detail})" for c in verification.failures))
            extra = cross_check_total(result)
            if not extra.ok:
                failures.append(f"seed={seed} {extra.code}({extra.detail})")
            after = apply_plan(result.rounded_net, result.plan)
            residual = {k: v for k, v in after.items() if v != 0}
            if residual:
                failures.append(f"seed={seed} 역검증 잔액 {residual}")
            if len(failures) >= 5:
                break
        self.assertFalse(failures, "\n".join(failures))

    def test_random_trips_serialize_roundtrip(self):
        """저장했다 다시 읽어도 정산 결과가 같아야 한다."""
        from settle.models import Trip

        for seed in range(min(COUNT, 200)):
            trip = random_trip(seed)
            restored = Trip.from_dict(trip.to_dict())
            before = compute(trip)
            after = compute(restored)
            self.assertEqual(before.total, after.total, f"seed={seed}")
            self.assertEqual(before.rounded_net, after.rounded_net, f"seed={seed}")
            self.assertEqual(
                [(t.from_id, t.to_id, t.amount) for t in before.plan],
                [(t.from_id, t.to_id, t.amount) for t in after.plan],
                f"seed={seed}",
            )

    def test_result_is_deterministic(self):
        """같은 입력이면 항상 같은 송금안이 나와야 한다."""
        for seed in range(min(COUNT, 200)):
            trip = random_trip(seed)
            first = compute(trip)
            second = compute(random_trip(seed))
            self.assertEqual(
                [(t.from_id, t.to_id, t.amount) for t in first.plan],
                [(t.from_id, t.to_id, t.amount) for t in second.plan],
                f"seed={seed}",
            )


if __name__ == "__main__":
    unittest.main()
