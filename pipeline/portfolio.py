"""보유 종목 목록을 읽어온다.

지금은 data/portfolio.json이 원본이지만, 나중에 토스증권 API를 붙이면
brokers/toss.py가 같은 스키마로 이 파일을 갱신하고 아래 코드는 그대로 둔다.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional

from config import PORTFOLIO_JSON


@dataclass
class Holding:
    market: str                      # "KR" | "US"
    ticker: str                      # KR은 6자리 종목코드, US는 심볼
    name: str                        # 화면에 쓰는 한글 표기
    quantity: Optional[float] = None   # 토스 연동 후 채워질 자리
    avg_price: Optional[float] = None  # 토스 연동 후 채워질 자리
    extra: dict = field(default_factory=dict)

    @property
    def is_kr(self) -> bool:
        return self.market.upper() == "KR"


def load_holdings() -> List[Holding]:
    with open(PORTFOLIO_JSON, encoding="utf-8") as f:
        raw = json.load(f)

    holdings = []
    for h in raw.get("holdings", []):
        market = str(h["market"]).upper()
        ticker = str(h["ticker"]).strip()
        if market == "KR":
            ticker = ticker.zfill(6)   # 005930이 5930으로 저장돼 있어도 살린다
        holdings.append(
            Holding(
                market=market,
                ticker=ticker,
                name=h.get("name") or ticker,
                quantity=h.get("quantity"),
                avg_price=h.get("avg_price"),
                extra={k: v for k, v in h.items()
                       if k not in ("market", "ticker", "name", "quantity", "avg_price")},
            )
        )
    if not holdings:
        raise SystemExit("data/portfolio.json에 holdings가 비어 있습니다.")
    return holdings


def split_by_market(holdings: List[Holding]):
    kr = [h for h in holdings if h.is_kr]
    us = [h for h in holdings if not h.is_kr]
    return kr, us
