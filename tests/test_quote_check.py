"""Boundary and subprocess tests using synthetic, non-personal input."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quote_check import InputError, parse_document, validate_document


def document(text="I wrote the script.", quote="wrote the script", turn_id="a"):
    return {"transcript": [{"turn_id": "a", "text": text}],
            "evidence": [{"turn_id": turn_id, "quote": quote}]}


class MatchingTests(unittest.TestCase):
    def test_exact_substring_matches_without_requiring_whole_turn(self):
        result = validate_document(document())
        self.assertEqual((result["status"], result["matched"]), ("pass", 1))

    def test_case_space_punctuation_and_normalization_are_significant(self):
        cases = [("I wrote", "i wrote"), ("two  spaces", "two spaces"),
                 ("I’m sure", "I'm sure"), ("café", "cafe\u0301"),
                 ("line\nbreak", "line break"), ("word\u00a0word", "word word")]
        for text, quote in cases:
            with self.subTest(text=text, quote=quote):
                self.assertEqual(validate_document(document(text, quote))["status"], "mismatch")

    def test_unicode_and_embedded_newline_match_exactly(self):
        for text in ("café", "cafe\u0301", "I’m sure", "line\nbreak", "A 🧪 test"):
            with self.subTest(text=text):
                self.assertEqual(validate_document(document(text, text))["status"], "pass")

    def test_spaces_are_not_trimmed_before_matching(self):
        self.assertEqual(validate_document(document("hello", " hello"))["status"], "mismatch")

    def test_quotes_from_another_turn_do_not_match(self):
        data = document(turn_id="b")
        data["transcript"].append({"turn_id": "b", "text": "I reviewed the design."})
        self.assertEqual(validate_document(data)["results"][0]["reason"], "quote_not_in_turn")

    def test_missing_turn_is_a_mismatch(self):
        self.assertEqual(validate_document(document(turn_id="missing"))["results"][0]["reason"], "missing_turn")

    def test_ids_are_exact_not_trimmed_or_casefolded(self):
        for turn_id in ("A", " a", "a "):
            with self.subTest(turn_id=turn_id):
                self.assertEqual(validate_document(document(turn_id=turn_id))["results"][0]["reason"], "missing_turn")

    def test_all_checks_are_reported_when_one_mismatches(self):
        data = document()
        data["evidence"].append({"turn_id": "a", "quote": "invented claim"})
        result = validate_document(data)
        self.assertEqual((result["checked"], result["matched"], result["status"]), (2, 1, "mismatch"))
        self.assertEqual([r["check_id"] for r in result["results"]], [1, 2])

    def test_input_is_not_modified(self):
        data = document()
        before = copy.deepcopy(data)
        validate_document(data)
        self.assertEqual(data, before)


class SchemaTests(unittest.TestCase):
    def test_root_and_array_shapes(self):
        for data in (None, [], {}, {"transcript": [], "evidence": []},
                     {"transcript": "a", "evidence": []},
                     {"transcript": document()["transcript"], "evidence": {}},
                     {**document(), "unexpected": True}):
            with self.subTest(data=data), self.assertRaises(InputError):
                validate_document(data)

    def test_empty_evidence_is_never_a_passing_report(self):
        data = document(); data["evidence"] = []
        with self.assertRaisesRegex(InputError, "evidence: expected nonempty array"):
            validate_document(data)

    def test_duplicate_turn_ids_are_rejected(self):
        data = document(); data["transcript"].append({"turn_id": "a", "text": "other"})
        with self.assertRaisesRegex(InputError, "duplicate turn_id"):
            validate_document(data)

    def test_nonstring_and_blank_required_values(self):
        for array, field in (("transcript", "turn_id"), ("evidence", "turn_id"), ("evidence", "quote")):
            for value in (None, 4, True, [], {}, "", " \t\n"):
                data = document(); data[array][0][field] = value
                with self.subTest(array=array, field=field, value=value), self.assertRaises(InputError):
                    validate_document(data)

    def test_empty_text_is_allowed_but_does_not_match_nonempty_quote(self):
        self.assertEqual(validate_document(document(text=""))["status"], "mismatch")
        data = document(); data["transcript"][0]["text"] = None
        with self.assertRaises(InputError):
            validate_document(data)

    def test_missing_extra_and_nonobject_items(self):
        for array in ("transcript", "evidence"):
            for item in ({}, None, "text", {"turn_id": "a", "quote": "q", "text": "q"}):
                data = document(); data[array] = [item]
                with self.subTest(array=array, item=item), self.assertRaises(InputError):
                    validate_document(data)

    def test_entire_schema_is_validated_before_matching(self):
        data = document(quote="missing"); data["evidence"].append({"turn_id": "a", "quote": 42})
        with self.assertRaisesRegex(InputError, "expected string"):
            validate_document(data)

    def test_invalid_utf8_malformed_json_duplicate_members_and_constants(self):
        cases = [(b'\xff', "invalid_utf8"), (b'{', "invalid_json"),
                 (b'{"x":1,"x":2}', "duplicate_json_member"),
                 (b'NaN', "non_json_number"), (b'Infinity', "non_json_number")]
        for raw, reason in cases:
            with self.subTest(raw=raw), self.assertRaisesRegex(InputError, reason):
                parse_document(raw)

    def test_unpaired_unicode_surrogate_is_rejected(self):
        with self.assertRaisesRegex(InputError, "unpaired Unicode surrogate"):
            validate_document(document(text="\ud800"))


class CLITests(unittest.TestCase):
    def run_cli(self, *args, data=None, cwd=None):
        return subprocess.run([sys.executable, "-B", str(ROOT / "quote_check.py"), *args],
                              input=data, capture_output=True, cwd=cwd, timeout=10)

    def test_fixture_exit_codes_and_actual_json(self):
        for name, code, status in (("valid", 0, "pass"), ("altered-quote", 1, "mismatch"),
                                   ("wrong-turn", 1, "mismatch"), ("unicode", 1, "mismatch"),
                                   ("malformed", 2, "error"), ("empty-evidence", 2, "error")):
            with self.subTest(name=name):
                run = self.run_cli(str(ROOT / "examples" / (name + ".json")))
                self.assertEqual(run.returncode, code, run.stderr)
                self.assertEqual(json.loads(run.stdout)["status"], status)
                self.assertEqual(run.stderr, b"")

    def test_stdin_default_and_explicit_dash(self):
        raw = json.dumps(document("café", "café"), ensure_ascii=False).encode("utf-8")
        for args in ((), ("-",)):
            with self.subTest(args=args):
                run = self.run_cli(*args, data=raw)
                self.assertEqual(run.returncode, 0)
                self.assertEqual(json.loads(run.stdout)["matched"], 1)

    def test_private_text_ids_and_file_paths_are_not_echoed(self):
        data = document(text="PRIVATE_CONTENT_MARKER", quote="PRIVATE_QUOTE_MARKER", turn_id="PRIVATE_ID_MARKER")
        run = self.run_cli(data=json.dumps(data).encode())
        self.assertEqual(run.returncode, 1)
        self.assertNotIn(b"PRIVATE_", run.stdout + run.stderr)
        run = self.run_cli("PRIVATE_PATH_DOES_NOT_EXIST.json")
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["reason"], "input_read_error")
        self.assertNotIn(b"PRIVATE_", run.stdout + run.stderr)

    def test_invalid_input_errors_do_not_echo_input(self):
        for raw in (b'{"PRIVATE_SECRET":', b'\xffPRIVATE_SECRET'):
            run = self.run_cli(data=raw)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(b"PRIVATE_SECRET", run.stdout + run.stderr)

    def test_cli_does_not_create_files_or_modify_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            original = json.dumps(document()).encode(); path.write_bytes(original)
            run = self.run_cli(str(path), cwd=folder)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ["input.json"])

    def test_invalid_arguments_have_fixed_json_error(self):
        run = self.run_cli("--PRIVATE_SECRET")
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout), {"status": "error", "reason": "usage_error"})


if __name__ == "__main__":
    unittest.main()
