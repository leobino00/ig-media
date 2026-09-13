# -*- coding: utf-8 -*-
"""QQQ 주간 종가 관측 — 계산 정의.

이 파일에는 계산만 있다. 수집도, 출력도, 판단도 없다.
정의를 바꾸면 CALC_VERSION을 올린다 — 소급 재계산을 하지 않으므로
어느 시점부터 정의가 달라졌는지 출력 파일만 보고 알 수 있어야 한다.

경계값은 약한 쪽으로 센다:
  - close == sma 는 「위」가 아니다 (strict >)
  - 낙폭 -10.00% 는 「-10% 이상 낙폭」에 포함한다 (<=)
  - 주간 등락률 0.00% 는 상승 주가 아니다 (strict >)
표준라이브러리만 쓴다.
"""

import datetime as dt
import math

CALC_VERSION = "0.1"

# 낙폭 구간 집계 임계치 (%). 바꾸면 CALC_VERSION을 올린다.
DD_THRESHOLDS = (-10.0, -20.0, -30.0)

# 임계치 비교 허용치 (%p).
# 90/100-1 은 이진부동소수에서 -9.999999999999998% 로 나온다. 허용치가 없으면
# 「정확히 -10% 낙폭」이 -10% 임계치에서 빠진다. 허용치는 표시 자리수(0.01%p)보다
# 일곱 자리 작으므로 -9.99% 를 -10% 로 끌어올리지는 않는다.
DD_EPS = 1e-9


# ---------------------------------------------------------------- 기초 통계

def mean(xs):
    xs = list(xs)
    if not xs:
        return None
    return sum(xs) / len(xs)


def stdev_sample(xs):
    """표본표준편차(n-1). 표본이 2개 미만이면 None."""
    xs = list(xs)
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def percentile(xs, q):
    """선형보간 백분위. q 는 0~100. 표본이 없으면 None."""
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * (q / 100.0)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[int(pos)]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


# ---------------------------------------------------------------- 가격 파생

def pct_change(new, old):
    """등락률 %. old 가 0 이하이거나 결측이면 None."""
    if new is None or old is None or old <= 0:
        return None
    return (new / old - 1.0) * 100.0


def weekly_returns(closes):
    """주간 등락률 % 리스트. 길이는 len(closes)-1."""
    return [pct_change(closes[i], closes[i - 1]) for i in range(1, len(closes))]


def sma(closes, n, end=None):
    """마지막 n주 단순이동평균. 표본이 n 미만이면 None."""
    end = len(closes) if end is None else end
    if n <= 0 or end < n:
        return None
    return mean(closes[end - n:end])


def above(value, reference):
    """strict >. 어느 한쪽이 결측이면 None (False 가 아니다)."""
    if value is None or reference is None:
        return None
    return value > reference


def trailing_return(closes, n, end=None):
    """n주 전 대비 등락률 %. 표본이 모자라면 None."""
    end = len(closes) if end is None else end
    i = end - 1
    j = i - n
    if j < 0:
        return None
    return pct_change(closes[i], closes[j])


def rolling_high_low(closes, n, end=None):
    """최근 n주(기준주 포함) 최고·최저 종가. 표본이 n 미만이면 (None, None)."""
    end = len(closes) if end is None else end
    if end < n:
        return (None, None)
    window = closes[end - n:end]
    return (max(window), min(window))


def annualized_vol(returns_pct, n, end=None):
    """최근 n개 주간 등락률의 표본표준편차를 연율화(x sqrt(52)). %."""
    end = len(returns_pct) if end is None else end
    if end < n:
        return None
    window = [r for r in returns_pct[end - n:end] if r is not None]
    if len(window) < n:
        return None
    sd = stdev_sample(window)
    if sd is None:
        return None
    return sd * math.sqrt(52.0)


def drawdown_series(closes):
    """각 주의 사상 최고 종가 대비 낙폭 % 리스트."""
    out = []
    peak = None
    for c in closes:
        peak = c if peak is None or c > peak else peak
        out.append((c / peak - 1.0) * 100.0)
    return out


