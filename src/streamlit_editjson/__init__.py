import json
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components

# Tell streamlit that there is a component called streamlit_editjson,
# and that the code to display that component is in the "frontend" folder
frontend_dir = (Path(__file__).parent / "frontend").absolute()
_component_func = components.declare_component(
    "streamlit_editjson", path=str(frontend_dir)
)


# Create the python function that will be called
def editjson(
    filepath: str,
    key_editable: Optional[bool] = False,
    value_editable: Optional[bool] = True,
    key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Render a JSON editor component and return the edited JSON as a Python dict.

    Args:
        filepath: Path to a JSON file.
        key_editable: Whether JSON keys can be edited. Default is False.
        value_editable: Whether JSON values can be edited. Default is True.
        key: Optional Streamlit component key.

    Returns:
        The edited JSON object as a Python dict.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        json_obj = json.load(f)

    component_value = _component_func(
        json_str=json.dumps(json_obj),
        key_editable=key_editable,
        value_editable=value_editable,
        key=key,
        default=json_obj,
    )

    if component_value is None:
        return json_obj

    return component_value


def main():
    st.write("## Example")
    value = editjson("test.json", key_editable=False, value_editable=True)
    st.write(value)


if __name__ == "__main__":
    main()
