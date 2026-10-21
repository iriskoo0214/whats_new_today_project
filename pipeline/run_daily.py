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
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief
import emit
import news as news_mod
import prices
from config import (BRIEFINGS_DIR, INTRADAY_ENABLED, KST, MARKET_SESSION,
                    MARKET_SUMMARY_FORBID, ensure_dirs)
from portfolio import load_holdings, split_by_market

SECTION_TITLE = {"us": "해외 (미국 증시)", "kr": "국내 (한국 증시)"}
SECTION_LABEL = {"us": "해외", "kr": "국내"}
# 시장 요약 LLM에 주는 이름 — "해외"만 주면 범위가 모호해서 국내 기사가 섞여도 못 걸렀다
SUMMARY_SCOPE = {"us": "미국 증시(뉴욕증시)", "kr": "한국 증시(코스피·코스닥)"}


def log(msg: str) -> None:
    print("[{}] {}".format(datetime.now(KST).strftime("%H:%M:%S"), msg), flush=True)


def resolve_markets(choice: str, now: datetime):
    """auto면 실행 시각으로 정한다 — 정오 이전은 미국 마감, 이후는 한국 마감."""
    if choice == "auto":
        return ["us"] if now.hour < 12 else ["kr"]
    if choice == "all":
        return ["us", "kr"]
    return [choice]


def last_session_day(market: str, now: datetime) -> date:
    """그 시장 현지 시각으로 장 마감이 이미 지난 가장 최근 날짜.

    주말·공휴일이어도 달력 날짜를 그대로 돌려준다. 그날 장이 열렸는지는
    휴장일 표가 아니라 받아온 시세의 거래일(as_of)이 말해준다.
    """
    s = MARKET_SESSION[market]
    local = now.astimezone(ZoneInfo(s["tz"]))
    day = local.date()
    if (local.hour, local.minute) < s["close"]:
        day -= timedelta(days=1)
    return day


