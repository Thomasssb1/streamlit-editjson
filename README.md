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