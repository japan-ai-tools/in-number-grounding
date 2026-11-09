"""MCP server (stdio, JSON-RPC 2.0). Python standard library only, no network.

Start: python -m innumground.server
"""
import json
import sys

from . import __version__
from .ground import check, extract, format_inr

PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
RO = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
MAX_CHARS = 200_000

TOOLS = [
    {
        "name": "in_number_grounding_check",
        "title": "Check Indian money amounts and numbers in a summary against its source",
        "annotations": RO,
        "description": ("Before you send a summary, article or answer written from an Indian source (news, filings, "
                        "box-office reports, budgets), pass both texts here. Every amount, number and percentage in "
                        "the summary is normalized (₹2.5 crore = ₹2,50,00,000 = 25 million rupees; Rs 1 crore 25 lakh "
                        "= 12,500,000; 5.6 lakh crore = 5.6 trillion; Devanagari digits) and looked up in the source. "
                        "Per-fact status: supported, rounded_supported (the source rounds to the summary's precision), "
                        "approx_supported (marked about/nearly and within tolerance), crore_read_as_million (the "
                        "summary wrote N million for N crore: 10x too small), lakh_crore_swap (100x), scale_mismatch "
                        "(other power of ten), currency_mismatch, conversion_unverified (amount in another currency: "
                        "the exchange rate cannot be checked from the source), unsupported, year. Deterministic, "
                        "offline. It checks values, not meaning."),
        "inputSchema": {"type": "object", "properties": {
            "source": {"type": "string", "description": "Original text"},
            "summary": {"type": "string", "description": "Text written from the source (by an AI or a person)"},
            "tolerance": {"type": "number", "description": "Relative tolerance for values marked approximate. Default 0.1"}},
            "required": ["source", "summary"]},
    },
    {
        "name": "in_number_extract",
        "title": "Extract Indian-format amounts and numbers from text",
        "annotations": RO,
        "description": ("List every amount, number and percentage in a text with its value: lakh/lac/L, crore/cr, "
                        "lakh crore, thousand crore, million/mn/billion/bn, ₹/Rs/INR/$, Indian (2,50,00,000) and "
                        "Western grouping, Devanagari digits. Flags commas that fit neither grouping "
                        "(W_BAD_GROUPING). Returns facts with kind, text, value, currency, scale, grouping, approx, issues."),
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "in_amount_format",
        "title": "Write a rupee amount in Indian and international form",
        "annotations": RO,
        "description": ("Give a rupee value; get it written three ways so you can quote it without a scale error: "
                        "Indian grouping (₹2,50,00,000), lakh/crore words (₹2.5 crore) and international "
                        "(₹25 million). 1 lakh = 100,000; 1 crore = 10 million = 100 lakh."),
        "inputSchema": {"type": "object", "properties": {"value": {"type": "number", "description": "Amount in rupees"}},
                        "required": ["value"]},
    },
]


def _str(args, key):
    v = args.get(key)
    if not isinstance(v, str):
        raise ValueError(f"'{key}' must be a string")
    if len(v) > MAX_CHARS:
        raise ValueError(f"'{key}' is longer than {MAX_CHARS} characters; split it")
    return v


def _tol(args):
    v = args.get("tolerance", 0.1)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
        raise ValueError("'tolerance' must be a number between 0 and 1")
    return float(v)


HANDLERS = {
    "in_number_grounding_check": lambda a: check(_str(a, "source"), _str(a, "summary"), _tol(a)),
    "in_number_extract": lambda a: {"facts": extract(_str(a, "text"))},
    "in_amount_format": lambda a: format_inr(a.get("value")),
}


def handle(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None
    try:
        if method == "initialize":
            want = params.get("protocolVersion")
            result = {"protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "in-number-grounding", "version": __version__},
                      "instructions": ("After writing a summary from an Indian source, call in_number_grounding_check "
                                       "with the source and your summary. Fix every fact reported as unsupported, "
                                       "crore_read_as_million, lakh_crore_swap, scale_mismatch or currency_mismatch "
                                       "before sending. 1 crore = 10 million.")}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name")
            if name not in HANDLERS:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
            try:
                out = HANDLERS[name](params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                          "structuredContent": out, "isError": False}
            except ValueError as e:
                result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except Exception as e:  # keep the server alive
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"Internal error: {e}"}}


def main():
    for s in (sys.stdin, sys.stdout):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(msg) if isinstance(msg, dict) else None
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
