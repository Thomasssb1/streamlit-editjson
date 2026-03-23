// The `Streamlit` object exists because our html file includes
// `streamlit-component-lib.js`.

const INDENT_PX = 18;

const editorState = {
  initialized: false,
  sourceJson: null,
  data: null,
  keyEditable: false,
  valueEditable: true,
};

function createLabel(text, className) {
  const node = document.createElement("span");
  node.className = className;
  node.textContent = text;
  return node;
}

function createTextInput(value, className, editable) {
  const input = document.createElement("input");
  input.className = className;
  input.type = "text";
  input.value = value;
  input.disabled = !editable;
  return input;
}

function createNumberInput(value, editable) {
  const input = document.createElement("input");
  input.className = "json-value json-value-number";
  input.type = "number";
  input.step = "any";
  input.value = Number.isFinite(value) ? String(value) : "0";
  input.disabled = !editable;
  return input;
}

function createBooleanSelect(value, editable) {
  const select = document.createElement("select");
  select.className = "json-value json-value-boolean";
  select.disabled = !editable;

  const trueOption = document.createElement("option");
  trueOption.value = "true";
  trueOption.textContent = "true";

  const falseOption = document.createElement("option");
  falseOption.value = "false";
  falseOption.textContent = "false";

  select.appendChild(trueOption);
  select.appendChild(falseOption);
  select.value = value ? "true" : "false";
  return select;
}

function parseLoosePrimitive(text) {
  const trimmed = text.trim();

  if (trimmed === "null") {
    return null;
  }
  if (trimmed === "true") {
    return true;
  }
  if (trimmed === "false") {
    return false;
  }

  const asNumber = Number(trimmed);
  if (trimmed !== "" && !Number.isNaN(asNumber)) {
    return asNumber;
  }

  return text;
}

function emitChange() {
  Streamlit.setComponentValue(editorState.data);
  Streamlit.setFrameHeight(document.body.scrollHeight + 20);
}

function renderPrimitiveControl(parentRow, value, onChange) {
  const editable = editorState.valueEditable;
  const valueType = value === null ? "null" : typeof value;

  if (valueType === "number") {
    const input = createNumberInput(value, editable);
    input.addEventListener("change", () => {
      onChange(Number(input.value));
      emitChange();
    });
    parentRow.appendChild(input);
    return;
  }

  if (valueType === "boolean") {
    const select = createBooleanSelect(value, editable);
    select.addEventListener("change", () => {
      onChange(select.value === "true");
      emitChange();
    });
    parentRow.appendChild(select);
    return;
  }

  const text = value === null ? "null" : String(value);
  const input = createTextInput(text, "json-value json-value-text", editable);
  input.addEventListener("change", () => {
    if (value === null) {
      onChange(parseLoosePrimitive(input.value));
    } else if (typeof value === "string") {
      onChange(input.value);
    } else {
      onChange(parseLoosePrimitive(input.value));
    }
    emitChange();
  });
  parentRow.appendChild(input);
}

function renderNode(container, value, indentLevel) {
  if (Array.isArray(value)) {
    renderArray(container, value, indentLevel);
    return;
  }

  if (value !== null && typeof value === "object") {
    renderObject(container, value, indentLevel);
    return;
  }

  const row = document.createElement("div");
  row.className = "json-row";
  row.style.marginLeft = `${indentLevel * INDENT_PX}px`;
  renderPrimitiveControl(row, value, (nextValue) => {
    editorState.data = nextValue;
    Streamlit.setComponentValue(editorState.data);
  });
  container.appendChild(row);
}

function renderObject(container, obj, indentLevel) {
  const open = createLabel("{", "json-punct");
  open.style.marginLeft = `${indentLevel * INDENT_PX}px`;
  container.appendChild(open);

  const entries = Object.entries(obj);

  entries.forEach(([entryKey, entryValue]) => {
    const row = document.createElement("div");
    row.className = "json-row";
    row.style.marginLeft = `${(indentLevel + 1) * INDENT_PX}px`;

    let currentKey = entryKey;
    const keyInput = createTextInput(
      currentKey,
      "json-key",
      editorState.keyEditable,
    );

    keyInput.addEventListener("change", () => {
      const nextKey = keyInput.value.trim();

      if (!editorState.keyEditable) {
        keyInput.value = currentKey;
        return;
      }
      if (nextKey.length === 0 || nextKey === currentKey) {
        keyInput.value = currentKey;
        return;
      }
      if (Object.prototype.hasOwnProperty.call(obj, nextKey)) {
        keyInput.value = currentKey;
        return;
      }

      obj[nextKey] = obj[currentKey];
      delete obj[currentKey];
      currentKey = nextKey;

      renderEditor();
      emitChange();
    });

    row.appendChild(keyInput);
    row.appendChild(createLabel(": ", "json-punct"));

    if (entryValue !== null && typeof entryValue === "object") {
      container.appendChild(row);
      renderNode(container, entryValue, indentLevel + 1);
    } else {
      renderPrimitiveControl(row, entryValue, (nextValue) => {
        obj[currentKey] = nextValue;
      });
      container.appendChild(row);
    }
  });

  const close = createLabel("}", "json-punct");
  close.style.marginLeft = `${indentLevel * INDENT_PX}px`;
  container.appendChild(close);
}

function renderArray(container, arr, indentLevel) {
  const open = createLabel("[", "json-punct");
  open.style.marginLeft = `${indentLevel * INDENT_PX}px`;
  container.appendChild(open);

  arr.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "json-row";
    row.style.marginLeft = `${(indentLevel + 1) * INDENT_PX}px`;
    row.appendChild(createLabel(`${index}: `, "json-index"));

    if (item !== null && typeof item === "object") {
      container.appendChild(row);
      renderNode(container, item, indentLevel + 1);
    } else {
      renderPrimitiveControl(row, item, (nextValue) => {
        arr[index] = nextValue;
      });
      container.appendChild(row);
    }
  });

  const close = createLabel("]", "json-punct");
  close.style.marginLeft = `${indentLevel * INDENT_PX}px`;
  container.appendChild(close);
}

function renderEditor() {
  const jsonContainer = document.getElementById("json-container");
  jsonContainer.innerHTML = "";
  renderNode(jsonContainer, editorState.data, 0);
  Streamlit.setFrameHeight(document.body.scrollHeight + 20);
}

/**
 * Called whenever the component receives data from Streamlit.
 */
function onRender(event) {
  const {
    json_str,
    key_editable = false,
    value_editable = true,
  } = event.detail.args;

  const shouldReset =
    !editorState.initialized || editorState.sourceJson !== json_str;

  if (shouldReset) {
    editorState.data = JSON.parse(json_str);
    editorState.sourceJson = json_str;
    editorState.initialized = true;
  }

  editorState.keyEditable = Boolean(key_editable);
  editorState.valueEditable = Boolean(value_editable);

  renderEditor();

  if (shouldReset) {
    Streamlit.setComponentValue(editorState.data);
  }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(120);
