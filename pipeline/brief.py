"""가격과 뉴스를 브리핑 문장으로 조립한다.

LLM을 쓰지 않고 규칙으로만 만든다. 카드 본문은 '가격 문장 + 뉴스 헤드라인' 순인데,
프로토타입 카드가 본문을 3줄에서 잘라내기 때문에(-webkit-line-clamp:3)
반드시 보여야 할 숫자를 앞에 둔 것이다. 뉴스 원문·출처·링크는 마크다운에 전부 남는다.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from config import KST
from news import NewsItem
from portfolio import Holding
from prices import Quote

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# 종목명이 알파벳·숫자로 끝나도 조사가 맞도록 — 마지막 글자의 한글 독음에 받침이 있는지
_TRAILING_CONSONANT = {
    "F": True, "H": True, "L": True, "M": True, "N": True, "R": True, "S": True, "X": True,
    "0": True, "1": True, "3": True, "6": True, "7": True, "8": True,
}


def has_batchim(word: str) -> bool:
    """마지막 글자에 받침이 있으면 True."""
    word = (word or "").strip()
    if not word:
        return False
    ch = word[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return _TRAILING_CONSONANT.get(ch.upper(), False)


def josa(word: str, with_batchim: str, without: str) -> str:
    """'삼성전자' + ('이','가') → '삼성전자가'"""
    return word + (with_batchim if has_batchim(word) else without)

BIG_MOVE_PCT = 5.0     # 이 이상 움직이면 '오늘의 액션'에 올린다
QUIET_PCT = 2.0        # 전 종목이 이 안에 있으면 조용한 날로 본다

# 카드가 잘리지 않고 꽉 차는 분량.
#
# 글자 수로는 맞출 수 없다 — 브라우저에서 실측하면 카드 한 줄(319px)에
# 한글은 25자(12.8px/자), 영문·숫자는 42자(7.6px/자)가 들어간다. 같은 101자여도
# 한글이 많으면 넘치고 숫자가 많으면 남는다. 그래서 '한글 몇 자 분량'으로 환산해
# 폭을 예산으로 쓴다. 영문 계수 0.6은 7.6/12.8에서 나온 값이다.
#
# 홈 카드와 Portfolios의 '시간대별 브리핑' 카드는 높이만 다르고(스탬프 줄 14px)
# 글자 영역은 둘 다 319px 폭 · 제목 1줄 · 본문 3줄이라 같은 예산을 쓴다.
LINE_UNITS = 25.0            # 한 줄에 들어가는 한글 글자 수
CARD_TITLE_UNITS = LINE_UNITS        # 제목 1줄 (종목명 포함)
CARD_BODY_UNITS = LINE_UNITS * 3     # 본문 3줄 (-webkit-line-clamp:3)
LATIN_UNIT = 0.6
ELLIPSIS = "…"

_TAG = re.compile(r"</?b>")


def visible(text: str) -> str:
    """폭을 잴 때 쓰는 실제 표시 문자열 — <b> 태그를 뺀 것."""
    return _TAG.sub("", text or "")


def char_units(ch: str) -> float:
    """글자 하나의 폭을 한글 한 글자 = 1.0으로 환산한다."""
    o = ord(ch)
    if (0xAC00 <= o <= 0xD7A3            # 한글 음절
            or 0x1100 <= o <= 0x11FF     # 한글 자모
            or 0x3130 <= o <= 0x318F     # 호환 자모
            or 0x3000 <= o <= 0x303F     # CJK 문장부호 (、。〈〉…)
            or 0x4E00 <= o <= 0x9FFF     # 한자
            or 0xFF00 <= o <= 0xFF60):   # 전각
        return 1.0
    if ch in "…—–·":                     # 본문에 자주 섞이는 전각폭 기호
        return 1.0
    return LATIN_UNIT


def text_units(text: str) -> float:
    return sum(char_units(c) for c in text)


def fit(text: str, budget: float) -> str:
    """예산(한글 환산 글자 수)을 넘지 않게 자른다. 자를 때는 끝에 …를 붙인다."""
    text = " ".join((text or "").split())
    if budget <= 0:
        return ""
    if text_units(text) <= budget:
        return text

    room = budget - char_units(ELLIPSIS)
    out, used = [], 0.0
    for ch in text:
        w = char_units(ch)
        if used + w > room:
            break
        out.append(ch)
        used += w
    return "".join(out).rstrip() + ELLIPSIS


@dataclass
class StockBrief:
    holding: Holding
    quote: Quote
    news: List[NewsItem]
    # LLM 요약 결과 {"title_tail":…, "reason":…}. 없으면 규칙 기반으로 쓴다.
    summary: Optional[dict] = None
    # 시간대별 슬롯 (Portfolios 탭 전용) — 시세와 문구를 나눠 담는다
    slots: Optional[list] = None
    slot_texts: Optional[list] = None

    @property
    def name(self) -> str:
        return self.holding.name

    @property
    def pct(self) -> Optional[float]:
        return self.quote.change_pct


# ------------------------------------------------------------------ 문장 조립

def price_sentence(q: Quote, html_bold: bool = True) -> str:
    """'+3.21% 오른 171,800원 마감.' 꼴의 한 문장."""
    if not q.ok:
        return "시세를 가져오지 못했습니다."

    price = q.format_price()
    if html_bold:
        price = "<b>{}</b>".format(price)

    pct = q.change_pct
    if pct is None:
        return "{} 마감.".format(price)
    if abs(pct) < 0.005:
        return "보합인 {} 마감.".format(price)
    verb = "오른" if pct > 0 else "내린"
    return "{:+.2f}% {} {} 마감.".format(pct, verb, price)


def _shorten(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def card_title(sb: StockBrief) -> str:
    """'종목명 - 사건 요약'을 제목 한 줄 폭에 맞춰 채운다.

    LLM 요약이 있으면 그 사건 요약을, 없으면 첫 헤드라인을 그대로 쓴다.
    """
    prefix = "{} - ".format(sb.name)
    room = CARD_TITLE_UNITS - text_units(prefix)

    tail = (sb.summary or {}).get("title_tail") or ""
    if tail and room > 0:
        return prefix + fit(tail, room)

    if sb.news:
        if room > 0:
            return prefix + fit(sb.news[0].title, room)
        return fit(sb.name, CARD_TITLE_UNITS)

    pct = sb.pct
    if pct is None:
        tail = "시세 확인 필요"
    elif abs(pct) < 0.005:
        tail = "전일과 같은 수준"
    else:
        tail = "전일 대비 {:+.2f}%".format(pct)
    return fit("{} - {}".format(sb.name, tail), CARD_TITLE_UNITS)


def card_body(sb: StockBrief) -> str:
    """'가격 문장 + 뉴스 헤드라인'을 본문 3줄 폭에 맞춰 채운다.

    가격 문장은 절대 자르지 않고, 남는 자리를 헤드라인으로 끝까지 메운다.
    헤드라인은 원문이라 문장 중간에서 끊길 수 있다 — 대신 카드가 고르게 찬다.
    뉴스가 짧으면 3줄을 못 채우고 그대로 끝난다(빈 칸을 지어내지 않는다).
    """
    price = price_sentence(sb.quote)
    room = CARD_BODY_UNITS - text_units(visible(price)) - char_units(" ")
    if room <= 0:
        return price

    # LLM 요약이 있으면 시안처럼 '원인절 → 가격' 순으로 간다.
    # 길이를 미리 확정해 두므로 원인절이 잘려나갈 걱정 없이 가격을 뒤에 둘 수 있다.
    if sb.summary is not None:
        reason = sb.summary.get("reason") or ""
        if reason:
            return "{} {}".format(fit(reason, room), price)
        # 요약은 돌았는데 원인절이 비었다 = 오늘 움직임을 설명할 재료가 없다는 판단.
        # 여기서 헤드라인을 쏟아내면 제목("특별한 이슈 없이")과 어긋난다.
        return "{} 주가를 움직인 뚜렷한 재료는 확인되지 않았습니다.".format(price)

    # 규칙 기반은 가격을 앞에 둔다 — 헤드라인 나열이 잘려도 숫자는 보여야 한다.
    if sb.news:
        tail = " · ".join(n.title for n in sb.news)
    else:
        tail = "오늘 새로 올라온 뉴스는 없습니다."
    return "{} {}".format(price, fit(tail, room))


# -------------------------------------------------------- 핵심 한 줄 / 액션

def _movers(briefs: List[StockBrief]):
    scored = [b for b in briefs if b.pct is not None]
    if not scored:
        return None, None
    scored.sort(key=lambda b: b.pct, reverse=True)
    return scored[0], scored[-1]


def headline_line(briefs: List[StockBrief], market_label: str) -> str:
    """'오늘의 핵심 한 줄' — 오른 종목 수와 최대 상승/하락 종목으로 만든다."""
    scored = [b for b in briefs if b.pct is not None]
    if not scored:
        return "{} 종목의 시세를 가져오지 못해 오늘 흐름을 판단할 수 없습니다.".format(market_label)

    up = [b for b in scored if b.pct > 0]
    down = [b for b in scored if b.pct < 0]
    best, worst = _movers(scored)

    head = "{} {}종목 중 {}종목 상승".format(market_label, len(scored), len(up))
    if down:
        head += ", {}종목 하락".format(len(down))

    # 전 종목이 내린 날에는 "가장 많이 올랐고"라고 쓰면 안 된다
    best_verb = "가장 많이 올랐고" if best.pct > 0 else "낙폭이 가장 작았고"
    tail = "{} {:+.2f}%로 {}".format(josa(best.name, "이", "가"), best.pct, best_verb)
    if worst is not best:
        worst_verb = "가장 부진했습니다" if worst.pct < 0 else "상승폭이 가장 작았습니다"
        tail += " {} {:+.2f}%로 {}.".format(
            josa(worst.name, "이", "가"), worst.pct, worst_verb)
    else:
        tail += " 나머지는 큰 변동이 없었습니다."
    return "{} — {}".format(head, tail)


def action_items(briefs: List[StockBrief]) -> List[str]:
    """규칙 기반 '오늘의 액션'."""
    actions = []

    for b in briefs:
        if not b.quote.ok:
            actions.append(
                "{}({}) 시세 조회 실패 — 티커가 맞는지 확인하세요. [{}]".format(
                    b.name, b.holding.ticker, b.quote.error or "원인 미상")
            )

    big = [b for b in briefs if b.pct is not None and abs(b.pct) >= BIG_MOVE_PCT]
    big.sort(key=lambda b: abs(b.pct), reverse=True)
    for b in big:
        word = "급등" if b.pct > 0 else "급락"
        reason = b.news[0].title if b.news else "관련 뉴스 없음"
        actions.append("{} {} {:+.2f}% — {}".format(b.name, word, b.pct, _shorten(reason, 50)))

    silent = [b for b in briefs if b.quote.ok and not b.news]
    if silent:
        actions.append(
            "뉴스가 한 건도 안 잡힌 종목: {} — 검색어(종목명)를 조정해 보세요.".format(
                ", ".join(b.name for b in silent))
        )

    moved = [b for b in briefs if b.pct is not None]
    if moved and not big and all(abs(b.pct) < QUIET_PCT for b in moved):
        actions.append("전 종목이 ±{:.0f}% 안에서 움직였습니다. 오늘은 볼 것이 없습니다.".format(QUIET_PCT))

    return actions or ["특이사항 없음."]


# ------------------------------------------------------------------ 마크다운

def _fmt_date(d) -> str:
    return d.strftime("%Y-%m-%d") if d else "-"


def _price_table(briefs: List[StockBrief]) -> List[str]:
    lines = [
        "| 종목 | 티커 | 종가 | 전일 대비 | 기준 거래일 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for b in briefs:
        q = b.quote
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                b.name, q.ticker, q.format_price(), q.format_change(), _fmt_date(q.as_of)
            )
        )
    return lines


def _news_section(briefs: List[StockBrief]) -> List[str]:
    lines = []
    for b in briefs:
        lines.append("")
        lines.append("#### {} ({}) — {} {}".format(
            b.name, b.quote.ticker, b.quote.format_price(), b.quote.format_change()))
        if not b.news:
            lines.append("")
            lines.append("- 오늘자 뉴스 없음")
            continue
        lines.append("")
        for n in b.news:
            mark = "" if n.is_today else " _(24시간 내)_"
            line = "- [{}]({}) — {} · {}{}".format(n.title, n.url, n.source, n.stamp, mark)
            if n.translated:
                line += "\n  - 원문: {}".format(n.original_title)
            lines.append(line)
    return lines


def build_markdown(sections, now: datetime) -> str:
    """sections: [(제목, [StockBrief], 시장라벨), ...]"""
    stamp = "{} ({}) {}".format(
        now.strftime("%Y-%m-%d"), WEEKDAYS[now.weekday()], now.strftime("%H:%M"))
    scope = " · ".join(title for title, briefs, _ in sections if briefs)

    out = ["# 노트폴리오 데일리 브리핑{} — {} KST".format(
        (" · " + scope) if scope else "", stamp), ""]

    all_briefs = [b for _, briefs, _ in sections for b in briefs]

    out.append("## 가격 요약")
    out.append("")
    for title, briefs, _ in sections:
        if not briefs:
            continue
        out.append("**{}**".format(title))
        out.append("")
        out.extend(_price_table(briefs))
        out.append("")

    out.append("## 종목별 뉴스")
    for title, briefs, _ in sections:
        if not briefs:
            continue
        out.append("")
        out.append("### {}".format(title))
        out.extend(_news_section(briefs))
    out.append("")

    out.append("## 오늘의 핵심 한 줄")
    out.append("")
    for _, briefs, label in sections:
        if briefs:
            out.append("- {}".format(headline_line(briefs, label)))
    out.append("")

    out.append("## 오늘의 액션")
    out.append("")
    for a in action_items(all_briefs):
        out.append("- {}".format(a))
    out.append("")

    return "\n".join(out)


def build_briefs(holdings: List[Holding],
                 quotes: Dict[str, Quote],
                 news: Dict[str, List[NewsItem]]) -> List[StockBrief]:
    return [
        StockBrief(holding=h,
                   quote=quotes.get(h.ticker) or Quote(h.ticker, h.name, h.market,
                                                       error="시세 조회 안 됨"),
                   news=news.get(h.ticker, []))
        for h in holdings
    ]
