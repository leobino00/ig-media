# -*- coding: utf-8 -*-
"""「관측」 절에 판단 어휘가 섞이지 않았는지 검사한다.

이 프로그램의 산출물은 사실이어야 한다. 관측 절에 「매수」·「비중」·「전망」이 한 번
들어가면 그 파일은 관측이 아니라 판정이 되고, 판정은 어드바이저 프로토콜(P1~P5)을
거치지 않고는 나올 수 없다. 이 검사는 그 경계를 기계적으로 지킨다.

검사 대상은 `## 관측` 부터 다음 `## ` 직전까지다.
「경계」·「한계」·「결측」 절은 검사하지 않는다 — 거기서는 「판정하지 않는다」처럼
금지 어휘를 부정형으로 쓰는 것이 정상이다.

    python3 scripts/qqq_weekly/lint_no_judgment.py 출력/qqq-weekly-latest.md
종료코드 0 = 통과, 1 = 위반, 2 = 파일 문제.
"""

import sys

SECTION = "## 관측"

# 판정·행동·예측 어휘. 사실 기술에는 필요 없는 말만 넣는다.
FORBIDDEN = [
    "매수", "매도", "사야", "팔아야", "담아", "실을", "편입", "청산", "진입",
    "손절", "익절", "목표가", "적정가", "비중", "배분",
    "추천", "권장", "유망", "저평가", "고평가", "과열", "과매도", "과매수",
    "전망", "예상", "예측", "기대된다", "보인다", "판단", "판정",
    "기회", "위험하다", "안전하다", "유리", "불리", "좋다", "나쁘다",
    "강세장", "약세장", "바닥", "천장", "반등할", "조정받",
]


def extract(text):
    lines = text.splitlines()
    out = []
    inside = False
    for i, line in enumerate(lines, start=1):
        if line.strip() == SECTION:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            out.append((i, line))
    return inside, out


def lint(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        sys.stderr.write("읽을 수 없다: %s\n" % e)
        return 2

    found_section, body = extract(text)
    if not found_section:
        sys.stderr.write("`%s` 절이 없다: %s\n" % (SECTION, path))
        return 2

    hits = []
    for lineno, line in body:
        for word in FORBIDDEN:
            if word in line:
                hits.append((lineno, word, line.strip()))

    if hits:
        sys.stderr.write("판단 어휘 %d건 — 관측 절은 사실만 적는다\n" % len(hits))
        for lineno, word, line in hits:
            sys.stderr.write("  %d행 「%s」: %s\n" % (lineno, word, line[:90]))
        return 1

    sys.stdout.write("통과: 관측 절 %d행, 금지 어휘 %d개 검사\n" % (len(body), len(FORBIDDEN)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("사용법: lint_no_judgment.py <md 경로>\n")
        raise SystemExit(2)
    raise SystemExit(lint(sys.argv[1]))
