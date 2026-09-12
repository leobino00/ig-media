#!/usr/bin/env python3
"""계산 정의 — us-sector-strength (제안서 §5).

정의를 바꾸면 CALC_VERSION을 올린다. 어드바이저는 소급 채점을 하지 않으므로
버전이 바뀐 시점을 산출물에서 알 수 있어야 한다 (제안서 §5 마지막 문단).

경계값 처리: rs_ratio > 1 / rs_momentum > 0 만 강세·상승으로 센다. 같으면 약한 쪽이다.
"""
import datetime as dt
import statistics

CALC_VERSION = "0.1"
RS_WINDOW = 26      # 주 — rs_ratio 분모 평균 구간, 26주 고저 구간
MOM_LAG = 4         # 주 — 모멘텀·4주 변화 기준
DD_FIRE = -15.0     # % — rs_dd_15 (T4 손절 임계치와 같은 숫자)
UP_FIRE = 30.0      # % — rs_up_30 (T4 이익실현 검토 임계치와 같은 숫자)


def to_weekly(daily):
    """일봉 [(YYYY-MM-DD, close)] → 주봉 [(마지막거래일, close)]. ISO 주 단위 마지막 거래일."""
    by_week = {}
    for d, v in sorted(daily):
        key = dt.date.fromisoformat(d).isocalendar()[:2]
        by_week[key] = (d, v)          # 같은 주의 뒤 값이 앞 값을 덮는다 = 주 마지막 거래일
    return [by_week[k] for k in sorted(by_week)]


def ratio_series(sector_weekly, bench_weekly):
    """R(t) = 섹터 종가 ÷ QQQ 종가. 두 시리즈에 공통으로 있는 주만 쓴다."""
    bench = dict(bench_weekly)
    return [(d, v / bench[d]) for d, v in sector_weekly if d in bench and bench[d]]


def rs_series(ratios, window=RS_WINDOW):
    """rs_ratio(t) = R(t) / mean(R, 최근 window주). 워밍업 구간은 버린다."""
    out = []
    vals = [v for _, v in ratios]
    for i in range(window - 1, len(vals)):
        win = vals[i - window + 1:i + 1]
        m = sum(win) / len(win)
        if m:
            out.append((ratios[i][0], vals[i] / m))
    return out


def quadrant(rs, mom):
    """4분면. rs=rs_ratio, mom=rs_momentum(%)."""
    if rs is None or mom is None:
        return None
    if rs > 1:
        return "leading" if mom > 0 else "weakening"
    return "improving" if mom > 0 else "lagging"


def momentum(rs_vals, i, lag=MOM_LAG):
    """rs_momentum(t) = rs_ratio(t)/rs_ratio(t−lag) − 1, %."""
    if i - lag < 0 or not rs_vals[i - lag]:
        return None
    return (rs_vals[i] / rs_vals[i - lag] - 1) * 100


def quadrant_history(rs_list):
    """rs_series 결과 → [(날짜, 분면)]. 모멘텀을 만들 수 없는 앞 MOM_LAG주는 None."""
    vals = [v for _, v in rs_list]
    out = []
    for i, (d, v) in enumerate(rs_list):
        m = momentum(vals, i)
        out.append((d, quadrant(v, m), m))
    return out


def weeks_in_quadrant(quads):
    """[(날짜, 분면, 모멘텀)] → 마지막 분면이 며칠 주째인가. 분면이 None이면 0."""
    if not quads or quads[-1][1] is None:
        return 0
    cur, n = quads[-1][1], 0
    for _, q, _ in reversed(quads):
        if q != cur:
            break
        n += 1
    return n


