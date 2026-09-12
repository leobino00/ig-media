#!/usr/bin/env python3
"""계산 정의 단위 시험 — 네트워크 없이 돈다. 경계값(=1, =0, −15%, +30%)을 못 박는다.

실행: python -m unittest discover -s scripts/sector_us -p "self_test.py"
      또는 python scripts/sector_us/self_test.py
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc


class Weekly(unittest.TestCase):
    def test_주의_마지막_거래일을_고른다(self):
        daily = [("2026-09-07", 1), ("2026-09-08", 2), ("2026-09-11", 3),   # 월~금
                 ("2026-09-14", 4)]                                          # 다음 주 월
        self.assertEqual(calc.to_weekly(daily), [("2026-09-11", 3), ("2026-09-14", 4)])

    def test_주말_거래일이_없어도_주가_밀리지_않는다(self):
        daily = [("2026-09-10", 1), ("2026-09-17", 2)]
        self.assertEqual([d for d, _ in calc.to_weekly(daily)], ["2026-09-10", "2026-09-17"])


class RatioAndRS(unittest.TestCase):
    def test_동행하면_rs_ratio_1(self):
        sec = [(f"2026-01-{i:02d}", 100.0) for i in range(1, 29)]
        ben = [(d, 50.0) for d, _ in sec]
        ratios = calc.ratio_series(sec, ben)
        self.assertEqual(len(ratios), 28)
        rs = calc.rs_series(ratios)
        self.assertEqual(len(rs), 28 - calc.RS_WINDOW + 1)
        self.assertAlmostEqual(rs[-1][1], 1.0, places=12)

    def test_공통_주만_쓴다(self):
        sec = [("2026-01-02", 10.0), ("2026-01-09", 11.0)]
        ben = [("2026-01-09", 5.0)]
        self.assertEqual(calc.ratio_series(sec, ben), [("2026-01-09", 2.2)])


class Quadrant(unittest.TestCase):
    def test_경계값은_약한_쪽(self):
        self.assertEqual(calc.quadrant(1.0, 0.0), "lagging")     # rs=1, mom=0 → 후행
        self.assertEqual(calc.quadrant(1.0001, 0.0), "weakening")
        self.assertEqual(calc.quadrant(1.0, 0.0001), "improving")
        self.assertEqual(calc.quadrant(1.0001, 0.0001), "leading")
        self.assertIsNone(calc.quadrant(1.0, None))

    def test_연속_주수(self):
        quads = [("w1", "lagging", 0), ("w2", "leading", 1), ("w3", "leading", 1)]
        self.assertEqual(calc.weeks_in_quadrant(quads), 2)
        self.assertEqual(calc.weeks_in_quadrant([("w1", None, None)]), 0)

    def test_모멘텀은_4주_전_대비(self):
        vals = [1.0, 1.0, 1.0, 1.0, 1.1]
        self.assertAlmostEqual(calc.momentum(vals, 4), 10.0, places=9)
        self.assertIsNone(calc.momentum(vals, 3))


class Flags(unittest.TestCase):
    def _ratios(self, vals):
        return [(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", v) for i, v in enumerate(vals)]

    def test_dd15는_정확히_minus15에서_발동(self):
        vals = [1.0] * 25 + [0.85]                       # 26주 고점 1.0 → 현재 0.85 = −15.00%
        m = calc.sector_metrics(self._ratios(vals), calc.rs_series(self._ratios(vals)))
        self.assertAlmostEqual(m["rs_dd_from_26w_high"], -15.0, places=9)
        self.assertTrue(m["rs_dd_15"])

    def test_dd15는_minus14_99에서_발동하지_않는다(self):
        vals = [1.0] * 25 + [0.8501]
        m = calc.sector_metrics(self._ratios(vals), calc.rs_series(self._ratios(vals)))
        self.assertFalse(m["rs_dd_15"])

    def test_up30은_정확히_plus30에서_발동(self):
        vals = [1.0] * 25 + [1.3]
        m = calc.sector_metrics(self._ratios(vals), calc.rs_series(self._ratios(vals)))
        self.assertAlmostEqual(m["rs_up_from_26w_low"], 30.0, places=9)
        self.assertTrue(m["rs_up_30"])

    def test_26주_미달이면_None(self):
        vals = [1.0] * 25
        self.assertIsNone(calc.sector_metrics(self._ratios(vals), calc.rs_series(self._ratios(vals))))


class Regime(unittest.TestCase):
    def test_분산도는_표본표준편차(self):
        self.assertEqual(calc.dispersion([1.0, 1.0]), 0.0)
        self.assertAlmostEqual(calc.dispersion([0.9, 1.1]), 0.1414, places=4)
        self.assertIsNone(calc.dispersion([1.0]))

    def test_백분위(self):
        self.assertEqual(calc.percentile(0.05, [0.01, 0.02, 0.05, 0.09]), 75)
        self.assertIsNone(calc.percentile(None, [0.01]))
        self.assertIsNone(calc.percentile(0.05, []))

    def test_분산도_시계열은_모집단이_다_있는_주만(self):
        rs = {"A": [("w1", 1.0), ("w2", 1.1)], "B": [("w2", 0.9)]}
        self.assertEqual([d for d, _ in calc.dispersion_history(rs)], ["w2"])


class Breadth(unittest.TestCase):
    def _rows(self, vals):
        return [(f"d{i:04d}", v) for i, v in enumerate(vals)]

    def test_200일선_위_비율(self):
        up = self._rows([1.0] * 200 + [2.0])        # 마지막 종가 > 200일 평균
        flat = self._rows([1.0] * 201)              # 같으면 위가 아니다 (초과만 센다)
        short = self._rows([1.0] * 100)             # 구간 미달 → 판정에서 빠진다
        pct, n = calc.pct_above_sma200({"U": up, "F": flat, "S": short})
        self.assertEqual((pct, n), (50.0, 2))

    def test_4주_전_시점은_20거래일을_자른다(self):
        rows = self._rows([1.0] * 200 + [2.0] + [1.0] * 20)
        pct_now, _ = calc.pct_above_sma200({"X": rows})
        pct_4w, _ = calc.pct_above_sma200({"X": rows}, offset=20)
        self.assertEqual((pct_now, pct_4w), (0.0, 100.0))

    def test_신고가_신저가와_0분모(self):
        hi = self._rows([100 + i for i in range(253)])                  # 계속 오름 → 신고가만
        lo = self._rows([500 - i for i in range(253)])                  # 계속 내림 → 신저가만
        mid = self._rows([200 - i for i in range(120)] + [80 + i * 0.5 for i in range(133)])  # 둘 다 아님
        nh, nl, n = calc.new_highs_lows({"H": hi, "L": lo, "M": mid})
        self.assertEqual((nh, nl, n), (1, 1, 3))
        self.assertEqual(calc.nh_nl_ratio(9, 3), 3.0)
        self.assertIsNone(calc.nh_nl_ratio(9, 0))       # 신저가 0 → 비율은 결측

    def test_값이_완전히_평평하면_신고가와_신저가_양쪽에_센다(self):
        """동값 타이 처리. 실제 가격에서는 거의 없지만 정의를 못 박아 둔다."""
        flat = self._rows([1.0] * 253)
        self.assertEqual(calc.new_highs_lows({"F": flat}), (1, 1, 1))


class HoldingsCSV(unittest.TestCase):
    """구성종목 CSV 파서. 1회차 러너에서 Invesco 파일의 티커 열을 못 찾아 폴백했다 — 그 경로를 고정한다."""

    def test_안내문이_앞에_붙어도_읽는다(self):
        from yahoo import _parse_holdings_csv
        text = ("Invesco QQQ Trust\nAs of 09/11/2026\n\n"
                "Fund Ticker,Holding Ticker,Name,Weight\nQQQ,NVDA,NVIDIA,9.1\nQQQ,BRK.B,Berkshire,1.0\n")
        rows, col = _parse_holdings_csv(text)
        self.assertEqual(col, "Holding Ticker")
        self.assertEqual([r[col] for r in rows], ["NVDA", "BRK.B"])

    def test_열_이름이_Ticker_하나여도_읽는다(self):
        from yahoo import _parse_holdings_csv
        self.assertEqual(_parse_holdings_csv("Ticker,Name\nMSFT,Microsoft\n")[1], "Ticker")

    def test_CSV가_아니면_열을_못_찾고_None(self):
        from yahoo import _parse_holdings_csv
        self.assertIsNone(_parse_holdings_csv("<html><body>Access Denied</body></html>")[1])

    def test_티커_정규화(self):
        from yahoo import _norm
        self.assertEqual(_norm("brk.b"), "BRK-B")          # Yahoo 표기
        self.assertIsNone(_norm("USD"))                    # 현금 행은 버린다
        self.assertIsNone(_norm(""))


class SectorMapping(unittest.TestCase):
    """R4 섹터 이름 → ETF 대응. 두 출처의 분류 이름이 다르다."""

    def test_두_출처의_이름이_모두_대응된다(self):
        from fetch import SECTOR_TO_TICKER
        yahoo_names = ["Technology", "Healthcare", "Financial Services", "Consumer Cyclical",
                       "Communication Services", "Industrials", "Consumer Defensive", "Energy",
                       "Utilities", "Real Estate", "Basic Materials"]
        nasdaq_names = ["Technology", "Health Care", "Finance", "Consumer Discretionary",
                        "Telecommunications", "Industrials", "Consumer Staples", "Energy",
                        "Public Utilities", "Real Estate", "Basic Industries"]
        for n in yahoo_names + nasdaq_names:
            self.assertIn(SECTOR_TO_TICKER.get(n), ("XLK", "XLV", "XLF", "XLY", "XLC", "XLI",
                                                    "XLP", "XLE", "XLU", "XLRE", "XLB"), n)

    def test_대응_없는_값은_None으로_명시한다(self):
        from fetch import SECTOR_TO_TICKER
        self.assertIsNone(SECTOR_TO_TICKER["Miscellaneous"])       # 추정하지 않는다
        self.assertIsNone(SECTOR_TO_TICKER.get("없는 섹터"))


class Lint(unittest.TestCase):
    def test_판단_어휘를_잡고_한계절은_건너뛴다(self):
        from lint_no_judgment import scan
        self.assertTrue(scan("## 관측 — 사실만\n반도체 비중확대\n"))
        self.assertFalse(scan("## 한계 (고정)\n이 표는 관측이다. 판정·추천이 아니다.\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
