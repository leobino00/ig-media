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
    "DGS30":        ("DGS30",        "30년물 명목 (%)",                      "IRP-002 ⑧ (<4.00% 전환 보류)"),
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
        # 비교 기준은 실행일이 아니라 **그 시리즈의 최신 관측일**이다. 실행일 앵커링은 지연 시리즈(주간·T−1)의
        # 창을 짧게 만든다 — 「4주 전」이 실제로는 3주 전이 되는 식이다 (감사 F063·F062).
        rows = series.get(code, [])
        if not rows:
            return None
        base = dt.date.fromisoformat(rows[-1][0])
        return at_or_before(rows, (base - dt.timedelta(days=days)).isoformat())

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
    now_nl = nl_at(today.isoformat())
    m3_nl = nl_at((dt.date.fromisoformat(now_nl["date"]) - dt.timedelta(days=91)).isoformat()) if now_nl else None
    d["B5"] = {"latest": now_nl, "3m_ago": m3_nl,
               "chg_3m_pct": round((now_nl["net_liquidity_musd"] / m3_nl["net_liquidity_musd"] - 1) * 100, 2)
               if now_nl and m3_nl else None}
    # B34 — 실질금리 방향 (DFII10) + 명목 + 연방기금
    for code, key in (("DFII10", "B34_real"), ("DGS10", "B34_nominal"), ("DFF", "fed_funds")):
        l = latest(code); m3 = ago(code, 91)
        d[key] = {"latest": l, "3m_ago": m3, "chg_3m_pp": round(l[1] - m3[1], 2) if l and m3 else None}
    # 30년물 — IRP-002 무효화 조건 ⑧ (4.00% 미만이면 미국채30년 전환 보류). 판정은 어드바이저가 한다.
    l = latest("DGS30"); m3 = ago("DGS30", 91)
    d["UST30_IRP002"] = {"latest": l, "3m_ago": m3, "chg_3m_pp": round(l[1] - m3[1], 2) if l and m3 else None,
                         "below_4.00": (l[1] < 4.00) if l else None}
    # 참고 시계열
    for code in ("NASDAQCOM", "DEXKOUS"):
        l = latest(code); m3 = ago(code, 91)
        d[code] = {"latest": l, "3m_ago": m3}
    return d

