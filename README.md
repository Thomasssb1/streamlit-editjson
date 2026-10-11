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

`editjson(filepath, key_editable=False, value_editable=True, key=None) -> dict`

- `filepath`: path to a JSON file.
- `key_editable`: allow editing JSON keys.
- `value_editable`: allow editing JSON values.
- `key`: optional Streamlit component key.

The component returns the edited JSON object as a Python `dict`.
Integer values retain their exact digits, including integers outside JavaScript's
safe-integer range, when loaded, edited, and returned to Python.
Clearing a number field, or entering an invalid number, keeps its last valid value
and displays a validation error. Enter `0` explicitly to set a value to zero.

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
