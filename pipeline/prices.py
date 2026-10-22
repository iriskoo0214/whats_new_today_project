"""yfinance 일봉으로 최신 종가와 전일 종가 대비 변동률을 구한다.

"오늘자 가격"이라고 해도 장이 열리지 않은 날(주말·공휴일)이나 장 시작 전에는
오늘 데이터가 없다. 그래서 최근 며칠치를 받아 마지막 두 거래일을 쓰고,
그 종가가 실제로 언제 것인지 as_of에 남겨 브리핑에서 밝힌다.

국내도 pykrx가 아니라 yfinance(.KS/.KQ)를 먼저 쓴다. pykrx의 기본 조회
(adjusted=True)는 네이버 차트에서 받는데, 넥스트레이드(NXT)가 생긴 뒤로 네이버
일봉 종가는 KRX 정규장 종가가 아니라 NXT 애프터마켓(~20:00)까지 합친 통합
마지막 체결가다. 18:00 마감 브리핑 때는 아직 애프터마켓 중이라 그 시점 체결가가
잡히고, 다음 날 다시 받으면 20:00 체결가로 바뀐다. 어느 쪽도 다음 날 등락률의
기준이 되는 공식 종가가 아니다(2026-10-21 SK하이닉스: 공식 1,294,000원, 18:00
1,283,000원, 다음 날 1,288,000원). yfinance 일봉은 KRX 종가와 맞는다.
pykrx는 yfinance가 그 종목을 못 찾을 때만 쓴다.
"""

import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from config import KST
from portfolio import Holding

warnings.filterwarnings("ignore")

LOOKBACK_DAYS = 12   # 연휴를 감안해 두 거래일이 반드시 잡히도록

_symbol_cache = {}


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
    # 최근 거래일별 종가. 장중 슬롯이 시세와 다른 날일 때(아침에 오늘 일봉이 아직 없을 때)
    # 그 날의 전 거래일 종가를 여기서 찾는다 — 5분봉 마지막 값은 공식 종가가 아니다.
    closes: Dict[date, float] = field(default_factory=dict)

    def close_before(self, day: date) -> Optional[float]:
        """day 직전 거래일의 종가. 모르면 None."""
        earlier = [d for d in self.closes if d < day]
        return self.closes[max(earlier)] if earlier else None

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


def yf_symbol(holding: Holding) -> Optional[str]:
    """yfinance가 아는 심볼로 바꾼다. 국내는 .KS / .KQ 를 실제로 찔러 확인한다."""
    if not holding.is_kr:
        return holding.ticker
    if holding.ticker in _symbol_cache:
        return _symbol_cache[holding.ticker]

    import yfinance as yf
    for suffix in (".KS", ".KQ"):
        sym = holding.ticker + suffix
        try:
            if not yf.Ticker(sym).history(period="2d", interval="1d").empty:
                _symbol_cache[holding.ticker] = sym
                return sym
        except Exception:
            continue
    _symbol_cache[holding.ticker] = None
    return None


def _fill(q: Quote, closes) -> None:
    """(거래일, 종가) 목록을 날짜순으로 받아 시세를 채운다."""
    q.closes = {d: float(c) for d, c in closes}
    days = sorted(q.closes)
    if days:
        q.as_of = days[-1]
        q.close = q.closes[days[-1]]
    if len(days) >= 2:
        q.prev_close = q.closes[days[-2]]


def _yf_closes(symbol: str):
    import yfinance as yf
    df = yf.Ticker(symbol).history(period="{}d".format(LOOKBACK_DAYS))
    df = df[df["Close"].notna()]
    return [(ts.date(), c) for ts, c in df["Close"].items()]


# ------------------------------------------------------------------- 국내

def fetch_kr(holdings: List[Holding]) -> Dict[str, Quote]:
    out = {}
    for h in holdings:
        q = Quote(ticker=h.ticker, name=h.name, market="KR", currency="KRW")
        try:
            sym = yf_symbol(h)
            closes = _yf_closes(sym) if sym else []
            if not closes:
                closes = _pykrx_closes(h)
            _fill(q, closes)
            if q.close is None:
                q.error = "최근 {}일간 시세 없음".format(LOOKBACK_DAYS)
        except Exception as e:                # 한 종목이 실패해도 나머지는 계속
            q.error = "{}: {}".format(type(e).__name__, e)
        out[h.ticker] = q
    return out


def _pykrx_closes(h: Holding):
    """yfinance에 없는 종목용. 통합(NXT 포함) 종가라 공식 종가와 어긋날 수 있다."""
    from pykrx import stock

    today = datetime.now(KST).date()
    fromdate = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")
    df = stock.get_market_ohlcv(fromdate, todate, h.ticker)
    df = df[df["종가"] > 0]           # 거래정지일 등 0으로 채워진 행 제거
    return [(ts.date(), c) for ts, c in df["종가"].items()]


# ------------------------------------------------------------- 해외 (yfinance)

def fetch_us(holdings: List[Holding]) -> Dict[str, Quote]:
    out = {}
    for h in holdings:
        q = Quote(ticker=h.ticker, name=h.name, market="US", currency="USD")
        try:
            _fill(q, _yf_closes(h.ticker))
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
