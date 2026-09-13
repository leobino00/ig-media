# -*- coding: utf-8 -*-
"""주간 리밸런싱 백테스트 엔진.

타이밍 규약 (미래참조 차단):
    기준주 t 의 종가로 신호 S(t) 를 계산한다  →  t 주 종가에 포지션을 S(t) 로 바꾼다
    →  t+1 주 종가까지의 수익률을 그 포지션으로 받는다.
즉 실현 수익률 r(t+1) 에는 t+1 의 정보가 신호에 들어가지 않는다.
이 한 칸을 어기면 백테스트 수익률이 통째로 허구가 된다.

비용: 포지션이 바뀐 주에만 `switch_cost_bps` 를 곱셈으로 뺀다 (매도+매수 왕복 기준).
ETF 보수는 수정종가에 이미 반영돼 있으므로 **여기서 다시 빼지 않는다.**
"""

import datetime as dt
import math

import signals as S


class Result(object):
    pass


def run(dates, state_by_date, ret_by_symbol, state_to_symbol, rate_curve,
        switch_cost_bps=10.0, cash_state=S.NEUTRAL, periods_per_year=52):
    """dates 는 백테스트 구간의 주간 날짜(오름차순).

    state_by_date 는 그보다 앞선 날짜까지 포함해도 된다 (워밍업).
    반환: Result(equity, weekly, cagr_pct, mdd_pct, ...).
    """
    cost = switch_cost_bps / 10000.0
    eq = 1.0
    curve = [(dates[0], 1.0)]
    weekly = []
    prev_pos = None
    switches = 0
    weeks_in = {s: 0 for s in S.STATES}
    missing_signal = 0

    for i in range(1, len(dates)):
        d_sig, d_end = dates[i - 1], dates[i]
        st = state_by_date.get(d_sig)
        if st is None:
            missing_signal += 1
            st = cash_state
        weeks_in[st] += 1

        sym = state_to_symbol.get(st)
        if sym is None:
            r = rate_curve.period_return(d_sig, periods_per_year)
            if r is None:
                raise ValueError("금리 결측: %s" % d_sig)
        else:
            r = ret_by_symbol[sym].get(d_end)
            if r is None:
                raise ValueError("%s 수익률 결측: %s" % (sym, d_end))

        pos = sym or "CASH"
        if prev_pos is not None and pos != prev_pos:
            eq *= (1.0 - cost)
            switches += 1
        prev_pos = pos

        eq *= (1.0 + r)
        curve.append((d_end, eq))
        weekly.append((d_end, r, st, pos))

    res = Result()
    res.curve = curve
    res.weekly = weekly
    res.switches = switches
    res.weeks_in = weeks_in
    res.missing_signal = missing_signal
    res.years = (dates[-1] - dates[0]).days / 365.25
    res.total_pct = (eq - 1.0) * 100.0
    res.cagr_pct = ((eq ** (1.0 / res.years)) - 1.0) * 100.0 if res.years > 0 else None
    res.mdd_pct = max_drawdown_pct(curve)
    res.annual = annual_returns(curve)
    rs = [r for _, r, _, _ in weekly]
    res.vol_pct = (stdev(rs) * math.sqrt(periods_per_year) * 100.0) if len(rs) > 1 else None
    res.switches_per_year = switches / res.years if res.years > 0 else None
    return res


def stdev(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def max_drawdown_pct(curve):
    peak = None
    worst = 0.0
    for _, v in curve:
        peak = v if peak is None or v > peak else peak
        dd = v / peak - 1.0
        worst = min(worst, dd)
    return worst * 100.0


def annual_returns(curve):
    """연도별 수익률 %. 첫 해와 마지막 해는 부분 구간이므로 partial 로 표시한다."""
    by_year = {}
    for d, v in curve:
        by_year.setdefault(d.year, []).append((d, v))
    years = sorted(by_year)
    out = []
    prev_end = None
    for k, y in enumerate(years):
        rows = by_year[y]
        start_v = prev_end if prev_end is not None else rows[0][1]
        end_d, end_v = rows[-1]
        first_d = rows[0][0]
        partial = None
        if k == 0 and first_d.month > 1:
            partial = "%s 시작" % first_d.isoformat()
        elif y == years[-1] and end_d.month < 12:
            partial = "%s까지" % end_d.isoformat()
        out.append({
            "year": y,
            "return_pct": (end_v / start_v - 1.0) * 100.0,
            "partial": partial,
        })
        prev_end = end_v
    return out


def buy_and_hold(dates, ret_by_symbol, symbol, periods_per_year=52):
    eq = 1.0
    curve = [(dates[0], 1.0)]
    for i in range(1, len(dates)):
        eq *= (1.0 + ret_by_symbol[symbol][dates[i]])
        curve.append((dates[i], eq))
    res = Result()
    res.curve = curve
    res.years = (dates[-1] - dates[0]).days / 365.25
    res.total_pct = (eq - 1.0) * 100.0
    res.cagr_pct = ((eq ** (1.0 / res.years)) - 1.0) * 100.0
    res.mdd_pct = max_drawdown_pct(curve)
    res.annual = annual_returns(curve)
    res.switches = 0
    res.switches_per_year = 0.0
    res.weeks_in = None
    res.missing_signal = 0
    rs = [ret_by_symbol[symbol][dates[i]] for i in range(1, len(dates))]
    res.vol_pct = stdev(rs) * math.sqrt(periods_per_year) * 100.0
    return res
