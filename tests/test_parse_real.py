"""실제 카드사·간편결제·은행 알림 문자 형식 대응 테스트.

국내 주요 카드사와 은행이 실제로 보내는 승인 문자의 형태를 재현한 것이다.
카드사마다 줄 순서·가맹점 위치·마스킹 방식이 달라서, 이 표가 파서의 사양서다.
"""

import unittest
from datetime import date

from helpers import *  # noqa: F401,F403
from settle.parse_text import parse_text

Y = 2025


def one(text, base="KRW"):
    result = parse_text(text, Y, base)
    assert len(result) == 1, f"블록이 {len(result)}개로 나뉘었습니다: {[t.raw for t in result]}"
    return result[0]


class TestDomesticCardSms(unittest.TestCase):
    """국내 카드 승인 문자. (금액, 가맹점, 날짜) 세 개가 핵심이다."""

    CASES = [
        ("신한카드", """[Web발신]
신한카드(1234)승인 홍*동
5,500원 일시불
08/29 12:33
스타벅스강남2호점
누적1,234,500원""", 5500, "스타벅스강남2호점", date(Y, 8, 29)),

        ("KB국민카드 여러 줄", """[Web발신]
KB국민카드 승인
홍*동님
15,000원 일시불
08/29 13:05
이마트트레이더스""", 15000, "이마트트레이더스", date(Y, 8, 29)),

        ("KB국민 한 줄", """[Web발신] KB국민체크(9876) 홍*동 08/29 13:05 15,000원 이마트트레이더스""",
         15000, "이마트트레이더스", date(Y, 8, 29)),

        ("삼성카드", """[Web발신]
삼성카드 승인 홍*동
12,000원 일시불
08/29 19:20
김밥천국""", 12000, "김밥천국", date(Y, 8, 29)),

        ("롯데카드", """[Web발신]
롯데카드 승인 홍*동
1,200원 일시불
08/29 09:11
GS25제주점""", 1200, "GS25제주점", date(Y, 8, 29)),

        ("우리카드", """[Web발신]
우리카드(1111)
승인 12,000원
08/29 19:20
김밥천국""", 12000, "김밥천국", date(Y, 8, 29)),

        ("하나카드 (이름과 금액이 같은 줄)", """[Web발신]
하나카드 승인
홍*동님 12,000원
일시불 08/29 19:20
김밥천국""", 12000, "김밥천국", date(Y, 8, 29)),

        ("NH농협카드", """[Web발신]
NH카드 승인
홍*동
23,500원
08/29 20:15
한라산등심""", 23500, "한라산등심", date(Y, 8, 29)),

        ("BC카드", """[Web발신]
BC카드 승인
홍*동님
8,900원 일시불
08/30 12:10
롯데리아""", 8900, "롯데리아", date(Y, 8, 30)),

        ("마스킹 안 된 실명 (가맹점으로 오인 금지)", """[Web발신]
현대카드 승인
김철수님
5,000원 일시불
08/29 12:33
CU제주공항점""", 5000, "CU제주공항점", date(Y, 8, 29)),

        ("승인번호가 붙는 형식", """[Web발신]
신한카드(1234)승인
홍*동
33,000원 일시불
08/29 13:40
초당순두부
승인번호 12345678""", 33000, "초당순두부", date(Y, 8, 29)),

        ("연-월-일 + 초 단위 시각", """[Web발신]
우리카드 승인
2025.08.29 19:20:11
12,000원
김밥천국""", 12000, "김밥천국", date(Y, 8, 29)),

        ("마스킹된 카드번호가 금액으로 오인되지 않음", """[Web발신]
삼성 8*3*
승인 12,000원
08/29 19:20
백종원의고깃집""", 12000, "백종원의고깃집", date(Y, 8, 29)),
    ]

    def test_cases(self):
        for name, text, amount, merchant, day in self.CASES:
            with self.subTest(name):
                tx = one(text)
                self.assertEqual(tx.amount, amount, f"{name}: 금액")
                self.assertEqual(tx.merchant, merchant, f"{name}: 가맹점")
                self.assertEqual(tx.day, day, f"{name}: 날짜")
                self.assertEqual(tx.currency, "KRW")
                self.assertFalse(tx.is_refund)


