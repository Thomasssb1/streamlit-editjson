import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_dist import check_distribution


class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.dist = Path(self.directory.name)

    def build_fixtures(self, missing=None, changed=None, source_version="1.1.0"):
        files = {
            "streamlit_editjson/__init__.py": b"# package",
            "streamlit_editjson/frontend/index.html": b"<html></html>",
            "streamlit_editjson/frontend/main.js": b"// editor",
            "streamlit_editjson/frontend/style.css": b"/* styles */",
            "streamlit_editjson/frontend/streamlit-component-lib.js": b"// bridge",
        }
        metadata = "Metadata-Version: 2.4\nName: streamlit-editjson\nVersion: {}\n"
        with zipfile.ZipFile(
            self.dist / "streamlit_editjson-1.1.0-py3-none-any.whl", "w"
        ) as wheel:
            wheel.writestr(
                "streamlit_editjson-1.1.0.dist-info/METADATA", metadata.format("1.1.0")
            )
            for name, content in files.items():
                if name != missing:
                    wheel.writestr(name, content)
        with tarfile.open(
            self.dist / "streamlit_editjson-1.1.0.tar.gz", "w:gz"
        ) as source:
            entries = {"PKG-INFO": metadata.format(source_version).encode()}
            entries.update(
                {
                    "src/" + name: b"old code" if name == changed else content
                    for name, content in files.items()
                }
            )
            for name, content in entries.items():
                info = tarfile.TarInfo("streamlit_editjson-1.1.0/" + name)
                info.size = len(content)
                source.addfile(info, io.BytesIO(content))

    def test_matching_distributions_and_release_tag_pass(self):
        self.build_fixtures()
        self.assertEqual(check_distribution(self.dist, "v1.1.0"), "1.1.0")
        self.assertEqual(check_distribution(self.dist), "1.1.0")

    def test_mismatched_tag_is_rejected_before_publishing(self):
        self.build_fixtures()
        with self.assertRaisesRegex(ValueError, "tag"):
            check_distribution(self.dist, "v1.0.0")

    def test_missing_frontend_asset_is_rejected(self):
        self.build_fixtures(missing="streamlit_editjson/frontend/style.css")
        with self.assertRaisesRegex(ValueError, "style.css"):
            check_distribution(self.dist)

    def test_different_source_and_wheel_code_is_rejected(self):
        self.build_fixtures(changed="streamlit_editjson/frontend/main.js")
        with self.assertRaisesRegex(ValueError, "main.js"):
            check_distribution(self.dist)

    def test_source_and_wheel_versions_must_match(self):
        self.build_fixtures(source_version="1.0.0")
        with self.assertRaisesRegex(ValueError, "metadata"):
            check_distribution(self.dist)

    def test_stale_wheels_and_missing_archives_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "one wheel"):
            check_distribution(self.dist)
        self.build_fixtures()
        (self.dist / "old.whl").write_bytes(b"stale")
        with self.assertRaisesRegex(ValueError, "one wheel"):
            check_distribution(self.dist)
