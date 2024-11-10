// The `Streamlit` object exists because our html file includes
// `streamlit-component-lib.js`.
// If you get an error about "Streamlit" not being defined, that
// means you're missing that file.

function sendValue(value) {
  Streamlit.setComponentValue(value);
}

/**
 * The component's render function. This will be called immediately after
 * the component is initially loaded, and then again every time the
 * component gets new data from Python.
 */
function onRender(event) {
  // Only run the render code the first time the component is loaded.
  if (!window.rendered) {
    // You most likely want to get the data passed in like this
    // const {input1, input2, input3} = event.detail.args

    // You'll most likely want to pass some data back to Python like this
    // sendValue({output1: "foo", output2: "bar"})
    const { json_str, editable } = event.detail.args;

    const jsonContainer = document.getElementById("json-container");

    let json = JSON.parse(json_str);
    let labelledList = [];
    let structures = ["{", "}", "[", "]", '"', ",", ":"];

    labelledList = parse(json_str, structures, jsonContainer);
    console.log(labelledList);

    Streamlit.setFrameHeight(json_str.split("\n").length * 30);

    window.rendered = true;
  }
}

function parse(data, structures, jsonContainer) {
  function createInput(data) {
    let lineDiv = document.createElement("input");
    lineDiv.style.display = "inline-block";
    lineDiv.innerText = data;
    lineDiv.id = "input-" + data;
    return lineDiv;
  }

  function createPre(data) {
    let lineDiv = document.createElement("pre");
    lineDiv.style.display = "inline-block";
    lineDiv.innerText = data;
    return lineDiv;
  }

  let labelledList = [];
  let stringList = [];
  let lastStructureIndex = -1;
  for (let i = 0; i < data.length; i++) {
    let current = data[i];
    if (structures.includes(current)) {
      if (current == '"') {
        if (current == data[lastStructureIndex]) {
          let stringData = stringList.join("");
          labelledList.push(stringData);
          jsonContainer.appendChild(createInput(stringData));
        }
        stringList = [];
      } else if (current == ":") {
        let stringData = labelledList[labelledList.length - 2];
        let oldInput = document.getElementById("input-" + stringData);
        jsonContainer.replaceChild(createPre(stringData), oldInput);
      } else if (current == "," || current == "}") {
        let stringData = stringList.join("").substring(1, stringList.length);
        labelledList.push(stringData);
        jsonContainer.appendChild(createInput(stringData));
        stringList = [];
      }
      labelledList.push(current);
      jsonContainer.appendChild(createPre(current));
      lastStructureIndex = i;
    } else if (
      data[lastStructureIndex] == ":" ||
      data[lastStructureIndex] == '"'
    ) {
      stringList.push(current);
    }
  }
  return labelledList;
}

// Render the component whenever python send a "render event"
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
// Tell Streamlit that the component is ready to receive events
Streamlit.setComponentReady();
// Render with the correct height, if this is a fixed-height component
Streamlit.setFrameHeight(100);
