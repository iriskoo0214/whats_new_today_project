"""시장 전체(지수·유가·금리) 뉴스를 모은다.

news.py는 보유종목 이름으로만 검색해서 "외국인 3.4조 매도에 코스피 6700선
붕괴" 같은 지수·매크로 이슈를 못 잡는다. 여기서는 종목과 무관하게 시장
전체를 검색어(config.MARKET_NEWS_QUERIES)로 찾는다.

market_summary.py가 이 결과를 받아 헤드라인 한 줄과 3줄 요약을 만든다.
마감 브리핑에서만 부른다 — 장중 실행에서는 만들어도 emit이 버린다
(config.py의 MARKET_NEWS_QUERIES 옆 설명 참고).
"""

import re
from datetime import datetime, timedelta
from typing import List

from config import MARKET_NEWS_EXCLUDE, MARKET_NEWS_MAX_ITEMS, MARKET_NEWS_QUERIES
from news import NewsItem, _dedupe, _google_items, _pick


# "[뉴욕증시 29일] …"처럼 제목에 날짜(일)가 박힌 시황 기사는 구글뉴스가 지난 달 기사를
# 오늘 날짜로 다시 띄우는 일이 있다 — 그날 시황이 오늘 시황인 것처럼 요약에 섞인다.
_DAY_TAG = re.compile(r"^\[\s*뉴욕\s*증시\s*(\d{1,2})일\s*\]")


def _stale_day_tag(title: str, now: datetime) -> bool:
    """제목의 'N일'이 오늘·어제(KST)가 아니면 True — 옛 기사가 재발행된 것."""
    m = _DAY_TAG.match(title or "")
    if not m:
        return False
    return int(m.group(1)) not in {now.day, (now - timedelta(days=1)).day}


def fetch_market_news(market: str, now: datetime) -> List[NewsItem]:
    """market: 'kr' | 'us'. 오늘 발행분이 부족하면 최근 24시간으로 채운다.

    쿼리마다 따로 골라서 돌려가며 섞는다 — 세 쿼리를 한 통에 모아 최신순으로
    자르면, 기사가 제일 많고 제일 신선한 쿼리 하나가 12건을 다 먹는다(미국 요약
    재료가 국내 기름값 기사로 채워진 사고의 원인 중 하나). 시장과 무관한 단어가
    든 헤드라인은 config.MARKET_NEWS_EXCLUDE로 먼저 걸러낸다.
    """
    banned = MARKET_NEWS_EXCLUDE.get(market, [])
    queries = MARKET_NEWS_QUERIES.get(market, [])
    per_query = max(MARKET_NEWS_MAX_ITEMS // max(len(queries), 1), 1)

    lists: List[List[NewsItem]] = []
    for q in queries:
        items = [n for n in _google_items(q)
                 if not any(w in n.title for w in banned)
                 and not _stale_day_tag(n.title, now)]
        lists.append(_pick(_dedupe(items), now, limit=per_query))

    # 쿼리별 1위, 2위, … 순으로 번갈아 담는다. 같은 기사가 두 쿼리에 걸리면 한 번만.
    out: List[NewsItem] = []
    seen = set()
    for rank in range(per_query):
        for lst in lists:
            if rank < len(lst) and lst[rank].url not in seen:
                seen.add(lst[rank].url)
                out.append(lst[rank])
    out.sort(key=lambda i: i.published, reverse=True)
    return out[:MARKET_NEWS_MAX_ITEMS]
