// The `Streamlit` object exists because our html file includes
// `streamlit-component-lib.js`.

const editorState = {
  initialized: false,
  sourceJson: null,
  data: null,
  keyEditable: false,
  valueEditable: true,
  collapsed: new WeakSet(),
  rejections: new Map(),
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
function stringifyJson(value, pretty = false, depth = 0) {
  if (typeof value === "bigint") return value.toString();
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  const array = Array.isArray(value);
  const entries = array
    ? value.map((item) => stringifyJson(item, pretty, depth + 1))
    : Object.keys(value).map((key) =>
      JSON.stringify(key) + (pretty ? ": " : ":") + stringifyJson(value[key], pretty, depth + 1),
    );
  const open = array ? "[" : "{";
  const close = array ? "]" : "}";
  if (!pretty || entries.length === 0) return open + entries.join(",") + close;
  const indent = "  ".repeat(depth + 1);
  return open + "\n" + indent + entries.join(",\n" + indent) + "\n" + "  ".repeat(depth) + close;
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
  input.readOnly = !editable;
  input.disabled = false;
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
  input.title = String(value);
  input.style.width = `${Math.max(6, String(value).length + 2)}ch`;
  input.readOnly = !editable;
  input.disabled = false;
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
  select.setAttribute("data-value", select.value);
  return select;
}

function parseLoosePrimitive(text) {
  const trimmed = text.trim();
  if (trimmed.startsWith('"')) {
    try {
      return JSON.parse(trimmed);
    } catch (_) {
      throw new SyntaxError('Enter a complete quoted JSON string, such as "hello", or plain text without quotes.');
    }
  }

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

let copyButtonReady = false;

function resetCopyStatus() {
  document.getElementById("copy-status").textContent = "";
  document.getElementById("copy-fallback").hidden = true;
}

async function copyJson() {
  const text = stringifyJson(editorState.data, true);
  const button = document.getElementById("copy-json");
  const status = document.getElementById("copy-status");
  const fallback = document.getElementById("copy-fallback");
  resetCopyStatus();
  button.disabled = true;
  try {
    await navigator.clipboard.writeText(text);
    if (text === stringifyJson(editorState.data, true)) status.textContent = "Copied JSON";
  } catch (_) {
    if (text === stringifyJson(editorState.data, true)) {
      status.textContent = "Clipboard unavailable. Select the JSON below and copy it.";
      fallback.value = text;
      fallback.hidden = false;
      fallback.focus();
      fallback.select();
    }
  } finally {
    button.disabled = false;
    Streamlit.setFrameHeight(document.body.scrollHeight + 20);
  }
}

function setupCopyButton() {
  if (copyButtonReady) return;
  document.getElementById("copy-json").addEventListener("click", copyJson);
  copyButtonReady = true;
  resetCopyStatus();
}

function emitChange() {
  resetCopyStatus();
  sendValue();
  Streamlit.setFrameHeight(document.body.scrollHeight + 20);
}

const fieldErrors = new WeakMap();
let errorId = 0;

function bindFieldError(input, container, kind, path) {
  const error = createLabel("", "json-error");
  error.id = `json-error-${++errorId}`;
  error.setAttribute("role", "alert");
  error.hidden = true;
  container.appendChild(error);
  const key = JSON.stringify([kind, ...path]);
  fieldErrors.set(input, {error, key});
  if (input.readOnly || input.disabled) {
    editorState.rejections.delete(key);
  } else if (editorState.rejections.has(key)) {
    const rejected = editorState.rejections.get(key);
    input.value = rejected.value;
    showFieldError(input, rejected.message, false);
  }
}

function showFieldError(input, message, resize = true) {
  const {error, key} = fieldErrors.get(input);
  error.textContent = message;
  error.hidden = false;
  input.setCustomValidity(message);
  input.setAttribute("aria-invalid", "true");
  input.setAttribute("aria-describedby", error.id);
  editorState.rejections.set(key, {value: input.value, message});
  if (resize) Streamlit.setFrameHeight(document.body.scrollHeight + 20);
}

function clearFieldError(input) {
  const {error, key} = fieldErrors.get(input);
  error.textContent = "";
  error.hidden = true;
  input.setCustomValidity("");
  input.removeAttribute("aria-invalid");
  input.removeAttribute("aria-describedby");
  editorState.rejections.delete(key);
}

function moveRejectedPaths(oldPath, newPath) {
  for (const [key, value] of [...editorState.rejections]) {
    const [kind, ...path] = JSON.parse(key);
    if (oldPath.every((part, index) => path[index] === part)) {
      editorState.rejections.delete(key);
      editorState.rejections.set(JSON.stringify([kind, ...newPath, ...path.slice(oldPath.length)]), value);
    }
  }
}

function createColourPreview(input) {
  const swatch = document.createElement("span");
  swatch.className = "json-color";
  swatch.setAttribute("role", "img");
  const fill = document.createElement("span");
  fill.className = "json-color-fill";
  swatch.appendChild(fill);
  const update = () => {
    const valid = /^#(?:[a-f0-9]{3}|[a-f0-9]{4}|[a-f0-9]{6}|[a-f0-9]{8})$/i.test(input.value);
    swatch.hidden = !valid;
    fill.style.backgroundColor = valid ? input.value : "transparent";
    swatch.setAttribute("aria-label", valid ? `Colour preview ${input.value}` : "Colour preview");
    swatch.title = valid ? input.value : "";
  };
  input.addEventListener("input", update);
  update();
  return swatch;
}

function presentValue(parentRow, input, valueType, path) {
  const type = valueType === "bigint" ? "number" : valueType;
  const field = document.createElement("div");
  field.className = `json-field json-field-${type}`;
  const control = document.createElement("div");
  control.className = "json-control";
  const quote = () => {
    const mark = createLabel('"', "json-quote");
    mark.setAttribute("aria-hidden", "true");
    return mark;
  };
  if (type === "string") {
    control.appendChild(createColourPreview(input));
    control.appendChild(quote());
  }
  control.appendChild(input);
  if (type === "string") control.appendChild(quote());
  field.appendChild(control);
  field.appendChild(createLabel(type, "json-type"));
  bindFieldError(input, field, "value", path);
  parentRow.appendChild(field);
  return field;
}

function renderPrimitiveControl(parentRow, value, onChange, label = "Value", path = []) {
  const editable = editorState.valueEditable;
  const valueType = value === null ? "null" : typeof value;
  let field;
  const commitValue = (input, nextValue) => {
    const focused = document.activeElement === input;
    const nextType = nextValue === null ? "null" : typeof nextValue;
    clearFieldError(input);
    onChange(nextValue);
    if (nextType !== valueType) {
      const staging = document.createElement("div");
      const replacement = renderPrimitiveControl(staging, nextValue, onChange, label, path);
      parentRow.replaceChild(replacement.field, field);
      if (focused) replacement.input.focus();
    } else if (nextType === "number" || nextType === "bigint") {
      input.title = String(nextValue);
    }
    emitChange();
  };

  if (valueType === "number" || valueType === "bigint") {
    const input = createNumberInput(value, editable);
    input.setAttribute("aria-label", label);
    input.addEventListener("input", () => {
      input.style.width = `${Math.max(6, input.value.length + 2)}ch`;
    });
    input.addEventListener("change", () => {
      if (!editable) return;
      const text = input.value.trim();
      const nextValue = parseNumber(text);
      if (
        !/^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text) ||
        (typeof nextValue !== "bigint" && !Number.isFinite(nextValue))
      ) {
        showFieldError(input, text === ""
          ? "Enter a number. The last valid value is kept."
          : "Enter a finite number, such as 0 or 1.5. The last valid value is kept.");
        return;
      }
      commitValue(input, nextValue);
    });
    field = presentValue(parentRow, input, valueType, path);
    return {field, input};
  }

  if (valueType === "boolean") {
    const select = createBooleanSelect(value, editable);
    select.setAttribute("aria-label", label);
    select.addEventListener("change", () => {
      if (!editable) return;
      select.setAttribute("data-value", select.value);
      commitValue(select, select.value === "true");
    });
    field = presentValue(parentRow, select, valueType, path);
    return {field, input: select};
  }

  const text = value === null ? "null" : String(value);
  const input = createTextInput(
    text, "json-value json-value-text", editable, typeof value === "string",
  );
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => {
    if (!editable) return;
    let nextValue;
    try {
      nextValue = typeof value === "string" ? input.value : parseLoosePrimitive(input.value);
    } catch (error) {
      if (!(error instanceof RangeError) && !(error instanceof SyntaxError)) {
        throw error;
      }
      showFieldError(input, error.message);
      return;
    }
    commitValue(input, nextValue);
  });
  field = presentValue(parentRow, input, valueType, path);
  return {field, input};
}

