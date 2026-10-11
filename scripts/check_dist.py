"""Validate the exact archives that CI will publish to PyPI and GitHub."""

import argparse
import email
import tarfile
import zipfile
from pathlib import Path

REQUIRED_FILES = (
    "streamlit_editjson/__init__.py",
    "streamlit_editjson/frontend/index.html",
    "streamlit_editjson/frontend/main.js",
    "streamlit_editjson/frontend/style.css",
    "streamlit_editjson/frontend/streamlit-component-lib.js",
)


def check_distribution(directory, tag=None):
    directory = Path(directory)
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected exactly one wheel and one source archive")

    with zipfile.ZipFile(wheels[0]) as wheel, tarfile.open(sources[0]) as source:
        metadata_paths = [
            n for n in wheel.namelist() if n.endswith(".dist-info/METADATA")
        ]
        if len(metadata_paths) != 1:
            raise ValueError("Expected one wheel metadata file")
        metadata = email.message_from_bytes(wheel.read(metadata_paths[0]))
        version = metadata["Version"]
        if metadata["Name"] != "streamlit-editjson" or not version:
            raise ValueError("Unexpected package metadata")
        if tag and tag != "v" + version:
            raise ValueError(
                f"Release tag {tag!r} does not match package version {version!r}"
            )

        source_metadata_paths = [
            n
            for n in source.getnames()
            if n.count("/") == 1 and n.endswith("/PKG-INFO")
        ]
        if len(source_metadata_paths) != 1:
            raise ValueError("Expected one source metadata file")
        source_metadata = email.message_from_bytes(
            source.extractfile(source_metadata_paths[0]).read()
        )
        if (source_metadata["Name"], source_metadata["Version"]) != (
            metadata["Name"],
            version,
        ):
            raise ValueError("Source and wheel metadata do not match")
        root = source_metadata_paths[0].rsplit("/", 1)[0]
        for name in REQUIRED_FILES:
            source_name = root + "/src/" + name
            if name not in wheel.namelist() or source_name not in source.getnames():
                raise ValueError(f"Missing packaged file: {name}")
            if wheel.read(name) != source.extractfile(source_name).read():
                raise ValueError(f"Source and wheel contents differ: {name}")
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--tag", help="Release tag, such as v1.1.0")
    args = parser.parse_args()
    try:
        version = check_distribution(args.dist_dir, args.tag)
    except (
        ValueError,
        KeyError,
        OSError,
        zipfile.BadZipFile,
        tarfile.TarError,
    ) as error:
        parser.exit(1, f"Distribution check failed: {error}\n")
    print(f"Validated streamlit-editjson {version}: wheel, source, and frontend assets")
