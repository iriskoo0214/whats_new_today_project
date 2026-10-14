"""시장 전체 헤드라인 한 줄과 "OO장 어땠지" 3줄 요약을 LLM으로 만든다.

종목 카드 문구(summarize.py)와는 다른 결과물을 한 콜에서 뽑는다.
  · headline    — 배지 옆에 쓰는 한 줄. 그날 시장을 움직인 사건 하나를
                  원인→결과로 압축한다.
                  예) "외국인 3.4조 매도에 코스피 6700선 붕괴"
  · card.title  — "OO장 어땠지" 카드 제목. 지수 레벨·흐름만으로 마감을 총평한다.
                  수급·업종·대외 변수는 쓰지 않는다 — 그건 불릿 몫이다.
                  예) "코스피 0.44% 하락 마감...6000선 턱걸이하며 6거래일 연속 약세"
  · card.bullets — 번호마다 담당 영역이 고정된 3줄(SLOT_GUIDE). 한국은
                  1 수급 · 2 업종·주도주 · 3 대외 변수, 미국은 1 업종·주도주 ·
                  2 금리·유가·달러 · 3 이벤트·일정. 재료도 번호별 묶음으로 받는다
                  (market_news.fetch_slot_news).

예전엔 영역 없이 "근거 3개"만 시켰더니 그날 기사가 몰린 지수 이야기로 쏠려
제목을 되풀이하거나(2026-10-14 "6600선 턱걸이" 중복) 수급·환율이 통째로 빠졌다.

코드로 지키는 것 — 모델이 스스로 못 지키는 규칙이라 프롬프트만 믿지 않는다.
  · 길이: 불릿이 MARKET_BULLET_MAX_LEN을 넘으면 그 항목만 글자 수를 알려주고
          다시 쓰게 한다(최대 MARKET_BULLET_RETRIES번). 모델은 글자를 못 센다.
  · 제목 반복: 제목 어절을 절반 이상 베낀 불릿은 뺀다(_repeats).
  · 시장 범위: 다른 나라 단어가 나오면 요약을 통째로 버린다(forbid).

실패하면 조용히 빈 값으로 물러난다 — summarize.py와 같은 이유(브리핑은
나가야 한다). 마감 브리핑 전체를 이걸로 막지 않는다.
"""

import json
import os
from typing import Dict, List, Optional

from config import (MARKET_BULLET_MAX_LEN, MARKET_BULLET_RETRIES, MARKET_SUMMARY_MAX_TOKENS,
                    MARKET_SUMMARY_MODEL)
from market_news import Slot, Window

# 번호별 담당 영역 설명 — key는 config.MARKET_SUMMARY_SLOTS와 맞춘다.
# 예시는 일부러 실제 그날 기사와 다른 소재로 둔다. 모델이 예시를 베끼는 일이 잦다.
SLOT_GUIDE = {
    "supply": ('수급: 외국인·기관·개인 중 누가 사고 팔았는지와 그 결과(지수 방향).',
               "기관 1.2조 순매수에 코스닥 3거래일 만에 반등"),
    "sector": ('업종·주도주: 그 시장에서 오른/내린 업종과 대표 종목. 다른 나라 증시'
               '(니케이 등)의 업종 이야기는 쓰지 않습니다.',
               "조선주 수주 기대에 HD현대중공업 8% 급등"),
    "external": ('대외 변수: 환율·미 증시·금리·다가오는 지표 일정.',
                 "엔화 약세에 원·달러 환율 1,410원대 상승"),
    "macro": ('금리·유가·달러: 미 국채 금리, 국제유가(WTI), 달러 흐름과 그 영향.',
              "10년물 금리 4.1%대 하락에 성장주 숨통"),
    "event": ('이벤트·일정: 연준 발언, 주요 기업 실적, 경제지표 발표와 다가오는 일정.',
              "엔비디아 실적 발표 앞두고 관망세"),
}

# 제목에 쓸 지수 — 이것만 주어로 쓰게 한다
TITLE_INDEX = {"kr": "코스피·코스닥", "us": "3대 지수(다우·S&P500·나스닥)"}
TITLE_EXAMPLE = {
    "kr": "코스닥 2% 반등 마감...850선 회복하며 3거래일 만에 상승",
    "us": "3대 지수 동반 상승 마감...S&P500 6800선 사상 최고치",
}

