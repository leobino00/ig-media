# -*- coding: utf-8 -*-
"""가격·금리 로더와 주간 정렬.

세 종목의 주간 수정종가(배당·분할 반영)를 같은 날짜 축에 올린다.
수정종가를 쓰는 이유: 전략이 TQQQ·SQQQ를 실제로 보유하므로 분배금이 수익의 일부다.
특히 SQQQ는 담보 이자를 분배하므로 고금리 구간에서 미수정 종가는 수익을 과소계상한다.

ETF 보수(TQQQ 0.84%·SQQQ 0.95% 등)는 이미 NAV 안에서 차감된 뒤의 가격이다.
그래서 백테스트에서 보수를 다시 빼지 않는다. 다시 빼면 이중 계상이다.
"""

import csv
import datetime as dt


def _rows(path, cols):
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            out.append(tuple(r[c] for c in cols))
    return out


def load_series(path, value_col="adj_close"):
    """(date, value) 오름차순 리스트."""
    out = [(dt.date.fromisoformat(d), float(v)) for d, v in _rows(path, ("date", value_col))]
    out.sort()
    # 정렬은 무해하므로 한다. 조용히 못 고치는 것은 중복이다 —
    # 같은 날짜가 두 번 있으면 어느 값이 그 주의 종가인지 알 수 없고,
    # dict 로 넘어가는 순간 하나가 소리 없이 사라진다.
    dates = [d for d, _ in out]
    if len(set(dates)) != len(dates):
        dup = sorted({d for d in dates if dates.count(d) > 1})
        raise ValueError("날짜가 중복된다(%s): %s" % (path, ", ".join(x.isoformat() for x in dup[:5])))
    if any(v <= 0 for _, v in out):
        raise ValueError("0 이하 가격이 있다: %s" % path)
    return out


class RateCurve:
    """연준금리(주간). 기준일 **이하**의 가장 최근 값을 쓴다 — 미래를 보지 않는다."""

    def __init__(self, path):
        self.rows = [(dt.date.fromisoformat(d), float(v)) for d, v in _rows(path, ("date", "ffr_pct"))]
        self.rows.sort()
        if not self.rows:
            raise ValueError("금리 시계열이 비었다")

    def annual_pct(self, on):
        lo, hi = 0, len(self.rows) - 1
        if on < self.rows[0][0]:
            return None
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.rows[mid][0] <= on:
                lo = mid
            else:
                hi = mid - 1
        return self.rows[lo][1]

    def weekly_return(self, on):
        """주간 현금 수익률(소수). 연율 단순 1/52. 결측이면 0.0 을 쓰지 않고 None."""
        a = self.annual_pct(on)
        return None if a is None else (a / 100.0) / 52.0


def to_returns(series):
    """(date, value) → {date: 직전 관측 대비 수익률(소수)}. 첫 주는 없다."""
    return {series[i][0]: series[i][1] / series[i - 1][1] - 1.0 for i in range(1, len(series))}


def align(named_series):
    """{이름: [(date, value)]} → (공통 날짜 오름차순, {이름: {date: value}})."""
    maps = {k: dict(v) for k, v in named_series.items()}
    common = set.intersection(*(set(m) for m in maps.values()))
    return sorted(common), maps
