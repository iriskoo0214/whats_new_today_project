"""종목별 오늘자 뉴스를 모은다.

국내: Google News RSS의 when:1d 검색 — KST 기준 오늘 발행분만 남긴다.
해외: yfinance Ticker(...).news + Google News RSS(한글명·영문명) 를 합친다.
      yfinance만 쓰면 무관한 기사(NVDA 뉴스에 리얼티 인컴 배당)가 섞여 들어와서,
      종목명·티커가 제목에 없는 기사는 걸러낸다. 영문 헤드라인만 한글로 옮긴다.

오전 7시에 돌리면 "KST 오늘"에 해당하는 국내 뉴스는 7시간치뿐이라 자주 빈다.
그래서 3건이 안 차면 최근 24시간 안에서 채우고(NEWS_FALLBACK_24H),
각 항목이 언제 나온 기사인지 published에 남겨 브리핑에서 그대로 보여준다.
"""

import html
import re
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from config import (HTTP_TIMEOUT, KST, NEWS_FALLBACK_24H, NEWS_PER_STOCK,
                    TRANSLATE_HEADLINES, USER_AGENT)
from portfolio import Holding

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


@dataclass
class NewsItem:
    title: str                        # 화면에 쓰는 제목 (해외는 번역본)
    original_title: str
    source: str
    url: str
    published: datetime               # KST
    translated: bool = False
    is_today: bool = True             # KST 기준 오늘 발행분인지

    @property
    def stamp(self) -> str:
        return self.published.strftime("%m/%d %H:%M")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read()


def _pick(items: List[NewsItem], now: datetime,
          limit: int = NEWS_PER_STOCK) -> List[NewsItem]:
    """오늘 발행분을 먼저 채우고, 모자라면 최근 24시간으로 보충한다.

    limit 기본값은 종목당 개수(NEWS_PER_STOCK)지만, market_news.py는 시장 전체
    후보 목록을 더 넉넉히 받아야 해서 다른 값을 넘긴다.
    """
    today = now.date()
    for it in items:
        it.is_today = it.published.date() == today

    items.sort(key=lambda i: i.published, reverse=True)
    picked = [i for i in items if i.is_today][:limit]

    if NEWS_FALLBACK_24H and len(picked) < limit:
        cutoff = now - timedelta(hours=24)
        seen = {i.url for i in picked}
        for i in items:
            if len(picked) >= limit:
                break
            if i.url not in seen and i.published >= cutoff:
                picked.append(i)
                seen.add(i.url)
        picked.sort(key=lambda i: i.published, reverse=True)
    return picked


# ---------------------------------------------------------- 국내 (Google News)

def _clean_google_title(title: str):
    """구글 뉴스 제목은 '기사 제목 - 언론사' 꼴이라 뒤쪽 언론사를 떼어낸다."""
    title = html.unescape(title or "").strip()
    if " - " in title:
        head, _, tail = title.rpartition(" - ")
        if head and len(tail) <= 25:
            return head.strip(), tail.strip()
    return title, ""


