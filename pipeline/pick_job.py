"""스케줄로 돌 때 "이번 실행이 무엇을 할지"를 정한다 — 워크플로의 pick 스텝이 부른다.

출력은 한 줄 "시장|플래그" (예: "kr|", "us|--slots-only", "|"). 시장이 비면 건너뛴다.

왜 시각 버킷이 아니라 데이터로 정하나
  GitHub 크론은 best-effort라 1~2시간씩 밀리거나 한 번 걸러뛴다. "KST 16시대에 시작된
  실행이 국내 마감을 한다"처럼 시각에 못박으면, 16:10 예정 실행이 17시에 시작하는 순간
  '건너뜀' 버킷으로 떨어져 그날 마감 브리핑이 통째로 사라진다(실제로 9/16~9/18 사흘
  국내 마감이 한 번도 안 돌았다). 그래서 "오늘 그 시각 이후 전체 갱신이 이미 됐나"를
  data/briefing.json의 refreshed_at으로 보고, 안 됐으면 이번 실행이 채운다 — 밀려도,
  하나 걸러도 다음 실행이 알아서 메운다.

창(KST 기준)
  07~15시  미국 전체 갱신이 오늘 07:00 이후로 아직이면 → us 전체(미국 마감은 07:00보다
           당길 수 없다 — README '알아둘 것'). 이미 했으면 09~15시에 한해 kr 슬롯만.
  18~21시  국내 전체 갱신이 오늘 18:00 이후로 아직이면 → kr 전체. 했으면 건너뜀.
           (2026-10-15: 국내 마감 시각을 16:30 → 18:00으로 옮김. 16~17시대는 건너뜀.)
  22~06시  us 슬롯만(11:00PM 슬롯 — 자정을 넘는 구간).
  그 외(08시대 등)는 위 규칙에 안 걸리면 건너뜀.
"""

import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "briefing.json")


def _last_full_refresh(market):
    """그 시장의 전체 갱신 시각(KST, naive). 없거나 못 읽으면 None."""
    try:
        with open(DATA, encoding="utf-8") as f:
            stamp = json.load(f)["markets"][market]["refreshed_at"]
        return datetime.strptime(stamp.replace(" KST", "").strip(), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _stale(market, now, since_hour):
    """오늘 since_hour시 이후에 그 시장 전체 갱신이 없었나."""
    last = _last_full_refresh(market)
    line = now.replace(hour=since_hour, minute=0, second=0, microsecond=0)
    return last is None or last < line


def pick(now):
    h = now.hour
    if 7 <= h <= 15:
        if _stale("us", now, 7):
            return "us", ""
        if 9 <= h <= 15:
            return "kr", "--slots-only"
        return "", ""
    if 18 <= h <= 21:
        if _stale("kr", now, 18):
            return "kr", ""
        return "", ""
    if h >= 22 or h <= 6:
        return "us", "--slots-only"
    return "", ""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="테스트용 KST 시각 'YYYY-MM-DD HH:MM' (기본: 지금)")
    args = ap.parse_args()
    now = (datetime.strptime(args.now, "%Y-%m-%d %H:%M") if args.now
           else datetime.now(KST).replace(tzinfo=None))
    market, flag = pick(now)
    print("{}|{}".format(market, flag))