SYSTEM = """당신은 증권 앱의 "장 마감" 요약을 쓰는 편집자입니다.
입력 맨 위 [ ] 안에 요약할 시장과 날짜가 적혀 있고, 그 아래 번호별 재료 묶음이
있습니다. 각 헤드라인 앞 [시각]은 한국 시간 발행 시각입니다.

[시장 범위 — 가장 먼저 지킬 것]
그 시장의 증시 소식만 씁니다. 증시와 무관한 헤드라인(정치·사건사고·국내 주유소
기름값·유류세·통행료 같은 생활물가·광고성 글)은 통째로 무시하세요.

[title]
마감을 한 문장으로 총평합니다. "OOO 마감...XXX" 형태.
title에는 {index}의 레벨과 흐름(등락률·연속 일수·지지선/저항선)만 씁니다.
수급 주체, 업종·종목(예: 반도체주), 환율·금리·해외 변수는 title에 쓰지 않습니다
— 불릿이 맡습니다.
  예) "{title_example}"
  나쁜 예) "코스피 마감...외인 매도에 6거래일째 하락"  ← 수급(외인)이 들어감

[headline]
배지 옆에 붙는 한 줄. 그날 가장 임팩트 있는 사건 하나를 "원인에 결과"로 압축합니다.
  예) "외국인 3.4조 매도에 코스피 6700선 붕괴"

[불릿 — 번호별 담당 영역, 순서 고정]
{slots}
불릿의 주재료는 자기 번호 묶음에서 고릅니다. 다만 쓰기 전에 모든 묶음을 다 읽고,
다른 묶음에 반대 방향의 사실(예: 한쪽은 "긴축 우려", 다른 쪽은 "긴축 가능성 약화")이
있으면 어느 한쪽 해석을 고르지 말고 양쪽 다 맞는 사실만 쓰세요.
자기 묶음에 쓸 만한 재료가 없으면 그 항목은 빈 문자열("")로 두세요. 다른 번호의
영역(예: 업종 칸에 환율)으로 채우지 않습니다.

[길이와 밀도]
- 불릿은 마침표 없는 20~{max_len}자(공백 포함) 명사형 구절. 20자보다 짧으면 안 됩니다.
- 각 불릿에는 "사실 + (원인 또는 구체 수치)"를 함께 담습니다. 재료에 있는 연속 일수·
  등락률·금액·환율 레벨·종목명을 씁니다. 종목은 대표 하나만.
  나쁜 예) "외인·개인 동반 매도 지속"  ← 사실만 있고 수치·결과가 없음
- title에 이미 쓴 사실(지수 레벨·등락·마감)을 불릿에서 반복하지 않습니다.

[해석 금지 — 헤드라인에 그 말이 있을 때만 씁니다]
- 헤드라인에 없는 수치·원인·종목명을 지어내지 않습니다.
- "우려 재부각", "기대 확산", "심리 위축", "경계감 고조", "출렁"처럼 시장 심리나
  움직임을 해석하는 말은 재료 헤드라인에 같은 뜻의 표현이 직접 있을 때만 씁니다.
  "CPI 상회 → 긴축 우려"처럼 상식으로 원인·결과를 이어 붙이지 마세요.
  나쁜 예) 재료 "美 CPI 3.7% 상회" → "美 CPI 상회에 긴축 우려 재부각"
  좋은 예) 재료 "美 CPI 3.7% 상회" → "美 9월 CPI 3.7%로 예상치 상회"

[시점 — 요약하는 장과 맞을 것]
- 이 요약은 맨 위에 적힌 날의 그 시장 정규장을 설명합니다. 장 마감 뒤에 일어난
  일을 그날 장의 원인으로 쓰지 마세요. 아직 발표 전이던 지표는 "발표 앞두고",
  "대기"처럼 기다리는 상황으로만 씁니다.

- 영문 고유명사는 한글로 옮기세요(예: Fed → 연준)."""


def _system(market: str, slots: List[Slot]) -> str:
    lines = []
    for i, s in enumerate(slots, 1):
        desc, ex = SLOT_GUIDE[s.key]
        lines.append('{}. {} — {}\n   예) "{}"'.format(i, s.key, desc, ex))
    return SYSTEM.format(index=TITLE_INDEX[market], title_example=TITLE_EXAMPLE[market],
                         slots="\n".join(lines), max_len=MARKET_BULLET_MAX_LEN)


def _schema(slots: List[Slot]) -> dict:
    keys = ["headline", "title"] + [s.key for s in slots]
    return {
        "type": "object",
        "properties": {k: {"type": "string"} for k in keys},
        "required": keys,
        "additionalProperties": False,
    }


def _block(market_label: str, win: Window, slots: List[Slot]) -> str:
    lines = ["[{}] {} 장 마감 요약 (재료: 한국 시간 {} ~ {} 발행 기사)".format(
        market_label, win.day.strftime("%Y-%m-%d"),
        win.start.strftime("%m/%d %H:%M"), win.end.strftime("%m/%d %H:%M"))]
    for i, s in enumerate(slots, 1):
        lines.append("\n[{}번 {} ({}) 재료]".format(i, s.label, s.key))
        if not s.news:
            lines.append("  (재료 없음)")
        lines += ["  - [{}] {}".format(n.published.strftime("%H:%M"), n.title) for n in s.news]
    return "\n".join(lines)


def _repeats(bullet: str, title: str, ratio: float = 0.5) -> bool:
    """불릿의 어절 절반 이상이 제목에 그대로 들어 있으면 제목 반복으로 본다.

    한 글자 어절(및·미 등)은 우연히 겹치기 쉬워 세지 않는다. 조사가 붙은 어절
    ("급락에")은 제목에 그 모양 그대로 있을 때만 맞는다 — 느슨하지만, 같은 사실을
    다른 말로 쓴 건 놔두고 문구째 베낀 것만 잡으려는 것이라 이 정도면 된다.
    """
    words = [w for w in bullet.split() if len(w) >= 2]
    if not words or not title:
        return False
    return sum(1 for w in words if w in title) / len(words) >= ratio