class TestNoiseLines(unittest.TestCase):
    """문자 끝 안내 꼬리말과 라벨형 형식. 가맹점 오인의 주범이다."""

    def test_trailing_notice_is_not_the_merchant(self):
        tx = one("""[Web발신]
신한카드(1234)승인 홍*동
5,500원 일시불
08/29 12:33
스타벅스강남2호점
※본인 이용이 아닌 경우 고객센터 1588-1234""")
        self.assertEqual(tx.merchant, "스타벅스강남2호점")
        self.assertEqual(tx.amount, 5500)

    def test_labelled_format(self):
        tx = one("""[Web발신]
비씨카드 승인
거래금액 12,500원
가맹점 스타벅스제주공항점
거래일시 08/29 12:33""")
        self.assertEqual(tx.amount, 12500)
        self.assertEqual(tx.merchant, "스타벅스제주공항점")
        self.assertEqual(tx.day, date(Y, 8, 29))

    def test_phone_number_is_not_an_amount(self):
        tx = one("""[Web발신]
롯데카드 승인
8,900원
08/30 12:10
롯데리아제주점
문의 1588-8100""")
        self.assertEqual(tx.amount, 8900)
        self.assertEqual(tx.merchant, "롯데리아제주점")


class TestBankAndPay(unittest.TestCase):
    def test_bank_withdrawal_ignores_balance(self):
        tx = one("""[Web발신]
KB국민은행
08/29 12:33
출금 15,000원
잔액 1,234,567원
이마트""")
        self.assertEqual(tx.amount, 15000)
        self.assertEqual(tx.merchant, "이마트")

    def test_masked_account_number_is_not_an_amount(self):
        tx = one("""[Web발신]
농협 08/29 12:33
352-****-4567
출금 15,000원
잔액 500,000원
스타벅스제주""")
        self.assertEqual(tx.amount, 15000)
        self.assertEqual(tx.merchant, "스타벅스제주")

    def test_amount_without_currency_unit(self):
        tx = one("""[Web발신]
KB국민은행
08/29 12:33
출금 15,000
잔액 1,234,567
이마트""")
        self.assertEqual(tx.amount, 15000)

    def test_toss(self):
        tx = one("""[Web발신]
토스뱅크 체크카드 승인
12,500원
08/29 09:12
스타벅스강남점""")
        self.assertEqual(tx.amount, 12500)
        self.assertEqual(tx.merchant, "스타벅스강남점")
        self.assertEqual(tx.card, "토스뱅크")

    def test_kakaopay(self):
        tx = one("""카카오페이머니 결제
23,000원
교촌치킨 서초점
2025-08-27 18:40""")
        self.assertEqual(tx.amount, 23000)
        self.assertEqual(tx.merchant, "교촌치킨 서초점")
        self.assertEqual(tx.day, date(Y, 8, 27))


class TestRefundAndInstallment(unittest.TestCase):
    def test_cancellation(self):
        tx = one("""[Web발신]
신한카드(1234)취소 홍*동
5,500원
08/29 13:02
스타벅스강남2호점""")
        self.assertEqual(tx.amount, -5500)
        self.assertTrue(tx.is_refund)

    def test_partial_cancellation(self):
        tx = one("""[Web발신]
삼성카드 부분취소
홍*동
3,000원
08/30 15:00
다이소제주점""")
        self.assertEqual(tx.amount, -3000)
        self.assertTrue(tx.is_refund)

    def test_installment_is_captured(self):
        tx = one("""[Web발신]
현대카드 승인
홍길동님
120,000원 3개월
08/29 12:33
하나투어""")
        self.assertEqual(tx.amount, 120000)
        self.assertEqual(tx.merchant, "하나투어")
        self.assertEqual(tx.installment, "3개월")