def _google_items(query: str) -> List[NewsItem]:
    """Google News RSS(한국어) 검색 결과를 NewsItem으로 돌려준다."""
    url = "{}?{}".format(
        GOOGLE_NEWS_RSS,
        urllib.parse.urlencode(
            {"q": "{} when:1d".format(query), "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
        ),
    )
    try:
        root = ET.fromstring(_get(url))
    except Exception:
        return []

    items = []
    for node in root.iterfind("./channel/item"):
        title_raw = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub = node.findtext("pubDate")
        if not title_raw or not pub:
            continue
        try:
            published = parsedate_to_datetime(pub).astimezone(KST)
        except Exception:
            continue
        title, source = _clean_google_title(title_raw)
        if not source:
            source = (node.findtext("source") or "Google News").strip()
        items.append(
            NewsItem(title=title, original_title=title, source=source,
                     url=link, published=published)
        )
    return items


def fetch_kr_news(holding: Holding, now: datetime) -> List[NewsItem]:
    return _pick(_google_items(holding.name), now)


# ------------------------------------------------------------ 해외 (yfinance)

def _yf_field(item: dict) -> Optional[dict]:
    """yfinance 1.x는 {'content': {...}}, 구버전은 평평한 dict를 준다."""
    content = item.get("content")
    if isinstance(content, dict) and content.get("title"):
        pub = content.get("pubDate") or content.get("displayTime")
        published = None
        if pub:
            try:
                published = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
            except ValueError:
                published = None
        url = ""
        for key in ("canonicalUrl", "clickThroughUrl"):
            node = content.get(key)
            if isinstance(node, dict) and node.get("url"):
                url = node["url"]
                break
        provider = content.get("provider") or {}
        return {
            "title": content["title"],
            "published": published,
            "url": url,
            "source": provider.get("displayName") or "Yahoo Finance",
        }

    if item.get("title"):
        ts = item.get("providerPublishTime")
        published = (datetime.fromtimestamp(ts, tz=timezone.utc)
                     if isinstance(ts, (int, float)) else None)
        return {
            "title": item["title"],
            "published": published,
            "url": item.get("link", ""),
            "source": item.get("publisher") or "Yahoo Finance",
        }
    return None


def _mentions(item: NewsItem, holding: Holding) -> bool:
    """이 종목을 실제로 다루는 기사인지 본다.

    yfinance의 종목 뉴스에는 다른 회사 기사나 일반 투자 조언이 섞여 들어온다
    (NVDA 뉴스에 리얼티 인컴 배당 기사가 오는 식). 종목명·티커가 제목에 없으면 버린다.
    """
    text = "{} {}".format(item.title, item.original_title).lower()
    needles = [holding.name, holding.ticker, holding.extra.get("en_name") or ""]
    return any(n and n.lower() in text for n in needles)


def _dedupe(items: List[NewsItem]) -> List[NewsItem]:
    """같은 기사가 두 소스에서 겹쳐 들어오는 것을 제목 기준으로 정리한다."""
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\W+", "", it.title.lower())[:40]
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def fetch_us_news(holding: Holding, now: datetime) -> List[NewsItem]:
    """yfinance(영문) + Google News RSS(한글)를 합쳐 쓴다.

    yfinance만으로는 무관한 기사만 잡히는 날이 있어서, 한글 검색 결과를 함께 본다.
    한글 기사는 번역도 필요 없다.
    """
    import yfinance as yf

    items = []
    try:
        for entry in yf.Ticker(holding.ticker).news or []:
            f = _yf_field(entry) if isinstance(entry, dict) else None
            if not f or not f["published"]:
                continue
            items.append(NewsItem(
                title=f["title"], original_title=f["title"], source=f["source"],
                url=f["url"], published=f["published"].astimezone(KST)))
    except Exception:
        pass

    items += _google_items(holding.name)                 # 한글 기사
    en = holding.extra.get("en_name")
    if en and en.lower() != holding.name.lower():
        items += _google_items(en)                       # 영문명으로도 한 번

    items = _dedupe([i for i in items if _mentions(i, holding)])
    return _pick(items, now)   # 번역은 fetch_all에서 한 번에 몰아서 한다


# ---------------------------------------------------------------------------

def _translate_in_place(items: List[NewsItem]) -> None:
    """해외 헤드라인을 한 번의 API 호출로 모두 번역한다(종목별로 부르면 5배 든다)."""
    if not items:
        return
    from translate import to_korean_batch
    pairs = to_korean_batch([i.original_title for i in items])
    for item, (text, ok) in zip(items, pairs):
        item.title, item.translated = text, ok


def fetch_all(holdings: List[Holding], now: Optional[datetime] = None
              ) -> Dict[str, List[NewsItem]]:
    now = now or datetime.now(KST)
    out = {}
    for h in holdings:
        out[h.ticker] = fetch_kr_news(h, now) if h.is_kr else fetch_us_news(h, now)

    if TRANSLATE_HEADLINES:
        _translate_in_place(
            [item for h in holdings if not h.is_kr for item in out[h.ticker]])
    return out
