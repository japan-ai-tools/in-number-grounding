"""Find money amounts and numbers written the Indian way and check a summary against its source.

Standard library only. No network. Same input -> same output.

Handles: lakh / lac / L, crore / cr / Cr., "lakh crore", "thousand crore", "1 crore 25 lakh",
Indian digit grouping (9,22,436.38 / 2,50,00,000), Western grouping, million / mn / billion / bn /
trillion / k, currency marks (₹, Rs, Rs., INR, $, US$, USD), percentages, Devanagari digits (०-९).
"""
import re
import unicodedata

SCALES = {
    "thousand": 1e3, "k": 1e3,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5,
    "crore": 1e7, "crores": 1e7, "cr": 1e7, "crs": 1e7,
    "million": 1e6, "millions": 1e6, "mn": 1e6, "mln": 1e6, "m": 1e6,
    "billion": 1e9, "billions": 1e9, "bn": 1e9, "b": 1e9,
    "trillion": 1e12, "tn": 1e12,
    "arab": 1e9, "kharab": 1e11,
}
INDIAN = {"lakh", "crore", "arab", "kharab"}
FAMILY = {"lakh": "lakh", "lakhs": "lakh", "lac": "lakh", "lacs": "lakh", "l": "lakh",
          "crore": "crore", "crores": "crore", "cr": "crore", "crs": "crore",
          "million": "million", "millions": "million", "mn": "million", "mln": "million", "m": "million",
          "billion": "billion", "billions": "billion", "bn": "billion", "b": "billion",
          "trillion": "trillion", "tn": "trillion", "thousand": "thousand", "k": "thousand",
          "arab": "arab", "kharab": "kharab"}
CURRENCY = {"₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "rupees": "INR", "rupee": "INR",
            "$": "USD", "us$": "USD", "usd": "USD", "dollars": "USD",
            "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP"}
APPROX = ("about", "around", "approximately", "approx.", "approx", "roughly", "nearly", "almost",
          "over", "more than", "less than", "under", "some", "close to", "~", "an estimated", "estimated")
WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "half a": 0.5, "a quarter": 0.25}

_SCALE_RE = (r"lakh\s+crores?|thousand\s+crores?|lakhs?|lacs?|crores?|crs?|cr\.?|thousand|million|millions|mln|mn|"
             r"billion|billions|bn|trillion|tn|kharab|arab|[kmbl](?![a-z])")
_NUM_RE = (r"\d{1,3}(?:,\d{2})+,\d{3}(?![\d,])(?:\.\d+)?"      # Indian 2,50,00,000
           r"|\d{1,3}(?:,\d{3})+(?![\d,])(?:\.\d+)?"            # Western 25,000,000
           r"|\d+(?:,\d{2,4})+(?:\.\d+)?"                      # badly grouped: flagged
           r"|\d+(?:\.\d+)?"
           r"|\.\d+")
_CUR_RE = r"(?:₹|rs\.?|inr|us\$|usd|\$|€|eur|£|gbp)"
_AMOUNT_RX = re.compile(
    r"(?P<cur>" + _CUR_RE + r")?\s?"
    r"(?P<num>" + _NUM_RE + r"|half a|a quarter|(?:one|two|three|four|five|six|seven|eight|nine|ten|a)(?=\s+(?:lakh|crore|million|billion)))"
    r"(?:\s?(?P<scale>" + _SCALE_RE + r"))?"
    r"(?P<pct>\s?(?:%|per\s?cent|percent))?"
    r"(?:\s?(?P<cur2>rupees|rupee|dollars|inr|usd))?",
    re.I)
_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
_NEXT_PART = re.compile(r"^\s*(?:and\s+)?(\d+(?:\.\d+)?)\s?(lakhs?|lacs?|thousand)\b", re.I)


def _clean(text):
    t = unicodedata.normalize("NFKC", text).translate(_DEVANAGARI)
    return t.replace(" ", " ").replace(" ", " ")


def grouping_issue(num):
    """Return a warning code when the commas match neither the Indian nor the Western pattern."""
    if "," not in num:
        return None
    whole = num.split(".")[0]
    if re.fullmatch(r"\d{1,3}(,\d{3})+", whole) or re.fullmatch(r"\d{1,2}(,\d{2})*,\d{3}", whole):
        return None
    return "W_BAD_GROUPING"


def _scale_key(s):
    s = re.sub(r"\s+", " ", s.lower().rstrip("."))
    if s.startswith("lakh crore"):
        return "lakh crore", 1e12
    if s.startswith("thousand crore"):
        return "thousand crore", 1e10
    return FAMILY[s], SCALES[s]


