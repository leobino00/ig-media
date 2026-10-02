import numpy as np, pandas as pd
from bt import base, lev, sim, stats, TBILL


def sleeves(df):
    s = {"Q": lev(df, 1), "Q2": lev(df, 2), "Q3": lev(df, 3)}
    for c in ("TLT", "GLD"):
        if c in df:
            s[c] = df[c].fillna(0.0) + (0.03 / 252 if c == "TLT" else 0.0)
    return s


def emit(df, w):
    """목표비중이 바뀐 날만 행을 남기고 나머지는 NaN(매매 없음)."""
    w = w.reindex(df.index).ffill().fillna(0.0)
    chg = (w.diff().abs().sum(axis=1) > 1e-9)
    chg.iloc[0] = True
    t = w.copy()
    t[~chg] = np.nan
    return t


def periodic(df, weights, freq="QE"):
    """고정 비중, 분기(기본) 리밸런싱."""
    t = pd.DataFrame(np.nan, index=df.index, columns=list(weights))
    ends = df.index.to_series().groupby(df.index.to_period(freq[0])).max()
    days = set(ends.values) | {df.index[0]}
    for d in days:
        t.loc[d] = [weights[c] for c in weights]
    return t


def one(df, col, on, off_col=None):
    """on=True면 col 100%, 아니면 off_col 100%(없으면 현금)."""
    cols = ["Q", "Q2", "Q3", "TLT", "GLD"]
    cols = [c for c in cols if c in df.columns or c.startswith("Q")]
    w = pd.DataFrame(0.0, index=df.index, columns=cols)
    w.loc[on, col] = 1.0
    if off_col:
        w.loc[~on, off_col] = 1.0
    return emit(df, w)


def sma_signal(px, n=200, band=0.0):
    """종가 > SMA*(1+band) 진입, < SMA*(1-band) 이탈 (히스테리시스)."""
    ma = px.rolling(n).mean()
    up, dn = px > ma * (1 + band), px < ma * (1 - band)
    st = np.zeros(len(px), bool); cur = False
    for i in range(len(px)):
        if np.isnan(ma.iloc[i]):
            cur = False
        elif up.iloc[i]:
            cur = True
        elif dn.iloc[i]:
            cur = False
        st[i] = cur
    return pd.Series(st, index=px.index)


def vol_target(df, target=0.20, lmax=3.0, lookback=20, step=0.5, trend=None):
    """실현변동성 역비례 레버리지. step 단위로 반올림(매매 횟수 억제). trend가 False면 0."""
    rv = df.r.rolling(lookback).std() * np.sqrt(252)
    L = (target / rv).clip(0, lmax)
    L = (L / step).round() * step
    if trend is not None:
        L = L.where(trend, 0.0)
    L = L.fillna(0.0)
    # L배 노출을 Q(1x)와 Q3(3x) 조합이 아니라 합성 단일 슬리브로: Q3 비중 = L/3
    w = pd.DataFrame(0.0, index=df.index, columns=["Q", "Q2", "Q3"])
    w["Q3"] = L / 3.0
    return emit(df, w)


def u1(df, ratio=0.5, trig=0.5, tp=(1.0, 1.25, 1.5), stop=0.9, cost=0.001):
    """사용자 U1: 평소 QQQ 100%. 합성 TQQQ 종가 ≤ 역대최고×trig → 다음날 QQQ의 ratio를 TQQQ로.
    목표가=당시 전고점. 목표×1/1.25/1.5에서 1/3씩 매도→QQQ. 분할 중 목표×stop 아래면 잔량 매도.
    """
    rq = df.r.values; r3 = lev(df, 3).values; rf = df.rf.values
    p3 = np.cumprod(1 + r3)
    q = 1.0; x = 0.0; ath = p3[0]
    holding = False; target = None; tranche = 0; sold_any = False
    out = np.empty(len(df)); pend = None
    for t in range(len(df)):
        if pend is not None:
            kind, amt = pend
            if kind == "buy":
                q -= amt; x += amt - amt * cost
            else:
                amt = min(amt, x); x -= amt; q += amt - amt * cost
            pend = None
        q *= 1 + rq[t]; x *= 1 + r3[t]
        out[t] = q + x
        p = p3[t]
        if not holding:
            ath = max(ath, p)
            if p <= ath * trig:
                pend = ("buy", q * ratio); holding = True; target = ath; tranche = 0; sold_any = False
        else:
            levels = [target * m for m in tp]
            if tranche < 3 and p >= levels[tranche]:
                tranche += 1; sold_any = True
                # 1/3씩: 남은 수량 기준 (3→2→1 균등)
                amt = x / (4 - tranche) if tranche < 3 else x
                pend = ("sell", amt)
                if tranche == 3:
                    holding = False; ath = max(ath, p)
            elif sold_any and p < target * stop:
                pend = ("sell", x); holding = False; ath = max(ath, p)
    eq = pd.Series(out, index=df.index)
    return eq.pct_change().fillna(0.0)


