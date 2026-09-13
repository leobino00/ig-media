# -*- coding: utf-8 -*-
"""QQQ 주간 종가 CSV 로더.

입력은 `date,close` 두 열이다. 추정하지 않는다 — 이상은 고치지 않고 기록한다.
결측 주를 보간하지 않는 이유: 보간한 값은 관측이 아니고, 뒤에서 낙폭·변동성을
계산할 때 어느 값이 관측이고 어느 값이 채워넣은 것인지 구별할 수 없게 된다.
"""

import csv
import datetime as dt

# 주 간격이 이 일수를 넘으면 「결측 주 의심」으로 기록한다 (채우지는 않는다).
MAX_GAP_DAYS = 10


class LoadError(Exception):
    pass


def load(path):
    """(dates, closes, report) 를 돌려준다.

    report = {
        "row_count", "first_date", "last_date",
        "weekday_counts", "gaps"(결측 의심 구간), "anomalies"(값 이상)
    }
    치명적 이상(파일 없음·열 없음·정렬 불가·중복 날짜·0 이하 종가)은 LoadError 로 올린다.
    시계열을 조용히 고쳐서 계산을 계속하는 것보다 멈추는 편이 낫다.
    """
    rows = []
    try:
        fh = open(path, newline="", encoding="utf-8-sig")
    except OSError as e:
        raise LoadError("파일을 열 수 없다: %s" % e)
    with fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise LoadError("빈 파일이다: %s" % path)
        cols = [c.strip().lower() for c in reader.fieldnames]
        if "date" not in cols or "close" not in cols:
            raise LoadError("`date`·`close` 열이 필요하다. 받은 열: %r" % (reader.fieldnames,))
        dkey = reader.fieldnames[cols.index("date")]
        ckey = reader.fieldnames[cols.index("close")]
        for lineno, row in enumerate(reader, start=2):
            raw_d = (row.get(dkey) or "").strip()
            raw_c = (row.get(ckey) or "").strip()
            if not raw_d and not raw_c:
                continue
            try:
                d = dt.date.fromisoformat(raw_d)
            except ValueError:
                raise LoadError("%d행: 날짜를 읽을 수 없다: %r" % (lineno, raw_d))
            try:
                c = float(raw_c)
            except ValueError:
                raise LoadError("%d행: 종가를 읽을 수 없다: %r" % (lineno, raw_c))
            if c <= 0:
                raise LoadError("%d행: 종가가 0 이하다: %r" % (lineno, raw_c))
            rows.append((d, c))

    if len(rows) < 2:
        raise LoadError("관측이 2주 미만이다 (%d행)" % len(rows))

    dates = [r[0] for r in rows]
    if len(set(dates)) != len(dates):
        dup = sorted({d for d in dates if dates.count(d) > 1})
        raise LoadError("날짜가 중복된다: %s" % ", ".join(x.isoformat() for x in dup[:5]))
    if any(dates[i] >= dates[i + 1] for i in range(len(dates) - 1)):
        raise LoadError("날짜가 오름차순이 아니다")

    closes = [r[1] for r in rows]

    weekday_counts = {}
    for d in dates:
        key = d.strftime("%a")
        weekday_counts[key] = weekday_counts.get(key, 0) + 1

    gaps = []
    for i in range(len(dates) - 1):
        delta = (dates[i + 1] - dates[i]).days
        if delta > MAX_GAP_DAYS:
            gaps.append({
                "from": dates[i].isoformat(),
                "to": dates[i + 1].isoformat(),
                "days": delta,
            })

    report = {
        "row_count": len(rows),
        "first_date": dates[0].isoformat(),
        "last_date": dates[-1].isoformat(),
        "weekday_counts": dict(sorted(weekday_counts.items(), key=lambda kv: -kv[1])),
        "gaps": gaps,
        "anomalies": [],
    }
    if gaps:
        report["anomalies"].append(
            "결측 주 의심 %d건 (간격 %d일 초과). 보간하지 않았다" % (len(gaps), MAX_GAP_DAYS)
        )
    return dates, closes, report
