"""시장 전체 헤드라인 한 줄과 "OO장 어땠지" 3줄 요약을 LLM으로 만든다.

종목 카드 문구(summarize.py)와는 다른 결과물 두 가지를 한 콜에서 뽑는다.
  · headline    — 배지 옆에 쓰는 한 줄. 오늘 시장을 움직인 사건 하나를
                  원인→결과로 압축한다.
                  예) "외국인 3.4조 매도에 코스피 6700선 붕괴"
  · card.title  — "OO장 어땠지" 카드 제목. 마감을 한 문장으로 총평한다.
                  예) "3대 지수 반등 마감...델 테크놀로지스 사상 최고치 경신"
  · card.bullets — 총평을 뒷받침하는 근거 3개. Figma 시안 그대로 마침표 없는
                  15~25자 내외의 짧은 구절이다. 완결된 문장이 아니라
                  "[사실]+[원인]"을 한 호흡에 압축한다.
                  예) "양대 지수, 외국인과 기관 동반 매도세에 하락"

headline과 card.title은 같은 소재를 다른 관점(임팩트 한 줄 vs 총평)으로
쓴 것이라 문장이 겹치지 않아도 된다.

실패하면 조용히 빈 값으로 물러난다 — summarize.py와 같은 이유(브리핑은
나가야 한다). 마감 브리핑 전체를 이걸로 막지 않는다.
"""

import json
import os
from typing import List, Optional

from config import MARKET_SUMMARY_MAX_TOKENS, MARKET_SUMMARY_MODEL
from news import NewsItem

SYSTEM = """당신은 증권 앱의 "오늘 장 마감" 요약을 쓰는 편집자입니다.
주어진 오늘자 헤드라인들만 보고, 개별 종목이 아니라 시장 전체(지수·수급·
매크로) 관점에서 씁니다.

[headline]
배지 옆에 붙는 한 줄입니다. 오늘 가장 임팩트 있는 사건 하나를 "원인에 결과"
형태로 압축하세요. 지수·수급·매크로 지표를 주어로 씁니다.
  예) "외국인 3.4조 매도에 코스피 6700선 붕괴"
      "중동 확전 우려에 유가 100달러 돌파와 금리 급등 충격"

[card.title]
마감을 한 문장으로 총평합니다. "OOO 마감...XXX" 형태를 씁니다.
  예) "3대 지수 반등 마감...델 테크놀로지스 사상 최고치 경신"

[card.bullets]
총평을 뒷받침하는 근거를 정확히 3개, Figma 시안과 똑같이 마침표 없는
15~25자 내외의 짧은 구절로 씁니다. 완결된 문장이 아니라 "[사실] + [원인]"을
한 호흡에 압축한 명사형 구절입니다. 시사점·전망은 넣지 않습니다.
  예) "양대 지수, 외국인과 기관 동반 매도세에 하락"
      "유가 급등 및 미 국채 금리 상승에 심리 위축"
      "미국 CPI 발표 앞둔 관망세 확산"

[반드시 지킬 것]
- 주어진 헤드라인에 없는 사실을 지어내지 마세요. 수치·원인·종목명은
  헤드라인에 근거가 있을 때만 씁니다.
- card.bullets는 마침표를 찍지 않습니다. 각 불릿은 한 줄에 들어갈 만큼
  짧게 — 예시 3개와 비슷한 길이(15~25자)를 지키세요. 원인을 찾기 어려우면
  시사점을 채우려 하지 말고 사실만 짧게 쓰세요.
- 헤드라인이 서로 다른 이야기를 하면, 그날 가장 비중 있어 보이는 것 하나를
  중심으로 삼고 나머지는 bullets로 보조하세요. 억지로 하나의 인과로 엮지
  마세요.
- 영문 고유명사는 한글로 옮기세요(예: Fed → 연준).
- 재료가 부족하면 짧고 담백하게 쓰는 편이 낫습니다. 없는 디테일을 채우지
  마세요."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "card": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                # bullets 개수는 "정확히 3개"를 스키마로 강제 못 한다 — Anthropic
                # structured output이 array의 minItems/maxItems로 0·1 외의
                # 값을 안 받아준다(400 에러). 프롬프트로 개수를 지시하고,
                # summarize()에서 3개로 잘라/채운다.
                "bullets": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "bullets"],
            "additionalProperties": False,
        },
    },
    "required": ["headline", "card"],
    "additionalProperties": False,
}


def _block(market_label: str, news: List[NewsItem]) -> str:
    lines = ["[{}] 오늘 헤드라인:".format(market_label)]
    lines += ["  {}. {}".format(i + 1, n.title) for i, n in enumerate(news)]
    return "\n".join(lines)


def summarize(market_label: str, news: List[NewsItem]) -> Optional[dict]:
    """{"headline":…, "card": {"title":…, "bullets":[…]}}. 실패/재료 없음이면 None."""
    if not news:
        print("  [시장 요약] {} 매크로 뉴스 없음 → 건너뜀".format(market_label))
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [시장 요약] ANTHROPIC_API_KEY 없음 → 건너뜀")
        return None

    try:
        # summarize.py와 같은 이유로 import까지 try 안에 둔다.
        import anthropic

        resp = anthropic.Anthropic().messages.create(
            model=MARKET_SUMMARY_MODEL,
            max_tokens=MARKET_SUMMARY_MAX_TOKENS,
            thinking={"type": "disabled"},
            system=SYSTEM,
            messages=[{"role": "user", "content": _block(market_label, news)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise RuntimeError(
                "응답에 텍스트가 없습니다 (stop_reason={}, 출력 {}토큰)".format(
                    resp.stop_reason, resp.usage.output_tokens))
        result = json.loads(text)
    except Exception as e:
        print("  [시장 요약] 실패 → 건너뜀: {}: {}".format(type(e).__name__, e))
        return None

    card = result.get("card") or {}
    # 스키마로 개수를 강제할 수 없어(위 주석) 3개로 자른다. 모자라면 있는
    # 만큼만 둔다 — 없는 불릿을 지어내는 것보다 낫다.
    bullets = [str(b).strip() for b in (card.get("bullets") or []) if str(b).strip()][:3]
    return {
        "headline": (result.get("headline") or "").strip(),
        "card": {
            "title": (card.get("title") or "").strip(),
            "bullets": bullets,
        },
    }