def dual_mom(df, lookback=252, risk="Q", safe="TLT"):
    """QQQ 12개월 수익 > T-bill 누적이면 risk, 아니면 safe. 월말 판단."""
    px = df.px
    mom = px / px.shift(lookback) - 1
    rfc = (1 + df.rf).rolling(lookback).apply(np.prod, raw=True) - 1
    on = mom > rfc
    me = df.index.to_series().groupby(df.index.to_period("M")).max().values
    on_m = on.where(df.index.isin(me)).ffill().fillna(False).astype(bool)
    return one(df, risk, on_m, safe if safe in df.columns else None)


def vt2(df, target=0.25, lmax=3.0, lookback=20, step=0.5, trend=None, off_cap=0.0,
        ewm=False, weekly=False, band=0.0):
    """변동성 타깃 확장: 추세 이탈 시 레버리지 상한 off_cap(0=현금, 1=1배).
    band>0이면 목표 레버리지가 현재값과 band 이상 차이날 때만 조정(매매 억제)."""
    if ewm:
        rv = np.sqrt((df.r ** 2).ewm(span=lookback).mean() * 252)
    else:
        rv = df.r.rolling(lookback).std() * np.sqrt(252)
    L = (target / rv).clip(0, lmax).fillna(0.0)
    if trend is not None:
        L = L.where(trend, np.minimum(L, off_cap))
    if weekly:
        fri = df.index.to_series().groupby(df.index.to_period("W")).max().values
        L = L.where(df.index.isin(fri)).ffill().fillna(0.0)
    L = (L / step).round() * step
    if band > 0:
        cur = 0.0; out = []
        for v in L.values:
            if abs(v - cur) >= band or (v == 0) != (cur == 0):
                cur = v
            out.append(cur)
        L = pd.Series(out, index=L.index)
    w = pd.DataFrame(0.0, index=df.index, columns=["Q", "Q2", "Q3"])
    w["Q3"] = L / 3.0
    return emit(df, w)


def vt3(df, target=0.25, lmax=2.0, lookback=40, step=0.5, sleeve="Q3", rebalance="weekly"):
    """VT 구현 방식 검증용. sleeve: Q(1배, lmax≤1)·Q2(QLD, 비중 L/2)·Q3(TQQQ, 비중 L/3).
    rebalance: 'weekly' = 매주 금요일 목표비중으로 되돌림 · 'change' = L이 바뀔 때만 (vt2와 같음, 비중 드리프트 허용)."""
    rv = df.r.rolling(lookback).std() * np.sqrt(252)
    L = (target / rv).clip(0, lmax).fillna(0.0)
    fri = df.index.isin(df.index.to_series().groupby(df.index.to_period("W")).max().values)
    L = L.where(fri).ffill().fillna(0.0)
    L = (L / step).round() * step
    mult = {"Q": 1.0, "Q2": 2.0, "Q3": 3.0}[sleeve]
    w = pd.DataFrame(0.0, index=df.index, columns=["Q", "Q2", "Q3"])
    w[sleeve] = L / mult
    if rebalance == "change":
        return emit(df, w)
    t = w.copy(); t[~fri] = np.nan; t.iloc[0] = w.iloc[0]
    return t
