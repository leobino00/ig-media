# -*- coding: utf-8 -*-
"""일간 리셋 레버리지 ETF 시뮬레이터.

TQQQ 상장(2010-02) 이전 구간을 보려면 3배를 합성해야 한다.
**주간 등락률에 3을 곱하는 방식은 쓰지 않는다** — 실제 TQQQ를 연 +9.66%p 과대평가한다
(`README.md` 「왜 실제 가격을 쓰는가」). 일간 리셋과 차입비용이 빠졌기 때문이다.

표준 상수레버리지 모형:

    r_port(일) = L·r_자산(일) + (1 − L)·r_무위험(일) − 보수(일)

    L = 1  → r_자산                     (차입 없음)
    L = 3  → 3r − 2·r_f                 (2배를 빌린다)
    L = −3 → −3r + 4·r_f                (3배를 공매도하고 4배를 현금으로 굴린다)

`보수`는 운용보수 + 차입 스프레드 + 추적오차를 한 숫자로 흡수한 값이다.
실제 TQQQ·SQQQ에 맞춰 **적합(fit)** 하고, 적합값이 공시 보수(TQQQ 0.84%·SQQQ 0.95%)
근처로 나오는지를 모형이 구조적으로 맞는지의 검사로 쓴다.
동떨어진 값이 나오면 모형이 뭔가를 빠뜨린 것이므로 그대로 보고한다.

일간으로 복리한 뒤 주간 종가로 집계한다 — 변동성 끌림(volatility drag)이 계산에서 저절로 나온다.
"""

import datetime as dt

TRADING_DAYS = 252.0


def simulate_daily(daily_dates, daily_closes, leverage, rate_curve, fee_annual_pct):
    """일간 리셋 상수레버리지 시계열을 만든다. 시작값 1.0.

    반환: [(date, value)] — daily_dates 와 같은 길이.
    """
    fee_d = (fee_annual_pct / 100.0) / TRADING_DAYS
    out = [(daily_dates[0], 1.0)]
    v = 1.0
    for i in range(1, len(daily_dates)):
        d = daily_dates[i]
        r = daily_closes[i] / daily_closes[i - 1] - 1.0
        rf_a = rate_curve.annual_pct(d)
        rf_d = ((rf_a / 100.0) / TRADING_DAYS) if rf_a is not None else 0.0
        step = leverage * r + (1.0 - leverage) * rf_d - fee_d
        v *= (1.0 + step)
        if v <= 0:
            v = 1e-12  # 전액 손실. 0으로 두면 이후 수익률이 정의되지 않는다
        out.append((d, v))
    return out


def to_weekly(daily_series, week_end_dates):
    """일간 시계열을 주간 종료일 축으로 집계한다.

    각 주간 종료일에 대해 **그 날짜 이하의 마지막 일간 값**을 쓴다 (미래를 보지 않는다).
    해당 주 이전에 일간 데이터가 없으면 그 주는 건너뛴다.
    """
    ds = [d for d, _ in daily_series]
    vs = [v for _, v in daily_series]
    out = []
    j = 0
    for wd in week_end_dates:
        while j + 1 < len(ds) and ds[j + 1] <= wd:
            j += 1
        if ds[j] <= wd:
            out.append((wd, vs[j]))
    return out


def cagr_pct(series):
    y = (series[-1][0] - series[0][0]).days / 365.25
    if y <= 0 or series[0][1] <= 0:
        return None
    return ((series[-1][1] / series[0][1]) ** (1.0 / y) - 1.0) * 100.0


def fit_fee(daily_dates, daily_closes, leverage, rate_curve, target_cagr_pct,
            lo=-5.0, hi=25.0, iters=60):
    """목표 CAGR에 맞는 연 보수를 이분법으로 찾는다.

    보수를 올리면 L>0 에서는 CAGR이 내려간다. L<0 에서도 마찬가지다(보수는 항상 차감).
    따라서 보수에 대해 CAGR은 단조감소이고 이분법이 성립한다.
    """
    def c(fee):
        return cagr_pct(simulate_daily(daily_dates, daily_closes, leverage, rate_curve, fee))

    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if c(mid) > target_cagr_pct:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0
