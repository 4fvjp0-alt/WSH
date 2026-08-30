#!/usr/bin/env python3
"""전체 테스트 실행기.

    python3 tests/run.py                 # 기본 (무작위 1,500건 포함)
    python3 tests/run.py --fuzz 20000    # 폐루프 검증 강도 높이기
    python3 tests/run.py -v
"""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main() -> int:
    parser = argparse.ArgumentParser(description="여행 정산 계산기 테스트")
    parser.add_argument("--fuzz", type=int, help="무작위 여행 검증 건수 (기본 1500)")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-k", "--pattern", default="test_*.py")
    args = parser.parse_args()

    if args.fuzz:
        os.environ["TRAVEL_SETTLE_FUZZ"] = str(args.fuzz)

    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern=args.pattern,
                            top_level_dir=str(ROOT / "tests"))
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
