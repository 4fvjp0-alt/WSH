"""GUI가 쓰는 API 계층 테스트. HTTP 없이 순수 함수로 검증한다."""

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import *  # noqa: F401,F403
from settle import api
from settle.api import ApiError, handle
from settle.models import POT_ID, Book


class ApiCase(unittest.TestCase):
    def setUp(self):
        self.book = Book()
        handle(self.book, "POST", "/api/trip/new",
               {"name": "제주", "start": "2025-09-05", "end": "2025-09-08", "rounding": 100})
        handle(self.book, "POST", "/api/member/add", {"names": "민수 지영 현우"})
        self.ids = {m["name"]: m["id"] for m in self.state()["trip"]["members"]}

    def state(self):
        return handle(self.book, "GET", "/api/state")

    def add(self, **kw):
        return handle(self.book, "POST", "/api/expense/add", kw)


class TestState(ApiCase):
    def test_empty_book_has_no_trip(self):
        state = handle(Book(), "GET", "/api/state")
        self.assertIsNone(state["trip"])
        self.assertEqual(state["trips"], [])

    def test_state_shape(self):
        state = self.state()
        self.assertEqual(state["trip"]["name"], "제주")
        self.assertEqual(len(state["trip"]["members"]), 3)
        self.assertIn("settlement", state)
        self.assertTrue(state["verification"]["ok"])

    def test_minor_digits_covers_currencies_not_yet_used(self):
        """화면이 금액을 찍는 근거다. 여행에 아직 없는 통화도 알려줘야 한다.

        이게 빠지면 문자에서 처음 인식된 엔화 결제를 화면이 소수 두 자리로
        착각해 3,200엔을 32엔으로 등록한다.
        """
        digits = self.state()["minor_digits"]
        self.assertEqual(digits["JPY"], 0)
        self.assertEqual(digits["KRW"], 0)
        self.assertEqual(digits["USD"], 2)
        self.assertEqual(digits["EUR"], 2)

    def test_multi_currency_state_is_serialisable(self):
        """통화가 여러 개일 때 상태를 만들다 죽지 않아야 한다."""
        handle(self.book, "POST", "/api/rate/set", {"currency": "JPY", "rate": 9.2})
        self.add(title="라멘", amount="3200", currency="JPY", payer_id=self.ids["민수"])
        self.add(title="택시", amount="12000", payer_id=self.ids["지영"])
        state = self.state()
        names = [c["name"] for c in state["settlement"]["by_currency"]]
        self.assertEqual(names, ["JPY", "KRW"])
        self.assertEqual(state["minor_digits"]["JPY"], 0)
        self.assertTrue(state["verification"]["ok"])


class TestExpenses(ApiCase):
    def test_add_and_remove(self):
        out = self.add(title="흑돼지", amount="120,000", payer_id=self.ids["민수"],
                       category="식비")
        self.assertEqual(out["state"]["settlement"]["total"], 120000)
        handle(self.book, "POST", "/api/expense/remove", {"id": out["id"]})
        self.assertEqual(self.state()["settlement"]["total"], 0)

    def test_adjustment(self):
        self.add(title="고기", amount="100000", payer_id=self.ids["지영"],
                 adjustments={self.ids["민수"]: "40000"})
        owed = {b["name"]: b["owed"] for b in self.state()["settlement"]["balances"]}
        self.assertEqual(owed["민수"], 60000)
        self.assertEqual(owed["지영"], 20000)

    def test_exact_split_values_are_amounts(self):
        self.add(title="숙소", amount="100000", payer_id=self.ids["민수"],
                 split_method="exact",
                 split_values={self.ids["민수"]: "50000", self.ids["지영"]: "30000",
                               self.ids["현우"]: "20000"})
        owed = {b["name"]: b["owed"] for b in self.state()["settlement"]["balances"]}
        self.assertEqual(owed["현우"], 20000)

    def test_payment_sum_mismatch_rejected(self):
        with self.assertRaises(ApiError):
            self.add(title="x", amount="10000", payments=[
                {"member_id": self.ids["민수"], "amount": "3000"}])

    def test_failed_update_rolls_back(self):
        out = self.add(title="밥", amount="30000", payer_id=self.ids["민수"])
        with self.assertRaises(ApiError):
            handle(self.book, "POST", "/api/expense/update",
                   {"id": out["id"], "amount": "0"})
        self.assertEqual(self.state()["settlement"]["total"], 30000)

    def test_unknown_category_rejected(self):
        with self.assertRaises(ApiError):
            self.add(title="x", amount="1000", payer_id=self.ids["민수"], category="없는것")

    def test_personal_expense_excluded(self):
        self.add(title="기념품", amount="40000", payer_id=self.ids["지영"], personal=True)
        state = self.state()
        self.assertEqual(state["settlement"]["total"], 0)
        self.assertEqual(state["settlement"]["personal_total"], 40000)