def sector_metrics(ratios, rs_list):
    """한 섹터의 §5 지표 일괄 계산. 값이 모자라면 해당 항목만 None."""
    if not rs_list:
        return None
    quads = quadrant_history(rs_list)
    rs_vals = [v for _, v in rs_list]
    d, rs = rs_list[-1]
    mom = quads[-1][2]
    prev_q = quads[-2][1] if len(quads) >= 2 else None
    r_vals = [v for _, v in ratios]
    win = r_vals[-RS_WINDOW:]
    hi, lo = max(win), min(win)
    dd = (r_vals[-1] / hi - 1) * 100 if hi else None
    up = (r_vals[-1] / lo - 1) * 100 if lo else None
    rs_4w = rs_vals[-1 - MOM_LAG] if len(rs_vals) > MOM_LAG else None
    hist = rs_list[-13:]
    return {
        "as_of": d,
        "rs_ratio": round(rs, 4),
        "rs_chg_4w": round(rs - rs_4w, 4) if rs_4w is not None else None,
        "rs_momentum": round(mom, 2) if mom is not None else None,
        "quadrant": quads[-1][1],
        "weeks_in_quadrant": weeks_in_quadrant(quads),
        "quadrant_changed": (quads[-1][1] != prev_q) if prev_q is not None else None,
        "rs_dd_from_26w_high": round(dd, 2) if dd is not None else None,
        "rs_dd_15": (dd <= DD_FIRE) if dd is not None else None,
        "rs_up_from_26w_low": round(up, 2) if up is not None else None,
        "rs_up_30": (up >= UP_FIRE) if up is not None else None,
        "weeks_used": len(rs_list),
        "history_13w": {"week": [d for d, _ in hist],
                        "rs_ratio": [round(v, 4) for _, v in hist],
                        "quadrant": [q for _, q, _ in quads[-13:]]},
    }


def dispersion(rs_values):
    """같은 주 rs_ratio들의 표본표준편차(n−1). 2개 미만이면 None."""
    vals = [v for v in rs_values if v is not None]
    return round(statistics.stdev(vals), 4) if len(vals) >= 2 else None


def dispersion_history(rs_by_ticker, weeks=104 + RS_WINDOW):
    """주별 분산도 시계열. 해당 주에 모든 티커 값이 있는 주만 센다 (모집단 고정)."""
    per_week = {}
    for rs_list in rs_by_ticker.values():
        for d, v in rs_list[-weeks:]:
            per_week.setdefault(d, []).append(v)
    n = len(rs_by_ticker)
    return [(d, dispersion(v)) for d, v in sorted(per_week.items()) if len(v) == n]


def percentile(value, history):
    """history 중 value 이하인 비율(%). history가 비면 None."""
    if value is None or not history:
        return None
    le = sum(1 for h in history if h is not None and h <= value)
    return round(le / len([h for h in history if h is not None]) * 100)


def sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def pct_above_sma200(daily_by_symbol, offset=0, n=200):
    """구성종목 중 종가 > 200일 단순이동평균인 비율(%).
    offset>0이면 그만큼 거래일을 잘라 과거 시점으로 본다. 반환: (비율, 판정된 종목 수)."""
    above = total = 0
    for rows in daily_by_symbol.values():
        vals = [v for _, v in rows]
        if offset:
            vals = vals[:-offset] if offset < len(vals) else []
        m = sma(vals, n)
        if m is None:
            continue
        total += 1
        if vals[-1] > m:
            above += 1
    return (round(above / total * 100, 1) if total else None), total


def new_highs_lows(daily_by_symbol, window=5, lookback=252):
    """최근 window 거래일 안에 52주 신고가·신저가를 기록한 종목 수 (종가 기준).
    반환: (신고가, 신저가, 판정된 종목 수)."""
    nh = nl = total = 0
    for rows in daily_by_symbol.values():
        vals = [v for _, v in rows]
        if len(vals) < lookback:
            continue
        total += 1
        hit_h = hit_l = False
        for k in range(window):
            end = len(vals) - k
            win = vals[max(0, end - lookback):end]
            if vals[end - 1] >= max(win):
                hit_h = True
            if vals[end - 1] <= min(win):
                hit_l = True
        nh += hit_h
        nl += hit_l
    return nh, nl, total


def nh_nl_ratio(nh, nl):
    """신저가 0이면 나눌 수 없다 → None (제안서 R3: null + 신고가 수 병기)."""
    return round(nh / nl, 2) if nl else None
