import json
import unittest
from pathlib import Path

from py_mini_racer import py_mini_racer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS_PATH = PROJECT_ROOT / "src" / "streamlit_editjson" / "frontend" / "main.js"


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
                  validationMessage: "",
                  setCustomValidity: function (message) { this.validationMessage = message; },
                  reportValidity: function () { return !this.validationMessage; },
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

    def _capture_render(self, data):
        ctx = self._ctx()
        ctx.eval(
            "var __emitted; var __emissionCount = 0; Streamlit.setComponentValue = function (v) { __emitted = v; __emissionCount++; };"
        )
        event = {"detail": {"args": {"json_str": json.dumps(data)}}}
        ctx.eval("onRender(" + json.dumps(event) + ");")
        return ctx

    def _returned_value(self, ctx):
        value = json.loads(ctx.eval("JSON.stringify(__emitted)"))
        return json.loads(value) if isinstance(value, str) else value

    def test_large_integers_round_trip_without_changing_strings(self):
        data = {
            "positive": 9007199254740993,
            "negative": -9007199254740993,
            "huge": 10**100 + 123,
            "nested": [9007199254740991, {"id": 9007199254740992}],
            "strings": [
                "9007199254740993",
                'quoted "9007199254740993"',
                "\\9007199254740993",
            ],
            "9007199254740993": True,
            "__proto__": {"id": 9007199254740993},
            "decimal": 1.25,
            "nothing": None,
        }
        self.assertEqual(self._returned_value(self._capture_render(data)), data)

    def test_large_integer_root_round_trip(self):
        value = -(10**100 + 123)
        self.assertEqual(self._returned_value(self._capture_render(value)), value)

    def test_number_edits_preserve_large_integer_digits(self):
        for original, edited in [
            (9007199254740993, "9007199254740995"),
            (12, "-9007199254740993"),
            (9007199254740993, "42"),
        ]:
            with self.subTest(original=original, edited=edited):
                ctx = self._capture_render({"id": original})
                result = json.loads(
                    ctx.eval(
                        """
                    JSON.stringify((function () {
                      var row = document.createElement("div");
                      renderPrimitiveControl(row, editorState.data.id, function (v) {
                        editorState.data.id = v;
                      });
                      var input = row.children[0];
                      var initial = input.value;
                      input.value = %s;
                      input._listener();
                      return { initial: initial };
                    })())
                """
                        % json.dumps(edited)
                    )
                )
                self.assertEqual(result["initial"], str(original))
                self.assertEqual(self._returned_value(ctx), {"id": int(edited)})

    def test_parse_loose_primitive_preserves_large_integers(self):
        ctx = self._ctx()
        self.assertEqual(
            ctx.eval('String(parseLoosePrimitive("9007199254740993"))'),
            "9007199254740993",
        )

    def test_parse_loose_primitive_all_primitives(self):
        ctx = self._ctx()

        self.assertIsNone(ctx.eval('parseLoosePrimitive(" null ")'))
        self.assertTrue(ctx.eval('parseLoosePrimitive("true")'))
        self.assertFalse(ctx.eval('parseLoosePrimitive("false")'))
        self.assertEqual(ctx.eval('parseLoosePrimitive("42")'), 42)
        self.assertEqual(ctx.eval('parseLoosePrimitive("3.5")'), 3.5)
        self.assertEqual(ctx.eval('parseLoosePrimitive("hello")'), "hello")
        self.assertEqual(ctx.eval('parseLoosePrimitive("   ")'), "   ")

    def test_invalid_numeric_edits_keep_last_value_and_report_error(self):
        for original in [12, 0, -1.5, 9007199254740993]:
            for draft in ["", "   ", "invalid", "Infinity", "1e999", "0x10"]:
                with self.subTest(original=original, draft=draft):
                    ctx = self._capture_render({"count": original})
                    result = json.loads(
                        ctx.eval(
                            """
                        JSON.stringify((function () {
                          var row = document.createElement("div");
                          renderPrimitiveControl(row, editorState.data.count, function (v) {
                            editorState.data.count = v;
                          });
                          var input = row.children[0];
                          input.value = %s;
                          input._listener();
                          return { error: input.validationMessage, emissions: __emissionCount };
                        })())
                    """
                            % json.dumps(draft)
                        )
                    )
                    self.assertEqual(self._returned_value(ctx), {"count": original})
                    self.assertEqual(result["emissions"], 1)
                    self.assertTrue(result["error"])

    def test_numeric_edit_recovers_after_empty_draft(self):
        for text, expected in [("0", 0), ("-2.5", -2.5), ("1e3", 1000), (".5", 0.5)]:
            with self.subTest(text=text):
                ctx = self._capture_render({"count": 7})
                result = json.loads(
                    ctx.eval(
                        """
                    JSON.stringify((function () {
                      var row = document.createElement("div");
                      renderPrimitiveControl(row, editorState.data.count, function (v) {
                        editorState.data.count = v;
                      });
                      var input = row.children[0];
                      input.value = "";
                      input._listener();
                      input.value = %s;
                      input._listener();
                      return { error: input.validationMessage, emissions: __emissionCount };
                    })())
                """
                        % json.dumps(text)
                    )
                )
                self.assertEqual(self._returned_value(ctx), {"count": expected})
                self.assertEqual(result["emissions"], 2)
                self.assertEqual(result["error"], "")

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

    def test_rename_to_proto_keeps_value_and_object_prototype(self):
        for value in [{"enabled": True}, [1, 2], 123, "text", None]:
            with self.subTest(value=value):
                ctx = self._capture_render({"old": value, "untouched": 7})
                result = json.loads(
                    ctx.eval("""
                    JSON.stringify((function () {
                      editorState.keyEditable = true;
                      var obj = editorState.data;
                      var prototype = Object.getPrototypeOf(obj);
                      var container = document.createElement("div");
                      renderObject(container, obj, 0);
                      var input = container.children[1].children[0];
                      input.value = "__proto__";
                      input._listener();
                      return {
                        samePrototype: Object.getPrototypeOf(obj) === prototype,
                        ownsKey: Object.prototype.hasOwnProperty.call(obj, "__proto__"),
                        hasOldKey: Object.prototype.hasOwnProperty.call(obj, "old")
                      };
                    })())
                """)
                )
                self.assertTrue(result["samePrototype"])
                self.assertTrue(result["ownsKey"])
                self.assertFalse(result["hasOldKey"])
                self.assertEqual(
                    self._returned_value(ctx), {"__proto__": value, "untouched": 7}
                )

    def test_rename_does_not_overwrite_existing_proto_property(self):
        data = {"old": 1, "__proto__": {"enabled": True}}
        ctx = self._capture_render(data)
        ctx.eval("""
            editorState.keyEditable = true;
            var container = document.createElement("div");
            renderObject(container, editorState.data, 0);
            var input = container.children[1].children[0];
            input.value = "__proto__";
            input._listener();
        """)
        self.assertEqual(self._returned_value(ctx), data)
        self.assertEqual(ctx.eval("input.value"), "old")

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
