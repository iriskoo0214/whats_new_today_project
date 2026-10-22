"""프로토타입(index.html)이 읽는 형태로 브리핑을 내보낸다.

index.html은 file://로 열리는 일이 많은데 그 상태에서는 fetch()가 CORS로 막힌다.
그래서 진짜 산출물은 data/briefing.js — `window.NOTEFOLIO_BRIEFING = {...}` 한 줄짜리
스크립트다. <script src>로 읽으면 로컬 서버 없이도 동작한다.
data/briefing.json은 같은 내용을 사람이 보거나 다른 도구가 쓰라고 함께 남긴다.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from brief import StockBrief, card_body, card_title, headline_line
from config import (BRIEFING_JS, BRIEFING_JSON, INTRADAY_TIMES_KR,
                    INTRADAY_TIMES_US, KST)

MARKET_META = {
    "us": {
        "icon": "assets/sun-horizon.svg",
        "title": "미국 증시 요약",
        "label_ko": "해외",
        "next": "kr",
        "allReadSub": ["오후 6시, 국내 시장을 움직인 이유를 확인하세요."],
    },
    "kr": {
        "icon": "assets/moon.svg",
        "title": "한국 증시 요약",
        "label_ko": "국내",
        "next": "us",
        "allReadSub": ["내일 오전 7시, 미국 시장 브리핑으로", "다시 찾아올게요."],
    },
}


def _label(key: str, now: datetime) -> str:
    hour12 = now.hour % 12 or 12
    ampm = "AM" if now.hour < 12 else "PM"
    return "{} {}. {}. {}. {}:{:02d}{}".format(
        MARKET_META[key]["title"], now.year, now.month, now.day, hour12, now.minute, ampm
    )


def _slot_total(holding) -> int:
    """그 시장의 하루 슬롯 수 — 지정한 시각들 + 마감."""
    times = INTRADAY_TIMES_KR if holding.is_kr else INTRADAY_TIMES_US
    return len(times) + 1


def _slots_payload(sb: StockBrief) -> list:
    """시간대별 슬롯 — Portfolios 탭에서만 쓴다. 없으면 빈 배열."""
    slots = getattr(sb, "slots", None) or []
    texts = getattr(sb, "slot_texts", None) or []
    out = []
    for i, s in enumerate(slots):
        t = texts[i] if i < len(texts) else {}
        out.append({
            "time": s.label,
            "price": s.price,
            "pct": None if s.pct is None else round(s.pct, 2),
            # 등락률의 기준선(그 슬롯 날짜의 전 거래일 종가). Portfolios 바에 그대로 적는다.
            # 슬롯이 직전 거래일 것일 때는 시세의 prev_close와 다르다(intraday.fetch_slots).
            "prev_close": None if s.pct is None else getattr(s, "prev_close", None),
            "is_close": s.is_close,
            # 장중에 돌리면 슬롯은 직전 거래일 것이라 카드 as_of와 다를 수 있다
            "date": s.day.isoformat() if getattr(s, "day", None) else None,
            "title": t.get("title", ""),
            "text": t.get("text", ""),
        })
    return out


def _market_payload(key: str, briefs: List[StockBrief], now: datetime,
                    market_summary: Optional[dict] = None) -> dict:
    meta = MARKET_META[key]
    payload = {
        "icon": meta["icon"],
        "label": _label(key, now),
        # 칩은 짧게 — 해외는 티커(MSFT), 국내는 종목명(SK하이닉스).
        # 카드 본문·제목은 그대로 한글 종목명을 쓴다.
        "chips": ["전체"] + [
            b.name if b.holding.is_kr else b.quote.ticker for b in briefs],
        "allReadSub": meta["allReadSub"],
        "next": meta["next"],
        "headline": headline_line(briefs, meta["label_ko"]) if briefs else "",
        # market_headline/market_card — Home 탭 상단 "OO장 마감 요약" 배지와
        # "OO장 어땠지" 3줄 카드. 보유종목이 아니라 시장 전체(지수·유가·금리)
        # 뉴스로 만든다(market_news.py, market_summary.py). LLM이 없거나
        # 실패하면 market_summary가 None으로 와서 두 필드 다 비워둔다 —
        # 프론트는 이 값이 없으면 그 블록을 숨기면 된다.
        "market_headline": (market_summary or {}).get("headline", ""),
        "market_card": (market_summary or {}).get("card"),
        "cards": [
            {
                "stock": b.name,
                "ticker": b.quote.ticker,
                "title": card_title(b),
                "body": card_body(b),
                "pct": None if b.pct is None else round(b.pct, 2),
                "price": b.quote.close,
                "prev_close": b.quote.prev_close,
                "currency": b.quote.currency,
                "as_of": b.quote.as_of.isoformat() if b.quote.as_of else None,
                "slots": _slots_payload(b),
                # 그 시장에 원래 있는 슬롯 수(국내 4 · 해외 2). 진행 바는 이걸로
                # 나눠야 한다 — 있는 슬롯 수로 나누면 장중에 11:00PM 하나뿐일 때
                # 1/1이 되어 하루가 다 간 것처럼 꽉 찬다.
                "slot_total": _slot_total(b.holding),
                "news": [
                    {"title": n.title, "original": n.original_title,
                     "source": n.source, "url": n.url,
                     "published": n.published.isoformat()}
                    for n in b.news
                ],
            }
            for b in briefs
        ],
    }
    return payload


def _load_previous() -> dict:
    """직전 산출물. 이번에 갱신하지 않는 시장의 데이터를 살려두려고 읽는다."""
    try:
        with open(BRIEFING_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _merge_slots(prev_market: dict, briefs: List[StockBrief], now: datetime) -> dict:
    """직전 마감 브리핑은 그대로 두고 시간대별 슬롯만 갈아끼운다.

    장중 실행이 쓰는 길이다. 홈 탭은 하루 두 번 마감 브리핑만 보여주기로 돼 있어서
    (config.INTRADAY_ENABLED 옆 설명) 장중에 카드 제목·본문·헤드라인·라벨까지
    덮어쓰면 오전 10시에 '한국 증시 요약 10:40AM'이 마감 요약 자리에 앉는다.
    그래서 여기서는 Portfolios 탭이 읽는 slots만 건드린다.

    슬롯을 못 받은 종목은 직전 것을 남긴다 — 비우는 것보다 낫다.
    """
    fresh = {b.quote.ticker: b for b in briefs if getattr(b, "slots", None)}
    if not fresh:
        return prev_market

    market = dict(prev_market)
    cards = []
    for card in market.get("cards") or []:
        b = fresh.get(card.get("ticker"))
        if b is None:
            cards.append(card)
            continue
        card = dict(card)
        card["slots"] = _slots_payload(b)
        card["slot_total"] = _slot_total(b.holding)
        cards.append(card)
    market["cards"] = cards
    market["slots_refreshed_at"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    return market


def build_payload(briefs_by_market: Dict[str, List[StockBrief]],
                  now: datetime, markdown_path: str = "",
                  slots_only: bool = False,
                  market_summaries: Optional[Dict[str, dict]] = None) -> dict:
    """이번 실행이 맡은 시장만 새로 쓰고, 나머지 시장은 직전 것을 그대로 둔다.

    오전 7시 실행은 미국만, 오후 6시 실행은 한국만 갱신한다. 그래도 프로토타입의
    시장 전환 버튼이 살아 있어야 하므로 반대편 시장은 지우지 않고 남긴다.

    slots_only면 마감 브리핑은 손대지 않고 시간대별 슬롯만 갱신한다. 장중에 도는
    실행이 여기에 해당한다. refreshed에도 넣지 않는다 — 그 목록이 default 시장을
    정하는데, 장중 슬롯 갱신 때문에 홈 탭이 국내로 뒤집히면 안 된다.

    market_summaries는 {"kr": {...}, "us": {...}} — run_daily.py가 마감
    브리핑에서만 채워서 넘긴다(market_news.py + market_summary.py). slots_only
    실행은 애초에 안 만들므로 여기서도 자연히 비워진다.
    """
    previous = _load_previous()
    markets = dict(previous.get("markets") or {})
    market_summaries = market_summaries or {}

    refreshed, slots_refreshed = [], []
    for key, briefs in briefs_by_market.items():
        if not briefs:
            continue
        # 직전 산출물이 없으면 슬롯만 갈아끼울 대상도 없다. 통째로 쓴다.
        if slots_only and markets.get(key):
            markets[key] = _merge_slots(markets[key], briefs, now)
            slots_refreshed.append(key)
            continue
        payload = _market_payload(key, briefs, now, market_summaries.get(key))
        payload["markdown"] = markdown_path
        payload["refreshed_at"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        markets[key] = payload
        refreshed.append(key)

    # 방금 갱신한 시장을 먼저 보여준다
    default = refreshed[0] if refreshed else previous.get("default")
    if default not in markets:
        default = next(iter(markets), None)

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "refreshed": refreshed,
        "slots_refreshed": slots_refreshed,
        "default": default,
        "markets": markets,
    }


def write(payload: Dict) -> None:
    with open(BRIEFING_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(BRIEFING_JS, "w", encoding="utf-8") as f:
        f.write("/* 자동 생성 — pipeline/run_daily.py가 덮어쓴다. 직접 고치지 마세요. */\n")
        f.write("window.NOTEFOLIO_BRIEFING = ")
        f.write(body)
        f.write(";\n")
