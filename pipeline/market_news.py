"""시장 전체(지수·수급·업종·환율·금리) 뉴스를 3줄 요약의 번호별로 모은다.

news.py는 보유종목 이름으로만 검색해서 "외국인 3.4조 매도에 코스피 6700선
붕괴" 같은 지수·매크로 이슈를 못 잡는다. 여기서는 종목과 무관하게 시장
전체를 검색어(config.MARKET_SUMMARY_SLOTS)로 찾는다.

번호(1·2·3)마다 담당 영역과 검색어가 따로 있고, 재료도 번호별 묶음으로
돌려준다. market_summary.py가 이 묶음을 받아 제목·헤드라인과 번호별 불릿을
만든다. 마감 브리핑에서만 부른다 — 장중 실행에서는 만들어도 emit이 버린다.

재료는 요약하는 장의 시간대(session_window)에 나온 기사로만 제한한다.
"""

import re
from datetime import datetime, timedelta
from typing import List, NamedTuple, Tuple
from zoneinfo import ZoneInfo

from config import (KST, MARKET_NEWS_EXCLUDE, MARKET_NEWS_PER_QUERY, MARKET_NEWS_PER_SLOT,
                    MARKET_SESSION, MARKET_SESSION_LEAD_HOURS, MARKET_SUMMARY_SLOTS)
from news import NewsItem, _dedupe, _google_items


# "[뉴욕증시 29일] …"처럼 제목에 날짜(일)가 박힌 시황 기사는 구글뉴스가 지난 달 기사를
# 오늘 날짜로 다시 띄우는 일이 있다 — 그날 시황이 오늘 시황인 것처럼 요약에 섞인다.
_DAY_TAG = re.compile(r"^\[\s*뉴욕\s*증시\s*(\d{1,2})일\s*\]")


class Window(NamedTuple):
    start: datetime   # KST
    end: datetime     # KST — 발송 기준 시각(국내 18:00 · 미국 07:00). 그 전에 돌면 지금
    day: datetime     # 요약하는 장의 날짜(현지)


class Slot(NamedTuple):
    key: str
    label: str
    news: List[NewsItem]


def _stale_day_tag(title: str, now: datetime) -> bool:
    """제목의 'N일'이 오늘·어제(KST)가 아니면 True — 옛 기사가 재발행된 것."""
    m = _DAY_TAG.match(title or "")
    if not m:
        return False
    return int(m.group(1)) not in {now.day, (now - timedelta(days=1)).day}


def session_window(market: str, now: datetime) -> Window:
    """요약할 장의 재료 시간대 — 개장 LEAD시간 전 ~ 발송 기준 시각(cutoff_kst).

    cutoff은 마감 직후에 오는 그 시각이다(국내 15:30 → 같은 날 18:00, 미국 16:00 ET
    → 한국 시간 다음 날 07:00). 언제 돌려도 정시 발송본과 같은 범위의 기사만 쓴다.

    아직 그날 장이 안 끝났으면(현지 마감 전) 직전 거래일을 요약한다. 주말은
    금요일로 물린다. 공휴일은 따로 거르지 않는다 — 휴장일엔 마감 기사가 없어
    재료가 비고, 요약은 조용히 건너뛴다.
    """
    s = MARKET_SESSION[market]
    local = now.astimezone(ZoneInfo(s["tz"]))
    day = local
    if (local.hour, local.minute) < s["close"]:
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    open_ = day.replace(hour=s["open"][0], minute=s["open"][1], second=0, microsecond=0)
    close = open_.replace(hour=s["close"][0], minute=s["close"][1])
    start = open_ - timedelta(hours=MARKET_SESSION_LEAD_HOURS)
    close_kst = close.astimezone(KST)
    cutoff = close_kst.replace(hour=s["cutoff_kst"][0], minute=s["cutoff_kst"][1])
    if cutoff < close_kst:
        cutoff += timedelta(days=1)
    end = min(cutoff, now.astimezone(KST))
    return Window(start.astimezone(KST), end, day)


def fetch_slot_news(market: str, now: datetime) -> Tuple[Window, List[Slot]]:
    """market: 'kr' | 'us'. 번호별 재료 묶음을 config 순서대로 돌려준다.

    검색어마다 따로 최신순으로 잘라 담는다 — 한 통에 모아 자르면 기사가 제일 많은
    검색어 하나가 묶음을 다 먹는다. 같은 기사가 두 검색어에 걸리면 한 번만 담는다.
    번호끼리는 겹쳐도 둔다(예: 마감 시황 한 건이 수급·업종 재료에 다 쓰일 수 있다).
    """
    win = session_window(market, now)
    banned = MARKET_NEWS_EXCLUDE.get(market, [])
    slots: List[Slot] = []
    for key, label, queries in MARKET_SUMMARY_SLOTS.get(market, []):
        seen, out = set(), []
        for q in queries:
            items = [n for n in _dedupe(_google_items(q))
                     if win.start <= n.published <= win.end
                     and not any(w in n.title for w in banned)
                     and not _stale_day_tag(n.title, now)]
            items.sort(key=lambda n: n.published, reverse=True)
            for n in items[:MARKET_NEWS_PER_QUERY]:
                if n.url not in seen:
                    seen.add(n.url)
                    out.append(n)
        out.sort(key=lambda n: n.published, reverse=True)
        slots.append(Slot(key, label, out[:MARKET_NEWS_PER_SLOT]))
    return win, slots
