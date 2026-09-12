#!/usr/bin/env python3
"""데이터 수집 — Yahoo 차트 API + 나스닥100 구성종목 (제안서 R3 · R8).

표준 라이브러리만 쓴다. 실패는 예외로 올리고 호출 쪽이 결측으로 기록한다 — 추정하지 않는다.
stooq는 쓰지 않는다 (봇 차단 확인됨, 제안서 R8).

캐시: --cache-dir를 주면 원본 응답을 그대로 저장하고 다음 실행에서 재사용한다.
네트워크가 막힌 세션에서 같은 입력으로 재현하거나(§9 데이터 안정성) 파서를 시험할 때 쓴다.
"""
import csv, io, json, os, time, datetime as dt, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (advisor-sector-us)"}
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"
QUOTE_SUMMARY = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
INVESCO_CSV = ("https://www.invesco.com/us/financial-products/etfs/holdings/main/holdings/0"
               "?audienceType=Investor&action=download&ticker=QQQ")
NASDAQ_API = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
WIKI_NDX = "https://en.wikipedia.org/wiki/Nasdaq-100"


def _get(url, timeout=30, retries=3, sleep=1.5):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                      # 네트워크·HTTP 모두
            last = e
            if i + 1 < retries:
                time.sleep(sleep * (i + 1))
    raise RuntimeError(f"{url.split('?')[0]}: {last}")


def _cache_path(cache_dir, key):
    return os.path.join(cache_dir, key.replace("/", "_") + ".json") if cache_dir else None


def chart(symbol, rng="5y", interval="1d", cache_dir=None, network=True, retries=3):
    """일봉 수정종가. 반환: {"symbol","rows":[(날짜, 종가)],"price_field","source_url"}.

    배당 차이가 큰 섹터(XLU·XLP vs QQQ)의 비율이 배당만큼 흘러내리지 않게 수정종가를 쓴다.
    수정종가가 없으면 종가로 내려가고 어느 쪽을 썼는지 기록한다.
    """
    url = f"{CHART}{symbol}?range={rng}&interval={interval}"
    cp = _cache_path(cache_dir, f"chart_{symbol}_{rng}_{interval}")
    raw = None
    if cp and os.path.exists(cp):
        with open(cp, "rb") as f:
            raw = f.read()
    elif network:
        raw = _get(url, retries=retries)
        if cp:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cp, "wb") as f:
                f.write(raw)
    else:
        raise RuntimeError(f"{symbol}: 캐시 없음 + 네트워크 꺼짐")
    data = json.loads(raw)
    res = (data.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(f"{symbol}: chart.result 없음 ({str(data)[:120]})")
    res = res[0]
    ts = res.get("timestamp") or []
    ind = res.get("indicators") or {}
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
    close = (ind.get("quote") or [{}])[0].get("close")
    series, field = (adj, "adjclose") if adj else (close, "close")
    if not series:
        raise RuntimeError(f"{symbol}: 종가 배열 없음")
    rows = [(dt.datetime.utcfromtimestamp(t).date().isoformat(), float(c))
            for t, c in zip(ts, series) if c is not None]
    if not rows:
        raise RuntimeError(f"{symbol}: 0행")
    return {"symbol": symbol, "rows": rows, "price_field": field, "source_url": url}


def sector_of(symbol, cache_dir=None, network=True):
    """Yahoo quoteSummary assetProfile.sector (B등급). 실패하면 None — 추정하지 않는다."""
    url = f"{QUOTE_SUMMARY}{symbol}?modules=assetProfile"
    cp = _cache_path(cache_dir, f"profile_{symbol}")
    raw = None
    if cp and os.path.exists(cp):
        with open(cp, "rb") as f:
            raw = f.read()
    elif network:
        try:
            raw = _get(url, retries=2)
        except Exception:
            return None
        if cp:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cp, "wb") as f:
                f.write(raw)
    else:
        return None
    try:
        res = json.loads(raw)["quoteSummary"]["result"]
        return (res[0]["assetProfile"] or {}).get("sector") or None
    except Exception:
        return None


