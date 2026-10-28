#!/usr/bin/env python3
"""Check exact quote membership in identified transcript turns, entirely offline."""
import json
from pathlib import Path
import sys


class InputError(ValueError):
    """An input error whose fixed message contains no supplied text."""


def _unique_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate_json_member")
        result[key] = value
    return result


def _reject_constant(_value):
    raise InputError("non_json_number")


def parse_document(raw):
    """Decode strict UTF-8 JSON; do not expose the input in an error message."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("invalid_utf8") from None
    try:
        return json.loads(text, object_pairs_hook=_unique_members,
                          parse_constant=_reject_constant)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("invalid_json") from None


def _keys(value, expected, location):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise InputError(location + ": expected exactly " + ", ".join(expected))


def _string(value, location, nonblank=False):
    if not isinstance(value, str):
        raise InputError(location + ": expected string")
    if nonblank and not value.strip():
        raise InputError(location + ": expected nonblank string")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise InputError(location + ": unpaired Unicode surrogate")


def validate_document(document):
    """Validate the complete schema before checking any quote.

    A result describes exact membership only. It does not establish that the
    transcript, turn identifiers, quotation context, or coaching is correct.
    """
    _keys(document, ("transcript", "evidence"), "document")
    transcript, evidence = document["transcript"], document["evidence"]
    if not isinstance(transcript, list) or not transcript:
        raise InputError("transcript: expected nonempty array")
    if not isinstance(evidence, list) or not evidence:
        raise InputError("evidence: expected nonempty array")
    turns = {}
    for index, turn in enumerate(transcript, 1):
        location = f"transcript[{index}]"
        _keys(turn, ("turn_id", "text"), location)
        _string(turn["turn_id"], location + ".turn_id", nonblank=True)
        _string(turn["text"], location + ".text")
        if turn["turn_id"] in turns:
            raise InputError(location + ": duplicate turn_id")
        turns[turn["turn_id"]] = turn["text"]
    for index, item in enumerate(evidence, 1):
        location = f"evidence[{index}]"
        _keys(item, ("turn_id", "quote"), location)
        _string(item["turn_id"], location + ".turn_id", nonblank=True)
        _string(item["quote"], location + ".quote", nonblank=True)
    results = []
    for index, item in enumerate(evidence, 1):
        turn_id, quote = item["turn_id"], item["quote"]
        if turn_id not in turns:
            reason = "missing_turn"
        elif quote not in turns[turn_id]:
            reason = "quote_not_in_turn"
        else:
            reason = "exact_substring"
        results.append({"check_id": index,
                        "status": "match" if reason == "exact_substring" else "mismatch",
                        "reason": reason})
    matched = sum(item["status"] == "match" for item in results)
    return {"status": "pass" if matched == len(results) else "mismatch",
            "checked": len(results), "matched": matched, "results": results}


def _output(result):
    # ASCII JSON avoids terminal encoding surprises; output contains no quotes,
    # transcript text, supplied turn IDs, or local file paths.
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--help"], ["-h"]):
        print("Usage: python quote_check.py [PATH|-]\n"
              "Read UTF-8 JSON from PATH or stdin (default).\n"
              "Exit 0: every supplied quote matches its identified turn.\n"
              "Exit 1: at least one mismatch or missing turn.\n"
              "Exit 2: usage, file, encoding, JSON, or schema error.\n"
              "No network requests or output files. See README.md for schema.")
        return 0
    if len(args) > 1 or (args and args[0].startswith("-") and args[0] != "-"):
        _output({"status": "error", "reason": "usage_error"})
        return 2
    source = args[0] if args else "-"
    try:
        raw = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
    except OSError:
        _output({"status": "error", "reason": "input_read_error"})
        return 2
    try:
        result = validate_document(parse_document(raw))
    except (InputError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InputError) else "input_nesting_too_deep"
        _output({"status": "error", "reason": reason})
        return 2
    _output(result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
