"""장중 시세를 받아 시간대별 슬롯으로 자른다.

파이프라인은 하루 두 번(장 마감 뒤)만 돈다. 그래도 시간대별 흐름을 보여줄 수 있는 건
마감 후에 그날 30분봉을 통째로 받아 원하는 시점을 골라내면 되기 때문이다.
장중에 여러 번 돌 필요가 없다.

국내는 yfinance 심볼이 종목코드+.KS(코스피)/.KQ(코스닥) 꼴이라 붙여서 조회한다.
해외는 티커를 그대로 쓴다.
"""

import warnings
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from config import INTRADAY_INTERVAL, INTRADAY_SLOTS, KST
from portfolio import Holding

warnings.filterwarnings("ignore")

_symbol_cache = {}


@dataclass
class Slot:
    """하루 중 한 시점의 시세."""
    label: str          # 화면에 쓰는 시각 표기 ("9:00AM", "3:30PM 마감")
    price: float
    pct: Optional[float]      # 전일 종가 대비 등락률
    is_close: bool = False


def _symbol(holding: Holding) -> Optional[str]:
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


def _label(ts, is_close: bool) -> str:
    """'9:00AM' / '3:30PM 마감' 꼴로 만든다(시안 표기와 같은 형식)."""
    local = ts.tz_convert(KST) if ts.tzinfo else ts
    hour12 = local.hour % 12 or 12
    ampm = "AM" if local.hour < 12 else "PM"
    text = "{}:{:02d}{}".format(hour12, local.minute, ampm)
    return text + " 마감" if is_close else text


def fetch_slots(holding: Holding, prev_close: Optional[float],
                close_price: Optional[float] = None) -> List[Slot]:
    """마지막 거래일의 장중 시세에서 INTRADAY_SLOTS개 시점을 균등하게 고른다.

    마지막 슬롯은 공식 종가(close_price)로 덮어쓴다. yfinance의 장중 마지막 봉은
    거래소 공식 종가와 어긋나고(국내는 15:30 마감인데 14:30 봉이 마지막인 경우가 있다),
    그대로 두면 같은 화면에서 카드 가격과 슬롯 가격이 달라진다.

    데이터가 모자라면 있는 만큼만 돌려주고, 아예 없으면 빈 리스트를 준다
    (호출한 쪽이 마감 한 슬롯으로 떨어진다).
    """
    sym = _symbol(holding)
    if not sym:
        return []

    import yfinance as yf
    try:
        df = yf.Ticker(sym).history(period="5d", interval=INTRADAY_INTERVAL)
    except Exception:
        return []
    if df.empty:
        return []

    df = df[df["Close"].notna()]
    if df.empty:
        return []

    # 마지막 거래일만 남긴다 — 5일치를 받아 왔으므로 날짜로 잘라야 한다
    last_day: date = max(ts.date() for ts in df.index)
    day = df[[ts.date() == last_day for ts in df.index]]
    if day.empty:
        return []

    n = len(day)
    want = min(INTRADAY_SLOTS, n)
    # 마지막(종가)을 반드시 포함하도록 균등 배치한다
    idx = sorted({round(i * (n - 1) / (want - 1)) for i in range(want)}) if want > 1 else [n - 1]

    def pct_of(p):
        return None if not prev_close else (p - prev_close) / prev_close * 100.0

    slots = []
    for k, i in enumerate(idx):
        last = (k == len(idx) - 1)
        if last:
            # 마지막은 공식 종가로. 시각도 봉 시각이 아니라 '마감'으로만 쓴다
            # (정확한 마감 시각을 알 수 없어 틀린 시각을 적느니 생략하는 편이 낫다)
            price = close_price if close_price is not None else float(day["Close"].iloc[i])
            slots.append(Slot(label="마감", price=price, pct=pct_of(price), is_close=True))
        else:
            price = float(day["Close"].iloc[i])
            slots.append(Slot(label=_label(day.index[i], False), price=price,
                              pct=pct_of(price)))

    # 값이 같은 슬롯이 연달아 나오면(거래 없는 구간) 하나로 줄인다
    deduped = [slots[0]]
    for s in slots[1:]:
        if s.is_close or round(s.price, 4) != round(deduped[-1].price, 4):
            deduped.append(s)
    return deduped


def fetch_all(holdings: List[Holding], quotes) -> dict:
    """{티커: [Slot, ...]}. 실패한 종목은 키 자체가 없다."""
    out = {}
    for h in holdings:
        q = quotes.get(h.ticker)
        if not q or not q.ok:
            continue
        slots = fetch_slots(h, q.prev_close, q.close)
        if len(slots) >= 2:          # 슬롯이 하나뿐이면 굳이 시간대별로 보여줄 게 없다
            out[h.ticker] = slots
    return out