def to_markdown(out: dict) -> str:
    g = out["derived"]; s = []
    s.append(f"# FRED 자동 수집 — {out['fetched_at']} (UTC)\n")
    s.append("> 추정 없음. `null` = 결측. 스킬 채점은 어드바이저가 한다 — 이 파일은 값과 방향만 준다.\n")
    if out.get("basis"):
        s.append(f"> **기준일 {out['basis']} 이하로 잘라 계산** (월간 판정용). 비교 기준(4주·3개월 전)은 각 시리즈의 최신 관측일에서 센다.\n")
    else:
        s.append("> 비교 기준(4주·1개월·3개월 전)은 실행일이 아니라 **각 시리즈의 최신 관측일**에서 센다.\n")
    sup = out.get("supplement") or {}
    parts = []
    for code, v in sup.items():
        if v.get("yahoo_added"):
            parts.append(f"{code}: FRED ≤{v['fred_through']} + Yahoo {v['yahoo_symbol']} {', '.join(d for d, _ in v['yahoo_added'])}")
        elif v.get("error"):
            parts.append(f"{code}: FRED ≤{v.get('fred_through')} (Yahoo 보강 실패)")
        else:
            parts.append(f"{code}: FRED ≤{v.get('fred_through')} (보강 불필요)")
    if parts:
        s.append("> 최신 종가 보강: " + " · ".join(parts) + "\n")
    s.append("| 스킬 코드 | 항목 | 최신 | 비교 | 변화 |\n|---|---|---|---|---|")
    b = g["B2"]; s.append(f"| B2 | 청구 4주 평균 | {b['latest']} | 4주 전 {b['4w_ago']} · 3개월 전 {b['3m_ago']} | 4주 {b['chg_4w_pct']}% · 3개월 {b['chg_3m_pct']}% |")
    c = g["C3_T3"]; s.append(f"| C3 · T3 | HY OAS %p | {c['latest']} | 1개월 전 {c['1m_ago']} · 3개월 전 {c['3m_ago']} | 1개월 {c['chg_1m_pp']} · 3개월 {c['chg_3m_pp']} · **T3 발동 {c['T3_fire_(>=+0.60pp_3m)']}** |")
    v = g["C4_T2"]; s.append(f"| C4 · T2 · T6 | VIX | 최근 2일 {v['last_2_closes']} | 월평균 {v['monthly_avg_prev_months']} | **T2 발동 {v['T2_fire_(>=30_two_days)']}** · T6 VIX<25 {v['T6_vix_below_25']} |")
    n = g["B5"]; s.append(f"| B5 | 순유동성 (백만$) | {n['latest']} | 3개월 전 {n['3m_ago']} | 3개월 {n['chg_3m_pct']}% |")
    r = g["B34_real"]; s.append(f"| B34 실질 | DFII10 % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p |")
    r = g["B34_nominal"]; s.append(f"| B34 명목 | DGS10 % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p |")
    r = g["fed_funds"]; s.append(f"| 연방기금 | DFF % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p |")
    r = g["UST30_IRP002"]; s.append(f"| IRP-002 ⑧ | DGS30 % | {r['latest']} | 3개월 전 {r['3m_ago']} | {r['chg_3m_pp']}p · **4.00% 미만 {r['below_4.00']}** |")
    s.append(f"| 참고 | 나스닥 종합 | {g['NASDAQCOM']['latest']} | 3개월 전 {g['NASDAQCOM']['3m_ago']} | |")
    s.append(f"| 참고 | 원달러 | {g['DEXKOUS']['latest']} | 3개월 전 {g['DEXKOUS']['3m_ago']} | |")
    m = out.get("market", {})
    if m.get("NDX"):
        q = m["NDX"]; s.append(f"| C1 · T1 · T5 | NDX ({m.get('index_source')}) | {q['last']} · 200일선 {q['sma200']} ({q['pct_vs_sma200']:+}%) | 사상최고 {q['ath_close']} (탐색 창 {q.get('ath_window_start')}~) · 3개월 {q['chg_3m_pct']}% | 달러 낙폭 {q['drawdown_usd_pct']}% · **T1a {q['T1a_(<=-10%)']} · T1b {q['T1b_(<=-20%)']} · T5 {q['T5_(3m>=+25%)']}** |")
    if m.get("C2_breadth_QQQE_over_QQQ"):
        c = m["C2_breadth_QQQE_over_QQQ"]; s.append(f"| C2 (대체) | QQQE/QQQ | {c['now']} | 3개월 전 {c['3m_ago']} | {c['chg_3m_pct']}% |")
    if m.get("D3_dollar"):
        d3 = m["D3_dollar"]; s.append(f"| D3 (대체) | {d3['source']} | {d3['last']} | 3개월 전 {d3['3m_ago']} | {d3['chg_3m_pct']}% |")
    if m.get("D1_USDKRW"):
        d1 = m["D1_USDKRW"]; s.append(f"| D1 | 원달러 5년 밴드 | {d1['last']} | {d1['5y_low']} ~ {d1['5y_high']} | 위치 {d1['band_pos_pct']}% |")
    if m.get("KRW_drawdown_(부칙4)"):
        k = m["KRW_drawdown_(부칙4)"]; s.append(f"| 부칙 4 | QQQ 원화 낙폭 | {k['last']} | 원화 사상최고 {k['ath']} (창 {k.get('ath_window_start')}~ · 환율 {k.get('fx_used_for_last')}) | **{k['drawdown_krw_pct']}% · 경보(−25%) {k['alert_(<=-25%)']}** |")
    if m.get("HYT_GLB008"):
        hh = m["HYT_GLB008"]; s.append(f"| GLB-008 · GLB-004 | HYT 종가 ({hh['source']}) | {hh['last']} | 52주 {hh['52w_low']}~{hh['52w_high']} · $9.00까지 {hh['to_9.00_pct']:+}% | **정지 ≤7.50 {hh['stop_(close<=7.50)']} (2일 연속 {hh['stop_2days_(prev_and_last<=7.50)']}) · 목표 ≥9.00 {hh['target_(close>=9.00)']}** · 분배 공시 <$0.0779 여부는 수동 |")
    if m.get("QQQ_price"):
        qp = m["QQQ_price"]; s.append(f"| 부칙 5 대체 | QQQ {qp['field']} ({qp['source']}) | {qp['last']} | r_idx 대체 가능 {qp['usable_for_r_idx']} | Twelve Data 불가 시만 |")
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

