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
    console.log(json);
    console.log(json.split("\n"));

    console.log(`hi: ${json_str.split("\n").length}`);

    for (let line of json_str.split("\n")) {
      let lineDiv = document.createElement("pre");
      lineDiv.innerText = line;
      jsonContainer.appendChild(lineDiv);
    }

    Streamlit.setFrameHeight(json_str.split("\n").length * 30);

    window.rendered = true;
  }
}

// Render the component whenever python send a "render event"
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
// Tell Streamlit that the component is ready to receive events
Streamlit.setComponentReady();
// Render with the correct height, if this is a fixed-height component
Streamlit.setFrameHeight(100);