function renderNode(container, value, indentLevel, openingRow = null, path = []) {
  if (Array.isArray(value)) {
    renderArray(container, value, indentLevel, openingRow, path);
    return;
  }

  if (value !== null && typeof value === "object") {
    renderObject(container, value, indentLevel, openingRow, path);
    return;
  }

  const row = document.createElement("div");
  row.className = "json-row";
  renderPrimitiveControl(row, value, (nextValue) => {
    editorState.data = nextValue;
  }, "Value", path);
  container.appendChild(row);
}

let collectionId = 0;

function createCollection(container, value, indentLevel, openingRow) {
  const isArray = Array.isArray(value);
  const count = isArray ? value.length : Object.keys(value).length;
  const unit = isArray ? (count === 1 ? "item" : "items") : (count === 1 ? "property" : "properties");
  const kind = isArray ? "array" : "object";
  const row = openingRow || document.createElement("div");
  if (!openingRow) {
    row.className = "json-row";
    container.appendChild(row);
  }
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "json-toggle";
  row.insertBefore(toggle, row.children[0] || null);
  row.appendChild(createLabel(isArray ? "[" : "{", "json-punct"));
  const closed = createLabel(isArray ? "\u2026 ]" : "\u2026 }", "json-collapsed-end json-punct");
  row.appendChild(closed);
  row.appendChild(createLabel(`${count} ${unit}`, "json-count"));

  const body = document.createElement("div");
  body.className = "json-children";
  body.id = `json-collection-${++collectionId}`;
  toggle.setAttribute("aria-controls", body.id);
  container.appendChild(body);
  const update = () => {
    const collapsed = editorState.collapsed.has(value);
    toggle.textContent = collapsed ? "\u25b8" : "\u25be";
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", `${collapsed ? "Expand" : "Collapse"} ${kind}, ${count} ${unit}`);
    body.hidden = collapsed;
    closed.hidden = !collapsed;
  };
  toggle.addEventListener("click", () => {
    if (editorState.collapsed.has(value)) {
      editorState.collapsed.delete(value);
    } else {
      editorState.collapsed.add(value);
    }
    update();
    Streamlit.setFrameHeight(document.body.scrollHeight + 20);
  });
  update();
  return body;
}

