"""시간대별 슬롯에 붙는 제목·본문을 LLM으로 쓴다 (Portfolios 탭 전용).

카드 요약(summarize.py)과 역할이 다르다. 저쪽은 하루 한 장의 마감 브리핑이고,
여기는 한 종목의 하루를 4개 시점으로 나눠 흐름을 이야기한다.

가격과 등락률은 파이썬이 계산해 화면이 따로 표시하므로 LLM은 문구만 쓴다.
헤드라인에는 발행 시각이 있어서 "그 시간대 이전에 나온 뉴스"만 근거로 삼게 한다 —
오후 2시에 나온 기사로 오전 9시 움직임을 설명하면 인과가 거꾸로 된다.
"""

import json
import os
from typing import Dict, List

from config import INTRADAY_MAX_TOKENS, SUMMARY_MODEL

SYSTEM = """당신은 개인 투자자용 '시간대별 브리핑'을 쓰는 편집자입니다.
한 종목의 하루를 시간 순서대로 따라가며, 각 시점마다 제목과 본문을 씁니다.

[제목]
그 시점까지의 움직임을 한 구절로. 예) "장 초반 강세 출발", "낙폭 확대", "상한가 근접"
종목명은 넣지 않습니다.

[본문]
그 시점까지 무슨 일이 있었는지 한 문장으로. 가격과 등락률 숫자는 쓰지 마세요 —
화면에 따로 표시됩니다.

주어진 글자 수를 채우세요. 한 줄로 끝내지 말고 두 줄 분량으로 쓰되,
자리를 채우려고 없는 사실을 지어내서는 안 됩니다. 지어내지 않고 채울 수 있는
재료는 이미 충분히 주어져 있습니다.
  · 앞 시점과 견준 변화 — 오름세가 이어졌는지, 방향이 꺾였는지, 낙폭이 줄었는지
  · 하루 안에서의 위치 — 장 초반/중반/후반, 그날 고점·저점 부근인지
  · 그 시각 이전에 나온 헤드라인의 내용
예) "장 초반 낙폭을 오후 들어 일부 만회했으나 전 거래일 수준은 회복하지 못함"
    "투자 확정 소식이 나온 뒤에도 매수세가 붙지 않으며 낙폭이 하루 중 가장 크게 벌어짐"

[반드시 지킬 것]
- 각 헤드라인에는 발행 시각이 붙어 있습니다. 그 시점보다 나중에 나온 헤드라인은
  근거로 쓰지 마세요. 오후에 나온 기사로 오전 움직임을 설명하면 인과가 거꾸로 됩니다.
- 헤드라인에 없는 사실을 지어내지 마세요. 수급 주체(외국인·기관·개인), 거래 규모,
  "차익실현 매물", "경계 매물" 같은 표현은 헤드라인에 근거가 있을 때만 씁니다.
- 근거가 될 헤드라인이 없는 시점은 가격 흐름 사실만 담백하게 쓰세요.
  예) "장 초반 상승분을 지키지 못하고 밀림", "오후 들어 낙폭을 일부 회복"
- 시간이 흐르는 이야기입니다. 앞 시점과 같은 말을 반복하지 말고 변화를 쓰세요.
- 제목과 본문 모두 주어진 글자 수를 지키세요."""

SCHEMA = {
    "type": "object",
    "properties": {
        "stocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "slots": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["title", "text"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["ticker", "slots"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stocks"],
    "additionalProperties": False,
}

TITLE_LIMIT = 16     # pf-brief__title 한 줄
# pf-brief__text 2줄. 카드 높이를 홈 카드와 같은 122px로 맞추면서
# 스탬프 줄만큼 자리가 줄어 2줄이 됐다. 실측 용량은 한글 54자라 여유를 둔다.
TEXT_LIMIT = 52


def _block(name, ticker, slots, news) -> str:
    lines = ["[{}] {}".format(ticker, name), "시간대별 시세:"]
    for s in slots:
        pct = "-" if s.pct is None else "{:+.2f}%".format(s.pct)
        lines.append("  {:>10s}  {:>14,.2f}  {}".format(s.label, s.price, pct))
    if news:
        lines.append("오늘 헤드라인 (발행시각):")
        for n in news:
            lines.append("  {}  {}".format(n.published.strftime("%H:%M"), n.title))
    else:
        lines.append("오늘 헤드라인: 없음")
    lines.append(
        "슬롯 {}개. 제목 최대 {}자 / 본문 {}~{}자 — 본문은 {}자 아래로 내려가지 않게,"
        " 카드 두 줄을 채운다는 느낌으로 쓸 것.".format(
            len(slots), TITLE_LIMIT,
            int(TEXT_LIMIT * 0.8), TEXT_LIMIT, int(TEXT_LIMIT * 0.8)))
    return "\n".join(lines)


def summarize(briefs, slots_by_ticker: Dict[str, list]) -> Dict[str, List[dict]]:
    """{티커: [{"title":…, "text":…}, ...]}. 실패하면 빈 dict."""
    targets = [b for b in briefs if b.quote.ticker in slots_by_ticker]
    if not targets:
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [시간대별] ANTHROPIC_API_KEY 없음 → 문구 없이 가격만 표시")
        return {}

    import anthropic

    blocks = [_block(b.name, b.quote.ticker, slots_by_ticker[b.quote.ticker], b.news)
              for b in targets]
    try:
        resp = anthropic.Anthropic().messages.create(
            model=SUMMARY_MODEL,
            max_tokens=INTRADAY_MAX_TOKENS,
            thinking={"type": "disabled"},
            system=SYSTEM,
            messages=[{"role": "user", "content": "\n\n".join(blocks)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise RuntimeError("응답에 텍스트가 없습니다 (stop_reason={})".format(resp.stop_reason))
        data = json.loads(text)["stocks"]
    except Exception as e:
        print("  [시간대별] 실패 → 문구 없이 가격만 표시: {}: {}".format(type(e).__name__, e))
        return {}

    out = {}
    for entry in data:
        t = str(entry.get("ticker", "")).strip()
        if t not in slots_by_ticker:
            continue
        want = len(slots_by_ticker[t])
        got = entry.get("slots") or []
        # 개수가 어긋나면 짝이 밀려 엉뚱한 시각에 붙는다 — 그 종목만 버린다
        if len(got) != want:
            print("  [시간대별] {} 슬롯 수 불일치({} != {}) → 문구 생략".format(t, len(got), want))
            continue
        out[t] = [{"title": (s.get("title") or "").strip(),
                   "text": (s.get("text") or "").strip()} for s in got]
    return out