class TestMembersAndPot(ApiCase):
    def test_member_in_use_cannot_be_removed(self):
        self.add(title="밥", amount="30000", payer_id=self.ids["민수"])
        with self.assertRaises(ApiError):
            handle(self.book, "POST", "/api/member/remove", {"id": self.ids["민수"]})

    def test_pot_contribution_and_refund(self):
        for name in ("민수", "지영", "현우"):
            handle(self.book, "POST", "/api/transfer/add",
                   {"from_id": self.ids[name], "to_id": POT_ID, "amount": "100000"})
        self.add(title="숙소", amount="210000", payer_id=POT_ID)
        state = self.state()
        self.assertEqual(state["settlement"]["pot"]["balance"], 90000)
        refunds = [p["amount"] for p in state["settlement"]["plan"] if p["from"] == "공금"]
        self.assertEqual(sorted(refunds), [30000, 30000, 30000])
        self.assertTrue(state["verification"]["ok"])


class TestImport(ApiCase):
    SMS = """[Web발신]
신한카드(1234)승인 홍*동
5,500원 일시불
09/06 12:33
스타벅스강릉점
누적1,234,500원"""

    def test_parse_then_import(self):
        out = handle(self.book, "POST", "/api/parse", {"text": self.SMS})
        item = out["items"][0]
        self.assertEqual(item["amount"], 5500)
        self.assertEqual(item["merchant"], "스타벅스강릉점")
        self.assertEqual(item["category"], "카페/간식")
        # 미리보기는 장부를 바꾸지 않는다
        self.assertEqual(self.state()["settlement"]["total"], 0)

        item["payer_id"] = self.ids["민수"]
        added = handle(self.book, "POST", "/api/import", {"items": [item]})
        self.assertEqual(added["added"], 1)
        self.assertEqual(self.state()["settlement"]["total"], 5500)

    def test_overseas_import_uses_implied_rate(self):
        text = ("[Web발신]\n신한카드(1234) 해외승인\n3,200엔\n(29,440원)\n"
                "09/06 20:11\n이치란라멘")
        item = handle(self.book, "POST", "/api/parse", {"text": text})["items"][0]
        item["payer_id"] = self.ids["민수"]
        handle(self.book, "POST", "/api/import", {"items": [item]})
        state = self.state()
        self.assertEqual(state["settlement"]["total"], 29440)
        self.assertTrue(state["verification"]["ok"])

    def test_import_skips_when_no_rate(self):
        text = "[Web발신]\nBC카드 승인\n$18.50\n09/06 08:12\nBLUE BOTTLE"
        item = handle(self.book, "POST", "/api/parse", {"text": text})["items"][0]
        item["payer_id"] = self.ids["민수"]
        out = handle(self.book, "POST", "/api/import", {"items": [item]})
        self.assertEqual(out["added"], 0)
        self.assertEqual(len(out["skipped"]), 1)
        self.assertIn("환율", out["skipped"][0])