YAHOO_FIELDS: dict = {}   # 심볼별로 어느 가격 필드를 썼는지 (adjclose / close) — 감사 F074

def fetch_yahoo(sym: str, range_: str = "1y", prefer_adj: bool = True) -> list[tuple[str, float]]:
    """Yahoo Finance chart API (키 불필요). 일봉. **수정종가(adjclose)** 를 우선 쓴다 —
    채점규칙 §2의 r_idx 정의(QQQ 수정종가)와 맞추기 위해서다. 지수(^NDX·^VIX)는 adjclose=close.
    prefer_adj=False면 미수정 종가 — 가격 조건(HYT $7.50/$9.00, `GLB-008`)은 분배금을 빼지 않은 시장가로 잰다."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={range_}&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    res = data["chart"]["result"][0]
    ts = res["timestamp"]
    adj = ((res["indicators"].get("adjclose") or [{}])[0] or {}).get("adjclose")
    closes = res["indicators"]["quote"][0]["close"]
    field = "adjclose" if prefer_adj and adj and any(v is not None for v in adj) else "close"
    vals = adj if field == "adjclose" else closes
    YAHOO_FIELDS[sym] = field
    rows = [(dt.datetime.utcfromtimestamp(t).date().isoformat(), float(c)) for t, c in zip(ts, vals) if c is not None]
    if not rows:
        raise RuntimeError(f"yahoo {sym}: 0 rows")
    return rows

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

def market(px: dict, krw: list, today: dt.date, ndx: list | None = None, dxy: list | None = None,
           px_src: dict | None = None) -> dict:
    """벤더 도구가 없는 세션을 위한 시장 지표: C1·C2·D1·D3·T1·T5·원화 낙폭.
    지수는 FRED NASDAQ100(NDX) — 트리거 스킬 규정과 일치. Yahoo/stooq QQQ는 폴백.
    「사상최고」는 시리즈 전체(1985~)에서 찾는다 — 400일 창은 장기 하락장에서 T1·−25% 경보를 꺼 버린다 (감사 F059).
    창 시작일을 함께 기록해 어드바이저가 창을 확인할 수 있게 한다."""
    px_src = px_src or {}
    out = {}
    q = ndx if ndx else px.get("QQQ", [])
    out["index_source"] = "FRED NASDAQ100" if ndx else (f"{px_src.get('QQQ', '?')} QQQ" if q else None)
    if q:
        closes = [v for _, v in q]
        last_d, last = q[-1]
        base = dt.date.fromisoformat(last_d)
        sma200 = round(sum(closes[-200:]) / min(len(closes), 200), 2)
        sma200_prev = round(sum(closes[-220:-20]) / min(len(closes[-220:-20]), 200), 2) if len(closes) > 220 else None
        ath = max(q, key=lambda x: x[1])
        m3 = at_or_before(q, (base - dt.timedelta(days=91)).isoformat())
        out["NDX"] = {"last": (last_d, last), "sma200": sma200, "sma200_20d_ago": sma200_prev,
                      "pct_vs_sma200": round((last / sma200 - 1) * 100, 2),
                      "ath_close": ath, "ath_window_start": q[0][0],
                      "drawdown_usd_pct": round((last / ath[1] - 1) * 100, 2),
                      "T1a_(<=-10%)": (last / ath[1] - 1) <= -0.10, "T1b_(<=-20%)": (last / ath[1] - 1) <= -0.20,
                      "chg_3m_pct": round((last / m3[1] - 1) * 100, 2) if m3 else None,
                      "T5_(3m>=+25%)": ((last / m3[1] - 1) >= 0.25) if m3 else None}
    # HYT 가격 조건 (`GLB-008` P3, 감사 F110) — 미수정 종가. 판정은 어드바이저가 한다.
    h = px.get("HYT", [])
    if h:
        hd, hl = h[-1]
        yr = [v for d, v in h if d >= (dt.date.fromisoformat(hd) - dt.timedelta(days=365)).isoformat()]
        prev = h[-2][1] if len(h) > 1 else None
        out["HYT_GLB008"] = {"last": (hd, round(hl, 2)), "source": f"{px_src.get('HYT', '?')} close (B)",
                             "52w_low": round(min(yr), 2), "52w_high": round(max(yr), 2),
                             "to_9.00_pct": round((9.00 / hl - 1) * 100, 2),
                             "stop_(close<=7.50)": hl <= 7.50,
                             "stop_2days_(prev_and_last<=7.50)": (hl <= 7.50 and prev is not None and prev <= 7.50),
                             "target_(close>=9.00)": hl >= 9.00}
    e = px.get("QQQE", []); qq = px.get("QQQ", [])
    if qq:
        # 채점규칙 §2 r_idx 대체 출처 (Twelve Data가 없는 회차용). 미수정 종가면 채점에 쓰지 않는다 (감사 F074).
        out["QQQ_price"] = {"last": qq[-1], "field": YAHOO_FIELDS.get("QQQ") if px_src.get("QQQ") == "Yahoo" else "close",
                            "source": f"{px_src.get('QQQ', '?')} (B)",
                            "usable_for_r_idx": YAHOO_FIELDS.get("QQQ") == "adjclose" and px_src.get("QQQ") == "Yahoo"}
    if qq and e:
        ed = {d: v for d, v in e}
        pairs = [(d, ed[d] / v) for d, v in qq if d in ed]
        if pairs:
            r_now = pairs[-1]
            r_3m = at_or_before(pairs, (dt.date.fromisoformat(r_now[0]) - dt.timedelta(days=91)).isoformat())
            out["C2_breadth_QQQE_over_QQQ"] = {"now": (r_now[0], round(r_now[1], 4)),
                                               "3m_ago": (r_3m[0], round(r_3m[1], 4)) if r_3m else None,
                                               "chg_3m_pct": round((r_now[1] / r_3m[1] - 1) * 100, 2) if r_3m else None}
    u = dxy if dxy else px.get("UUP", [])
    if u:
        m3 = at_or_before(u, (dt.date.fromisoformat(u[-1][0]) - dt.timedelta(days=91)).isoformat())
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
            lastk = None; lastk_d = None
            for d, v in q:
                if d in kd: lastk = kd[d]; lastk_d = d
                if lastk: kq.append((d, v * lastk))
            if kq:
                athk = max(kq, key=lambda x: x[1]); lk = kq[-1]
                out["KRW_drawdown_(부칙4)"] = {"last": (lk[0], round(lk[1])), "ath": (athk[0], round(athk[1])),
                                              "ath_window_start": kq[0][0],
                                              "fx_used_for_last": (lastk_d, lastk),   # 지수 날짜와 환율 날짜가 다르면 여기서 드러난다
                                              "drawdown_krw_pct": round((lk[1] / athk[1] - 1) * 100, 2),
                                              "alert_(<=-25%)": (lk[1] / athk[1] - 1) <= -0.25}
    return out

LONG_START = "1985-01-01"          # 사상최고 탐색·원화 환산용 장기 창 (감사 F059)
LONG_SERIES = ("NASDAQ100", "NASDAQCOM", "DEXKOUS")
SUPPLEMENT = (("NASDAQ100", "^NDX"), ("VIXCLS", "^VIX"))   # FRED T−1 지연을 Yahoo 최신 종가로 보강 (감사 F060)

def truncate(rows, basis: str | None):
    return [r for r in rows if r[0] <= basis] if basis else rows

def main(out_dir: str, basis: str | None = None):
    """basis(YYYY-MM-DD)를 주면 모든 시리즈를 그 날짜 이하로 잘라 계산한다 — 월간 판정 기준일용 (감사 F062).
    주지 않으면 최신치 그대로 (주간 트리거 점검용)."""
    today = dt.date.today()
    ref = dt.date.fromisoformat(basis) if basis else today
    start = (today - dt.timedelta(days=400)).isoformat()
    series, errors = {}, []
    for code, (fid, _, _) in SERIES.items():
        try:
            series[code] = truncate(fetch_csv(fid, LONG_START if code in LONG_SERIES else start), basis)
        except Exception as e:
            errors.append(f"{code}: {e}")
    # FRED는 전 영업일까지만 준다. 지수·VIX의 마지막 하루(금요일 종가, 기준일 종가)를 Yahoo로 보강하고 날짜별 출처를 남긴다.
    supplement = {}
    for code, ysym in SUPPLEMENT:
        base_rows = series.get(code, [])
        try:
            yrows = truncate(fetch_yahoo(ysym, "3mo"), basis)
            fred_through = base_rows[-1][0] if base_rows else None
            added = [(d, round(v, 2)) for d, v in yrows if (fred_through is None or d > fred_through)]
            if added:
                series[code] = base_rows + added
            supplement[code] = {"fred_through": fred_through, "yahoo_symbol": ysym,
                                "yahoo_added": added, "note": "추가된 날짜는 Yahoo 종가(B). 그 이전은 FRED."}
        except Exception as e:
            supplement[code] = {"fred_through": base_rows[-1][0] if base_rows else None, "yahoo_symbol": ysym,
                                "yahoo_added": [], "error": str(e)}
            errors.append(f"supplement {ysym}: {e}")
    px, px_src = {}, {}
    for sym, code, rng in (("QQQ", "QQQ", "max"), ("QQQE", "QQQE", "1y"), ("HYT", "HYT", "2y")):
        try:
            px[code] = truncate(fetch_yahoo(sym, rng, prefer_adj=(code != "HYT")), basis); px_src[code] = "Yahoo"
        except Exception as e:
            try:
                px[code] = truncate(fetch_stooq(sym.lower() + ".us"), basis); px_src[code] = "stooq"
            except Exception as e2:
                errors.append(f"{code}: yahoo {e} / stooq {e2}")
    mkt = market(px, series.get("DEXKOUS", []), ref, ndx=series.get("NASDAQ100"), dxy=series.get("DTWEXBGS"), px_src=px_src)
    if supplement.get("NASDAQ100", {}).get("yahoo_added") and mkt.get("index_source"):
        mkt["index_source"] += f" + Yahoo ^NDX({supplement['NASDAQ100']['yahoo_added'][-1][0]})"
    fs, fs_err = try_factset()
    if fs_err: errors.append(fs_err)
    out = {"fetched_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
           "basis": basis,
           "series_meta": {k: {"fred_id": v[0], "desc": v[1], "skill_code": v[2]} for k, v in SERIES.items()},
           "windows": {"ath_search_start": LONG_START, "long_series": list(LONG_SERIES), "other_series_days": 400},
           "supplement": supplement,
           "yahoo_price_fields": dict(YAHOO_FIELDS),
           "last_values": {k: (v[-1] if v else None) for k, v in series.items()},
           "derived": derive(series, ref),
           "market": mkt,
           "factset_surprise_pct": fs,
           "errors": errors,
           "raw_recent": {k: v[-70:] for k, v in series.items()}}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "fred-latest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "fred-latest.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(out))
    # 월별 스냅샷 (기준일 첫 영업일용 보존). basis 실행은 파일명에 기준일을 붙여 주간 스냅샷을 덮어쓰지 않는다.
    snap = os.path.join(out_dir, f"fred-{today.strftime('%Y-%m-%d')}{'-basis-' + basis if basis else ''}.json")
    with open(snap, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(to_markdown(out))
    return 0 if not errors else 0  # 부분 실패도 커밋한다 (결측 표시가 목적)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default="claude/advisor/월간판정/입력")
    ap.add_argument("--basis", default=None, help="기준일 YYYY-MM-DD — 이 날짜 이하로 잘라 계산 (월간 판정용)")
    a = ap.parse_args()
    sys.exit(main(a.out_dir, a.basis))