class TestOverseas(unittest.TestCase):
    """해외 승인은 원화 청구액이 함께 오는데, 그 둘로 카드사 적용 환율이 나온다."""

    def test_usd_with_krw_conversion(self):
        tx = one("""[Web발신]
현대카드 해외승인
홍*동님
USD 42.35
(56,000원)
08/30 20:11
UBER TRIP SAN FRANCISCO""")
        self.assertEqual((tx.amount, tx.currency), (4235, "USD"))
        self.assertEqual((tx.converted_amount, tx.converted_currency), (56000, "KRW"))
        self.assertAlmostEqual(tx.implied_rate, 56000 / 42.35, places=4)
        self.assertEqual(tx.merchant, "UBER TRIP SAN FRANCISCO")

    def test_jpy_with_krw_conversion(self):
        tx = one("""[Web발신]
신한카드(1234) 해외승인
3,200엔
(29,440원)
08/30 20:11
이치란라멘""")
        self.assertEqual((tx.amount, tx.currency), (3200, "JPY"))
        self.assertEqual(tx.converted_amount, 29440)
        self.assertAlmostEqual(tx.implied_rate, 9.2, places=6)

    def test_foreign_only_has_no_rate(self):
        tx = one("""[Web발신]
BC카드 승인
$18.50
09/01 08:12
BLUE BOTTLE COFFEE""")
        self.assertEqual((tx.amount, tx.currency), (1850, "USD"))
        self.assertIsNone(tx.converted_amount)
        self.assertIsNone(tx.implied_rate)

    def test_krw_is_always_the_billing_amount(self):
        """국내 카드는 해외 결제도 원화로 청구한다. 기준통화와 무관하게
        원통화 쪽이 거래액, 원화 쪽이 청구액이다."""
        text = """[Web발신]
신한카드(1234) 해외승인
3,200엔
(29,440원)
09/01
이치란라멘"""
        for base in ("KRW", "JPY"):
            with self.subTest(base=base):
                tx = one(text, base=base)
                self.assertEqual((tx.amount, tx.currency), (3200, "JPY"))
                self.assertEqual((tx.converted_amount, tx.converted_currency),
                                 (29440, "KRW"))

    def test_base_currency_is_only_a_fallback_when_no_unit(self):
        tx = one("""[Web발신]
승인 12,500
09/01 10:00
라멘집""", base="JPY")
        self.assertEqual((tx.amount, tx.currency), (12500, "JPY"))
        self.assertIsNone(tx.converted_amount)


class TestBulk(unittest.TestCase):
    def test_multiple_web_messages(self):
        parsed = parse_text("""[Web발신]
신한카드(1234)승인 홍*동
12,500원 일시불
09/06 09:12
스타벅스강릉점
누적1,000,000원

[Web발신]
신한카드(1234)승인 홍*동
33,000원 일시불
09/06 13:40
초당순두부
누적1,033,000원""", Y)
        self.assertEqual([t.amount for t in parsed], [12500, 33000])
        self.assertEqual([t.merchant for t in parsed], ["스타벅스강릉점", "초당순두부"])

    def test_app_transaction_list(self):
        parsed = parse_text("""08/28 롯데리아 8,900원
08/28 GS25제주점 4,300원
08/29 카카오T택시 13,800원""", Y)
        self.assertEqual([t.amount for t in parsed], [8900, 4300, 13800])
        self.assertEqual(parsed[1].merchant, "GS25제주점")

    def test_garbage_is_reported_not_crashed(self):
        tx = one("오늘 점심 뭐 먹지")
        self.assertIsNone(tx.amount)
        self.assertTrue(tx.warnings)


if __name__ == "__main__":
    unittest.main()
