import importlib
import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

# Ensure local package import from src/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class TestEditJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.streamlit_editjson = importlib.import_module("streamlit_editjson")

    def _create_temp_json_file(self, data):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)

        filepath = Path(tmp_dir.name) / "input.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")
        return str(filepath)

    def test_returns_original_json_when_component_returns_none(self):
        original = {"name": "Alice", "age": 31}
        filepath = self._create_temp_json_file(original)

        mocked_component = Mock(return_value=None)

        with patch.object(self.streamlit_editjson, "_component_func", mocked_component):
            result = self.streamlit_editjson.editjson(filepath)

        self.assertEqual(result, original)

    def test_returns_component_json_when_component_returns_value(self):
        original = {"name": "Alice", "age": 31}
        edited = {"name": "Bob", "age": 42}
        filepath = self._create_temp_json_file(original)

        mocked_component = Mock(return_value=edited)

        with patch.object(self.streamlit_editjson, "_component_func", mocked_component):
            result = self.streamlit_editjson.editjson(
                filepath, key_editable=True, value_editable=False, key="editor_1"
            )

        self.assertEqual(result, edited)

    def test_decodes_exact_json_returned_by_frontend(self):
        original = {"id": 9007199254740993}
        edited = {"id": 9007199254740995, "nested": [-9007199254740993]}
        filepath = self._create_temp_json_file(original)
        with patch.object(
            self.streamlit_editjson,
            "_component_func",
            return_value=json.dumps(edited).encode("utf-8"),
        ):
            self.assertEqual(self.streamlit_editjson.editjson(filepath), edited)

    def test_legacy_root_strings_are_returned_without_decoding(self):
        filepath = self._create_temp_json_file("original")
        for value in ["plain text", "null", "123", "true", '"quoted"', "{}", "[]", ""]:
            with self.subTest(value=value):
                with patch.object(
                    self.streamlit_editjson, "_component_func", return_value=value
                ):
                    result = self.streamlit_editjson.editjson(filepath)
                self.assertEqual(result, value)
                self.assertIsInstance(result, str)

    def test_byte_transport_decodes_root_values_and_unicode(self):
        filepath = self._create_temp_json_file("original")
        for value in [
            "plain text",
            "null",
            "123",
            "caf\u00e9 \U0001f642",
            None,
            True,
            9007199254740993,
        ]:
            with self.subTest(value=value):
                with patch.object(
                    self.streamlit_editjson,
                    "_component_func",
                    return_value=json.dumps(value, ensure_ascii=False).encode("utf-8"),
                ):
                    result = self.streamlit_editjson.editjson(filepath)
                self.assertEqual(result, value)
                self.assertIs(type(result), type(value))

    def test_default_preserves_original_json(self):
        for original in [{"id": 9007199254740993}, "plain text", None]:
            with self.subTest(original=original):
                filepath = self._create_temp_json_file(original)
                with patch.object(
                    self.streamlit_editjson,
                    "_component_func",
                    side_effect=lambda **kw: kw["default"],
                ):
                    self.assertEqual(
                        self.streamlit_editjson.editjson(filepath), original
                    )

    def test_legacy_editable_keyword_maps_to_value_editable_and_warns(self):
        filepath = self._create_temp_json_file({"enabled": True})
        for editable in [True, False, None]:
            with self.subTest(editable=editable):
                with patch.object(
                    self.streamlit_editjson, "_component_func", return_value=None
                ) as component, self.assertWarnsRegex(
                    DeprecationWarning, "editable.*value_editable"
                ) as warning:
                    self.streamlit_editjson.editjson(
                        filepath, editable=editable, key="legacy"
                    )
                kwargs = component.call_args.kwargs
                self.assertIs(kwargs["value_editable"], editable)
                self.assertFalse(kwargs["key_editable"])
                self.assertEqual(kwargs["key"], "legacy")
                self.assertEqual(Path(warning.filename), Path(__file__))

    def test_explicit_value_editable_takes_precedence_over_legacy_alias(self):
        filepath = self._create_temp_json_file({"enabled": True})
        for value_editable, editable in [(True, False), (False, True), (None, True)]:
            with self.subTest(value_editable=value_editable, editable=editable):
                with patch.object(
                    self.streamlit_editjson, "_component_func", return_value=None
                ) as component, self.assertWarns(DeprecationWarning):
                    self.streamlit_editjson.editjson(
                        filepath,
                        key_editable=True,
                        value_editable=value_editable,
                        editable=editable,
                    )
                self.assertIs(
                    component.call_args.kwargs["value_editable"], value_editable
                )
                self.assertTrue(component.call_args.kwargs["key_editable"])

    def test_current_positional_arguments_keep_their_meaning_without_warnings(self):
        filepath = self._create_temp_json_file({"enabled": True})
        with patch.object(
            self.streamlit_editjson, "_component_func", return_value=None
        ) as component, warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            self.streamlit_editjson.editjson(filepath, True, False, "modern")
        kwargs = component.call_args.kwargs
        self.assertTrue(kwargs["key_editable"])
        self.assertFalse(kwargs["value_editable"])
        self.assertEqual(kwargs["key"], "modern")
        self.assertEqual(recorded, [])

    def test_passes_expected_arguments_to_component(self):
        original = {"enabled": True, "count": 3}
        filepath = self._create_temp_json_file(original)

        mocked_component = Mock(return_value=None)

        with patch.object(self.streamlit_editjson, "_component_func", mocked_component):
            self.streamlit_editjson.editjson(filepath)

        _, kwargs = mocked_component.call_args

        self.assertEqual(kwargs["json_str"], json.dumps(original))
        self.assertEqual(kwargs["key_editable"], False)
        self.assertEqual(kwargs["value_editable"], True)
        self.assertIsNone(kwargs["key"])
        self.assertEqual(kwargs["default"], original)


if __name__ == "__main__":
    unittest.main()