def max_drawdown(closes):
    """(낙폭%, 고점 index, 저점 index). 빈 입력이면 (None, None, None)."""
    if not closes:
        return (None, None, None)
    peak = closes[0]
    peak_i = 0
    worst = 0.0
    worst_peak_i = 0
    worst_trough_i = 0
    for i, c in enumerate(closes):
        if c > peak:
            peak = c
            peak_i = i
        dd = (c / peak - 1.0) * 100.0
        if dd < worst:
            worst = dd
            worst_peak_i = peak_i
            worst_trough_i = i
    return (worst, worst_peak_i, worst_trough_i)


def drawdown_episodes(dates, closes, threshold):
    """threshold(%) 이하로 내려간 낙폭 구간.

    한 구간은 「직전 사상 최고 종가 -> 그 뒤 최저 종가 -> 최고 종가 회복」이다.
    회복하지 못한 채 시계열이 끝나면 recovered=False 이고 회복 관련 값은 None.
    경계: 낙폭 == threshold 도 포함한다 (<=, 허용치 DD_EPS).
    """
    eps = []
    if not closes:
        return eps
    peak = closes[0]
    peak_i = 0
    cur = None  # {'peak_i','trough_i','trough'}
    for i, c in enumerate(closes):
        if cur is None:
            if c > peak:
                peak = c
                peak_i = i
                continue
            dd = (c / peak - 1.0) * 100.0
            if dd <= threshold + DD_EPS:
                cur = {"peak_i": peak_i, "trough_i": i, "trough": c}
        else:
            if c < cur["trough"]:
                cur["trough"] = c
                cur["trough_i"] = i
            if c >= closes[cur["peak_i"]]:
                eps.append(_close_episode(dates, closes, cur, i))
                cur = None
                peak = c
                peak_i = i
    if cur is not None:
        eps.append(_close_episode(dates, closes, cur, None))
    return eps


def _close_episode(dates, closes, cur, rec_i):
    pi, ti = cur["peak_i"], cur["trough_i"]
    return {
        "peak_date": dates[pi].isoformat(),
        "peak_close": closes[pi],
        "trough_date": dates[ti].isoformat(),
        "trough_close": closes[ti],
        "drawdown_pct": (closes[ti] / closes[pi] - 1.0) * 100.0,
        "weeks_peak_to_trough": ti - pi,
        "recovered": rec_i is not None,
        "recovery_date": dates[rec_i].isoformat() if rec_i is not None else None,
        "weeks_trough_to_recovery": (rec_i - ti) if rec_i is not None else None,
        "weeks_total": (rec_i - pi) if rec_i is not None else None,
    }


def annual_returns(dates, closes):
    """연도별 등락률 %.

    각 연도의 마지막 관측 종가를 직전 연도의 마지막 관측 종가와 비교한다.
    첫 연도는 직전 종가가 없으므로 return_pct=None 이다. 추정하지 않는다.

    partial 은 두 가지 이유로 붙는다. 둘을 partial_reason 으로 구분한다:
      - 첫 연도: 직전 연말 종가가 없어 등락률 자체가 없다
      - 마지막 연도: 12월 관측에 도달하지 못했다 (연중)
    연중 값을 연간 값처럼 읽는 것을 막기 위한 표시다.
    """
    last_of_year = {}
    for d, c in zip(dates, closes):
        last_of_year[d.year] = (d, c)
    years = sorted(last_of_year)
    out = []
    for k, y in enumerate(years):
        d, c = last_of_year[y]
        prev = last_of_year[years[k - 1]][1] if k > 0 else None
        reason = None
        if k == 0:
            reason = "직전 연말 종가 없음"
        elif y == years[-1] and d.month < 12:
            reason = "연중, %s까지" % d.isoformat()
        out.append({
            "year": y,
            "last_date": d.isoformat(),
            "last_close": c,
            "return_pct": pct_change(c, prev),
            "partial": reason is not None,
            "partial_reason": reason,
        })
    return out


def cagr(dates, closes):
    """전 구간 연평균 복리 등락률 %. 365.25일 기준. 구간이 없으면 None."""
    if len(closes) < 2:
        return None
    days = (dates[-1] - dates[0]).days
    if days <= 0 or closes[0] <= 0:
        return None
    years = days / 365.25
    return ((closes[-1] / closes[0]) ** (1.0 / years) - 1.0) * 100.0


def span_years(dates):
    if len(dates) < 2:
        return None
    return (dates[-1] - dates[0]).days / 365.25
