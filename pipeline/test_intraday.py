"""장중 슬롯의 등락률 기준선이 전 거래일 공식 종가인지 확인한다.

2026-10-21~22 SK하이닉스(000660) 실제 값으로 재현한다.
  공식 종가(yfinance 일봉 = 네이버 '전일 대비'로 역산한 값)
    10/19 1,277,000 / 10/20 1,223,000 / 10/21 1,294,000
  10/21 5분봉 마지막 값 1,287,000 — 공식 종가가 아니다
  pykrx(네이버 통합 시세) 10/21 종가 1,288,000 — 이것도 아니다

실행:  .venv/bin/python -m unittest discover -s pipeline -p 'test_*.py'
"""

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import emit
import intraday
from portfolio import Holding
from prices import Quote, _fill

HYNIX = Holding(market="KR", ticker="000660", name="SK하이닉스")
OFFICIAL = [(date(2026, 10, 19), 1277000.0), (date(2026, 10, 20), 1223000.0),
            (date(2026, 10, 21), 1294000.0)]


def _bars(rows):
    """[(KST 시각 문자열, 시가, 종가)] → yfinance 5분봉 꼴 DataFrame."""
    idx = pd.DatetimeIndex([pd.Timestamp(t, tz="Asia/Seoul") for t, _, _ in rows])
    return pd.DataFrame({"Open": [o for _, o, _ in rows],
                         "Close": [c for _, _, c in rows]}, index=idx)


BARS = _bars([
    ("2026-10-21 09:10", 1284000, 1290000),
    ("2026-10-21 14:55", 1290000, 1287000),   # 마지막 5분봉 — 공식 종가와 다르다
    ("2026-10-22 09:10", 1283000, 1280000),
    ("2026-10-22 10:30", 1268000, 1266000),
    ("2026-10-22 12:50", 1238000, 1236000),
])


def _quote(closes):
    q = Quote(ticker="000660", name="SK하이닉스", market="KR")
    _fill(q, closes)
    return q


class BaselineTest(unittest.TestCase):

    def _check(self, quote):
        slots = [s for s in intraday.slots_from_bars(HYNIX, BARS, quote) if not s.is_close]
        self.assertEqual([s.label for s in slots], ["9:10AM", "10:30AM", "12:50PM"])
        for s in slots:
            self.assertEqual(s.day, date(2026, 10, 22))
            self.assertEqual(s.prev_close, 1294000.0)
            self.assertAlmostEqual(s.pct, (s.price / 1294000.0 - 1) * 100)

        payload = emit._slots_payload(SimpleNamespace(slots=slots, slot_texts=None))
        self.assertEqual([p["prev_close"] for p in payload], [1294000.0] * 3)
        self.assertEqual(payload[0]["pct"], -0.85)

    def test_morning_before_todays_daily_bar(self):
        # 아침: 오늘 일봉이 아직 없어 시세는 10/21 기준(prev_close=10/20 종가)
        q = _quote(OFFICIAL)
        self.assertEqual(q.as_of, date(2026, 10, 21))
        self._check(q)

    def test_intraday_with_todays_daily_bar(self):
        # 장중: 오늘 일봉(진행 중)이 붙어 시세가 10/22 기준
        q = _quote(OFFICIAL + [(date(2026, 10, 22), 1230000.0)])
        self.assertEqual(q.prev_close, 1294000.0)
        self._check(q)

    def test_close_slot_uses_official_close(self):
        q = _quote(OFFICIAL)
        bars = BARS[[ts.date() == date(2026, 10, 21) for ts in BARS.index]]
        close = intraday.slots_from_bars(HYNIX, bars, q)[-1]
        self.assertTrue(close.is_close)
        self.assertEqual(close.price, 1294000.0)
        self.assertEqual(close.prev_close, 1223000.0)


if __name__ == "__main__":
    unittest.main()
