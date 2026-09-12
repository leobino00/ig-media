#!/usr/bin/env python3
"""판단 어휘 검사 (제안서 §3 · §10 완료 기준).

「관측」 절에 판단·추천 어휘가 섞이면 P2가 공격할 대상이 사라진다. 그래서 기계로 막는다.
「한계」 절은 제외한다 — 거기서는 "판정·추천이 아니다"라고 적는 것이 규정이다.

사용법: python scripts/sector_us/lint_no_judgment.py <파일 …>   (발견되면 종료코드 1)
"""
import re, sys

BANNED = ["매수", "매도", "비중확대", "비중축소", "유망", "회피", "주목", "추천",
          "목표가", "강세 전환 기대", "기대된다", "유리하다", "불리하다", "매력적",
          "사야", "팔아야", "담아야", "비중을 늘", "비중을 줄"]
SKIP_SECTION = ("한계", "caveat")


def scan(md: str):
    """금지 어휘가 나온 (절 제목, 단어, 주변 문자열) 목록. 「한계」 절은 건너뛴다."""
    hits = []
    parts = re.split(r"(?m)^##\s+", md)
    for i, part in enumerate(parts):
        title = part.splitlines()[0].strip() if i else "(머리)"
        if any(title.startswith(s) for s in SKIP_SECTION):
            continue
        for w in BANNED:
            for m in re.finditer(re.escape(w), part):
                hits.append({"section": title, "word": w,
                             "around": part[max(0, m.start() - 25):m.end() + 25].replace("\n", " ")})
    return hits


def main(paths):
    bad = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            hits = scan(f.read())
        if hits:
            bad = 1
            for h in hits:
                print(f"{p}: [{h['section']}] 「{h['word']}」 … {h['around']}")
        else:
            print(f"{p}: 판단 어휘 없음")
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["claude/advisor/월간판정/입력/sector-us-latest.md"]))