function renderObject(container, obj, indentLevel, openingRow = null, path = []) {
  container = createCollection(container, obj, indentLevel, openingRow);

  const entries = Object.entries(obj);

  entries.forEach(([entryKey, entryValue]) => {
    const row = document.createElement("div");
    row.className = "json-row";

    let currentKey = entryKey;
    const keyInput = createTextInput(
      currentKey,
      "json-key",
      editorState.keyEditable,
    );

    keyInput.disabled = false;
    keyInput.readOnly = !editorState.keyEditable;
    keyInput.setAttribute("aria-label", `Key ${currentKey}`);
    keyInput.title = currentKey;
    keyInput.spellcheck = false;
    const keyField = document.createElement("div");
    keyField.className = "json-key-field";
    keyField.appendChild(keyInput);
    bindFieldError(keyInput, keyField, "key", path.concat(entryKey));
    keyInput.addEventListener("change", () => {
      const nextKey = keyInput.value.trim();

      if (!editorState.keyEditable) {
        keyInput.value = currentKey;
        return;
      }
      if (nextKey.length === 0) {
        showFieldError(keyInput, "Keys cannot be empty. The original key is kept.");
        return;
      }
      if (nextKey === currentKey) {
        clearFieldError(keyInput);
        keyInput.value = currentKey;
        return;
      }
      if (Object.prototype.hasOwnProperty.call(obj, nextKey)) {
        showFieldError(keyInput, `The key "${nextKey}" already exists. Choose a unique key.`);
        return;
      }
      clearFieldError(keyInput);
      moveRejectedPaths(path.concat(currentKey), path.concat(nextKey));

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

    row.appendChild(keyField);
    row.appendChild(createLabel(": ", "json-punct"));

    if (entryValue !== null && typeof entryValue === "object") {
      container.appendChild(row);
      renderNode(container, entryValue, indentLevel + 1, row, path.concat(entryKey));
    } else {
      renderPrimitiveControl(row, entryValue, (nextValue) => {
        obj[currentKey] = nextValue;
      }, `Value for ${currentKey}`, path.concat(entryKey));
      container.appendChild(row);
    }
  });

  const close = createLabel("}", "json-close json-punct");
  container.appendChild(close);
}

function renderArray(container, arr, indentLevel, openingRow = null, path = []) {
  container = createCollection(container, arr, indentLevel, openingRow);

  arr.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "json-row";
    row.appendChild(createLabel(`${index}: `, "json-index"));

    if (item !== null && typeof item === "object") {
      container.appendChild(row);
      renderNode(container, item, indentLevel + 1, row, path.concat(index));
    } else {
      renderPrimitiveControl(row, item, (nextValue) => {
        arr[index] = nextValue;
      }, `Value at index ${index}`, path.concat(index));
      container.appendChild(row);
    }
  });

  const close = createLabel("]", "json-close json-punct");
  container.appendChild(close);
}

