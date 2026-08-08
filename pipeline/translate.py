"""영문 헤드라인을 한글로 옮긴다.

Claude API를 먼저 쓴다. 무료 구글 웹 번역은 고유명사를 영문 그대로 남겨서
(Michael Burry, SoFi, Ooredoo) 카드에 영문이 섞이는데, Claude는 사람·기업명까지
한글로 옮긴다. 카드 길이 계산에도 영향이 있다 — 한글이 영문보다 1.7배 넓다.

한 번 실행에 한 번만 호출하도록 배치로 번역한다. 실패하면 구글 → 원문 순으로
물러나고, 어디까지 됐는지는 translated 플래그로 알린다.
"""

import json
import os
import re
import urllib.parse
import urllib.request
from typing import List, Tuple

from config import (HTTP_TIMEOUT, TRANSLATE_MAX_TOKENS, TRANSLATE_MODEL,
                    USER_AGENT)

_HANGUL = re.compile(r"[가-힣]")
_cache = {}

SYSTEM = """당신은 금융 뉴스 헤드라인을 한국어로 옮기는 번역가입니다.

규칙:
- 사람 이름, 기업명, 제품명도 한글 표기로 옮깁니다.
  (Michael Burry → 마이클 버리, SoFi → 소파이, Ooredoo → 우리두, Visa → 비자)
- 티커(MSFT, NVDA), 숫자, 통화 기호, 퍼센트는 원문 그대로 둡니다.
- 헤드라인 문체를 유지하고, 설명이나 배경을 덧붙이지 않습니다.
- 원문에 없는 사실을 추가하지 않습니다.
- 입력과 같은 개수를, 입력 순서 그대로 반환합니다."""

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["translations"],
    "additionalProperties": False,
}


def _looks_korean(text: str) -> bool:
    hangul = len(_HANGUL.findall(text))
    return hangul >= max(2, len(text.replace(" ", "")) * 0.2)


# ------------------------------------------------------------------- Claude

def _claude(texts: List[str]) -> List[str]:
    """배치 번역. 개수가 어긋나면 통째로 실패 처리한다(잘못 짝지어지면 더 나쁘다)."""
    import anthropic

    client = anthropic.Anthropic()
    payload = "\n".join("{}. {}".format(i + 1, t) for i, t in enumerate(texts))

    resp = client.messages.create(
        model=TRANSLATE_MODEL,
        max_tokens=TRANSLATE_MAX_TOKENS,
        thinking={"type": "disabled"},   # 번역은 추론이 필요 없다 — 출력 토큰을 아낀다
        system=SYSTEM,
        messages=[{"role": "user", "content": payload}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )

    text = next(b.text for b in resp.content if b.type == "text")
    out = json.loads(text)["translations"]
    if len(out) != len(texts):
        raise ValueError("번역 개수 불일치: {} → {}".format(len(texts), len(out)))
    return [str(s).strip() for s in out]


# -------------------------------------------------------------------- 구글

def _google(text: str) -> str:
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
        {"client": "gtx", "sl": "en", "tl": "ko", "dt": "t", "q": text}
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        payload = json.load(r)
    return "".join(seg[0] for seg in payload[0] if seg and seg[0])


# ---------------------------------------------------------------------------

def to_korean_batch(texts: List[str]) -> List[Tuple[str, bool]]:
    """[(번역문, 번역 성공 여부)]를 입력 순서대로 돌려준다."""
    results = [None] * len(texts)
    todo = []   # (index, text) — 실제로 번역이 필요한 것만

    for i, raw in enumerate(texts):
        t = (raw or "").strip()
        if not t or _looks_korean(t):
            results[i] = (t, False)
        elif t in _cache:
            results[i] = (_cache[t], True)
        else:
            todo.append((i, t))

    if not todo:
        return results

    pending = [t for _, t in todo]
    translated = None

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            translated = _claude(pending)
        except Exception as e:
            print("  [번역] Claude 실패 → 구글로 대체: {}: {}".format(type(e).__name__, e))
    else:
        print("  [번역] ANTHROPIC_API_KEY 없음 → 구글 웹 번역 사용 (고유명사가 영문으로 남습니다)")

    if translated is None:
        translated = []
        for t in pending:
            try:
                translated.append(_google(t) or t)
            except Exception:
                translated.append(t)

    for (i, original), out in zip(todo, translated):
        out = (out or "").strip() or original
        ok = out != original
        if ok:
            _cache[original] = out
        results[i] = (out, ok)

    return results


def to_korean(text: str) -> Tuple[str, bool]:
    """단건 번역 — 배치를 쓸 수 없는 자리를 위한 얇은 래퍼."""
    return to_korean_batch([text])[0]
