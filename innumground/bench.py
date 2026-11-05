"""Score on data/in_number_grounding_cases_v1.jsonl.

python -m innumground.bench
The naive checker is what a quick script usually does: take every run of digits in the summary,
drop commas, and flag it when that string is not in the source (also with commas dropped).
Cases and rules come from the same author and the texts are invented: this is a regression suite,
not proof of accuracy on real text.
"""
import json
import os
import re
import sys

from .ground import check

CASES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                     "in_number_grounding_cases_v1.jsonl")


def load(path=CASES):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def naive_has_problem(source, summary):
    src = source.replace(",", "")
    nums = re.findall(r"\d+(?:\.\d+)?", summary.replace(",", ""))
    return any(n not in src for n in nums)


def ours_problems(case):
    return sorted(p["text"] for p in check(case["source"], case["summary"])["problems"])


def score(cases=None):
    cases = cases or load()
    exact = sum(ours_problems(c) == sorted(c["expected_problems"]) for c in cases)
    ours_flag = sum((not ours_problems(c)) == (not c["expected_problems"]) for c in cases)
    naive_flag = sum(naive_has_problem(c["source"], c["summary"]) == bool(c["expected_problems"]) for c in cases)
    return {"cases": len(cases), "in_number_grounding_exact": exact, "in_number_grounding_flag": ours_flag,
            "naive_flag": naive_flag}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cases = load()
    print(json.dumps(score(cases)))
    for c in cases:
        got = ours_problems(c)
        if got != sorted(c["expected_problems"]):
            print("MISS", c["id"], c["category"], "expected", c["expected_problems"], "got", got)


if __name__ == "__main__":
    main()