function renderEditor() {
  setupCopyButton();
  const jsonContainer = document.getElementById("json-container");
  jsonContainer.innerHTML = "";
  renderNode(jsonContainer, editorState.data, 0);
  Streamlit.setFrameHeight(document.body.scrollHeight + 20);
}

/**
 * Called whenever the component receives data from Streamlit.
 */
function onRender(event) {
  const theme = event.detail.theme || {};
  document.getElementById("root").setAttribute("data-theme", theme.base === "dark" ? "dark" : "light");
  const {
    json_str,
    key_editable = false,
    value_editable = true,
  } = event.detail.args;

  const shouldReset =
    !editorState.initialized || editorState.sourceJson !== json_str;

  if (shouldReset) {
    editorState.data = parseJson(json_str);
    editorState.collapsed = new WeakSet();
    editorState.rejections.clear();
    editorState.sourceJson = json_str;
    editorState.initialized = true;
  }

  const permissionsChanged = editorState.keyEditable !== Boolean(key_editable) ||
    editorState.valueEditable !== Boolean(value_editable);
  editorState.keyEditable = Boolean(key_editable);
  editorState.valueEditable = Boolean(value_editable);

  // Streamlit also sends render events after iframe height updates and reruns.
  // Preserve focus and uncommitted drafts when the editor's inputs are unchanged.
  if (shouldReset || permissionsChanged) {
    renderEditor();
  } else {
    Streamlit.setFrameHeight(document.body.scrollHeight + 20);
  }

  if (shouldReset) {
    resetCopyStatus();
    sendValue();
  }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(120);
