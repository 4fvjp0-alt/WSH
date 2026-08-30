import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from helpers import *  # noqa: F401,F403
from settle import store
from settle.cli import main
from settle.engine import compute
from settle.invariants import verify
from settle.models import Book


class CliCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name) / "data.json"

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *args, expect: int = 0) -> str:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--data", str(self.data), *args])
        self.assertEqual(code, expect, err.getvalue() or out.getvalue())
        return out.getvalue() + err.getvalue()

    def book(self) -> Book:
        return store.load(self.data)


class TestBasicFlow(CliCase):
    def test_full_trip_lifecycle(self):
        self.run_cli("trip", "new", "제주", "--start", "2025-05-01",
                     "--end", "2025-05-03", "--rounding", "100")
        self.run_cli("member", "add", "민수", "지영", "현우")
        self.run_cli("expense", "add", "--title", "흑돼지", "--amount", "120,000",
                     "--payer", "민수", "--date", "05-01", "--category", "식비")
        self.run_cli("expense", "add", "--title", "렌터카", "--amount", "90000",
                     "--payer", "지영:60000,현우:30000", "--date", "05-02")
        output = self.run_cli("settle")
        self.assertIn("총 지출", output)
        self.assertIn("210,000원", output)
        verification = self.run_cli("verify")
        self.assertIn("모든 검증을 통과", verification)

        trip = self.book().current()
        self.assertEqual(len(trip.expenses), 2)
        self.assertEqual(trip.expenses[0].day.isoformat(), "2025-05-01")

    def test_year_defaults_to_trip_year_not_today(self):
        self.run_cli("trip", "new", "작년여행", "--start", "2019-11-01",
                     "--end", "2019-11-03")
        self.run_cli("member", "add", "민수", "지영")
        self.run_cli("expense", "add", "--title", "밥", "--amount", "20000",
                     "--payer", "민수", "--date", "11-02")
        trip = self.book().current()
        self.assertEqual(trip.expenses[0].day.year, 2019)

    def test_adjustment_flag(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수", "지영")
        self.run_cli("expense", "add", "--title", "고기", "--amount", "100000",
                     "--payer", "지영", "--extra", "민수=40000")
        output = self.run_cli("settle")
        self.assertIn("70,000원", output)  # 민수 부담 = 40000 + 30000

    def test_pot_and_transfer(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수", "지영", "현우")
        for name in ("민수", "지영", "현우"):
            self.run_cli("pot", "in", name, "100000")
        self.run_cli("expense", "add", "--title", "숙소", "--amount", "210000",
                     "--payer", "공금")
        output = self.run_cli("settle")
        self.assertIn("공금", output)
        self.assertIn("남은 공금", output)
        self.run_cli("transfer", "add", "민수", "지영", "10000", "--note", "커피값")
        self.assertIn("커피값", self.run_cli("transfer", "list"))

    def test_demo_passes_verification(self):
        output = self.run_cli("demo")
        self.assertIn("모든 검증을 통과", output)

    def test_share_output(self):
        self.run_cli("demo")
        output = self.run_cli("share")
        self.assertIn("정산 결과", output)
        self.assertIn("송금", output)

    def test_export_and_import_json(self):
        self.run_cli("demo")
        target = Path(self.dir.name) / "backup.json"
        self.run_cli("export", "json", str(target))
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertTrue(payload["trips"])

        other = Path(self.dir.name) / "other.json"
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--data", str(other), "import", "json", str(target)])
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(len(store.load(other).trips), 1)

    def test_export_csv(self):
        self.run_cli("demo")
        target = Path(self.dir.name) / "out.csv"
        self.run_cli("export", "csv", str(target))
        text = target.read_text(encoding="utf-8-sig")
        self.assertIn("날짜,내용,카테고리", text)
        self.assertIn("보내는 사람", text)

    def test_fuzz_selftest(self):
        self.run_cli("trip", "new", "여행")
        output = self.run_cli("verify", "--fuzz", "50")
        self.assertIn("50건 모두 통과", output)


class TestErrors(CliCase):
    def test_no_trip_yet(self):
        output = self.run_cli("member", "add", "민수", expect=1)
        self.assertIn("여행이 없습니다", output)

    def test_unknown_member(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수")
        output = self.run_cli("expense", "add", "--title", "밥", "--amount", "10000",
                              "--payer", "없는사람", expect=1)
        self.assertIn("없습니다", output)

    def test_payment_sum_mismatch_is_rejected(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수", "지영")
        output = self.run_cli("expense", "add", "--title", "밥", "--amount", "10000",
                              "--payer", "민수:3000,지영:3000", expect=1)
        self.assertIn("다릅니다", output)

    def test_removing_member_in_use_is_blocked(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수", "지영")
        self.run_cli("expense", "add", "--title", "밥", "--amount", "10000",
                     "--payer", "민수")
        output = self.run_cli("member", "remove", "민수", expect=1)
        self.assertIn("삭제할 수 없습니다", output)

    def test_missing_rate_is_reported(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수", "지영")
        output = self.run_cli("expense", "add", "--title", "라멘", "--amount", "1000",
                              "--payer", "민수", "--currency", "JPY", expect=1)
        self.assertIn("환율", output)
        self.run_cli("rate", "set", "JPY", "9.2")
        self.run_cli("expense", "add", "--title", "라멘", "--amount", "1000",
                     "--payer", "민수", "--currency", "JPY")

    def test_bad_expense_is_not_saved(self):
        self.run_cli("trip", "new", "여행")
        self.run_cli("member", "add", "민수", "지영")
        self.run_cli("expense", "add", "--title", "밥", "--amount", "10000",
                     "--payer", "민수:99999,지영:1", expect=1)
        self.assertEqual(len(self.book().current().expenses), 0)


class TestImportText(CliCase):
    def test_import_from_file(self):
        self.run_cli("trip", "new", "여행", "--start", "2025-09-05")
        self.run_cli("member", "add", "민수", "지영")
        source = Path(self.dir.name) / "sms.txt"
        source.write_text(
            "[Web발신]\n신한카드(1234)승인\n12,500원\n09/06 09:12\n스타벅스강릉점\n\n"
            "[Web발신]\n신한카드(1234)승인\n33,000원\n09/06 13:40\n초당순두부\n",
            encoding="utf-8")
        output = self.run_cli("import", "text", "--file", str(source),
                              "--payer", "민수", "--yes")
        self.assertIn("2건 등록", output)
        trip = self.book().current()
        self.assertEqual(len(trip.expenses), 2)
        self.assertEqual(trip.expenses[0].category, "카페/간식")
        self.assertEqual(trip.expenses[0].source, "text")
        self.assertEqual(trip.expenses[0].day.year, 2025)


class TestImportRealSms(CliCase):
    def setUp(self):
        super().setUp()
        self.run_cli("trip", "new", "오사카", "--start", "2025-09-20", "--end", "2025-09-24")
        self.run_cli("member", "add", "민수", "지영", "현우")

    def write(self, text: str) -> str:
        path = Path(self.dir.name) / "sms.txt"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_preview_does_not_register_anything(self):
        source = self.write("[Web발신]\n신한카드(1234)승인 홍*동\n5,500원 일시불\n"
                            "09/20 12:33\n스타벅스강남2호점\n누적1,234,500원")
        output = self.run_cli("import", "text", "--file", source, "--preview")
        self.assertIn("스타벅스강남2호점", output)
        self.assertIn("5,500원", output)
        self.assertEqual(len(self.book().current().expenses), 0)

    def test_overseas_uses_the_card_issuers_own_rate(self):
        source = self.write("[Web발신]\n신한카드(1234) 해외승인\n3,200엔\n(29,440원)\n"
                            "09/21 20:11\n이치란라멘")
        self.run_cli("import", "text", "--file", source, "--payer", "민수", "--yes")
        expense = self.book().current().expenses[0]
        self.assertEqual((expense.amount, expense.currency), (3200, "JPY"))
        self.assertAlmostEqual(expense.rate, 9.2, places=6)
        # 여행 환율표가 비어 있어도 이 건은 카드사 환율로 정확히 환산된다
        settlement = compute(self.book().current())
        self.assertEqual(settlement.total, 29440)
        self.assertTrue(verify(settlement).ok)

    def test_foreign_expense_without_any_rate_is_skipped_not_crashed(self):
        source = self.write("[Web발신]\nBC카드 승인\n$18.50\n09/23 08:12\nBLUE BOTTLE")
        output = self.run_cli("import", "text", "--file", source, "--payer", "민수", "--yes")
        self.assertIn("환율이 없습니다", output)
        self.assertIn("0건 등록", output)
        self.assertEqual(len(self.book().current().expenses), 0)

    def test_installment_and_card_are_kept_as_a_note(self):
        source = self.write("[Web발신]\n현대카드 승인\n김철수님\n120,000원 3개월\n"
                            "09/20 15:10\n하나투어")
        self.run_cli("import", "text", "--file", source, "--payer", "민수", "--yes")
        expense = self.book().current().expenses[0]
        self.assertEqual(expense.title, "하나투어")   # 실명을 가맹점으로 잡지 않는다
        self.assertIn("3개월", expense.note)
        self.assertIn("현대카드", expense.note)

    def test_mixed_issuers_in_one_paste(self):
        source = self.write(
            "[Web발신]\n신한카드(1234)승인 홍*동\n5,500원 일시불\n09/20 12:33\n"
            "스타벅스강남2호점\n누적1,234,500원\n\n"
            "[Web발신]\n삼성카드 부분취소\n홍*동\n3,000원\n09/22 15:00\n다이소난바점\n\n"
            "[Web발신]\nKB국민은행\n09/22 12:33\n출금 15,000원\n"
            "잔액 1,234,567원\n이마트")
        output = self.run_cli("import", "text", "--file", source, "--payer", "민수", "--yes")
        self.assertIn("3건 등록", output)
        amounts = sorted(e.amount for e in self.book().current().expenses)
        self.assertEqual(amounts, [-3000, 5500, 15000])


class TestImportImage(CliCase):
    def test_import_with_mocked_claude_response(self):
        import os

        self.run_cli("trip", "new", "여행", "--start", "2025-09-05")
        self.run_cli("member", "add", "민수", "지영")
        mock = Path(self.dir.name) / "response.json"
        mock.write_text(json.dumps({"transactions": [
            {"date": "2025-09-06", "merchant": "이치란라멘", "amount": 1200,
             "currency": "JPY", "is_refund": False, "confidence": 0.93},
            {"date": "2025-09-06", "merchant": "돈키호테", "amount": 5400,
             "currency": "JPY", "is_refund": False, "confidence": 0.5,
             "note": "마지막 자리가 흐림"},
        ]}, ensure_ascii=False), encoding="utf-8")
        image = Path(self.dir.name) / "shot.png"
        image.write_bytes(b"fake")

        os.environ["TRAVEL_SETTLE_OCR_MOCK"] = str(mock)
        try:
            self.run_cli("rate", "set", "JPY", "9.2")
            output = self.run_cli("import", "image", str(image),
                                  "--payer", "민수", "--yes")
        finally:
            os.environ.pop("TRAVEL_SETTLE_OCR_MOCK", None)
        self.assertIn("2건 등록", output)
        self.assertIn("인식 신뢰도 낮음", output)
        trip = self.book().current()
        self.assertEqual(len(trip.expenses), 2)
        self.assertEqual(trip.expenses[0].currency, "JPY")
        self.assertEqual(trip.expenses[0].source, "image")
        self.assertTrue(trip.expenses[0].image_path.endswith("shot.png"))


if __name__ == "__main__":
    unittest.main()
