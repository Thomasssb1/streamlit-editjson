# streamlit-editjson
[![PyPI - Version](https://img.shields.io/badge/PyPI-v1.1.1-blue)](https://pypi.org/project/streamlit-editjson/1.1.1/)

A Streamlit component to view and edit JSON with a user-friendly UI.

![JSON editor showing nested settings, boolean controls, type dropdowns, hex colour previews, and Copy JSON](https://raw.githubusercontent.com/Thomasssb1/streamlit-editjson/75d744722f4dc03998f34dfcf01e403eda54a9fe/docs/images/example.png)

The bundled example, with collapsible objects, editable values, and colour previews.

## Installation

```sh
pip install streamlit-editjson
```

## Usage

```python
import streamlit as st
from streamlit_editjson import editjson

value = editjson(
    filepath="test.json",
    key_editable=False,   # default
    value_editable=True,  # default
)

st.write(value)  # Python dict
```

## API

`editjson(filepath, key_editable=False, value_editable=True, key=None, *, editable=...) -> dict`

- `filepath`: path to a JSON file.
- `key_editable`: allow editing JSON keys.
- `value_editable`: allow editing JSON values.
- `key`: optional Streamlit component key.
- `editable`: keyword-only compatibility alias for `value_editable`.

The component returns the edited JSON object as a Python `dict`.
Integer values retain their exact digits, including integers outside JavaScript's
safe-integer range, when loaded, edited, and returned to Python.
Clearing a number field, or entering an invalid number, keeps its last valid value
and explains the rejection next to the field. Rejected drafts stay visible until
corrected, including across Streamlit reruns. Empty or duplicate key renames also
show an inline explanation and keep the original key. Enter `0` explicitly to
set a numeric value to zero.
String values use text areas so line breaks remain visible and editable.

## Testing

Install the development dependencies so local checks use the same Ruff version
as CI:

```sh
python -m pip install -r requirements-dev.txt
python -m ruff check .
```

### Python unit tests

Run:

```sh
python -m unittest discover -s tests -p "test_*.py"
```

### Running locally

Run:

```sh
python -m streamlit run src/streamlit_editjson/__init__.py --server.port 8501
```
