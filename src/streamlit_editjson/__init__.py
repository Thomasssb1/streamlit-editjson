import json
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Union

import streamlit as st
import streamlit.components.v1 as components

# Tell streamlit that there is a component called streamlit_editjson,
# and that the code to display that component is in the "frontend" folder
frontend_dir = (Path(__file__).parent / "frontend").absolute()
_component_func = components.declare_component(
    "streamlit_editjson", path=str(frontend_dir)
)


class _Unset:
    """Distinguish omitted flags from explicit True, False, or None."""


_UNSET = _Unset()


# Create the python function that will be called
def editjson(
    filepath: str,
    key_editable: Optional[bool] = False,
    value_editable: Union[bool, None, _Unset] = _UNSET,
    key: Optional[str] = None,
    *,
    editable: Union[bool, None, _Unset] = _UNSET,
) -> Dict[str, Any]:
    """
    Render a JSON editor component and return the edited JSON as a Python dict.

    Args:
        filepath: Path to a JSON file.
        key_editable: Whether JSON keys can be edited. Default is False.
        value_editable: Whether JSON values can be edited. Default is True.
        key: Optional Streamlit component key.
        editable: Deprecated keyword-only alias for value_editable. If both are
            supplied, value_editable takes precedence. Keys are unaffected.

    Returns:
        The edited JSON object as a Python dict.
    """
    if editable is not _UNSET:
        warnings.warn(
            "editable is deprecated; use value_editable instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if value_editable is _UNSET:
            value_editable = editable
    if value_editable is _UNSET:
        value_editable = True

    with open(filepath, "r", encoding="utf-8") as f:
        json_obj = json.load(f)

    json_str = json.dumps(json_obj)
    component_value = _component_func(
        json_str=json_str,
        key_editable=key_editable,
        value_editable=value_editable,
        key=key,
        default=json_str,
    )

    if component_value is None:
        return json_obj

    # The frontend returns JSON text to preserve integers beyond JavaScript's
    # safe range. Accept object values from an already-mounted older frontend.
    if isinstance(component_value, str):
        return json.loads(component_value)
    return component_value


def main():
    st.write("## Example")
    value = editjson("test.json", key_editable=False, value_editable=True)
    st.write(value)


if __name__ == "__main__":
    main()
