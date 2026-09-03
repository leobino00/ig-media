#!/usr/bin/env python3
"""FRED 수집기 — nasdaq-monthly-allocation / nasdaq-event-trigger 입력 자동화.

GitHub Actions(또는 로컬)에서 실행한다. 이 세션 환경에서는 FRED가 차단돼 있으므로
결과 파일(claude/advisor/월간판정/입력/fred-latest.json · .md)을 저장소에 커밋해 두면
어드바이저가 저장소에서 읽는다.

API 키 없이 fredgraph.csv 엔드포인트를 쓴다. FRED_API_KEY 환경변수가 있으면 API를 우선 쓴다.
추정하지 않는다: 값이 없으면 null로 두고 결측으로 표시한다.
"""
import csv, io, json, os, sys, datetime as dt, urllib.request, urllib.parse, re

SERIES = {
    # code: (FRED id, 설명, 스킬 코드)
    "IC4WSA":       ("IC4WSA",       "신규 실업수당 청구 4주 이동평균",       "B2 원지표"),
    "BAMLH0A0HYM2": ("BAMLH0A0HYM2", "ICE BofA US HY OAS (%p)",            "C3 원지표 · T3"),
    "VIXCLS":       ("VIXCLS",       "VIX 종가",                            "C4 원지표 · T2 · T6"),
    "WALCL":        ("WALCL",        "연준 총자산 (백만$)",                  "B5 구성"),
    "WTREGEN":      ("WTREGEN",      "재무부 일반계정 TGA (백만$)",          "B5 구성"),
    "RRPONTSYD":    ("RRPONTSYD",    "역레포 ON RRP (십억$)",                "B5 구성"),
    "DFII10":       ("DFII10",       "10년 TIPS 실질금리 (%)",              "B34 실질금리"),
    "DGS10":        ("DGS10",        "10년물 명목 (%)",                      "B34 참고"),
    "DFF":          ("DFF",          "실효 연방기금금리 (%)",                "B34·D2 참고"),
    "NASDAQ100":    ("NASDAQ100",    "나스닥100 지수 (NDX)",                "C1 · T1 · T5 · 원화 낙폭"),
    "DTWEXBGS":     ("DTWEXBGS",     "달러 광의 지수 (DXY 대체)",           "D3 대체"),
    "NASDAQCOM":    ("NASDAQCOM",    "나스닥 종합 (참고)",                   "참고"),
    "DEXKOUS":      ("DEXKOUS",      "원달러 (참고)",                        "D1 참고"),
}

def fetch_csv(series_id: str, start: str) -> list[tuple[str, float]]:
    key = os.environ.get("FRED_API_KEY")
    rows = []
    if key:
        url = ("https://api.stlouisfed.org/fred/series/observations?"
               + urllib.parse.urlencode({"series_id": series_id, "api_key": key,
                                         "file_type": "json", "observation_start": start}))
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
        for o in data["observations"]:
            if o["value"] not in (".", ""):
                rows.append((o["date"], float(o["value"])))
        return rows
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    with urllib.request.urlopen(url, timeout=30) as r:
        text = r.read().decode("utf-8")
    for rec in csv.DictReader(io.StringIO(text)):
        v = rec.get(series_id) or rec.get("VALUE") or list(rec.values())[-1]
        if v and v != ".":
            rows.append((rec["observation_date"] if "observation_date" in rec else rec["DATE"], float(v)))
    return rows

def at_or_before(rows, date_str):
    best = None
    for d, v in rows:
        if d <= date_str:
            best = (d, v)
        else:
            break
    return best

def month_avg(rows, ym):
    vals = [v for d, v in rows if d.startswith(ym)]
    return (round(sum(vals) / len(vals), 2), len(vals)) if vals else (None, 0)

