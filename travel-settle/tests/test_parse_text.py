import unittest
from datetime import date

from helpers import *  # noqa: F401,F403
from settle.category import classify, learn
from settle.parse_text import parse_text


def one(text, year=2025):
    result = parse_text(text, year)
    assert len(result) == 1, f"블록이 {len(result)}개로 나뉘었습니다"
    return result[0]


class TestCardSms(unittest.TestCase):
    def test_shinhan_multiline(self):
        tx = one("[Web발신]\n신한카드(1234)승인 홍길동\n12,500원 일시불\n"
                 "08/29 12:33\n스타벅스강남2호점\n누적 1,234,500원")
        self.assertEqual(tx.amount, 12500)
        self.assertEqual(tx.currency, "KRW")
        self.assertEqual(tx.day, date(2025, 8, 29))
        self.assertEqual(tx.time, "12:33")
        self.assertEqual(tx.merchant, "스타벅스강남2호점")
        self.assertEqual(tx.card, "신한카드")
        self.assertFalse(tx.is_refund)

    def test_card_number_is_not_mistaken_for_amount(self):
        tx = one("KB국민체크(9876) 홍*동 08/29 13:05 15,000원 이마트트레이더스")
        self.assertEqual(tx.amount, 15000)
        self.assertEqual(tx.merchant, "이마트트레이더스")

    def test_cumulative_amount_ignored(self):
        tx = one("[Web발신]\n현대카드 승인\n7,700원\n09/01\n김밥천국\n누적 999,999원")
        self.assertEqual(tx.amount, 7700)

    def test_cancellation_is_negative(self):
        tx = one("[Web발신] 우리카드(1111) 승인취소 12,000원 08/29 19:20 김밥천국")
        self.assertEqual(tx.amount, -12000)
        self.assertTrue(tx.is_refund)

    def test_foreign_currency_suffix(self):
        tx = one("[Web발신]\n현대카드 해외승인\n3,200엔\n08/30 20:11\n이치란라멘 신주쿠")
        self.assertEqual((tx.amount, tx.currency), (3200, "JPY"))

    def test_foreign_currency_prefix(self):
        tx = one("[Web발신]\nBC카드 승인\n$18.50\n09/01 08:12\nBlue Bottle Coffee")
        self.assertEqual((tx.amount, tx.currency), (1850, "USD"))

    def test_currency_code_prefix_not_read_as_date(self):
        tx = one("USD 42.35 결제\n08/31\nUber Trip San Francisco")
        self.assertEqual((tx.amount, tx.currency), (4235, "USD"))
        self.assertEqual(tx.day, date(2025, 8, 31))


class TestBulk(unittest.TestCase):
    def test_multiple_web_messages(self):
        text = ("[Web발신]\n신한카드(1234)승인\n12,500원\n09/06 09:12\n스타벅스강릉점\n\n"
                "[Web발신]\n신한카드(1234)승인\n33,000원\n09/06 13:40\n초당순두부\n")
        parsed = parse_text(text, 2025)
        self.assertEqual(len(parsed), 2)
        self.assertEqual([t.amount for t in parsed], [12500, 33000])
        self.assertEqual([t.merchant for t in parsed], ["스타벅스강릉점", "초당순두부"])

    def test_transaction_list_one_per_line(self):
        parsed = parse_text("08/28 롯데리아 8,900원\n08/28 GS25제주점 4,300원\n"
                            "08/29 카카오T택시 13,800원", 2025)
        self.assertEqual(len(parsed), 3)
        self.assertEqual([t.amount for t in parsed], [8900, 4300, 13800])
        self.assertEqual(parsed[1].merchant, "GS25제주점")

    def test_garbage_reports_warnings_instead_of_crashing(self):
        tx = one("오늘 날씨가 좋네요")
        self.assertIsNone(tx.amount)
        self.assertFalse(tx.ok)
        self.assertTrue(tx.warnings)


class TestCategory(unittest.TestCase):
    def test_rules(self):
        cases = {
            "스타벅스 강남2호점": "카페/간식",
            "GS25 제주점": "식비",
            "호텔신라": "숙박",
            "카카오T 택시": "교통",
            "유니클로 명동": "쇼핑",
            "이치란 라멘": "식비",
            "대한항공": "항공/기차",
            "유니버설스튜디오 입장권": "관광/입장료",
            "이자카야 토리": "주류",
            "온누리약국": "의료",
        }
        for merchant, expected in cases.items():
            self.assertEqual(classify(merchant), expected, merchant)

    def test_unknown_is_etc(self):
        self.assertEqual(classify("가나다라마"), "기타")

    def test_learning_sticks(self):
        hints = {}
        learn(hints, "우리동네가게", "식비")
        self.assertEqual(classify("우리동네가게 2호점", hints), "식비")


if __name__ == "__main__":
    unittest.main()
