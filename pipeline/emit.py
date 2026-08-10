"""프로토타입(index.html)이 읽는 형태로 브리핑을 내보낸다.

index.html은 file://로 열리는 일이 많은데 그 상태에서는 fetch()가 CORS로 막힌다.
그래서 진짜 산출물은 data/briefing.js — `window.NOTEFOLIO_BRIEFING = {...}` 한 줄짜리
스크립트다. <script src>로 읽으면 로컬 서버 없이도 동작한다.
data/briefing.json은 같은 내용을 사람이 보거나 다른 도구가 쓰라고 함께 남긴다.
"""

import json
from datetime import datetime
from typing import Dict, List

from brief import StockBrief, card_body, card_title, headline_line
from config import BRIEFING_JS, BRIEFING_JSON, KST

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
            "is_close": s.is_close,
            # 장중에 돌리면 슬롯은 직전 거래일 것이라 카드 as_of와 다를 수 있다
            "date": s.day.isoformat() if getattr(s, "day", None) else None,
            "title": t.get("title", ""),
            "text": t.get("text", ""),
        })
    return out


def _market_payload(key: str, briefs: List[StockBrief], now: datetime) -> dict:
    meta = MARKET_META[key]
    return {
        "icon": meta["icon"],
        "label": _label(key, now),
        # 칩은 짧게 — 해외는 티커(MSFT), 국내는 종목명(SK하이닉스).
        # 카드 본문·제목은 그대로 한글 종목명을 쓴다.
        "chips": ["전체"] + [
            b.name if b.holding.is_kr else b.quote.ticker for b in briefs],
        "allReadSub": meta["allReadSub"],
        "next": meta["next"],
        "headline": headline_line(briefs, meta["label_ko"]) if briefs else "",
        "cards": [
            {
                "stock": b.name,
                "ticker": b.quote.ticker,
                "title": card_title(b),
                "body": card_body(b),
                "pct": None if b.pct is None else round(b.pct, 2),
                "price": b.quote.close,
                "currency": b.quote.currency,
                "as_of": b.quote.as_of.isoformat() if b.quote.as_of else None,
                "slots": _slots_payload(b),
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


def _load_previous() -> dict:
    """직전 산출물. 이번에 갱신하지 않는 시장의 데이터를 살려두려고 읽는다."""
    try:
        with open(BRIEFING_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def build_payload(briefs_by_market: Dict[str, List[StockBrief]],
                  now: datetime, markdown_path: str = "") -> dict:
    """이번 실행이 맡은 시장만 새로 쓰고, 나머지 시장은 직전 것을 그대로 둔다.

    오전 7시 실행은 미국만, 오후 6시 실행은 한국만 갱신한다. 그래도 프로토타입의
    시장 전환 버튼이 살아 있어야 하므로 반대편 시장은 지우지 않고 남긴다.
    """
    previous = _load_previous()
    markets = dict(previous.get("markets") or {})

    refreshed = []
    for key, briefs in briefs_by_market.items():
        if not briefs:
            continue
        payload = _market_payload(key, briefs, now)
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
