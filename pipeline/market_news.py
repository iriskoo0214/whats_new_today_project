"""시장 전체(지수·유가·금리) 뉴스를 모은다.

news.py는 보유종목 이름으로만 검색해서 "외국인 3.4조 매도에 코스피 6700선
붕괴" 같은 지수·매크로 이슈를 못 잡는다. 여기서는 종목과 무관하게 시장
전체를 검색어(config.MARKET_NEWS_QUERIES)로 찾는다.

market_summary.py가 이 결과를 받아 헤드라인 한 줄과 3줄 요약을 만든다.
마감 브리핑에서만 부른다 — 장중 실행에서는 만들어도 emit이 버린다
(config.py의 MARKET_NEWS_QUERIES 옆 설명 참고).
"""

from datetime import datetime
from typing import List

from config import MARKET_NEWS_MAX_ITEMS, MARKET_NEWS_QUERIES
from news import NewsItem, _dedupe, _google_items, _pick


def fetch_market_news(market: str, now: datetime) -> List[NewsItem]:
    """market: 'kr' | 'us'. 오늘 발행분이 부족하면 최근 24시간으로 채운다."""
    items: List[NewsItem] = []
    for q in MARKET_NEWS_QUERIES.get(market, []):
        items += _google_items(q)

    items = _dedupe(items)
    return _pick(items, now, limit=MARKET_NEWS_MAX_ITEMS)
