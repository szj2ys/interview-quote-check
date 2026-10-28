# Interview Quote Check

An offline Python standard-library CLI that checks whether each report quote is an exact substring of the transcript turn it identifies. It catches altered quotations and references to the wrong turn. It does **not** decide whether an interview answer is true or whether coaching is fair, relevant, or correct.

Published by the MakeInterview/MockLive team. This is an independent offline utility; the separate live AI interview service is currently paused. All bundled examples are fictional teaching data, not customer transcripts or production validation results.

## Quick start

Requires Python 3.10 or newer. No package installation, network access, account, or API key is needed. From the downloaded project folder:

```sh
python quote_check.py examples/valid.json
python quote_check.py examples/altered-quote.json
python -B -m unittest discover -s tests -v
```

The first command exits `0`; the second exits `1`. A mismatch is an expected diagnostic, not a crashed program. On PowerShell inspect `$LASTEXITCODE` immediately afterward; in a POSIX shell use `echo $?`.

For stdin, omit the path or pass `-`. In a POSIX shell:

```sh
python quote_check.py - < examples/valid.json
```

For a cross-platform, explicitly UTF-8 byte stream without shell-encoding assumptions:

```sh
python -c "import pathlib,subprocess,sys; data=pathlib.Path('examples/valid.json').read_bytes(); raise SystemExit(subprocess.run([sys.executable,'quote_check.py','-'],input=data).returncode)"
```

Open `index.html` locally for the worked tutorial. Keep `style.css` beside it. Only the optional external sample-report link requires the internet.

## Input contract

One UTF-8 JSON object with exactly these two keys:

```json
{
  "transcript": [
    {"turn_id": "answer-1", "text": "I wrote the import script."}
  ],
  "evidence": [
    {"turn_id": "answer-1", "quote": "wrote the import script"}
  ]
}
```

Both arrays must be nonempty. Each transcript item has exactly `turn_id` and `text`; each evidence item has exactly `turn_id` and `quote`. IDs and quotes must be nonblank strings. Transcript text must be a string; an empty turn is allowed but cannot match a nonblank quote. Transcript IDs must be unique. Unknown keys, duplicate JSON member names, non-JSON constants such as `NaN`, and unpaired Unicode surrogates are errors. Input must be UTF-8 without a byte-order mark.

IDs are compared exactly. Spaces around an otherwise nonblank ID are preserved; `answer-1` and `answer-1 ` are different IDs. Repeated evidence entries are permitted and checked independently, but do not become distinct support for a conclusion.

The complete input schema is validated before any quote result is produced. Invalid evidence anywhere causes an input error instead of a partial passing result. Empty evidence is an error: this tool never calls a report valid simply because there was nothing to check.

## Matching rule and output

After JSON escapes are decoded, the rule is precisely `quote in transcript_text` for the specified turn. Matching is case-sensitive and preserves punctuation, spaces, line breaks, and Unicode codepoints. There is no trimming, case folding, smart-quote replacement, whitespace collapsing, Unicode normalization, translation, or fuzzy matching. A phrase present only in another turn fails. A missing referenced turn is a mismatch, not a schema error.

Success for `examples/valid.json`:

```json
{"status":"pass","checked":2,"matched":2,"results":[{"check_id":1,"status":"match","reason":"exact_substring"},{"check_id":2,"status":"match","reason":"exact_substring"}]}
```

Mismatch for `examples/altered-quote.json`:

```json
{"status":"mismatch","checked":1,"matched":0,"results":[{"check_id":1,"status":"mismatch","reason":"quote_not_in_turn"}]}
```

`check_id` is the one-based position in the evidence array. Error locations also use one-based positions. Match reasons are `exact_substring`, `quote_not_in_turn`, and `missing_turn`. Input errors have `status: "error"` and a fixed reason or schema location, with no partial results.

| Exit code | Meaning | Suggested caller action |
| --- | --- | --- |
| `0` | Every supplied quote matches its identified turn. | Continue to contextual review; do not treat this as a report-quality score. |
| `1` | At least one quote mismatches or references a missing turn. | Locate its `check_id` in the source evidence; correct the quote or mapping. |
| `2` | Usage, file access, UTF-8, JSON, or schema error. | Repair the input or invocation and rerun before interpreting results. |

The CLI writes one compact JSON line to stdout for each validation invocation, and creates no output files. `--help` prints human-readable usage. Callers should check the exit code as well as the JSON; do not convert missing output or a failed process into success.

## Synthetic fixtures

| File | Expected exit | What it tests |
| --- | --- | --- |
| `examples/valid.json` | `0` | Two exact quotes from their own turns. |
| `examples/altered-quote.json` | `1` | “helped review” changed into “wrote.” |
| `examples/wrong-turn.json` | `1` | Quote exists, but only in a different turn. |
| `examples/unicode.json` | `1` | Two exact matches; three mismatches involving accents, apostrophes, and spaces. |
| `examples/malformed.json` | `2` | Incomplete JSON structure. |
| `examples/empty-evidence.json` | `2` | No evidence to check. |

## Privacy and limits

The validator reads the supplied file or stdin into memory. It makes no network requests, analytics calls, or storage writes. Results do not echo transcript text, quote text, supplied IDs, or file paths. This reduces accidental logging; it is not a guarantee against operating-system memory inspection, shell history, terminal capture, swap, backups, or logging by the caller. Avoid putting transcript content directly in a shell command. Protect your original JSON and any redirected output according to your own data policy.

This is a small local utility, not a hardened service for arbitrary hostile uploads. Input size is not capped: very large documents consume memory. Run it on trusted, appropriately sized local files. Running the unit tests may create temporary test files; those files contain synthetic input and are removed by the tests.

An exact match can still be misleading. “I led the migration” matches inside “I never said I led the migration.” A transcript may mishear the audio. A caller may assign the wrong speaker or turn ID before this tool sees the data. Translation, paraphrase, and ellipses generally fail even when their meaning is faithful; label them separately instead of silently normalizing quotations. A match proves only membership in the supplied text, not consent, provenance, truth, hiring suitability, or coaching quality.

For a real presentation example, the [MakeInterview sample report](https://makeinterview.com/en/report/sample) shows quoted evidence beside feedback and identifies its session as demo data. Its explanation of a transcription slip illustrates why a text match cannot verify the original audio. That page is context, not an endorsement or validation result from this utility.

## Public project contents

`quote_check.py`, `README.md`, `index.html`, `style.css`, `robots.txt`, `sitemap.xml`, the six `examples/*.json` fixtures, and `tests/test_quote_check.py` form this original resource. The README and hosted tutorial explain the same project; they are not independent endorsements. No customer data, application configuration, credentials, dependencies, or report captures are included. No third-party licence grant is asserted, and no LICENSE file is included.
