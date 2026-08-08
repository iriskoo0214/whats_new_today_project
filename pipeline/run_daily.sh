#!/bin/zsh
# launchd가 하루 두 번 호출하는 래퍼.
#   run_daily.sh us   오전 7시 — 미국 증시 마감
#   run_daily.sh kr   오후 6시 — 한국 증시 마감
# launchd는 로그인 셸 환경을 물려주지 않으므로 경로를 전부 절대경로로 박아 둔다.

set -u
MARKET="${1:-auto}"

ROOT="/Users/gugaon/노트폴리오/프로토타입"
PY="$ROOT/.venv/bin/python"
LOG_DIR="$ROOT/logs"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m).log"

{
  echo "──────────── $(date '+%Y-%m-%d %H:%M:%S %Z') · market=$MARKET ────────────"
  "$PY" "$ROOT/pipeline/run_daily.py" --market "$MARKET"
  echo "exit=$?"
} >> "$LOG" 2>&1

# 30일보다 오래된 로그는 정리
find "$LOG_DIR" -name '*.log' -mtime +30 -delete 2>/dev/null || true
