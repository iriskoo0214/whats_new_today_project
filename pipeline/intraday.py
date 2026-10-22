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

from config import (INTRADAY_INTERVAL, INTRADAY_TIMES_KR, INTRADAY_TIMES_US,
                    INTRADAY_TOLERANCE_MIN, KST)
from portfolio import Holding
from prices import Quote, yf_symbol

warnings.filterwarnings("ignore")


@dataclass
class Slot:
    """하루 중 한 시점의 시세."""
    label: str          # 화면에 쓰는 시각 표기 ("9:10AM", "마감")
    price: float
    pct: Optional[float]      # 전일 종가 대비 등락률
    prev_close: Optional[float] = None   # pct의 기준선(그 슬롯 날짜의 전 거래일 종가)
    is_close: bool = False
    day: Optional[date] = None   # 이 시세가 어느 거래일 것인지(카드 날짜 도장에 쓴다)


def _label(ts, is_close: bool) -> str:
    """'9:00AM' / '3:30PM 마감' 꼴로 만든다(시안 표기와 같은 형식)."""
    local = ts.tz_convert(KST) if ts.tzinfo else ts
    hour12 = local.hour % 12 or 12
    ampm = "AM" if local.hour < 12 else "PM"
    text = "{}:{:02d}{}".format(hour12, local.minute, ampm)
    return text + " 마감" if is_close else text


# 거래소 현지 기준 정규장 마감 시각
CLOSE_TIME = {"KR": (15, 30), "US": (16, 0)}


def _session_over(holding: Holding, last_ts, last_day: date) -> bool:
    """마지막 거래일의 정규장이 이미 끝났는지.

    봉 데이터만 보고는 판단할 수 없다 — 국내는 yfinance가 마감 30분 전 봉까지만
    주는 일이 잦아서 '데이터가 끊긴 것'과 '장이 닫힌 것'이 구분되지 않는다.
    그래서 거래소 현지 시계로 마감 시각을 지났는지 본다.

    파이프라인은 원래 장이 끝난 뒤에만 도는데, 손으로 장중에 돌리는 일이 있다.
    그때 아직 나오지도 않은 종가를 '마감'이라고 적지 않으려고 확인한다.
    """
    import pandas as pd
    now = pd.Timestamp.now(tz=last_ts.tzinfo)
    if now.date() > last_day:
        return True
    h, m = CLOSE_TIME["KR" if holding.is_kr else "US"]
    return (now.hour, now.minute) >= (h, m)


def _minutes(ts) -> int:
    """KST 기준 그날 몇 분째인지. 0시=0, 23시=1380."""
    local = ts.tz_convert(KST) if ts.tzinfo else ts
    return local.hour * 60 + local.minute


def _gap(a: int, b: int) -> int:
    """자정을 넘겨도 맞게 재는 시각 차이(분).

    해외장은 KST 22:30에 열어 다음 날 05:00에 닫는다. 그냥 빼면 자정 전후가
    1300분 넘게 떨어진 것처럼 나와서 짧은 쪽으로 돌려 재야 한다.
    """
    d = abs(a - b) % 1440
    return min(d, 1440 - d)


def _pick_day(holding: Holding, df):
    """가장 최근 거래일의 봉만 골라낸다. (날짜, 그날 봉들)

    장중이면 그날 봉이 반쪽만 있다. 그래도 그 날을 쓴다 — 화면 날짜는 언제나
    '가장 최근 거래일'이어야 하고, 아직 오지 않은 시각(1:00PM·마감)은 그 시각이
    지나면 다음 실행에서 채워진다.
    """
    for d in sorted({ts.date() for ts in df.index}, reverse=True):
        day = df[[ts.date() == d for ts in df.index]]
        if not day.empty:
            return d, day
    return None, None


