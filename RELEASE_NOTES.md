# streamlit-editjson 1.1.0

## Editor improvements

- Keep opening braces beside their keys and collapse objects and arrays with item counts.
- Use cleaner rows, accessible field labels, and distinct presentation for strings, numbers, booleans, and null.
- Change any JSON value's type using a dropdown, including root values, objects, and arrays. Preserve compatible values and confirm replacements inline.
- Preview hex colours, including transparency.
- Copy formatted JSON with a brief confirmation on the button and selectable text when clipboard access is unavailable.
- Explain rejected edits beside the field and preserve drafts through Streamlit reruns.

## Fixes

- Preserve large integers, multiline strings, and keys named `__proto__` without corrupting JSON.
- Reject invalid and non-finite numbers while keeping the last valid data.
- Refresh controls and type colours immediately after a type change, and decode quoted strings when converting null.
- Keep other fields editable while an error is visible and avoid repeated iframe resizing.
- Remove textarea resize handles.
- Restore compatibility with the legacy `editable` keyword.

## Install or upgrade

```sh
python -m pip install --upgrade streamlit-editjson==1.1.0
```