def _approx_before(text, start):
    before = text[max(0, start - 20):start].lower().rstrip()
    return any(before.endswith(w) for w in APPROX)


def extract(text):
    """List every amount/number in text with its value. Plain years (1900-2100 with no unit) get kind 'year'."""
    t = _clean(text)
    facts, pos = [], 0
    for m in _AMOUNT_RX.finditer(t):
        if m.start() < pos:
            continue
        raw_num = m.group("num")
        st = m.start("cur") if m.group("cur") else m.start("num")
        prev = t[st - 1] if st > 0 else " "
        if raw_num[0].isdigit() and (prev.isalpha() or prev == "-" and st > 1 and t[st - 2].isalnum()):
            continue  # FY2025-26 parts, ids like A12
        scale_txt = m.group("scale")
        cur_txt = (m.group("cur") or m.group("cur2") or "").lower()
        if scale_txt and scale_txt.lower() in ("l", "m", "b", "k") and not cur_txt and not raw_num[0].isdigit():
            continue
        if scale_txt and scale_txt.lower() == "l" and not cur_txt:
            scale_txt = None  # "5 L" without a currency is too ambiguous (litres)
        low = raw_num.lower()
        base = WORDS.get(low)
        if base is None:
            base = float(raw_num.replace(",", ""))
        issues = []
        g = grouping_issue(raw_num) if raw_num[0].isdigit() or raw_num[0] == "." else None
        if g:
            issues.append(g)
        family, mult = (None, 1.0)
        if scale_txt:
            family, mult = _scale_key(scale_txt)
        value = base * mult
        end = m.end()
        text_out = t[st:m.end()].strip()
        if family == "crore":
            nxt = _NEXT_PART.match(t[end:])
            if nxt:
                value += float(nxt.group(1)) * SCALES[nxt.group(2).lower().rstrip("s") if nxt.group(2).lower() != "thousand" else "thousand"]
                end += nxt.end()
                text_out = t[st:end].strip()
        pct = bool(m.group("pct"))
        currency = CURRENCY.get(cur_txt) if cur_txt else None
        if pct:
            kind = "percent"
        elif currency:
            kind = "money"
        elif family is None and float(base).is_integer() and 1900 <= base <= 2100 and "," not in raw_num:
            kind = "year"
        else:
            kind = "number"
        if "," in raw_num and re.fullmatch(r"\d{1,2}(,\d{2})+,\d{3}(\.\d+)?", raw_num):
            grouping = "indian"
        elif "," in raw_num and not g:
            grouping = "western"
        elif g:
            grouping = "invalid"
        else:
            grouping = None
        facts.append({"kind": kind, "text": text_out, "value": _round(value), "currency": currency,
                      "scale": family, "grouping": grouping, "approx": _approx_before(t, st),
                      "decimals": _decimals(raw_num), "start": st, "issues": issues})
        pos = end
    return facts


def _decimals(num):
    return len(num.split(".")[1]) if "." in num else 0


def _round(v):
    r = round(v, 6)
    return int(r) if float(r).is_integer() else r