def fetch_slots(holding: Holding, quote: Quote) -> List[Slot]:
    """가장 최근 거래일의 정해진 시각(KST) 시세를 뽑는다.

    시점은 시장마다 다르다 — 국내는 9:10 / 10:30 / 1:00 / 마감,
    해외는 11:00PM / 마감. config.INTRADAY_TIMES_* 에서 고친다.
    아직 오지 않은 시각은 빠진 채로 나오고, 그 시각이 지나면 다음 실행에서 채워진다.

    값은 그 시각 봉의 **시가**를 쓴다. 5분봉의 종가는 5분 뒤 가격이라
    '9:10의 주가'로 내걸기에 맞지 않는다.

    '마감' 슬롯과 등락률 기준선은 시세의 일봉 종가(quote.closes)에서 가져온다.
    5분봉의 마지막 값은 거래소 공식 종가와 어긋나서(종가 단일가가 빠진다), 그대로
    쓰면 카드 가격과 마감 슬롯이 다르고 다음 날 등락률 기준도 틀어진다.

    데이터가 없으면 빈 리스트를 준다(호출한 쪽이 마감 한 슬롯으로 떨어진다).
    """
    sym = yf_symbol(holding)
    if not sym:
        return []

    import yfinance as yf
    try:
        df = yf.Ticker(sym).history(period="5d", interval=INTRADAY_INTERVAL)
    except Exception:
        return []
    return slots_from_bars(holding, df, quote)


def slots_from_bars(holding: Holding, df, quote: Quote) -> List[Slot]:
    """받아 둔 5분봉(df)에서 슬롯을 뽑는다. 네트워크를 타지 않는 부분."""
    if df.empty:
        return []

    df = df[df["Close"].notna()]
    if df.empty:
        return []

    last_day, day = _pick_day(holding, df)
    if day is None:
        return []

    marks = [_minutes(ts) for ts in day.index]
    targets = INTRADAY_TIMES_KR if holding.is_kr else INTRADAY_TIMES_US

    # 등락률 기준선은 슬롯 날짜(last_day)의 전 거래일 종가. 시세의 prev_close를 그대로
    # 쓰면 안 된다 — 아침엔 오늘 일봉이 아직 없어 시세가 어제 기준(as_of=어제)이고,
    # 그 prev_close는 그저께 종가다. 일봉에 없을 때만 5분봉 마지막 값으로 때운다.
    prev_close = quote.close_before(last_day)
    if prev_close is None:
        days = sorted({ts.date() for ts in df.index})
        i = days.index(last_day)
        before = df[[ts.date() == days[i - 1] for ts in df.index]] if i > 0 else None
        prev_close = float(before["Close"].iloc[-1]) if before is not None and not before.empty else None

    def pct_of(p):
        return None if not prev_close else (p - prev_close) / prev_close * 100.0

    slots, used = [], set()
    for hh, mm in targets:
        want = hh * 60 + mm
        i = min(range(len(marks)), key=lambda k: _gap(marks[k], want))
        # 그 시각 봉이 없으면(거래 정지 등) 그 슬롯은 건너뛴다
        if _gap(marks[i], want) > INTRADAY_TOLERANCE_MIN or i in used:
            continue
        used.add(i)
        price = float(day["Open"].iloc[i])
        slots.append(Slot(label=_label(day.index[i], False), price=price,
                          pct=pct_of(price), prev_close=prev_close, day=last_day))

    # 마감은 마지막에. 시각은 봉 시각이 아니라 '마감'으로만 쓴다
    # (정확한 마감 시각을 알 수 없어 틀린 시각을 적느니 생략하는 편이 낫다)
    # 아직 장이 열려 있으면 붙이지 않는다 — 나오지도 않은 종가를 적을 수는 없다
    if _session_over(holding, day.index[-1], last_day):
        close = quote.closes.get(last_day)
        if close is None:
            close = float(day["Close"].iloc[-1])
        slots.append(Slot(label="마감", price=close, pct=pct_of(close),
                          prev_close=prev_close, is_close=True, day=last_day))
    return slots


def fetch_all(holdings: List[Holding], quotes) -> dict:
    """{티커: [Slot, ...]}. 실패한 종목은 키 자체가 없다."""
    out = {}
    for h in holdings:
        q = quotes.get(h.ticker)
        if not q or not q.ok:
            continue
        slots = fetch_slots(h, q)
        # 슬롯 하나라도 그 시각이 지났으면 보여준다. 예전엔 2개를 요구했는데,
        # 해외는 슬롯이 11:00PM·마감 둘뿐이라 장중에는 11:00PM 하나만 잡히고
        # 그대로 버려져서 어제 것이 계속 떠 있었다.
        if slots:
            out[h.ticker] = slots
    return out
