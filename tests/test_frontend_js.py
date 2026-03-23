import json
import unittest
from pathlib import Path

from py_mini_racer import py_mini_racer


MAIN_JS_PATH = Path("src/streamlit_editjson/frontend/main.js")


class TestFrontendJS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_js = MAIN_JS_PATH.read_text(encoding="utf-8")

    def _ctx(self):
        ctx = py_mini_racer.MiniRacer()
        ctx.eval(
            """
            var window = {};
            var document = {
              body: { scrollHeight: 120 },
              getElementById: function () {
                return {
                  innerHTML: "",
                  appendChild: function () {}
                };
              },
              createElement: function (tag) {
                return {
                  tagName: tag,
                  className: "",
                  type: "",
                  step: "",
                  value: "",
                  disabled: false,
                  textContent: "",
                  style: {},
                  children: [],
                  appendChild: function (child) { this.children.push(child); },
                  addEventListener: function (_name, cb) { this._listener = cb; }
                };
              }
            };

            var Streamlit = {
              setComponentValue: function (_value) {},
              setFrameHeight: function (_height) {},
              setComponentReady: function () {},
              RENDER_EVENT: "render",
              events: {
                addEventListener: function (_event, _cb) {}
              }
            };
            """
        )
        ctx.eval(self.main_js)
        return ctx

    def test_parse_loose_primitive_all_primitives(self):
        ctx = self._ctx()

        self.assertIsNone(ctx.eval('parseLoosePrimitive(" null ")'))
        self.assertTrue(ctx.eval('parseLoosePrimitive("true")'))
        self.assertFalse(ctx.eval('parseLoosePrimitive("false")'))
        self.assertEqual(ctx.eval('parseLoosePrimitive("42")'), 42)
        self.assertEqual(ctx.eval('parseLoosePrimitive("3.5")'), 3.5)
        self.assertEqual(ctx.eval('parseLoosePrimitive("hello")'), "hello")
        self.assertEqual(ctx.eval('parseLoosePrimitive("   ")'), "   ")

    def test_create_boolean_select_shape(self):
        ctx = self._ctx()

        payload_true = json.loads(
            ctx.eval(
                """
                JSON.stringify((function () {
                  var s = createBooleanSelect(true, false);
                  return {
                    className: s.className,
                    disabled: s.disabled,
                    value: s.value,
                    childCount: s.children.length,
                    optionValues: s.children.map(function (x) { return x.value; })
                  };
                })())
                """
            )
        )

        self.assertEqual(payload_true["className"], "json-value json-value-boolean")
        self.assertTrue(payload_true["disabled"])
        self.assertEqual(payload_true["value"], "true")
        self.assertEqual(payload_true["childCount"], 2)
        self.assertEqual(payload_true["optionValues"], ["true", "false"])

        payload_false = json.loads(
            ctx.eval(
                """
                JSON.stringify((function () {
                  var s = createBooleanSelect(false, true);
                  return {
                    disabled: s.disabled,
                    value: s.value
                  };
                })())
                """
            )
        )
        self.assertFalse(payload_false["disabled"])
        self.assertEqual(payload_false["value"], "false")

    def test_render_primitive_control_dispatches_correct_creator(self):
        ctx = self._ctx()

        ctx.eval(
            """
            var __calls = [];
            createNumberInput = function (value, editable) {
              __calls.push(["number", value, editable]);
              return { addEventListener: function () {} };
            };
            createBooleanSelect = function (value, editable) {
              __calls.push(["boolean", value, editable]);
              return { addEventListener: function () {} };
            };
            createTextInput = function (value, className, editable) {
              __calls.push(["text", value, className, editable]);
              return { addEventListener: function () {} };
            };

            editorState.valueEditable = true;
            var __parent = { children: [], appendChild: function (x) { this.children.push(x); } };

            renderPrimitiveControl(__parent, 7, function () {});
            renderPrimitiveControl(__parent, true, function () {});
            renderPrimitiveControl(__parent, "abc", function () {});
            renderPrimitiveControl(__parent, null, function () {});
            """
        )

        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))

        self.assertEqual(calls[0], ["number", 7, True])
        self.assertEqual(calls[1], ["boolean", True, True])
        self.assertEqual(calls[2], ["text", "abc", "json-value json-value-text", True])
        self.assertEqual(calls[3], ["text", "null", "json-value json-value-text", True])

    def test_render_object_key_rename_updates_underlying_object(self):
        ctx = self._ctx()

        result = json.loads(
            ctx.eval(
                """
                JSON.stringify((function () {
                  editorState.keyEditable = true;
                  var obj = { old_key: 123 };
                  editorState.data = obj;
                  var container = {
                    children: [],
                    appendChild: function (x) { this.children.push(x); }
                  };

                  renderObject(container, obj, 0);

                  var keyInput = container.children[1].children[0];
                  keyInput.value = "new_key";
                  keyInput._listener();

                  return {
                    hasOldKey: Object.prototype.hasOwnProperty.call(obj, "old_key"),
                    hasNewKey: Object.prototype.hasOwnProperty.call(obj, "new_key"),
                    newValue: obj.new_key
                  };
                })())
                """
            )
        )

        self.assertFalse(result["hasOldKey"])
        self.assertTrue(result["hasNewKey"])
        self.assertEqual(result["newValue"], 123)

    def test_render_object_key_rename_rejects_empty_and_collision(self):
        ctx = self._ctx()

        result = json.loads(
            ctx.eval(
                """
                JSON.stringify((function () {
                  editorState.keyEditable = true;
                  var obj = { first: 1, second: 2 };
                  editorState.data = obj;
                  var container = {
                    children: [],
                    appendChild: function (x) { this.children.push(x); }
                  };

                  renderObject(container, obj, 0);
                  var firstKeyInput = container.children[1].children[0];

                  firstKeyInput.value = "   ";
                  firstKeyInput._listener();

                  var keysAfterEmpty = Object.keys(obj).sort();

                  firstKeyInput.value = "second";
                  firstKeyInput._listener();

                  var keysAfterCollision = Object.keys(obj).sort();

                  return {
                    keysAfterEmpty: keysAfterEmpty,
                    keysAfterCollision: keysAfterCollision,
                    firstValue: obj.first,
                    secondValue: obj.second
                  };
                })())
                """
            )
        )

        self.assertEqual(result["keysAfterEmpty"], ["first", "second"])
        self.assertEqual(result["keysAfterCollision"], ["first", "second"])
        self.assertEqual(result["firstValue"], 1)
        self.assertEqual(result["secondValue"], 2)


if __name__ == "__main__":
    unittest.main()