import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from innumground import check, extract, format_inr, indian_group  # noqa: E402
from innumground.bench import load, score  # noqa: E402
from innumground.server import TOOLS, handle  # noqa: E402


def values(text):
    return [f["value"] for f in extract(text)]


def statuses(source, summary):
    return [f["status"] for f in check(source, summary)["facts"]]


class Extract(unittest.TestCase):
    def test_crore_and_lakh(self):
        self.assertEqual(values("₹2.5 crore and Rs 3 lakh"), [25_000_000, 300_000])

    def test_spellings(self):
        self.assertEqual(values("Rs. 5 lacs, ₹7 Cr., 2 crores, 4 lakhs"), [500_000, 70_000_000, 20_000_000, 400_000])

    def test_lakh_crore_and_thousand_crore(self):
        self.assertEqual(values("₹11.11 lakh crore; ₹45 thousand crore"), [11.11e12, 45e10])

    def test_composite(self):
        self.assertEqual(values("Rs 1 crore 25 lakh"), [12_500_000])

    def test_indian_grouping(self):
        f = extract("₹2,50,00,000")[0]
        self.assertEqual((f["value"], f["grouping"]), (25_000_000, "indian"))

    def test_western_grouping(self):
        f = extract("25,000,000 users")[0]
        self.assertEqual((f["value"], f["grouping"]), (25_000_000, "western"))

    def test_bad_grouping_flagged(self):
        f = extract("92,2436 rupees")[0]
        self.assertIn("W_BAD_GROUPING", f["issues"])

    def test_devanagari_digits(self):
        self.assertEqual(values("₹४५ crore"), [450_000_000])

    def test_million_billion(self):
        self.assertEqual(values("$3.2 bn and 18 million"), [3.2e9, 18e6])

    def test_percent_and_year(self):
        kinds = [f["kind"] for f in extract("In 2024 sales grew 12 per cent")]
        self.assertEqual(kinds, ["year", "percent"])

    def test_fiscal_year_parts_are_not_numbers(self):
        self.assertEqual([f["text"] for f in extract("FY2025-26 revenue ₹5 crore")], ["₹5 crore"])

    def test_bare_L_without_currency_is_not_lakh(self):
        self.assertEqual(values("5 L of water"), [5])

    def test_approx_marker(self):
        self.assertTrue(extract("about ₹45 crore")[0]["approx"])


class Check(unittest.TestCase):
    def test_crore_read_as_million(self):
        r = check("The film collected ₹150 crore.", "The film made 150 million rupees.")
        self.assertFalse(r["ok"])
        self.assertEqual(r["problems"][0]["status"], "crore_read_as_million")
        self.assertIn("1 crore = 10 million", r["problems"][0]["hint"])

    def test_correct_conversion_is_supported(self):
        self.assertEqual(statuses("Net profit Rs 820 crore.", "Net profit Rs 8.2 billion."), ["supported"])

    def test_lakh_crore_swap(self):
        r = check("Day one: ₹2.47 lakh.", "Day one: ₹2.47 crore.")
        self.assertEqual(r["problems"][0]["status"], "lakh_crore_swap")

    def test_scale_mismatch(self):
        self.assertEqual(statuses("Outlay ₹2,50,00,000.", "Outlay ₹25 lakh."), ["scale_mismatch"])

    def test_rounded(self):
        self.assertEqual(statuses("Revenue ₹1,234.56 crore.", "Revenue ₹1,235 crore."), ["rounded_supported"])

    def test_rounding_too_far(self):
        self.assertEqual(statuses("Revenue ₹1,234.56 crore.", "Revenue ₹1,240 crore."), ["unsupported"])

    def test_approx(self):
        self.assertEqual(statuses("Revenue ₹1,234.56 crore.", "Revenue about ₹1,300 crore."), ["approx_supported"])

    def test_currency_mismatch(self):
        self.assertEqual(statuses("The fee is ₹500.", "The fee is $500."), ["currency_mismatch"])

    def test_conversion_unverified_is_not_a_problem(self):
        r = check("Deal worth ₹830 crore.", "Deal worth $100 million.")
        self.assertTrue(r["ok"])
        self.assertEqual(r["counts"], {"conversion_unverified": 1})

    def test_invented_number(self):
        r = check("Hired 1,200 people.", "Hired 1,200 people and opened 40 offices.")
        self.assertEqual([p["text"] for p in r["problems"]], ["40"])

    def test_years_are_not_checked(self):
        self.assertTrue(check("Paid ₹6,000.", "In 2023 it paid ₹6,000.")["ok"])

    def test_deterministic(self):
        a = check("₹150 crore", "150 million rupees")
        self.assertEqual(a, check("₹150 crore", "150 million rupees"))


class Format(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_inr(25_000_000), {"value": 25_000_000, "indian_grouping": "₹2,50,00,000",
                                                  "indian_words": "₹2.5 crore", "international": "₹25 million"})

    def test_group_with_paise(self):
        self.assertEqual(indian_group(922436.38), "9,22,436.38")

    def test_bad_value(self):
        with self.assertRaises(ValueError):
            format_inr(-1)


class Bench(unittest.TestCase):
    def test_all_cases_pass_and_beat_naive(self):
        r = score(load())
        self.assertEqual(r["in_number_grounding_exact"], r["cases"])
        self.assertLess(r["naive_flag"], r["cases"])


class Server(unittest.TestCase):
    def call(self, name, args):
        return handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})

    def test_tools_have_annotations(self):
        self.assertEqual({t["name"] for t in TOOLS}, {"in_number_grounding_check", "in_number_extract", "in_amount_format"})
        for t in TOOLS:
            self.assertTrue(t["annotations"]["readOnlyHint"])

    def test_check_call(self):
        r = self.call("in_number_grounding_check", {"source": "₹150 crore", "summary": "150 million rupees"})
        self.assertFalse(r["result"]["structuredContent"]["ok"])

    def test_bad_input_is_tool_error(self):
        r = self.call("in_number_grounding_check", {"source": 1, "summary": "x"})
        self.assertTrue(r["result"]["isError"])

    def test_unknown_tool(self):
        self.assertIn("error", self.call("nope", {}))

    def test_stdio(self):
        msgs = "\n".join(json.dumps(m) for m in [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]) + "\n"
        out = subprocess.run([sys.executable, "-m", "innumground.server"], input=msgs, capture_output=True,
                             text=True, encoding="utf-8", cwd=ROOT, timeout=30).stdout.strip().splitlines()
        self.assertEqual(len(out), 2)
        self.assertEqual(json.loads(out[1])["result"]["tools"][0]["name"], "in_number_grounding_check")


class CLI(unittest.TestCase):
    def test_cli_exit_code(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s, m = os.path.join(d, "s.txt"), os.path.join(d, "m.txt")
            for path, text in ((s, "₹150 crore"), (m, "150 million rupees")):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            p = subprocess.run([sys.executable, "-m", "innumground", s, m], capture_output=True, cwd=ROOT, timeout=30)
            self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
