# IN Number Grounding

<!-- mcp-name: io.github.japan-ai-tools/in-number-grounding -->

Check the rupee amounts in an AI-written summary against the source before you publish it.

Indian sources write money in lakh and crore (₹150 crore, Rs 1 crore 25 lakh, ₹11.11 lakh crore) and group digits as 2,50,00,000. English summaries usually switch to million and billion. That switch is where the figures go wrong: 1 crore is 10 million, so "₹150 crore" written as "150 million rupees" is ten times too small.

This is not hypothetical. A test of five AI engines on Indian box-office questions (90 runs) found at least one materially wrong figure in 28 runs; crore treated as a million in 7% of runs and crore/lakh mixed up in 3% ([everything-pr.com, updated 2026-10-19](https://everything-pr.com/ai-entertainment-communications-playbook)).

IN Number Grounding reads both texts, turns every amount into a plain number, and tells you which summary figures are in the source and which are not. When a figure is off by a known scale error, it names the error.

- MCP server (stdio), CLI and Python library
- Python standard library only, no network, MIT
- Same input, same output: no model calls, nothing to pay per check

## Example

```text
source:  The film collected ₹150 crore worldwide. Day one was ₹2.47 lakh.
summary: The film made 150 million rupees worldwide; day one was ₹2.47 crore. That is about $18 million.
```

```json
{"ok": false,
 "problems": [
  {"text": "150 million rupees", "status": "crore_read_as_million", "source_text": "₹150 crore",
   "hint": "1 crore = 10 million. ₹150 crore = 1.5 billion, not 150 million rupees"},
  {"text": "₹2.47 crore", "status": "lakh_crore_swap", "source_text": "₹2.47 lakh",
   "hint": "1 crore = 100 lakh. The source says ₹2.47 lakh"}],
 "counts": {"crore_read_as_million": 1, "lakh_crore_swap": 1, "conversion_unverified": 1}}
```

The dollar figure is reported as `conversion_unverified`: the source has no dollar amount, so the exchange rate cannot be checked from it. It is not counted as a problem.

## Statuses

| status | meaning | problem? |
|---|---|---|
| supported | same value in the source (any spelling or grouping) | no |
| rounded_supported | a source value rounds to the summary at the precision the summary used (₹1,234.56 crore → ₹1,235 crore) | no |
| approx_supported | summary says about/nearly/over and is within `tolerance` (default 10%) | no |
| conversion_unverified | amount in another currency than all source amounts | no (check the rate yourself) |
| year | a plain year such as 2024; not checked | no |
| crore_read_as_million | summary value is 1/10 of a source crore amount and is written in million/billion | yes |
| lakh_crore_swap | factor 100 between a lakh and a crore figure | yes |
| scale_mismatch | off by 10, 100 or 1000 against a source amount | yes |
| currency_mismatch | same number, other currency (₹500 vs $500) | yes |
| unsupported | not in the source | yes |

## What it reads

- lakh, lakhs, lac, lacs, L after a currency mark (Rs 5 L); crore, crores, cr, Cr.
- lakh crore (10^12), thousand crore (10^10), composite "1 crore 25 lakh"
- thousand, k, million, mn, billion, bn, trillion, tn, arab, kharab
- ₹, Rs, Rs., INR, rupees, $, US$, USD, €, £
- Indian grouping (9,22,436.38), Western grouping (25,000,000); commas that fit neither are flagged `W_BAD_GROUPING`
- Devanagari digits (₹४५ crore); percentages (12%, 12 per cent)

## Use

MCP (Claude Desktop, Claude Code, Cursor and other MCP clients):

```json
{"mcpServers": {"in-number-grounding": {"command": "python", "args": ["-m", "innumground.server"], "cwd": "/path/to/in-number-grounding"}}}
```

Tools: `in_number_grounding_check(source, summary, tolerance?)`, `in_number_extract(text)`, `in_amount_format(value)`.

`in_amount_format(25000000)` returns `₹2,50,00,000`, `₹2.5 crore` and `₹25 million`, so an agent can quote a figure in both systems without converting by hand.

CLI (exit code 1 when there is a problem):

```bash
python -m innumground source.txt summary.txt
python -m innumground --extract source.txt
```

Python:

```python
from innumground import check
r = check(source_text, summary_text)
if not r["ok"]:
    for p in r["problems"]:
        print(p["text"], p["status"], p["hint"])
```

## Test cases

`data/in_number_grounding_cases_v1.jsonl` has 26 invented source/summary pairs (crore as million, lakh/crore swaps, rounding, composites, lakh crore, Devanagari digits, currency). `python -m innumground.bench` prints the score. This version gets all 26; a digits-only string search gets 10 of 26 right. The cases and the rules have the same author, so treat this as a regression suite, not as accuracy on real text. New cases are welcome: add a line to the file and open a pull request.

`python -m unittest discover -s tests` runs 35 tests.

## Limits

- It checks that values are present in the source. It does not check meaning: a correct number attached to the wrong film, company or year passes.
- Number words are read only for one to ten before lakh/crore/million/billion ("two crore"). "Twenty-five lakh" written in words is not read.
- Hindi scale words (लाख, करोड़) are not read yet; Devanagari digits are.
- A bare "L" or "m" without a currency mark is not taken as lakh or million.
- Exchange rates are never assumed. A converted amount is reported, not verified.
- It is a checking aid, not financial, tax or investment advice.

## Data and license

The code and the test cases were written for this project; the cases are invented sentences. MIT license (LICENSE). Not affiliated with any AI vendor.
