#!/usr/bin/env python3
"""검색 의존 지표를 1차 출처 페이지에서 직접 읽는다 (GitHub Actions에서 실행).
ISM 제조/서비스 PMI · 한국은행 기준금리 · FactSet EPS 서프라이즈 비율.
실패하면 null — 추정하지 않는다. 각 값에 URL·수집시각·정규식 일치 문자열을 남겨 감사 가능하게 한다.
CME FedWatch는 JS 렌더링이라 여기서 못 읽는다 → 검색(2출처 일치 규칙) 유지.
"""
import json, os, re, sys, datetime as dt, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (advisor-macro-fetch)"}
MONTHS = ["january","february","march","april","may","june","july","august","september","october","november","december"]

DEBUG = {}
def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "ignore")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    # 디버그: 상태·길이·키워드 주변 120자 (다음 실행에서 정규식을 고치기 위해)
    kw = next((k for k in ("PMI", "기준금리", "EPS surprise") if k in text), None)
    i = text.find(kw) if kw else -1
    DEBUG[url] = {"status": r.status, "len": len(html), "keyword": kw, "around": text[max(0, i-60):i+160] if i >= 0 else text[:200]}
    return html

def ism(kind: str, today: dt.date):
    """kind: 'pmi'(제조) | 'services'. 이번 달 페이지 → 없으면 지난달 페이지 (직전 최신값 규정)."""
    label = "Manufacturing PMI" if kind == "pmi" else "Services PMI"
    for back in (0, 1, 2):
        m = (today.month - 1 - back) % 12; y = today.year if today.month - 1 - back >= 0 else today.year - 1
        url = f"https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/{kind}/{MONTHS[m]}/"
        try:
            html = get(url)
        except Exception:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&reg;", "®").replace("&#174;", "®")
        pat = label.replace(" ", r"\s*") + r"\s*®?\s*(?:at|registered|was|came in at|of)\s*(\d{2}\.\d)\s*(?:percent|%)?"
        hit = re.search(pat, text, re.I) or re.search(r"PMI\s*®?\s*(?:at|registered)\s*(\d{2}\.\d)", text, re.I)
        if hit:
            return {"value": float(hit.group(1)), "report_month": f"{y}-{m+1:02d}", "url": url,
                    "matched": hit.group(0)[:80], "fetched_at": dt.datetime.utcnow().isoformat(timespec="minutes")}
    return {"value": None, "error": "ISM 페이지에서 패턴 미발견", "tried_months": 3}

def bok_base_rate():
    url = "https://www.bok.or.kr/portal/singl/baseRate/list.do?dataSeCd=01&menuNo=200643"
    try:
        html = get(url)
    except Exception as e:
        return {"value": None, "error": f"{e}", "url": url}
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    hit = re.search(r"(20\d\d)\s*[.\-년]\s*(\d{1,2})\s*[.\-월]\s*(\d{1,2})[^\d]{0,80}?(\d\.\d{2})\s*%?", text) or \
          re.search(r"(20\d\d)[.\-](\d{1,2})[.\-](\d{1,2})\D{0,80}?(\d\.\d{2})", text)
    if not hit:
        return {"value": None, "error": "한은 페이지에서 패턴 미발견", "url": url}
    return {"value": float(hit.group(4)), "decided_on": f"{hit.group(1)}-{int(hit.group(2)):02d}-{int(hit.group(3)):02d}",
            "url": url, "matched": hit.group(0)[:80], "fetched_at": dt.datetime.utcnow().isoformat(timespec="minutes")}

def factset_surprise():
    url = "https://insight.factset.com/topic/earnings"
    try:
        html = get(url)
    except Exception as e:
        return {"value": None, "error": f"{e}", "url": url}
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&amp;", "&")
    hit = re.search(r"(\d{2})%\s+of\s+S&P 500 companies have reported (?:a )?positive EPS surprise", text) or \
          re.search(r"(\d{2})%[^.]{0,60}positive EPS surprise", text)
    if not hit:
        return {"value": None, "error": "FactSet 요약 문장 미발견", "url": url}
    return {"value": float(hit.group(1)), "url": url, "matched": hit.group(0)[:100],
            "fetched_at": dt.datetime.utcnow().isoformat(timespec="minutes")}

def main(out_dir):
    today = dt.date.today()
    out = {"fetched_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
           "ISM_manufacturing": ism("pmi", today), "ISM_services": ism("services", today),
           "BOK_base_rate": bok_base_rate(), "FactSet_EPS_surprise_pct": factset_surprise(),
           "not_automated": {"FedWatch": "JS 렌더링 — 검색 2출처 일치 규칙", "NDX_forward_PE": "유료 — S&P 500 대체"},
           "debug": DEBUG}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "web-latest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    lines = [f"# 1차 출처 자동 수집 — {out['fetched_at']} (UTC)\n", "| 지표 | 값 | 출처 | 일치 문자열 |", "|---|---|---|---|"]
    for k in ("ISM_manufacturing", "ISM_services", "BOK_base_rate", "FactSet_EPS_surprise_pct"):
        v = out[k]; lines.append(f"| {k} | {v.get('value')} | {v.get('url','')} | {v.get('matched', v.get('error',''))} |")
    with open(os.path.join(out_dir, "web-latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "claude/advisor/월간판정/입력")