def _eq(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _rounds_to(summary_fact, source_value):
    """True when source_value, rounded to the precision the summary used, equals the summary value."""
    if summary_fact["scale"] is None:
        return False
    mult = summary_fact["value"] / float(_shown(summary_fact)) if _shown(summary_fact) else None
    if not mult:
        return False
    step = mult * (10 ** -summary_fact["decimals"])
    return abs(source_value - summary_fact["value"]) <= step / 2 + 1e-9 * abs(source_value)


def _shown(f):
    m = re.search(r"(\d+(?:\.\d+)?|\.\d+)", f["text"].replace(",", ""))
    return float(m.group(1)) if m else None


def indian_group(value):
    """2500000.5 -> '25,00,000.50' (two decimals only when there is a fraction)."""
    txt = f"{value:.2f}"
    whole, frac = txt.split(".")
    head, tail = whole[:-3], whole[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    out = ",".join(parts + [tail])
    return out if frac == "00" else out + "." + frac


def format_inr(value):
    """Write a rupee value three ways: Indian grouping, lakh/crore words, international millions."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1e16:
        raise ValueError("'value' must be a number from 0 to 1e16")
    if value >= 1e12:
        words = f"₹{_trim(value / 1e12)} lakh crore"
    elif value >= 1e7:
        words = f"₹{_trim(value / 1e7)} crore"
    elif value >= 1e5:
        words = f"₹{_trim(value / 1e5)} lakh"
    else:
        words = "₹" + indian_group(value)
    if value >= 1e12:
        intl = f"₹{_trim(value / 1e12)} trillion"
    elif value >= 1e9:
        intl = f"₹{_trim(value / 1e9)} billion"
    elif value >= 1e6:
        intl = f"₹{_trim(value / 1e6)} million"
    else:
        intl = f"₹{value:,.2f}".replace(".00", "")
    return {"value": _round(value), "indian_grouping": "₹" + indian_group(value), "indian_words": words,
            "international": intl}


def _trim(x):
    return f"{x:.4f}".rstrip("0").rstrip(".")


def check(source, summary, tolerance=0.1):
    """Look up each money amount, number and percentage of summary in source.

    status per fact: supported, rounded_supported, approx_supported, year (not checked),
    crore_read_as_million (summary is 1/10 of a source crore amount written in millions),
    lakh_crore_swap (factor 100 between lakh and crore), scale_mismatch (off by 10^k),
    currency_mismatch (same digits, other currency), conversion_unverified (summary is in another
    currency than every source amount: cannot confirm the exchange rate), unsupported.
    """
    src = [f for f in extract(source) if f["kind"] != "year"]
    out, problems = [], []
    for f in extract(summary):
        status, matched = _status(f, src, tolerance)
        row = dict(f, status=status, matched=matched["text"] if matched else None)
        out.append(row)
        if status in ("unsupported", "crore_read_as_million", "lakh_crore_swap", "scale_mismatch", "currency_mismatch"):
            problems.append({"text": f["text"], "status": status, "value": f["value"],
                             "source_text": matched["text"] if matched else None, "hint": _hint(status, f, matched)})
    counts = {}
    for r in out:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"ok": not problems, "problems": problems, "counts": counts, "facts": out}


def _compatible(a, b):
    if a["kind"] == "percent" or b["kind"] == "percent":
        return a["kind"] == b["kind"]
    return a["currency"] is None or b["currency"] is None or a["currency"] == b["currency"]


def _status(f, src, tol):
    if f["kind"] == "year":
        return "year", None
    same = [s for s in src if _eq(s["value"], f["value"])]
    for s in same:
        if _compatible(f, s):
            return "supported", s
    for s in src:
        if _compatible(f, s) and f["kind"] != "percent" and _rounds_to(f, s["value"]):
            return "rounded_supported", s
    if f["approx"]:
        for s in src:
            if _compatible(f, s) and abs(s["value"] - f["value"]) <= tol * abs(s["value"]):
                return "approx_supported", s
    if same:
        return "currency_mismatch", same[0]
    if f["kind"] != "percent" and f["value"]:
        for s in src:
            if not _compatible(f, s) or not s["value"]:
                continue
            ratio = s["value"] / f["value"]
            if (_eq(ratio, 10) and s["scale"] in ("crore", "lakh crore", "thousand crore")
                    and f["scale"] in ("million", "billion", "trillion")):
                return "crore_read_as_million", s
            if (_eq(ratio, 100) or _eq(ratio, 0.01)) and {f["scale"], s["scale"]} == {"lakh", "crore"}:
                return "lakh_crore_swap", s
        for s in src:
            if not _compatible(f, s) or not s["value"] or s["kind"] == "percent":
                continue
            ratio = s["value"] / f["value"]
            for k in (1, 2, 3):
                if _eq(ratio, 10 ** k) or _eq(ratio, 10 ** -k):
                    if f["scale"] or s["scale"]:
                        return "scale_mismatch", s
    if f["kind"] == "money" and f["currency"] and src and not any(
            s["currency"] in (None, f["currency"]) for s in src if s["kind"] == "money") and any(
            s["kind"] == "money" for s in src):
        return "conversion_unverified", None
    return "unsupported", None


def _hint(status, f, s):
    if status == "crore_read_as_million":
        return f"1 crore = 10 million. {s['text']} = {format_inr(s['value'])['international'].lstrip('₹')}, not {f['text']}"
    if status == "lakh_crore_swap":
        return f"1 crore = 100 lakh. The source says {s['text']}"
    if status == "scale_mismatch":
        return f"Off by a power of ten. The source says {s['text']}"
    if status == "currency_mismatch":
        return f"Same number, other currency. The source says {s['text']}"
    return "Not in the source. Remove it or quote the source figure"
