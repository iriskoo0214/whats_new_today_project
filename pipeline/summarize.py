"""카드 문구를 LLM으로 요약한다.

헤드라인을 이어붙이는 대신, 오늘 그 종목에 있었던 일을 한 구절(제목)과
"[등락률과 사실]+[원인]+[시사점]"을 인과관계로 엮은 완결된 1~2문장(본문)으로
압축한다. 간결한 증권사 리포트 문체가 목표다.

    아이온큐 - 스카이워터 인수 완료, 퀀텀 수직계열화 완성
    아이온큐는 자국산 파운드리 확보로 퀀텀 하드웨어 수직계열화를 완성했다는
    소식에 매수세가 유입되며 +9.00% 오른 36.44달러 마감. 이는 공급망 리스크가
    해소됐다는 신호로 해석된다.

역할을 나눈 이유:
  · 등락률·가격 숫자는 파이썬이 계산해서 정확한 문장("+9.00% 오른 36.44달러
    마감.")으로 프롬프트에 데이터로 준다. LLM에게 숫자 계산을 맡기면 틀릴 수
    있어서, 그 문장을 "그대로" 자기 문장 안에 이어 쓰게 하고(보통 원인절 뒤),
    받아온 본문에 그 문장이 실제로 들어있는지 검증한다(brief.card_body).
    검증에 실패하면(=숫자를 바꿔 썼다고 의심되면) 그 종목만 규칙 기반으로
    되돌린다 — 나머지 카드는 그대로 살린다.
  · 카드 높이는 고정값이 아니라 내용만큼 늘어나므로(Figma 패딩만 지키면 됨)
    본문 길이를 글자 수 예산으로 잘라내지 않는다 — 제목 꼬리만 한 줄 폭에
    맞춰 예산을 준다.

실패하면 조용히 규칙 기반(헤드라인 나열)으로 물러난다 — 브리핑은 나가야 한다.
"""

import json
import os
from typing import Dict, List

from brief import (CARD_TITLE_UNITS, StockBrief, body_has_numbers, market_open,
                   price_sentence, text_units)
from config import SUMMARY_MAX_TOKENS, SUMMARY_MODEL