def derive(series: dict, today: dt.date) -> dict:
    d = {}
    def latest(code): return series[code][-1] if series.get(code) else None
    def ago(code, days):
        return at_or_before(series.get(code, []), (today - dt.timedelta(days=days)).isoformat())

    # B2 — 청구 4주 평균: 최신 vs 4주 전 vs 3개월 전
    l = latest("IC4WSA"); m1 = ago("IC4WSA", 28); m3 = ago("IC4WSA", 91)
    d["B2"] = {"latest": l, "4w_ago": m1, "3m_ago": m3,
               "chg_4w_pct": round((l[1] / m1[1] - 1) * 100, 2) if l and m1 else None,
               "chg_3m_pct": round((l[1] / m3[1] - 1) * 100, 2) if l and m3 else None}
    # C3 / T3 — HY OAS: 최신 vs 1개월·3개월 전 (%p)
    l = latest("BAMLH0A0HYM2"); m1 = ago("BAMLH0A0HYM2", 30); m3 = ago("BAMLH0A0HYM2", 91)
    d["C3_T3"] = {"latest": l, "1m_ago": m1, "3m_ago": m3,
                  "chg_1m_pp": round(l[1] - m1[1], 2) if l and m1 else None,
                  "chg_3m_pp": round(l[1] - m3[1], 2) if l and m3 else None,
                  "T3_fire_(>=+0.60pp_3m)": (l[1] - m3[1] >= 0.60) if l and m3 else None}
    # C4 / T2 / T6 — VIX
    vix = series.get("VIXCLS", [])
    months = []
    for k in range(0, 3):
        first = (today.replace(day=1) - dt.timedelta(days=1)) if k == 0 else None
        ym = (today.replace(day=1) - dt.timedelta(days=1 + 31 * (k))).strftime("%Y-%m") if k else (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
        months.append((ym,) + month_avg(vix, ym))
    last2 = vix[-2:]
    d["C4_T2"] = {"monthly_avg_prev_months": months, "last_2_closes": last2,
                  "T2_fire_(>=30_two_days)": (len(last2) == 2 and all(v >= 30 for _, v in last2)),
                  "T6_vix_below_25": (last2[-1][1] < 25) if last2 else None}
    # B5 — 순유동성 = WALCL − WTREGEN − RRPONTSYD(십억→백만 환산)
    def nl_at(date_str):
        a = at_or_before(series.get("WALCL", []), date_str)
        t = at_or_before(series.get("WTREGEN", []), date_str)
        r = at_or_before(series.get("RRPONTSYD", []), date_str)
        if not (a and t and r): return None
        return {"date": a[0], "net_liquidity_musd": round(a[1] - t[1] - r[1] * 1000, 0),
                "WALCL": a[1], "WTREGEN": t[1], "RRPONTSYD_bn": r[1]}
    now_nl = nl_at(today.isoformat()); m3_nl = nl_at((today - dt.timedelta(days=91)).isoformat())
    d["B5"] = {"latest": now_nl, "3m_ago": m3_nl,
               "chg_3m_pct": round((now_nl["net_liquidity_musd"] / m3_nl["net_liquidity_musd"] - 1) * 100, 2)
               if now_nl and m3_nl else None}
    # B34 — 실질금리 방향 (DFII10) + 명목 + 연방기금
    for code, key in (("DFII10", "B34_real"), ("DGS10", "B34_nominal"), ("DFF", "fed_funds")):
        l = latest(code); m3 = ago(code, 91)
        d[key] = {"latest": l, "3m_ago": m3, "chg_3m_pp": round(l[1] - m3[1], 2) if l and m3 else None}
    # 참고 시계열
    for code in ("NASDAQCOM", "DEXKOUS"):
        l = latest(code); m3 = ago(code, 91)
        d[code] = {"latest": l, "3m_ago": m3}
    return d

def to_markdown(out: dict) -> str:
    g = out["derived"]; s = []
    s.append(f"# FRED 자동 수집 — {out['fetched_at']} (UTC)\n")
    s.append("> 추정 없음. `null` = 결측. 스킬 채점은 어드바이저가 한다 — 이 파일은 값과 방향만 준다.\n")
    s.append("| 스킬 코드 | 항목 | 최신 | 비교 | 변화 |\n|---|---|---|---|---|")
    b = g["B2"]; s.append(f"| B2 | 청구 4주 평균 | {b['latest']} | 4주 전 {b['4w_ago']} · 3개월 전 {b['3m_ago']} | 4주 {b['chg_4w_pct']}% · 3개월 {b['chg_3m_pct']}% |")
    c = g["C3_T3"]; s.append(f"| C3 · T3 | HY OAS %p | {c['latest']} | 1개월 전 {c['1m_ago']} · 3개월 전 {c['3m_ago']} | 1개월 {c['chg_1m_pp']} · 3개월 {c['chg_3m_pp']} · **T3 발동 {c['T3_fire_(>=+0.60pp_3m)']}** |")
    v = g["C4_T2"]; s.append(f"| C4 · T2 · T6 | VIX | 최근 2일 {v['last_2_closes']} | 월평균 {v['monthly_avg_prev_months']} | **T2 발동 {v['T2_fire_(>=30_two_days)']}** · T6 VIX<25 {v['T6_vix_below_25']} |")
    n = g["B5"]; s.append(f"| B5 | 순유동성 (백만$) | {n['latest']} | 3개월 전 {n['3m_ago']} | 3개월 {n['chg_3m_pct']}% |")
    r = g["B34_real"]; s.append(f"| B34 실질 | DFII10 % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p |")
    r = g["B34_nominal"]; s.append(f"| B34 명목 | DGS10 % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p |")
    r = g["fed_funds"]; s.append(f"| 연방기금 | DFF % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p |")
    s.append(f"| 참고 | 나스닥 종합 | {g['NASDAQCOM']['latest']} | 3개월 전 {g['NASDAQCOM']['3m_ago']} | |")
    s.append(f"| 참고 | 원달러 | {g['DEXKOUS']['latest']} | 3개월 전 {g['DEXKOUS']['3m_ago']} | |")
    m = out.get("market", {})
    if m.get("NDX"):
        q = m["NDX"]; s.append(f"| C1 · T1 · T5 | NDX ({m.get('index_source')}) | {q['last']} · 200일선 {q['sma200']} ({q['pct_vs_sma200']:+}%) | 사상최고 {q['ath_close']} · 3개월 {q['chg_3m_pct']}% | 달러 낙폭 {q['drawdown_usd_pct']}% · **T1a {q['T1a_(<=-10%)']} · T1b {q['T1b_(<=-20%)']} · T5 {q['T5_(3m>=+25%)']}** |")
    if m.get("C2_breadth_QQQE_over_QQQ"):
        c = m["C2_breadth_QQQE_over_QQQ"]; s.append(f"| C2 (대체) | QQQE/QQQ | {c['now']} | 3개월 전 {c['3m_ago']} | {c['chg_3m_pct']}% |")
    if m.get("D3_dollar"):
        d3 = m["D3_dollar"]; s.append(f"| D3 (대체) | {d3['source']} | {d3['last']} | 3개월 전 {d3['3m_ago']} | {d3['chg_3m_pct']}% |")
    if m.get("D1_USDKRW"):
        d1 = m["D1_USDKRW"]; s.append(f"| D1 | 원달러 5년 밴드 | {d1['last']} | {d1['5y_low']} ~ {d1['5y_high']} | 위치 {d1['band_pos_pct']}% |")
    if m.get("KRW_drawdown_(부칙4)"):
        k = m["KRW_drawdown_(부칙4)"]; s.append(f"| 부칙 4 | QQQ 원화 낙폭 | {k['last']} | 원화 사상최고 {k['ath']} | **{k['drawdown_krw_pct']}% · 경보(−25%) {k['alert_(<=-25%)']}** |")
    if out.get("factset_surprise_pct") is not None:
        s.append(f"| A3 | FactSet EPS 서프라이즈 비율 | {out['factset_surprise_pct']}% | (최선노력 파싱) | |")
    if out.get("errors"):
        s.append("\n**수집 실패:** " + ", ".join(out["errors"]))
    return "\n".join(s) + "\n"

def try_factset() -> tuple[float | None, str | None]:
    """최선노력: FactSet Earnings Insight 요약 페이지에서 'XX% ... positive EPS surprise' 패턴."""
    try:
        req = urllib.request.Request("https://insight.factset.com/topic/earnings", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "ignore")
        m = re.search(r"(\d{2})%\s+of\s+S&amp;P 500 companies have reported (?:a )?positive EPS surprise", html) or \
            re.search(r"(\d{2})%\s+of\s+S&P 500 companies have reported (?:a )?positive EPS surprise", html)
        return (float(m.group(1)), None) if m else (None, "factset: 패턴 미발견")
    except Exception as e:
        return None, f"factset: {e}"

def fetch_stooq(sym: str) -> list[tuple[str, float]]:
    """stooq 일봉 CSV (키 불필요). sym 예: qqq.us"""
    url = f"https://stooq.com/q/d/l/?s={sym}&d1=20000101&i=d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", "ignore")
    rows = []
    for rec in csv.DictReader(io.StringIO(text)):
        try:
            rows.append((rec["Date"], float(rec["Close"])))
        except (KeyError, ValueError):
            continue
    if not rows:
        raise RuntimeError(f"stooq {sym}: 0 rows; head={text[:120]!r}")
    return rows