def main() -> int:
    parser = argparse.ArgumentParser(description="노트폴리오 데일리 브리핑")
    parser.add_argument("--market", choices=["us", "kr", "all", "auto"], default="auto",
                        help="갱신할 시장 (기본 auto: 오전이면 us, 오후면 kr)")
    parser.add_argument("--summarizer", choices=["auto", "llm", "rule"], default="auto",
                        help="카드 문구 생성 방식 (기본 auto: API 키가 있으면 llm)")
    parser.add_argument("--slots-only", action="store_true",
                        help="장중 실행. 마감 브리핑은 그대로 두고 시간대별 슬롯만 갱신한다")
    args = parser.parse_args()

    ensure_dirs()
    now = datetime.now(KST)
    targets = resolve_markets(args.market, now)
    log("브리핑 생성 시작 — {} / 대상 시장: {}{}".format(
        now.strftime("%Y-%m-%d %H:%M:%S %Z"), ", ".join(targets),
        " / 슬롯만 갱신" if args.slots_only else ""))

    if args.slots_only and not INTRADAY_ENABLED:
        log("INTRADAY_ENABLED가 꺼져 있습니다. 갱신할 슬롯이 없어 종료합니다.")
        return 0

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

    # 휴장일엔 마감 브리핑을 만들지도, 알리지도 않는다. 정시 실행(cron-job.org)은
    # pick_job.py를 거치지 않고 여기로 바로 오므로 요일만으론 못 막는다. 공휴일
    # 표를 두는 대신 받은 종가의 거래일을 본다 — 설·추석·대체공휴일·임시공휴일,
    # 미국 휴장일까지 표 없이 걸러진다. 시세를 하나도 못 받았으면 휴장과 구분이
    # 안 되므로 예전처럼 진행한다.
    if not args.slots_only:
        for m in list(targets):
            day = last_session_day(m, now)
            got = [quotes[h.ticker].as_of for h in by_market[m]
                   if h.ticker in quotes and quotes[h.ticker].as_of]
            if got and max(got) < day:
                log("{} 휴장 — {} 장이 열리지 않았습니다(받은 마지막 거래일 {}). "
                    "마감 브리핑 갱신과 알림을 건너뜁니다.".format(
                        SECTION_LABEL[m], day.isoformat(), max(got).isoformat()))
                targets.remove(m)
        if not targets:
            log("갱신할 시장이 없어 종료합니다.")
            return 0
        wanted = [h for m in targets for h in by_market[m]]

    log("뉴스 수집 중…")
    articles = news_mod.fetch_all(wanted, now)
    log("뉴스 수집 완료 — 총 {}건".format(sum(len(v) for v in articles.values())))

    briefs_by_market = {
        m: brief.build_briefs(by_market[m], quotes, articles) for m in targets
    }

    all_briefs = [b for m in targets for b in briefs_by_market[m]]

    # 장중 실행은 홈 카드 문구를 건드리지 않는다. 어차피 emit에서 버려질 문구를
    # 만드느라 실행마다 API를 부르는 셈이 된다.
    if args.summarizer != "rule" and not args.slots_only:
        import summarize
        log("카드 문구 요약 중…")
        done = summarize.apply(all_briefs)
        log("카드 문구 요약 완료 — LLM {} / 규칙 {}".format(done, len(all_briefs) - done))

    # 시장 전체 헤드라인 / "OO장 어땠지" 3줄 요약 — Home 탭 전용, 마감
    # 브리핑에서만 만든다. 보유종목이 아니라 지수·유가·금리 뉴스가 재료다.
    market_summaries = {}
    if args.summarizer != "rule" and not args.slots_only:
        import market_news
        import market_summary as market_summary_mod
        log("시장 전체 헤드라인 생성 중…")
        for m in targets:
            if not briefs_by_market.get(m):
                continue
            win, slots = market_news.fetch_slot_news(m, now)
            log("  {} 매크로 뉴스 {} ({}~{}) — {}".format(
                SECTION_LABEL[m], win.day.strftime("%m/%d"),
                win.start.strftime("%m/%d %H:%M"), win.end.strftime("%m/%d %H:%M"),
                ", ".join("{} {}건".format(s.label, len(s.news)) for s in slots)))
            result = market_summary_mod.summarize(
                m, SUMMARY_SCOPE[m], win, slots, forbid=MARKET_SUMMARY_FORBID.get(m))
            if result:
                market_summaries[m] = result
        log("시장 전체 헤드라인 완료 — {}개 시장".format(len(market_summaries)))

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

    # 장중 실행은 마크다운을 쓰지 않는다. 반쪽짜리 하루로 그날 브리핑 문서를
    # 덮어쓰면, 저녁 마감 실행 전까지 남는 기록이 장중 스냅샷이 된다.
    markdown_path = ""
    if not args.slots_only:
        md = brief.build_markdown(sections, now)
        md_path = BRIEFINGS_DIR / "{}-{}.md".format(
            now.strftime("%Y-%m-%d"), "-".join(targets))
        md_path.write_text(md, encoding="utf-8")
        markdown_path = "briefings/{}".format(md_path.name)
        log("마크다운 브리핑 저장 — {}".format(md_path))

    payload = emit.build_payload(
        briefs_by_market, now,
        markdown_path=markdown_path, slots_only=args.slots_only,
        market_summaries=market_summaries)
    emit.write(payload)

    if args.slots_only:
        log("프로토타입 데이터 저장 — 슬롯 갱신 {} / 마감 브리핑은 그대로".format(
            payload["slots_refreshed"]))
        for m in payload["slots_refreshed"]:
            counts = [len(c.get("slots") or []) for c in payload["markets"][m]["cards"]]
            log("{} 시점 수 — 종목당 {}".format(SECTION_LABEL[m], counts))
        return 0

    log("프로토타입 데이터 저장 — 갱신 {} / 보존 {}".format(
        payload["refreshed"],
        [k for k in payload["markets"] if k not in payload["refreshed"]]))

    for title, briefs, label in sections:
        log("핵심: " + brief.headline_line(briefs, label))

    # 홈 카드가 방금 완성됐을 때만 알린다. 장중 실행(--slots-only)은 위에서
    # 이미 돌아갔으므로 여기 오지 않는다 — 슬롯만 채운 걸로 알림을 보내면
    # 열어봐야 어제 브리핑이 그대로 있다.
    import notify
    for m in payload["refreshed"]:
        notify.send(m)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