def _parse_holdings_csv(text):
    """보유종목 CSV를 읽는다. 받은 파일에 안내문·빈 줄이 앞에 붙어 있을 수 있어
    「Ticker」가 들어간 첫 줄을 머리글로 잡는다. 반환: (행 목록, 티커 열 이름)."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines[:40]) if "ticker" in ln.lower() and ln.count(",") >= 2), 0)
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))
    keys = [k for k in (rows[0].keys() if rows else []) if k]
    for want in ("holding ticker", "ticker", "holdingticker", "security ticker", "symbol"):
        col = next((k for k in keys if k.strip().lower() == want), None) \
            or next((k for k in keys if want in k.strip().lower()), None)
        if col:
            return rows, col
    return rows, None


def _norm(t):
    """Yahoo 표기로 맞춘다: BRK.B → BRK-B. 현금·선물 행은 버린다."""
    t = (t or "").strip().upper().replace(".", "-").replace("/", "-")
    if not t or len(t) > 6 or not t.replace("-", "").isalnum():
        return None
    if t in {"USD", "CASH", "NA", "N-A", "--"}:
        return None
    return t


def ndx_constituents(cache_dir=None, network=True, allow_wikipedia=True):
    """나스닥100 구성종목. 출처 순서 ① Invesco CSV(A−) → ② api.nasdaq.com(A−) → ③ Wikipedia(C).
    전부 실패하면 예외 → 호출 쪽이 폭 지표를 결측으로 남긴다 (제안서 R3)."""
    errors = []

    # ① Invesco QQQ 보유종목 CSV (일일 갱신)
    try:
        cp = _cache_path(cache_dir, "invesco_qqq")
        if cp and os.path.exists(cp):
            text = open(cp, encoding="utf-8").read()
        elif network:
            text = _get(INVESCO_CSV, retries=2).decode("utf-8", "ignore")
            if cp:
                os.makedirs(cache_dir, exist_ok=True)
                open(cp, "w", encoding="utf-8").write(text)
        else:
            raise RuntimeError("캐시 없음 + 네트워크 꺼짐")
        rows, col = _parse_holdings_csv(text)
        tick = sorted({_norm(r[col]) for r in rows if _norm(r.get(col))}) if col else []
        if len(tick) >= 90:
            asof = next((str(r.get(c)) for r in rows[:1] for c in r
                         if c and "date" in c.strip().lower()), None)
            return {"tickers": tick, "source": "invesco_qqq_holdings", "grade": "A-",
                    "as_of": asof, "url": INVESCO_CSV, "n": len(tick), "attempt_errors": errors}
        errors.append(f"invesco: 티커 {len(tick)}개 (열={col}) 받은 내용 앞머리={text[:120]!r}")
    except Exception as e:
        errors.append(f"invesco: {e}")

    # ② 나스닥 공식 API
    try:
        cp = _cache_path(cache_dir, "nasdaq_api_ndx")
        if cp and os.path.exists(cp):
            raw = open(cp, "rb").read()
        elif network:
            raw = _get(NASDAQ_API, retries=2)
            if cp:
                os.makedirs(cache_dir, exist_ok=True)
                open(cp, "wb").write(raw)
        else:
            raise RuntimeError("캐시 없음 + 네트워크 꺼짐")
        d = json.loads(raw)
        rows = ((d.get("data") or {}).get("data") or {}).get("rows") or []
        tick = sorted({_norm(r.get("symbol")) for r in rows if _norm(r.get("symbol"))})
        if len(tick) >= 90:
            return {"tickers": tick, "source": "nasdaq_api", "grade": "A-",
                    "as_of": None, "url": NASDAQ_API, "n": len(tick), "attempt_errors": errors}
        errors.append(f"nasdaq_api: 티커 {len(tick)}개")
    except Exception as e:
        errors.append(f"nasdaq_api: {e}")

    # ③ Wikipedia — 최후 수단. 등급 C (출처 등급표에서 C는 결측 취급이므로 플래그를 남긴다)
    if allow_wikipedia:
        try:
            cp = _cache_path(cache_dir, "wiki_ndx")
            if cp and os.path.exists(cp):
                html = open(cp, encoding="utf-8").read()
            elif network:
                html = _get(WIKI_NDX, retries=2).decode("utf-8", "ignore")
                if cp:
                    os.makedirs(cache_dir, exist_ok=True)
                    open(cp, "w", encoding="utf-8").write(html)
            else:
                raise RuntimeError("캐시 없음 + 네트워크 꺼짐")
            import re
            tick = sorted({_norm(m) for m in re.findall(
                r'<td><a rel="nofollow" class="external text" href="https://www\.nasdaq\.com/market-activity/stocks/[^"]*">([A-Z.\-]{1,6})</a>', html)}
                - {None})
            if len(tick) < 90:
                tick = sorted({_norm(m) for m in re.findall(r"<td>([A-Z]{1,5}(?:\.[A-Z])?)\n?</td>", html)} - {None})
            if len(tick) >= 90:
                return {"tickers": tick, "source": "wikipedia", "grade": "C",
                        "as_of": None, "url": WIKI_NDX, "n": len(tick), "attempt_errors": errors}
            errors.append(f"wikipedia: 티커 {len(tick)}개")
        except Exception as e:
            errors.append(f"wikipedia: {e}")

    raise RuntimeError(" / ".join(errors))


def charts(symbols, rng="2y", cache_dir=None, network=True, pause=0.25,
           retries=2, deadline_s=600):
    """여러 종목 일봉. 실패한 종목은 errors에 남기고 계속한다 (부분 결측 허용).

    구성종목 100종목을 도는 경로라 시간 예산(deadline_s)을 둔다. 예산을 넘기면 남은 종목을
    결측으로 남기고 멈춘다 — 커버리지가 80% 미만이면 호출 쪽이 폭 지표 전체를 결측 처리한다.
    재시도는 2회로 줄인다: 여기서는 한 종목을 끝까지 받아내는 것보다 전체가 제때 끝나는 것이 중요하다.
    """
    ok, errors = {}, {}
    t0 = time.monotonic()
    for i, s in enumerate(symbols):
        if deadline_s and time.monotonic() - t0 > deadline_s:
            for rest in symbols[i:]:
                errors[rest] = f"시간 예산 {deadline_s}초 초과 — 수집하지 않았다"
            break
        try:
            ok[s] = chart(s, rng=rng, cache_dir=cache_dir, network=network, retries=retries)["rows"]
        except Exception as e:
            errors[s] = str(e)[:120]
        if network and pause:
            time.sleep(pause)
    return ok, errors
