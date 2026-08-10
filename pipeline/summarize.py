"""카드 문구를 LLM으로 요약한다.

헤드라인을 이어붙이는 대신, 오늘 그 종목에 있었던 일을 한 구절(제목)과
한 문장(본문 원인절)으로 압축한다. 프로토타입 시안의 문체가 목표다.

    아이온큐 - 스카이워터 인수 완료, 퀀텀 수직계열화 완성
    자국산 파운드리 확보로 퀀텀 하드웨어 수직계열화 기대감이 부각되며 매수세
    유입, 인수 완료 소식에 투자심리 개선. +9% 오른 36.44달러 마감.

역할을 나눈 이유:
  · 가격 문장("+9% 오른 36.44달러 마감.")은 파이썬이 계산해 뒤에 붙인다.
    숫자를 LLM에 맡기면 틀릴 수 있고, 길이도 미리 확정해야 예산을 나눌 수 있다.
  · LLM은 제목 꼬리와 원인절만 쓴다. 남은 폭을 글자 수로 환산해 프롬프트에 준 뒤,
    받아온 문장을 파이썬이 다시 폭 기준으로 잘라 카드가 절대 넘치지 않게 한다.

실패하면 조용히 규칙 기반(헤드라인 나열)으로 물러난다 — 브리핑은 나가야 한다.
"""

import json
import os
from typing import Dict, List

from brief import (CARD_BODY_UNITS, CARD_TITLE_UNITS, StockBrief, char_units,
                   market_open, price_sentence, text_units, visible)
from config import SUMMARY_MAX_TOKENS, SUMMARY_MODEL

SYSTEM = """당신은 개인 투자자용 데일리 브리핑 카드를 쓰는 편집자입니다.
종목마다 '제목 꼬리'와 '본문 원인절' 두 가지만 씁니다.

[제목 꼬리]
종목명 뒤에 붙는 사건 요약입니다. 헤드라인을 그대로 옮기지 말고 오늘 그 종목에
있었던 일을 한 구절로 압축하세요. 종목명은 넣지 않습니다(앞에 이미 붙습니다).
  예) "17년 만에 상한가"
      "스카이워터 인수 완료, 퀀텀 수직계열화 완성"
      "최대 매출에도 이익은 뒷걸음"

[본문 원인절]
"[원인]에 [수급·심리 변화], [결과]." 형태의 한 문장입니다.
  예) "자국산 파운드리 확보로 퀀텀 하드웨어 수직계열화 기대감이 부각되며 매수세 유입,
       인수 완료 소식에 투자심리 개선."
가격과 등락률은 쓰지 마세요 — 뒤에 따로 붙습니다.

주어진 글자 수를 최대한 채우세요. 한 줄 요약이 아니라 카드를 채우는 본문입니다.
헤드라인이 여럿이고 서로 이어지면 엮어서 맥락을 담고, 배경·규모·시점처럼 헤드라인에
실제로 있는 구체적인 내용을 함께 넣으세요. 남는 자리를 빈 채로 두지 마세요.
다만 자리를 채우려고 없는 사실을 지어내서는 안 됩니다 — 쓸 내용이 정말 없으면
짧게 끝내는 편이 낫습니다.

[반드시 지킬 것]
- 제공된 헤드라인에 없는 사실을 지어내지 마세요.
- 수급 주체(외국인·기관·개인), 거래 규모, 구체적 수치는 헤드라인에 근거가 있을 때만
  쓰세요. 근거가 없으면 헤드라인에 있는 내용만으로 담백하게 쓰고, 억지로 인과를
  만들지 마세요. 등락의 이유를 모르면 모르는 채로 두는 편이 낫습니다.
- 주가의 시장 내 위치를 임의로 단정하지 마세요. "신고가", "52주 최고/최저",
  "사상 최대", "연중 최저" 같은 표현은 헤드라인에 그대로 있을 때만 씁니다.
  주어진 정보는 오늘 종가와 등락률뿐이며, 과거 주가 범위는 알 수 없습니다.
- 헤드라인과 주가 방향이 어긋날 때(호재인데 하락, 악재인데 상승) 그 간극을 메우는
  설명을 만들어내지 마세요. "차익실현 매물", "경계 매물", "선반영" 같은 표현은
  헤드라인에 그런 말이 있을 때만 씁니다. 없으면 "…에도 불구하고 하락"처럼
  사실 관계만 쓰세요.
- reason을 빈 문자열로 두는 경우는 헤드라인이 다른 회사 이야기나 일반적인 투자
  조언처럼 이 종목과 상관없는 내용일 때뿐입니다. 이 종목에 관한 헤드라인이 있으면,
  그것이 등락을 설명하지 못하더라도 그 사실을 한 문장에 담아 쓰세요.
  (예: "용인·청주 54조원 투자와 주당 375원 배당 확정을 발표했으나 주가는 급락.")
- 영문 고유명사는 한글로 옮기세요(SoFi → 소파이, Michael Burry → 마이클 버리).
- 뉴스가 없으면 title_tail에 등락 사실만 쓰고 reason은 빈 문자열로 두세요.
- 주어진 글자 수 제한을 지키세요."""

SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "title_tail": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["ticker", "title_tail", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


def _budget(sb: StockBrief):
    """이 종목에 남는 제목/본문 예산을 한글 글자 수로 환산해 돌려준다."""
    title_room = CARD_TITLE_UNITS - text_units("{} - ".format(sb.name))
    body_room = (CARD_BODY_UNITS
                 - text_units(visible(price_sentence(
                     sb.quote, closed=not market_open(sb.holding.is_kr))))
                 - char_units(" "))
    return max(int(title_room), 0), max(int(body_room), 0)


def _block(sb: StockBrief) -> str:
    title_room, body_room = _budget(sb)
    pct = "-" if sb.pct is None else "{:+.2f}%".format(sb.pct)
    lines = [
        "[{}] {} · {} · {}".format(
            sb.quote.ticker, sb.name, pct, sb.quote.format_price()),
        # 상한만 주면 한참 못 미치게 쓴다. 하한을 함께 줘서 카드를 채우게 한다.
        # 하한이 0.85면 실제로는 79%쯤 쓰는데, 그러면 넓은 폰(430px)에서 본문이
        # 2줄에 들어가 카드 아래가 빈다. 좁은 폰에서 넘치지 않으면서 넓은 폰에서도
        # 3줄이 되는 구간이 예산의 90~100%라 하한을 그 위로 올린다.
        "제목 꼬리 최대 {}자 / 본문 원인절 {}~{}자(가능한 한 끝까지 채울 것)".format(
            title_room, int(body_room * 0.95), body_room),
    ]
    if sb.news:
        lines.append("오늘 헤드라인:")
        lines += ["  {}. {}".format(i + 1, n.title) for i, n in enumerate(sb.news)]
    else:
        lines.append("오늘 헤드라인: 없음")
    return "\n".join(lines)


def summarize(briefs: List[StockBrief]) -> Dict[str, dict]:
    """{티커: {"title_tail":…, "reason":…}}. 실패하면 빈 dict."""
    briefs = [b for b in briefs if b.quote.ok]
    if not briefs:
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [요약] ANTHROPIC_API_KEY 없음 → 규칙 기반(헤드라인 나열)으로 진행")
        return {}

    try:
        # import까지 try 안에 둔다 — 라이브러리가 없다고 브리핑 전체가 죽으면 안 된다.
        # 요약은 부가 기능이라 실패하면 규칙 기반으로 물러나는 것이 맞다.
        import anthropic

        resp = anthropic.Anthropic().messages.create(
            model=SUMMARY_MODEL,
            max_tokens=SUMMARY_MAX_TOKENS,
            # Sonnet 5는 thinking이 기본으로 켜져 있다. 켜두면 종목이 많을 때
            # thinking이 max_tokens를 다 먹고 본문 없이 끝난다(StopIteration).
            # 정해진 형식으로 쓰는 작업이라 추론이 필요 없다.
            thinking={"type": "disabled"},
            system=SYSTEM,
            messages=[{"role": "user",
                       "content": "\n\n".join(_block(b) for b in briefs)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise RuntimeError(
                "응답에 텍스트가 없습니다 (stop_reason={}, 출력 {}토큰)".format(
                    resp.stop_reason, resp.usage.output_tokens))
        cards = json.loads(text)["cards"]
    except Exception as e:
        print("  [요약] 실패 → 규칙 기반으로 진행: {}: {}".format(type(e).__name__, e))
        return {}

    known = {b.quote.ticker for b in briefs}
    out = {}
    for c in cards:
        t = str(c.get("ticker", "")).strip()
        if t in known:
            out[t] = {"title_tail": (c.get("title_tail") or "").strip(),
                      "reason": (c.get("reason") or "").strip()}

    missing = known - set(out)
    if missing:
        print("  [요약] 누락 {}건은 규칙 기반으로: {}".format(
            len(missing), ", ".join(sorted(missing))))
    return out


def apply(briefs: List[StockBrief]) -> int:
    """요약 결과를 StockBrief에 붙인다. 붙은 개수를 돌려준다."""
    result = summarize(briefs)
    for b in briefs:
        if b.quote.ticker in result:
            b.summary = result[b.quote.ticker]
    return len(result)