def market(px: dict, krw: list, today: dt.date, ndx: list | None = None, dxy: list | None = None) -> dict:
    """벤더 도구가 없는 세션을 위한 시장 지표: C1·C2·D1·D3·T1·T5·원화 낙폭.
    지수는 FRED NASDAQ100(NDX) — 트리거 스킬 규정과 일치. stooq QQQ는 폴백."""
    out = {}
    q = ndx if ndx else px.get("QQQ", [])
    out["index_source"] = "FRED NASDAQ100" if ndx else ("stooq QQQ" if q else None)
    if q:
        closes = [v for _, v in q]
        last_d, last = q[-1]
        sma200 = round(sum(closes[-200:]) / min(len(closes), 200), 2)
        sma200_prev = round(sum(closes[-220:-20]) / min(len(closes[-220:-20]), 200), 2) if len(closes) > 220 else None
        ath = max(q, key=lambda x: x[1])
        m3 = at_or_before(q, (today - dt.timedelta(days=91)).isoformat())
        out["NDX"] = {"last": (last_d, last), "sma200": sma200, "sma200_20d_ago": sma200_prev,
                      "pct_vs_sma200": round((last / sma200 - 1) * 100, 2),
                      "ath_close": ath, "drawdown_usd_pct": round((last / ath[1] - 1) * 100, 2),
                      "T1a_(<=-10%)": (last / ath[1] - 1) <= -0.10, "T1b_(<=-20%)": (last / ath[1] - 1) <= -0.20,
                      "chg_3m_pct": round((last / m3[1] - 1) * 100, 2) if m3 else None,
                      "T5_(3m>=+25%)": ((last / m3[1] - 1) >= 0.25) if m3 else None}
    e = px.get("QQQE", []); qq = px.get("QQQ", [])
    if qq and e:
        ed = {d: v for d, v in e}
        pairs = [(d, ed[d] / v) for d, v in qq if d in ed]
        if pairs:
            r_now = pairs[-1]; r_3m = at_or_before(pairs, (today - dt.timedelta(days=91)).isoformat())
            out["C2_breadth_QQQE_over_QQQ"] = {"now": (r_now[0], round(r_now[1], 4)),
                                               "3m_ago": (r_3m[0], round(r_3m[1], 4)) if r_3m else None,
                                               "chg_3m_pct": round((r_now[1] / r_3m[1] - 1) * 100, 2) if r_3m else None}
    u = dxy if dxy else px.get("UUP", [])
    if u:
        m3 = at_or_before(u, (today - dt.timedelta(days=91)).isoformat())
        out["D3_dollar"] = {"source": "FRED DTWEXBGS" if dxy else "stooq UUP", "last": u[-1], "3m_ago": m3,
                            "chg_3m_pct": round((u[-1][1] / m3[1] - 1) * 100, 2) if m3 else None}
    if krw:
        five = [v for d, v in krw if d >= (today - dt.timedelta(days=365 * 5)).isoformat()]
        lo, hi = min(five), max(five); last = krw[-1]
        out["D1_USDKRW"] = {"last": last, "5y_low": lo, "5y_high": hi,
                            "band_pos_pct": round((last[1] - lo) / (hi - lo) * 100, 1) if hi > lo else None}
        if q:
            kd = {d: v for d, v in krw}
            kq = []
            lastk = None
            for d, v in q:
                if d in kd: lastk = kd[d]
                if lastk: kq.append((d, v * lastk))
            if kq:
                athk = max(kq, key=lambda x: x[1]); lk = kq[-1]
                out["KRW_drawdown_(부칙4)"] = {"last": (lk[0], round(lk[1])), "ath": (athk[0], round(athk[1])),
                                              "drawdown_krw_pct": round((lk[1] / athk[1] - 1) * 100, 2),
                                              "alert_(<=-25%)": (lk[1] / athk[1] - 1) <= -0.25}
    return out