def summarize(market: str, market_label: str, win: Window, slots: List[Slot],
              forbid: Optional[List[str]] = None) -> Optional[dict]:
    """{"headline":…, "card": {"title":…, "bullets":[…]}}. 실패/재료 없음이면 None.

    bullets는 번호 순서를 지킨다. 재료가 없거나 걸러진 번호는 빠지므로 3개보다
    적을 수 있다 — 없는 불릿을 지어내는 것보다 낫다.
    """
    if not any(s.news for s in slots):
        print("  [시장 요약] {} 재료 없음(휴장일?) → 건너뜀".format(market_label))
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [시장 요약] ANTHROPIC_API_KEY 없음 → 건너뜀")
        return None

    keys = [s.key for s in slots]
    try:
        # summarize.py와 같은 이유로 import까지 try 안에 둔다.
        import anthropic

        client = anthropic.Anthropic()
        system, schema = _system(market, slots), _schema(slots)
        messages = [{"role": "user", "content": _block(market_label, win, slots)}]

        def ask() -> str:
            resp = client.messages.create(
                model=MARKET_SUMMARY_MODEL,
                max_tokens=MARKET_SUMMARY_MAX_TOKENS,
                thinking={"type": "disabled"},
                system=system,
                messages=messages,
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
            text = next((b.text for b in resp.content if b.type == "text"), None)
            if text is None:
                raise RuntimeError(
                    "응답에 텍스트가 없습니다 (stop_reason={}, 출력 {}토큰)".format(
                        resp.stop_reason, resp.usage.output_tokens))
            return text

        text = ask()
        result: Dict[str, str] = {k: str(v).strip() for k, v in json.loads(text).items()}

        # 모델은 글자 수를 정확히 세지 못한다 — 코드로 재고, 넘친 항목만 글자 수를
        # 알려주며 다시 쓰게 한다. 고친 항목만 받아들여 다른 줄이 바뀌는 걸 막는다.
        for _ in range(MARKET_BULLET_RETRIES):
            over = {k: len(result[k]) for k in keys if len(result[k]) > MARKET_BULLET_MAX_LEN}
            if not over:
                break
            print("  [시장 요약] {} 길이 초과 → 다시 씀: {}".format(market_label, over))
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "\n".join(
                    ["다음 항목이 공백 포함 {0}자를 넘었습니다. 이 항목만 {0}자 이하로 다시 쓰고,"
                     " 나머지 항목은 글자 하나 바꾸지 말고 그대로 두세요."
                     .format(MARKET_BULLET_MAX_LEN)]
                    + ['- {}: "{}" ({}자)'.format(k, result[k], n) for k, n in over.items()]
                    + ["종목을 여러 개 나열했다면 대표 종목 하나만 남기세요. 단어를 잘라"
                       " 붙이지 말고, 사실 하나를 골라 자연스럽게 읽히는 한 구절로 새로 쓰세요."])},
            ]
            text = ask()
            fixed = json.loads(text)
            for k in over:
                result[k] = str(fixed.get(k, result[k])).strip()
    except Exception as e:
        print("  [시장 요약] 실패 → 건너뜀: {}: {}".format(type(e).__name__, e))
        return None

    title = result.get("title", "")
    bullets = []
    for k in keys:
        b = result.get(k, "")
        if not b:
            continue                                   # 재료가 없던 번호
        if len(b) > MARKET_BULLET_MAX_LEN:
            # 다시 써도 넘쳤다. 두 줄로 넘어가도 내용은 맞으니 버리지 않고 남긴다.
            print("  [시장 요약] {} {}번 여전히 {}자: {}".format(market_label, k, len(b), b))
        if _repeats(b, title):
            # 바로 아래 붙어 읽히니 같은 말이 두 번 보인다 — 반복보다 한 줄 적은 게 낫다.
            print("  [시장 요약] {} 제목 반복 불릿 뺌: {}".format(market_label, b))
            continue
        bullets.append(b)

    out = {
        "headline": result.get("headline", ""),
        "card": {"title": title, "bullets": bullets},
    }

    # 마지막 안전망 — 재료를 걸렀고 프롬프트로 범위를 못박았는데도 엉뚱한 나라 이야기가
    # 나오면(예: 미국 요약에 코스피) 그 요약은 통째로 버린다. 틀린 요약을 보여주느니
    # 요약 카드를 숨기는 편이 낫다(호출부가 None이면 카드를 안 만든다).
    joined = " ".join([out["headline"], title] + bullets)
    hit = [w for w in (forbid or []) if w in joined]
    if hit:
        print("  [시장 요약] {} 요약에 다른 시장 단어 {} → 버림".format(market_label, hit))
        return None
    return out