SYSTEM = """당신은 증권사 리포트 톤으로 개인 투자자용 데일리 브리핑 카드를 쓰는
편집자입니다. 종목마다 '제목 꼬리'와 '본문' 두 가지를 씁니다.

[제목 꼬리]
종목명 뒤에 붙는 사건 요약입니다. 헤드라인을 그대로 옮기지 말고 오늘 그 종목에
있었던 일을 한 구절로 압축하세요. 종목명은 넣지 않습니다(앞에 이미 붙습니다).
  예) "17년 만에 상한가"
      "스카이워터 인수 완료, 퀀텀 수직계열화 완성"
      "최대 매출에도 이익은 뒷걸음"

[본문]
재료가 충분하면 2문장으로 씁니다. 불릿이 아니라 문장으로 씁니다.
  · 첫 문장 — 종목명을 주어로 시작합니다("IBM은 …", "삼성전자는 …"). 오늘 등락을
    가장 잘 설명하는 원인 + 아래 "그대로 포함할 등락률·가격 문장". "[등락률과
    사실] + [원인]"을 인과로 잇습니다.
  · 둘째 문장 — 첫 문장에 안 쓴 다른 헤드라인의 배경·규모·전문가 분석을 엮어서
    시장 반응이나 투자심리를 정리합니다("~라는 분석도 나오며 ~한 모습이다",
    "~로 해석된다" 등). 헤드라인에 실제로 있는 내용만 씁니다.
재료가 하나뿐이거나 다른 헤드라인이 이 종목과 상관없으면 첫 문장만 쓰세요.
억지로 둘째 문장을 만들려고 없는 사실을 지어내면 안 됩니다.

  예) "IBM은 31년 연속 배당을 인상했지만 인상폭이 인플레이션에 못 미친다는 평가
       속에 -3.45% 내린 229.55달러 마감. 한때 엔비디아 자리를 꿰찼던 기술주
       최강자가 고점 대비 25% 폭락했다는 분석도 나오며 투자심리가 위축된
       모습이다."

등락률·가격은 데이터 블록에 "그대로 포함할 문장"으로 정확한 값이 주어집니다.
그 문장의 숫자(등락률·가격)를 절대 다시 계산하거나 바꾸지 말고, 원인절 뒤에
그대로 이어붙여 첫 문장을 완성하세요(위 예시의 "-3.45% 내린 229.55달러 마감."
처럼). 숫자가 본문에 그대로 들어있지 않으면 카드가 버려지고 규칙 기반으로
대체됩니다.

[시사점]은 헤드라인의 사실에서 합리적으로 따라 나올 때만 쓰세요. 근거 없는
해석·전망을 지어내는 것보다, 시사점 없이 사실+원인 문장 하나로 끝내는 편이
낫습니다.

헤드라인이 여럿이고 서로 이어지면 엮어서 맥락을 담고, 배경·규모·시점처럼
헤드라인에 실제로 있는 구체적인 내용을 넣으세요. 다만 자리를 채우려고 없는
사실을 지어내서는 안 됩니다 — 쓸 내용이 정말 없으면 짧게 끝내는 편이 낫습니다.

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
  헤드라인에 그런 말이 있을 때만 씁니다. 없으면 사실 관계만 담백하게 쓰되,
  "~에도 불구하고"를 매번 기계적으로 쓰지 마세요. "~했지만", "~한 가운데",
  "~에도", "~했으나" 등 자연스러운 연결 중 문맥에 맞는 것을 골라 변주하세요.
  카드가 여러 장 이어질 때 같은 연결 표현이 반복되면 안 됩니다.
- 본문을 빈 문자열로 두는 경우는 헤드라인이 다른 회사 이야기나 일반적인 투자
  조언처럼 이 종목과 상관없는 내용일 때뿐입니다. 이 종목에 관한 헤드라인이 있으면,
  그것이 등락을 설명하지 못하더라도 등락률·가격 문장과 함께 한 문장에 담아 쓰세요.
  (예: "용인·청주 54조원 투자와 주당 375원 배당 확정을 발표했으나 -2.10% 내린
       68,500원 마감.")
- 주어진 오늘 등락률과 다른 등락 수치가 든 헤드라인(예: 실제로는 +1.3%인데 헤드라인은
  "3.9%↑")은 다른 날 이야기일 수 있습니다. 오늘 움직임의 "원인"으로 단정하지 마세요.
  다만 "고점 대비 25% 폭락했다는 분석도 나오며"처럼 배경·분석으로 언급하는 건
  둘째 문장에 써도 좋습니다.
- "주의가 필요하다", "매수 기회", "지켜봐야 한다" 같은 투자 권유·당부 문구는 쓰지
  마세요. 헤드라인에 있는 사실과 시장 반응만 씁니다.
- 그 종목 주가와 직접 상관없는 곁다리 헤드라인(타사 제품 사용 팁, 파트너 연동 홍보,
  행사 후기, 광고성 글)은 근거로 쓰지 마세요. 쓸 만한 헤드라인이 없으면 있는 것만
  담백하게 쓰세요.
- 헤드라인끼리 방향이 상충하면(하나는 급등, 하나는 하락) 오늘 등락 방향과 맞는
  쪽만 근거로 삼으세요.
- 영문 고유명사는 한글로 옮기세요(SoFi → 소파이, Michael Burry → 마이클 버리).
- 뉴스가 없거나 전부 이 종목과 상관없어서 본문을 비울 때도 title_tail은 비우지 말고
  등락 사실로 채우세요(예: "뚜렷한 재료 없이 소폭 하락", "재료 없이 강보합").
- 제목 꼬리는 주어진 글자 수 제한을 지키세요(본문은 길이 제한이 없습니다)."""

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
                    "body": {"type": "string"},
                },
                "required": ["ticker", "title_tail", "body"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


def _title_room(sb: StockBrief) -> int:
    """제목 꼬리에 남는 예산을 한글 글자 수로 환산해 돌려준다."""
    return max(int(CARD_TITLE_UNITS - text_units("{} - ".format(sb.name))), 0)


def _block(sb: StockBrief) -> str:
    pct = "-" if sb.pct is None else "{:+.2f}%".format(sb.pct)
    price_line = price_sentence(sb.quote, html_bold=False,
                                 closed=not market_open(sb.holding.is_kr))
    lines = [
        "[{}] {} · 등락률 {} · 가격 {}".format(
            sb.quote.ticker, sb.name, pct, sb.quote.format_price()),
        "제목 꼬리 최대 {}자".format(_title_room(sb)),
        "본문에 그대로 포함할 등락률·가격 문장: \"{}\"".format(price_line),
    ]
    if sb.news:
        lines.append("오늘 헤드라인:")
        lines += ["  {}. {}".format(i + 1, n.title) for i, n in enumerate(sb.news)]
    else:
        lines.append("오늘 헤드라인: 없음")
    return "\n".join(lines)


def summarize(briefs: List[StockBrief]) -> Dict[str, dict]:
    """{티커: {"title_tail":…, "body":…}}. 실패하면 빈 dict."""
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
                      "body": (c.get("body") or "").strip()}

    missing = known - set(out)
    if missing:
        print("  [요약] 누락 {}건은 규칙 기반으로: {}".format(
            len(missing), ", ".join(sorted(missing))))
    return out


def apply(briefs: List[StockBrief]) -> int:
    """요약 결과를 StockBrief에 붙인다. 붙은 개수를 돌려준다."""
    result = summarize(briefs)

    # LLM이 가끔 숫자를 빼먹거나 바꿔 쓴다(간헐적). 그 본문은 brief.card_body가 버리고
    # 헤드라인 나열 폴백을 쓰는데 카드가 볼품없어지니, 버리기 전에 그 종목만 한 번 더
    # 시킨다. 그래도 안 되면 요약을 통째로 빼서 제목도 폴백으로 통일한다.
    by_ticker = {b.quote.ticker: b for b in briefs}
    bad = [by_ticker[t] for t, r in result.items()
           if r.get("body") and not body_has_numbers(by_ticker[t], r["body"])]
    if bad:
        print("  [요약] 숫자 불일치 {}건 재시도: {}".format(
            len(bad), ", ".join(b.name for b in bad)))
        retry = summarize(bad)
        for b in bad:
            r = retry.get(b.quote.ticker)
            if r and r.get("body") and body_has_numbers(b, r["body"]):
                result[b.quote.ticker] = r
            else:
                result.pop(b.quote.ticker, None)

    for b in briefs:
        if b.quote.ticker in result:
            b.summary = result[b.quote.ticker]
    return len(result)
