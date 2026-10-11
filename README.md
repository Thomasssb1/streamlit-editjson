# streamlit-editjson

A Streamlit component to view and edit JSON with a user-friendly UI.

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
- `editable`: deprecated keyword-only alias for `value_editable`.

The component returns the edited JSON object as a Python `dict`.
Integer values retain their exact digits, including integers outside JavaScript's
safe-integer range, when loaded, edited, and returned to Python.
Clearing a number field, or entering an invalid number, keeps its last valid value
and displays a validation error. Enter `0` explicitly to set a value to zero.
String values use text areas so line breaks remain visible and editable.

## Migrating from `editable`

The old `editable=` keyword still works and emits a `DeprecationWarning` pointing
at the caller. Replace it with `value_editable=`:

```python
# Before (still supported with a deprecation warning)
value = editjson("test.json", editable=False, key="editor")

# After
value = editjson("test.json", value_editable=False, key="editor")
```

If both keywords are supplied, the explicit `value_editable` wins. The alias does
not change `key_editable`, which remains `False` by default.

This compatibility alias applies to keyword calls. Rewrite old positional calls
such as `editjson(path, False, "editor")` as
`editjson(path, value_editable=False, key="editor")`; positional arguments now
mean `filepath, key_editable, value_editable, key`.

## Testing

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
