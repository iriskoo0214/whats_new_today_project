#!/usr/bin/env python3
"""브리핑 생성 진입점. 하루 두 번, 시장별로 나눠 돈다.

  오전 7시  --market us   미국 증시 마감 브리핑 (해외 종목)
  오후 6시  --market kr   한국 증시 마감 브리핑 (국내 종목)

각 실행은 자기 시장만 갱신하고 반대편 시장 데이터는 직전 것을 그대로 남긴다.
프로토타입의 시장 전환 버튼이 양쪽 다 살아 있어야 하기 때문이다.

  포트폴리오 → 가격(pykrx/yfinance) → 뉴스(Google News RSS/yfinance)
  → briefings/YYYY-MM-DD-{us,kr}.md → data/briefing.js, data/briefing.json

수동 실행:  .venv/bin/python pipeline/run_daily.py --market us
"""

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief
import emit
import news as news_mod
import prices
from config import BRIEFINGS_DIR, INTRADAY_ENABLED, KST, ensure_dirs
from portfolio import load_holdings, split_by_market

SECTION_TITLE = {"us": "해외 (미국 증시)", "kr": "국내 (한국 증시)"}
SECTION_LABEL = {"us": "해외", "kr": "국내"}


def log(msg: str) -> None:
    print("[{}] {}".format(datetime.now(KST).strftime("%H:%M:%S"), msg), flush=True)


def resolve_markets(choice: str, now: datetime):
    """auto면 실행 시각으로 정한다 — 정오 이전은 미국 마감, 이후는 한국 마감."""
    if choice == "auto":
        return ["us"] if now.hour < 12 else ["kr"]
    if choice == "all":
        return ["us", "kr"]
    return [choice]


def main() -> int:
    parser = argparse.ArgumentParser(description="노트폴리오 데일리 브리핑")
    parser.add_argument("--market", choices=["us", "kr", "all", "auto"], default="auto",
                        help="갱신할 시장 (기본 auto: 오전이면 us, 오후면 kr)")
    parser.add_argument("--summarizer", choices=["auto", "llm", "rule"], default="auto",
                        help="카드 문구 생성 방식 (기본 auto: API 키가 있으면 llm)")
    args = parser.parse_args()

    ensure_dirs()
    now = datetime.now(KST)
    targets = resolve_markets(args.market, now)
    log("브리핑 생성 시작 — {} / 대상 시장: {}".format(
        now.strftime("%Y-%m-%d %H:%M:%S %Z"), ", ".join(targets)))

    holdings = load_holdings()
    kr_h, us_h = split_by_market(holdings)
    by_market = {"us": us_h, "kr": kr_h}

    wanted = [h for m in targets for h in by_market[m]]
    if not wanted:
        log("대상 시장에 보유 종목이 없습니다. 아무것도 하지 않고 종료합니다.")
        return 0
    log("대상 종목 {}개 (전체 보유 {}개)".format(len(wanted), len(holdings)))

    log("가격 조회 중…")
    quotes = prices.fetch_all(
        [h for h in wanted if h.is_kr], [h for h in wanted if not h.is_kr])
    failed = [q.name for q in quotes.values() if not q.ok]
    log("가격 조회 완료 — 성공 {} / 실패 {}{}".format(
        len(quotes) - len(failed), len(failed),
        (" (" + ", ".join(failed) + ")") if failed else ""))

    log("뉴스 수집 중…")
    articles = news_mod.fetch_all(wanted, now)
    log("뉴스 수집 완료 — 총 {}건".format(sum(len(v) for v in articles.values())))

    briefs_by_market = {
        m: brief.build_briefs(by_market[m], quotes, articles) for m in targets
    }

    all_briefs = [b for m in targets for b in briefs_by_market[m]]

    if args.summarizer != "rule":
        import summarize
        log("카드 문구 요약 중…")
        done = summarize.apply(all_briefs)
        log("카드 문구 요약 완료 — LLM {} / 규칙 {}".format(done, len(all_briefs) - done))

    # 시간대별 브리핑 — Portfolios 탭에서만 쓴다. 홈 카드에는 영향이 없다.
    if INTRADAY_ENABLED:
        import intraday
        log("장중 시세 수집 중…")
        slots_by_ticker = intraday.fetch_all([b.holding for b in all_briefs], quotes)
        for b in all_briefs:
            b.slots = slots_by_ticker.get(b.quote.ticker)
        log("장중 시세 수집 완료 — {}종목 × 최대 {}시점".format(
            len(slots_by_ticker), max([len(v) for v in slots_by_ticker.values()] or [0])))

        if slots_by_ticker and args.summarizer != "rule":
            import intraday_summary
            log("시간대별 문구 생성 중…")
            texts = intraday_summary.summarize(all_briefs, slots_by_ticker)
            for b in all_briefs:
                b.slot_texts = texts.get(b.quote.ticker)
            log("시간대별 문구 완료 — {}종목".format(len(texts)))

    sections = [(SECTION_TITLE[m], briefs_by_market[m], SECTION_LABEL[m])
                for m in targets if briefs_by_market[m]]

    md = brief.build_markdown(sections, now)
    md_path = BRIEFINGS_DIR / "{}-{}.md".format(
        now.strftime("%Y-%m-%d"), "-".join(targets))
    md_path.write_text(md, encoding="utf-8")
    log("마크다운 브리핑 저장 — {}".format(md_path))

    payload = emit.build_payload(
        briefs_by_market, now,
        markdown_path="briefings/{}".format(md_path.name))
    emit.write(payload)
    log("프로토타입 데이터 저장 — 갱신 {} / 보존 {}".format(
        payload["refreshed"],
        [k for k in payload["markets"] if k not in payload["refreshed"]]))

    for title, briefs, label in sections:
        log("핵심: " + brief.headline_line(briefs, label))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