class TestImageImport(ApiCase):
    """캡쳐 이미지 -> Claude Code CLI. CLI 응답은 목으로 대체한다."""

    def setUp(self):
        super().setUp()
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name) / "data.json"
        self.png = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()

    def tearDown(self):
        os.environ.pop("TRAVEL_SETTLE_OCR_MOCK", None)
        self.dir.cleanup()

    def use_mock(self, payload):
        mock = Path(self.dir.name) / "resp.json"
        mock.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.environ["TRAVEL_SETTLE_OCR_MOCK"] = str(mock)

    def parse(self, **kw):
        body = {"name": "capture.png", "data": self.png}
        body.update(kw)
        return handle(self.book, "POST", "/api/parse_image", body, self.data)

    def test_extract_classify_and_register(self):
        self.use_mock({"transactions": [
            {"date": "2025-09-06", "merchant": "스타벅스제주점", "amount": 5500,
             "currency": "KRW", "confidence": 0.95}]})
        out = self.parse()
        item = out["items"][0]
        self.assertEqual(item["amount"], 5500)
        self.assertEqual(item["category"], "카페/간식")     # 자동 분류
        self.assertEqual(item["source"], "image")
        self.assertTrue(item["image_path"].endswith(".png"))
        # 원본 이미지는 장부 옆에 남는다
        self.assertTrue(Path(item["image_path"]).exists())
        # 인식만으로는 장부가 바뀌지 않는다
        self.assertEqual(self.state()["settlement"]["total"], 0)

        item["payer_id"] = self.ids["민수"]
        handle(self.book, "POST", "/api/import", {"items": [item]})
        expense = self.book.current().expenses[0]
        self.assertEqual(expense.source, "image")
        self.assertEqual(expense.image_path, item["image_path"])
        self.assertEqual(self.state()["settlement"]["total"], 5500)

    def test_low_confidence_is_surfaced(self):
        self.use_mock({"transactions": [
            {"date": "2025-09-06", "merchant": "흐릿한가게", "amount": 8000,
             "currency": "KRW", "confidence": 0.4, "note": "마지막 자리 불확실"}]})
        item = self.parse()["items"][0]
        self.assertTrue(any("신뢰도" in w for w in item["warnings"]))
        self.assertTrue(any("불확실" in w for w in item["warnings"]))

    def test_data_url_prefix_accepted(self):
        self.use_mock({"transactions": [
            {"date": "2025-09-06", "merchant": "김밥천국", "amount": 8000,
             "currency": "KRW", "confidence": 0.9}]})
        out = self.parse(data="data:image/png;base64," + self.png)
        self.assertEqual(out["items"][0]["amount"], 8000)

    def test_unsupported_extension_rejected(self):
        self.use_mock({"transactions": []})
        with self.assertRaises(ApiError) as ctx:
            self.parse(name="notes.txt")
        self.assertIn("형식", ctx.exception.message)

    def test_path_traversal_in_filename_is_harmless(self):
        self.use_mock({"transactions": [
            {"date": "2025-09-06", "merchant": "x", "amount": 100,
             "currency": "KRW", "confidence": 0.9}]})
        out = self.parse(name="../../../../etc/passwd.png")
        saved = Path(out["image_path"])
        self.assertEqual(saved.parent, self.data.parent / "images")

    def test_broken_base64_rejected(self):
        self.use_mock({"transactions": []})
        with self.assertRaises(ApiError):
            self.parse(data="!!!not base64!!!")

    def test_oversized_image_rejected(self):
        self.use_mock({"transactions": []})
        huge = base64.b64encode(b"\x00" * (api.MAX_IMAGE_BYTES + 1)).decode()
        with self.assertRaises(ApiError) as ctx:
            self.parse(data=huge)
        self.assertIn("너무 큽니다", ctx.exception.message)

    def test_missing_claude_cli_gives_a_clear_message(self):
        os.environ.pop("TRAVEL_SETTLE_OCR_MOCK", None)
        os.environ["TRAVEL_SETTLE_CLAUDE_CMD"] = "definitely-not-a-real-command-xyz"
        try:
            with self.assertRaises(ApiError) as ctx:
                self.parse()
            self.assertIn("Claude Code CLI", ctx.exception.message)
            self.assertEqual(ctx.exception.status, 503)
        finally:
            os.environ.pop("TRAVEL_SETTLE_CLAUDE_CMD", None)

    def test_image_route_is_read_only_and_needs_the_data_path(self):
        self.assertIn("/api/parse_image", api.READ_ONLY)
        self.assertIn("/api/parse_image", api.NEEDS_DATA_PATH)


class TestRouting(ApiCase):
    def test_unknown_route(self):
        with self.assertRaises(ApiError) as ctx:
            handle(self.book, "POST", "/api/nope", {})
        self.assertEqual(ctx.exception.status, 404)

    def test_missing_field(self):
        with self.assertRaises(ApiError):
            handle(Book(), "POST", "/api/trip/new", {})

    def test_read_only_routes_are_marked(self):
        self.assertIn("/api/parse", api.READ_ONLY)
        self.assertIn("/api/state", api.READ_ONLY)
        self.assertNotIn("/api/expense/add", api.READ_ONLY)

    def test_mutations_return_fresh_state(self):
        out = self.add(title="밥", amount="30000", payer_id=self.ids["민수"])
        self.assertIn("state", out)
        self.assertEqual(out["state"]["settlement"]["total"], 30000)


if __name__ == "__main__":
    unittest.main()
