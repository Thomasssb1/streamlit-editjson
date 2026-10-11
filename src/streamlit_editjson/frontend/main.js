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

// JSON.parse rounds integer tokens before a reviver can see them. Parse a
// second copy with unsafe integer tokens quoted, then restore only numeric
// positions as BigInt. Genuine strings (including object keys) stay strings.
function parseJson(source) {
  const quoted = source.replace(
    /"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
    (token) => /^-?\d+$/.test(token) && !Number.isSafeInteger(Number(token))
      ? JSON.stringify(token)
      : token,
  );
  const data = JSON.parse(source);
  if (quoted === source) {
    return data;
  }
  function restore(value, exact) {
    if (typeof value === "number" && typeof exact === "string") {
      return BigInt(exact);
    }
    if (value !== null && typeof value === "object") {
      Object.keys(value).forEach((key) => {
        value[key] = restore(value[key], exact[key]);
      });
    }
    return value;
  }
  return restore(data, JSON.parse(quoted));
}

// Send JSON text through Streamlit so Python, rather than the browser's
// number serializer, decodes integer tokens into arbitrary-precision ints.
function stringifyJson(value) {
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (Array.isArray(value)) {
    return "[" + value.map(stringifyJson).join(",") + "]";
  }
  if (value !== null && typeof value === "object") {
    return "{" + Object.keys(value).map((key) =>
      JSON.stringify(key) + ":" + stringifyJson(value[key]),
    ).join(",") + "}";
  }
  return JSON.stringify(value);
}

function parseNumber(text) {
  const trimmed = text.trim();
  if (/^-?\d+$/.test(trimmed) && !Number.isSafeInteger(Number(trimmed))) {
    return BigInt(trimmed);
  }
  return Number(trimmed);
}

function createLabel(text, className) {
  const node = document.createElement("span");
  node.className = className;
  node.textContent = text;
  return node;
}

function createTextInput(value, className, editable, multiline = false) {
  const input = document.createElement(multiline ? "textarea" : "input");
  input.className = className;
  if (!multiline) {
    input.type = "text";
  }
  input.value = value;
  input.disabled = !editable;
  if (multiline) {
    const updateRows = () => {
      input.rows = Math.min(8, input.value.split(/\r\n|\r|\n/).length);
    };
    updateRows();
    input.addEventListener("input", () => {
      updateRows();
      Streamlit.setFrameHeight(document.body.scrollHeight + 20);
    });
  }
  return input;
}

function createNumberInput(value, editable) {
  const input = document.createElement("input");
  input.className = "json-value json-value-number";
  input.type = typeof value === "bigint" ? "text" : "number";
  input.inputMode = "decimal";
  input.step = "any";
  input.required = true;
  input.value = String(value);
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

  const asNumber = parseNumber(trimmed);
  if (trimmed !== "" && !Number.isNaN(asNumber)) {
    if (typeof asNumber !== "bigint" && !Number.isFinite(asNumber)) {
      throw new RangeError("Enter a finite number. This value is not saved.");
    }
    return asNumber;
  }

  return text;
}

function sendValue() {
  // Bytes distinguish serialized JSON from raw strings sent by older frontends.
  Streamlit.setComponentValue(new TextEncoder().encode(stringifyJson(editorState.data)));
}

function emitChange() {
  sendValue();
  Streamlit.setFrameHeight(document.body.scrollHeight + 20);
}

function renderPrimitiveControl(parentRow, value, onChange) {
  const editable = editorState.valueEditable;
  const valueType = value === null ? "null" : typeof value;

  if (valueType === "number" || valueType === "bigint") {
    const input = createNumberInput(value, editable);
    input.addEventListener("input", () => input.setCustomValidity(""));
    input.addEventListener("change", () => {
      const text = input.value.trim();
      const nextValue = parseNumber(text);
      if (
        !/^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text) ||
        (typeof nextValue !== "bigint" && !Number.isFinite(nextValue))
      ) {
        input.setCustomValidity("Enter a finite number. Empty or invalid values are not saved.");
        input.reportValidity();
        return;
      }
      input.setCustomValidity("");
      onChange(nextValue);
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
  const input = createTextInput(
    text, "json-value json-value-text", editable, typeof value === "string",
  );
  input.addEventListener("input", () => input.setCustomValidity(""));
  input.addEventListener("change", () => {
    let nextValue;
    try {
      nextValue = typeof value === "string" ? input.value : parseLoosePrimitive(input.value);
    } catch (error) {
      if (!(error instanceof RangeError)) {
        throw error;
      }
      input.setCustomValidity(error.message);
      input.reportValidity();
      return;
    }
    input.setCustomValidity("");
    onChange(nextValue);
    emitChange();
  });
  parentRow.appendChild(input);
}

function renderNode(container, value, indentLevel, openingRow = null) {
  if (Array.isArray(value)) {
    renderArray(container, value, indentLevel);
    return;
  }

  if (value !== null && typeof value === "object") {
    renderObject(container, value, indentLevel, openingRow);
    return;
  }

  const row = document.createElement("div");
  row.className = "json-row";
  row.style.marginLeft = `${indentLevel * INDENT_PX}px`;
  renderPrimitiveControl(row, value, (nextValue) => {
    editorState.data = nextValue;
    sendValue();
  });
  container.appendChild(row);
}

function renderObject(container, obj, indentLevel, openingRow = null) {
  const open = createLabel("{", "json-punct");
  if (openingRow) {
    openingRow.appendChild(open);
  } else {
    open.style.marginLeft = `${indentLevel * INDENT_PX}px`;
    container.appendChild(open);
  }

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

      // Define an own data property: assignment to __proto__ would invoke
      // Object.prototype's setter and discard the renamed JSON entry.
      Object.defineProperty(obj, nextKey, {
        value: obj[currentKey],
        writable: true,
        enumerable: true,
        configurable: true,
      });
      delete obj[currentKey];
      currentKey = nextKey;

      renderEditor();
      emitChange();
    });

    row.appendChild(keyInput);
    row.appendChild(createLabel(": ", "json-punct"));

    if (entryValue !== null && typeof entryValue === "object") {
      container.appendChild(row);
      renderNode(container, entryValue, indentLevel + 1, row);
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
      renderNode(container, item, indentLevel + 1, row);
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
    editorState.data = parseJson(json_str);
    editorState.sourceJson = json_str;
    editorState.initialized = true;
  }

  editorState.keyEditable = Boolean(key_editable);
  editorState.valueEditable = Boolean(value_editable);

  renderEditor();

  if (shouldReset) {
    sendValue();
  }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(120);