def main(out_dir: str):
    today = dt.date.today()
    start = (today - dt.timedelta(days=400)).isoformat()
    series, errors = {}, []
    for code, (fid, _, _) in SERIES.items():
        try:
            series[code] = fetch_csv(fid, (today - dt.timedelta(days=365 * 5 + 30)).isoformat() if code == "DEXKOUS" else start)
        except Exception as e:
            errors.append(f"{code}: {e}")
    px = {}
    for sym, code in (("qqq.us", "QQQ"), ("qqqe.us", "QQQE"), ("uup.us", "UUP")):
        try:
            px[code] = fetch_stooq(sym)
        except Exception as e:
            errors.append(f"stooq {sym}: {e}")
    mkt = market(px, series.get("DEXKOUS", []), today, ndx=series.get("NASDAQ100"), dxy=series.get("DTWEXBGS"))
    fs, fs_err = try_factset()
    if fs_err: errors.append(fs_err)
    out = {"fetched_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
           "series_meta": {k: {"fred_id": v[0], "desc": v[1], "skill_code": v[2]} for k, v in SERIES.items()},
           "last_values": {k: (v[-1] if v else None) for k, v in series.items()},
           "derived": derive(series, today),
           "market": mkt,
           "factset_surprise_pct": fs,
           "errors": errors,
           "raw_recent": {k: v[-70:] for k, v in series.items()}}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "fred-latest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "fred-latest.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(out))
    # 월별 스냅샷 (기준일 첫 영업일용 보존)
    snap = os.path.join(out_dir, f"fred-{today.strftime('%Y-%m-%d')}.json")
    with open(snap, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(to_markdown(out))
    return 0 if not errors else 0  # 부분 실패도 커밋한다 (결측 표시가 목적)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "claude/advisor/월간판정/입력"))
