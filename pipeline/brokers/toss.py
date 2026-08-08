"""토스증권 연동 자리.

아직 붙이지 않았다. 계좌 API가 준비되면 fetch_holdings()만 채우면 되고,
파이프라인의 나머지는 data/portfolio.json 스키마만 보므로 손댈 필요가 없다.

붙이는 순서
  1. fetch_holdings()에서 실제 잔고를 받아 Holding 리스트로 변환
  2. sync()를 실행해 data/portfolio.json을 덮어씀 (source: "toss")
  3. run_daily.py는 그대로 두면 된다 — portfolio.load_holdings()가 갱신된 파일을 읽는다
"""

import json
import os
from datetime import datetime
from typing import List

from config import KST, PORTFOLIO_JSON
from portfolio import Holding

# 실제 연동 시 환경변수로 넣을 값들
TOSS_APP_KEY    = os.environ.get("TOSS_APP_KEY")
TOSS_APP_SECRET = os.environ.get("TOSS_APP_SECRET")
TOSS_ACCOUNT_NO = os.environ.get("TOSS_ACCOUNT_NO")


class TossNotConfigured(RuntimeError):
    pass


def fetch_holdings() -> List[Holding]:
    """토스증권 계좌의 보유 종목을 가져온다. (미구현)

    구현할 때 채워야 하는 것
      - 액세스 토큰 발급 (TOSS_APP_KEY / TOSS_APP_SECRET)
      - 잔고 조회 엔드포인트 호출
      - 응답의 종목코드/심볼을 market("KR"/"US")과 ticker로 정규화
        · 국내는 6자리 종목코드 (zfill(6))
        · 해외는 yfinance가 아는 심볼 형태로 (예: 나스닥 AAPL)
      - name은 화면에 쓸 한글 표기로 (없으면 종목명 그대로)
      - quantity / avg_price를 함께 채우면 나중에 평가손익까지 브리핑에 넣을 수 있다
    """
    if not (TOSS_APP_KEY and TOSS_APP_SECRET):
        raise TossNotConfigured(
            "TOSS_APP_KEY / TOSS_APP_SECRET가 없습니다. "
            "아직 토스 연동 전이면 data/portfolio.json을 직접 쓰세요."
        )
    raise NotImplementedError("토스증권 잔고 조회 미구현")


def sync() -> None:
    """토스에서 받은 잔고로 data/portfolio.json을 덮어쓴다."""
    holdings = fetch_holdings()
    payload = {
        "_comment": "토스증권 잔고에서 자동 동기화됨. 직접 수정하면 다음 동기화 때 덮어써진다.",
        "source": "toss",
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "holdings": [
            {
                "market": h.market,
                "ticker": h.ticker,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
            }
            for h in holdings
        ],
    }
    with open(PORTFOLIO_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    sync()
