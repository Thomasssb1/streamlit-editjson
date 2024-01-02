from pathlib import Path
from typing import Optional

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
    editable: Optional[bool] = True,
    key: Optional[str] = None,
):
    """
    Add a descriptive docstring
    """

    with open(filepath, "r") as f:
        json_str = f.read()

    component_value = _component_func(
        json_str=json_str,
        editable=editable,
        key=key,
        default=editable,
    )

    return component_value


def main():
    st.write("## Example")
    value = editjson("test.json", editable=True)

    st.write(value)


if __name__ == "__main__":
    main()
