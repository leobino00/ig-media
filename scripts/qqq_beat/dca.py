"""적립식 비교: 매월 첫 거래일 1씩 납입. BH(QQQM) · U1(적립은 QQQM, −50% 신호 시 QQQM의 ratio → TQQQ) · VT25(납입 후 그 주 비중으로 맞춤)."""
import numpy as np, pandas as pd
from bt import *
from strats import *


def month_starts(idx):
    return set(idx.to_series().groupby(idx.to_period("M")).min().values)


def dca_vt(df, S, targets, cost=COST):
    cols = list(targets.columns)
    R = np.column_stack([S[c].reindex(df.index).fillna(0.0).values for c in cols])
    T = targets.ffill().fillna(0.0).values; rf = df.rf.values; ms = month_starts(df.index)
    val = np.zeros(len(cols)); cash = 0.0; out = np.empty(len(df)); flows = np.zeros(len(df))
    prev = None
    for t, d in enumerate(df.index):
        tgt_w = T[t - 1] if t else T[0]
        if d in ms:
            cash += 1.0; flows[t] = 1.0
        if d in ms or prev is None or not np.array_equal(tgt_w, prev):
            tot = val.sum() + cash; tgt = tgt_w * tot
            c = np.abs(tgt - val).sum() * cost
            val = tgt; cash = tot - tgt.sum() - c; prev = tgt_w
        val = val * (1 + R[t]); cash *= 1 + rf[t]
        out[t] = val.sum() + cash
    return pd.Series(out, index=df.index), pd.Series(flows, index=df.index)


def dca_u1(df, ratio=0.5, trig=0.5, tp=(1.0, 1.25, 1.5), stop=0.9, cost=0.001):
    rq = df.r.values; r3 = lev(df, 3).values; ms = month_starts(df.index)
    p3 = np.cumprod(1 + r3); q = x = 0.0; ath = p3[0]; holding = False; tranche = 0; sold = False; target = None
    out = np.empty(len(df)); flows = np.zeros(len(df)); pend = None
    for t, d in enumerate(df.index):
        if d in ms:
            q += 1.0; flows[t] = 1.0
        if pend:
            k, a = pend
            if k == "buy": q -= a; x += a * (1 - cost)
            else: a = min(a, x); x -= a; q += a * (1 - cost)
            pend = None
        q *= 1 + rq[t]; x *= 1 + r3[t]; out[t] = q + x; p = p3[t]
        if not holding:
            ath = max(ath, p)
            if p <= ath * trig:
                pend = ("buy", q * ratio); holding = True; target = ath; tranche = 0; sold = False
        else:
            if tranche < 3 and p >= target * tp[tranche]:
                tranche += 1; sold = True; pend = ("sell", x / (4 - tranche) if tranche < 3 else x)
                if tranche == 3: holding = False; ath = max(ath, p)
            elif sold and p < target * stop:
                pend = ("sell", x); holding = False; ath = max(ath, p)
    return pd.Series(out, index=df.index), pd.Series(flows, index=df.index)


def irr(values, flows, s0, s1):
    """월 납입 흐름의 연 IRR (s0~s1 창). 창 시작 시 잔고 0 가정 → 창마다 새로 적립한 결과를 쓰므로 호출 쪽이 창별 시뮬레이션."""
    f = flows[s0:s1]; v = values[s1]
    ts = np.array([(d - f.index[0]).days / 365.25 for d in f.index[f > 0]]); T = (s1 - f.index[0]).days / 365.25
    lo, hi = -0.99, 2.0
    for _ in range(100):
        r = (lo + hi) / 2; fv = np.sum((1 + r) ** (T - ts))
        lo, hi = (r, hi) if fv < v else (lo, r)
    return r
