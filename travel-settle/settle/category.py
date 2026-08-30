"""가맹점명으로 카테고리 자동 분류.

규칙표로 1차 분류하고, 사용자가 고치면 그 가맹점명을 기억해서(학습)
다음부터는 바로 맞춘다.
"""

from __future__ import annotations

import re

from .models import CATEGORIES

# 순서가 중요하다. 위쪽 규칙이 먼저 이긴다.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("카페/간식", (
        "스타벅스", "starbucks", "투썸", "이디야", "커피", "coffee", "카페", "cafe",
        "빽다방", "메가커피", "컴포즈", "할리스", "폴바셋", "베이커리", "파리바게",
        "뚜레쥬르", "던킨", "베스킨", "설빙", "요거트", "cafe", "bakery",
    )),
    ("주류", (
        "호프", "포차", "이자카야", "펍", "bar", "술집", "와인", "맥주", "소주",
        "브루어리", "brewery", "liquor", "sake",
    )),
    ("숙박", (
        "호텔", "hotel", "모텔", "리조트", "resort", "게스트하우스", "guesthouse",
        "펜션", "hostel", "호스텔", "에어비앤비", "airbnb", "agoda", "booking.com",
        "야놀자", "여기어때", "숙박", "ryokan", "료칸",
    )),
    ("항공/기차", (
        "항공", "air", "asiana", "대한항공", "제주항공", "티웨이", "진에어", "에어부산",
        "ana", "jal", "코레일", "korail", "ktx", "srt", "철도", "railway", "shinkansen",
        "신칸센", "expedia", "스카이스캐너",
    )),
    ("교통", (
        "택시", "taxi", "카카오t", "버스", "bus", "지하철", "메트로", "metro", "교통",
        "주유", "gs칼텍스", "s-oil", "sk에너지", "현대오일", "충전", "렌터카", "rent",
        "하이패스", "통행료", "주차", "parking", "uber", "grab", "lyft", "ic카드",
        "suica", "pasmo",
    )),
    ("관광/입장료", (
        "입장", "티켓", "ticket", "박물관", "museum", "미술관", "수족관", "aquarium",
        "테마파크", "랜드", "world", "관광", "투어", "tour", "전망대", "온천", "스파",
        "spa", "케이블카", "유니버설", "디즈니",
    )),
    ("쇼핑", (
        "면세", "duty", "백화점", "아울렛", "outlet", "올리브영", "다이소", "무인양품",
        "muji", "유니클로", "uniqlo", "돈키호테", "마트", "mart", "이마트", "홈플러스",
        "코스트코", "costco", "쇼핑", "store", "샵", "shop", "기념품", "souvenir",
    )),
    ("통신", ("통신", "sk텔레콤", "kt", "lg유플러스", "로밍", "esim", "sim", "와이파이", "wifi")),
    ("의료", ("약국", "병원", "의원", "pharmacy", "clinic", "hospital", "치과", "한의원")),
    ("식비", (
        "식당", "restaurant", "김밥", "국밥", "고기", "고깃", "구이", "삼겹", "곱창",
        "치킨", "피자", "순두부", "두부", "칼국수", "국수", "백반", "한식", "찌개",
        "찜", "탕", "족발", "보쌈", "쌈", "덮밥", "비빔밥", "돈부리", "면옥",
        "버거", "횟집", "맥도날드", "롯데리아", "버거킹", "kfc", "서브웨이", "분식", "정식",
        "초밥", "스시", "sushi", "라멘", "ramen", "우동", "돈까스", "food",
        "다이닝", "dining", "포차", "곰탕", "칼국수", "냉면", "쌈밥", "뷔페", "buffet",
        "편의점", "cu", "gs25", "세븐일레븐", "이마트24", "패밀리마트", "lawson", "7-eleven",
    )),
]


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-_()·.]", "", text or "").lower()


def classify(merchant: str, hints: dict[str, str] | None = None) -> str:
    """가맹점명 -> 카테고리. 모르면 '기타'."""
    if not merchant:
        return "기타"
    key = _normalize(merchant)
    if hints:
        if merchant in hints:
            return hints[merchant]
        if key in hints:
            return hints[key]
        for hint_key, category in hints.items():
            normalized = _normalize(hint_key)
            if normalized and normalized in key:
                return category
    for category, keywords in RULES:
        for word in keywords:
            if _normalize(word) in key:
                return category
    return "기타"


def learn(hints: dict[str, str], merchant: str, category: str) -> None:
    """사용자가 고친 분류를 기억한다."""
    if not merchant or category not in CATEGORIES:
        return
    hints[_normalize(merchant)] = category
