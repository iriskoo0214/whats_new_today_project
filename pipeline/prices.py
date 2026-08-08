"""국내는 pykrx, 해외는 yfinance로 최신 종가와 전일 종가 대비 변동률을 구한다.

"오늘자 가격"이라고 해도 장이 열리지 않은 날(주말·공휴일)이나 장 시작 전에는
오늘 데이터가 없다. 그래서 최근 며칠치를 받아 마지막 두 거래일을 쓰고,
그 종가가 실제로 언제 것인지 as_of에 남겨 브리핑에서 밝힌다.
"""

import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from config import KST
from portfolio import Holding

warnings.filterwarnings("ignore")

LOOKBACK_DAYS = 12   # 연휴를 감안해 두 거래일이 반드시 잡히도록


@dataclass
class Quote:
    ticker: str
    name: str
    market: str
    close: Optional[float] = None
    prev_close: Optional[float] = None
    as_of: Optional[date] = None       # close가 어느 거래일 것인지
    currency: str = "KRW"
    error: Optional[str] = None

    @property
    def change(self) -> Optional[float]:
        if self.close is None or self.prev_close is None:
            return None
        return self.close - self.prev_close

    @property
    def change_pct(self) -> Optional[float]:
        if self.change is None or not self.prev_close:
            return None
        return self.change / self.prev_close * 100.0

    @property
    def ok(self) -> bool:
        return self.close is not None and self.error is None

    def format_price(self) -> str:
        if self.close is None:
            return "-"
        if self.currency == "KRW":
            return "{:,.0f}원".format(self.close)
        return "{:,.2f}달러".format(self.close)

    def format_change(self) -> str:
        pct = self.change_pct
        if pct is None:
            return "-"
        sign = "+" if pct > 0 else ""
        return "{}{:.2f}%".format(sign, pct)


# ---------------------------------------------------------------- 국내 (pykrx)

def fetch_kr(holdings: List[Holding]) -> Dict[str, Quote]:
    from pykrx import stock

    today = datetime.now(KST).date()
    fromdate = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")

    out = {}
    for h in holdings:
        q = Quote(ticker=h.ticker, name=h.name, market="KR", currency="KRW")
        try:
            df = stock.get_market_ohlcv(fromdate, todate, h.ticker)
            df = df[df["종가"] > 0]           # 거래정지일 등 0으로 채워진 행 제거
            if len(df) >= 1:
                q.close = float(df["종가"].iloc[-1])
                q.as_of = df.index[-1].date()
            if len(df) >= 2:
                q.prev_close = float(df["종가"].iloc[-2])
            if q.close is None:
                q.error = "최근 {}일간 시세 없음".format(LOOKBACK_DAYS)
        except Exception as e:                # 한 종목이 실패해도 나머지는 계속
            q.error = "{}: {}".format(type(e).__name__, e)
        out[h.ticker] = q
    return out


# ------------------------------------------------------------- 해외 (yfinance)

def fetch_us(holdings: List[Holding]) -> Dict[str, Quote]:
    import yfinance as yf

    out = {}
    for h in holdings:
        q = Quote(ticker=h.ticker, name=h.name, market="US", currency="USD")
        try:
            df = yf.Ticker(h.ticker).history(period="{}d".format(LOOKBACK_DAYS))
            df = df[df["Close"].notna()]
            if len(df) >= 1:
                q.close = float(df["Close"].iloc[-1])
                q.as_of = df.index[-1].date()
            if len(df) >= 2:
                q.prev_close = float(df["Close"].iloc[-2])
            if q.close is None:
                q.error = "yfinance에서 시세를 받지 못함"
        except Exception as e:
            q.error = "{}: {}".format(type(e).__name__, e)
        out[h.ticker] = q
    return out


def fetch_all(kr: List[Holding], us: List[Holding]) -> Dict[str, Quote]:
    quotes = {}
    if kr:
        quotes.update(fetch_kr(kr))
    if us:
        quotes.update(fetch_us(us))
    return quotes
