import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import *  # noqa: F401,F403
from settle import ocr_claude
from settle.ocr_claude import OcrError, _extract_json, _to_parsed


class TestJsonExtraction(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_extract_json('{"transactions": []}'), {"transactions": []})

    def test_code_fenced(self):
        text = 'json 결과입니다\n```json\n{"transactions": [1]}\n```\n끝'
        self.assertEqual(_extract_json(text), {"transactions": [1]})

    def test_json_with_surrounding_chatter(self):
        text = '이미지를 읽었습니다. {"transactions": [2]} 이상입니다.'
        self.assertEqual(_extract_json(text), {"transactions": [2]})

    def test_empty_response(self):
        with self.assertRaises(OcrError):
            _extract_json("   ")

    def test_no_json_at_all(self):
        with self.assertRaises(OcrError):
            _extract_json("죄송하지만 읽을 수 없습니다")


class TestEntryConversion(unittest.TestCase):
    def test_krw_entry(self):
        tx = _to_parsed({"date": "2025-08-29", "merchant": "김밥천국",
                         "amount": 8500, "currency": "KRW", "confidence": 0.9},
                        2025, "shot.png")
        self.assertEqual(tx.amount, 8500)
        self.assertEqual(tx.merchant, "김밥천국")
        self.assertEqual(tx.warnings, [])

    def test_usd_entry_converted_to_cents(self):
        tx = _to_parsed({"merchant": "Uber", "amount": 42.35, "currency": "USD",
                         "date": "2025-08-31", "confidence": 0.95}, 2025, "s.png")
        self.assertEqual(tx.amount, 4235)

    def test_refund_becomes_negative(self):
        tx = _to_parsed({"merchant": "호텔", "amount": 30000, "currency": "KRW",
                         "is_refund": True, "date": "2025-08-31"}, 2025, "s.png")
        self.assertEqual(tx.amount, -30000)

    def test_low_confidence_warns(self):
        tx = _to_parsed({"merchant": "?", "amount": 100, "currency": "KRW",
                         "date": "2025-01-01", "confidence": 0.3}, 2025, "s.png")
        self.assertTrue(any("신뢰도" in w for w in tx.warnings))

    def test_missing_amount_warns_instead_of_crashing(self):
        tx = _to_parsed({"merchant": "?", "currency": "KRW"}, 2025, "s.png")
        self.assertIsNone(tx.amount)
        self.assertFalse(tx.ok)

    def test_bad_date_warns(self):
        tx = _to_parsed({"merchant": "x", "amount": 1, "currency": "KRW",
                         "date": "어제"}, 2025, "s.png")
        self.assertTrue(any("날짜" in w for w in tx.warnings))


class TestExtract(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.image = Path(self.dir.name) / "shot.png"
        self.image.write_bytes(b"fake")
        self.mock = Path(self.dir.name) / "resp.json"

    def tearDown(self):
        os.environ.pop("TRAVEL_SETTLE_OCR_MOCK", None)
        self.dir.cleanup()

    def use_mock(self, payload):
        self.mock.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.environ["TRAVEL_SETTLE_OCR_MOCK"] = str(self.mock)

    def test_missing_file(self):
        with self.assertRaises(OcrError):
            ocr_claude.extract(Path(self.dir.name) / "nope.png")

    def test_unsupported_format(self):
        other = Path(self.dir.name) / "note.txt"
        other.write_text("x", encoding="utf-8")
        with self.assertRaises(OcrError):
            ocr_claude.extract(other)

    def test_extracts_entries(self):
        self.use_mock({"transactions": [
            {"date": "2025-08-29", "merchant": "스타벅스", "amount": 5500,
             "currency": "KRW", "confidence": 0.9}]})
        result = ocr_claude.extract(self.image, 2025)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].amount, 5500)

    def test_empty_transactions_is_an_error(self):
        self.use_mock({"transactions": []})
        with self.assertRaises(OcrError):
            ocr_claude.extract(self.image, 2025)

    def test_single_object_response_is_accepted(self):
        self.use_mock({"merchant": "김밥천국", "amount": 8000, "currency": "KRW",
                       "date": "2025-08-29"})
        result = ocr_claude.extract(self.image, 2025)
        self.assertEqual(result[0].amount, 8000)

    def test_wrong_shape_is_an_error(self):
        self.use_mock({"transactions": "없음"})
        with self.assertRaises(OcrError):
            ocr_claude.extract(self.image, 2025)


if __name__ == "__main__":
    unittest.main()
