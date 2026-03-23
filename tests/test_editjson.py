import importlib
import json
import sys
import tempfile
import unittest
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

        with patch.object(
            self.streamlit_editjson, "_component_func", mocked_component
        ):
            result = self.streamlit_editjson.editjson(filepath)

        self.assertEqual(result, original)

    def test_returns_component_json_when_component_returns_value(self):
        original = {"name": "Alice", "age": 31}
        edited = {"name": "Bob", "age": 42}
        filepath = self._create_temp_json_file(original)

        mocked_component = Mock(return_value=edited)

        with patch.object(
            self.streamlit_editjson, "_component_func", mocked_component
        ):
            result = self.streamlit_editjson.editjson(
                filepath, key_editable=True, value_editable=False, key="editor_1"
            )

        self.assertEqual(result, edited)

    def test_passes_expected_arguments_to_component(self):
        original = {"enabled": True, "count": 3}
        filepath = self._create_temp_json_file(original)

        mocked_component = Mock(return_value=None)

        with patch.object(
            self.streamlit_editjson, "_component_func", mocked_component
        ):
            self.streamlit_editjson.editjson(filepath)

        _, kwargs = mocked_component.call_args

        self.assertEqual(kwargs["json_str"], json.dumps(original))
        self.assertEqual(kwargs["key_editable"], False)
        self.assertEqual(kwargs["value_editable"], True)
        self.assertIsNone(kwargs["key"])
        self.assertEqual(kwargs["default"], original)


if __name__ == "__main__":
    unittest.main()