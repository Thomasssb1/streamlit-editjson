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
        cls.bridge_js = MAIN_JS_PATH.with_name("streamlit-component-lib.js").read_text(
            encoding="utf-8"
        )

    def _ctx(self):
        ctx = py_mini_racer.MiniRacer()
        ctx.eval(
            r"""
            var __messages = [];
            var console = { log: function () {} };
            var window = {
              parent: { postMessage: function (message) { __messages.push(message); } },
              addEventListener: function () {}
            };
            // V8 has no browser TextEncoder; supply its UTF-8 API for bridge tests.
            function TextEncoder() {}
            TextEncoder.prototype.encode = function (text) {
              var utf8 = unescape(encodeURIComponent(text));
              return Uint8Array.from(utf8, function (c) { return c.charCodeAt(0); });
            };
            function findByClass(node, className) {
              var found = (node.className || "").split(" ").includes(className) ? [node] : [];
              return found.concat((node.children || []).flatMap(function (child) {
                return findByClass(child, className);
              }));
            }
            var document = {
              body: { scrollHeight: 120 },
              getElementById: function (id) {
                if (!this.nodes) this.nodes = {};
                if (!this.nodes[id]) this.nodes[id] = this.createElement("div");
                return this.nodes[id];
              },
              createElement: function (tag) {
                var element = {
                  tagName: tag,
                  className: "",
                  type: "",
                  step: "",
                  value: "",
                  disabled: false,
                  textContent: "",
                  style: {},
                  hidden: false,
                  attributes: {},
                  listeners: {},
                  setAttribute: function (name, value) { this.attributes[name] = String(value); },
                  getAttribute: function (name) { return this.attributes[name] || null; },
                  removeAttribute: function (name) { delete this.attributes[name]; },
                  children: [],
                  validationMessage: "",
                  focus: function () {},
                  select: function () {},
                  setCustomValidity: function (message) { this.validationMessage = message; },
                  reportValidity: function () { return !this.validationMessage; },
                  appendChild: function (child) { this.children.push(child); child.parentElement = this; },
                  replaceChild: function (child, old) {
                    var index = this.children.indexOf(old);
                    if (index < 0) throw new Error("Child not found");
                    this.children[index] = child;
                    child.parentElement = this;
                    old.parentElement = null;
                  },
                  insertBefore: function (child, before) {
                    var index = this.children.indexOf(before);
                    this.children.splice(index < 0 ? this.children.length : index, 0, child);
                    child.parentElement = this;
                  },
                  addEventListener: function (name, cb) {
                    if (!this.listeners[name]) this.listeners[name] = [];
                    this.listeners[name].push(cb);
                    this._listener = () => this.dispatchEvent({type: name});
                  },
                  dispatchEvent: function (event) {
                    (this.listeners[event.type] || []).forEach(cb => cb(event));
                  }
                };
                Object.defineProperty(element, "innerHTML", {
                  get: function () { return ""; },
                  set: function () { this.children = []; }
                });
                // Model the browser's single-line input value sanitization.
                Object.defineProperty(element, "value", {
                  get: function () { return this._value || ""; },
                  set: function (value) {
                    this._value = String(value);
                    if (tag === "input" && this.type === "text") {
                      this._value = this._value.replace(/[\r\n]/g, "");
                    } else if (tag === "textarea") {
                      this._value = this._value.replace(/\r\n?/g, "\n");
                    }
                  }
                });
                return element;
              }
            };

            """
        )
        ctx.eval(self.bridge_js)
        ctx.eval(self.main_js)
        return ctx

    def _capture_render(self, data):
        ctx = self._ctx()
        ctx.eval(
            """
            var __emitted; var __emissionCount = 0;
            window.parent.postMessage = function (message) {
              __messages.push(message);
              if (message.type === "streamlit:setComponentValue") {
                __emitted = message.value;
                __emissionCount++;
              }
            };
            """
        )
        event = {"detail": {"args": {"json_str": json.dumps(data)}}}
        ctx.eval("onRender(" + json.dumps(event) + ");")
        return ctx

    def _returned_value(self, ctx):
        value = json.loads(ctx.eval("JSON.stringify(Array.from(__emitted))"))
        return json.loads(bytes(value))

    def test_component_transport_is_unambiguous_utf8_bytes(self):
        for value in [
            "plain text",
            "null",
            "123",
            "caf\u00e9 \U0001f642",
            "\ud800",
            None,
            True,
            {"id": 9007199254740993},
        ]:
            with self.subTest(value=value):
                ctx = self._capture_render(value)
                self.assertEqual(
                    ctx.eval("__messages[__messages.length - 1].dataType"), "bytes"
                )
                self.assertTrue(ctx.eval("__emitted instanceof Uint8Array"))
                self.assertEqual(self._returned_value(ctx), value)

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
                ctx.eval("var __draft = " + json.dumps(edited) + ";")
                result = json.loads(
                    ctx.eval(
                        """
                    JSON.stringify((function () {
                      var row = document.createElement("div");
                      renderPrimitiveControl(row, editorState.data.id, function (v) {
                        editorState.data.id = v;
                      });
                      var input = findByClass(row, "json-value")[0];
                      var initial = input.value;
                      input.value = __draft;
                      input.dispatchEvent({type: "change"});
                      return { initial: initial };
                    })())
                """
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

    def test_null_edits_reject_non_finite_numbers_and_recover(self):
        for draft in ["Infinity", "-Infinity", "+Infinity", "1e999", "-1e999"]:
            for recovery, expected in [
                ("0", 0),
                ("-2.5", -2.5),
                ("1e3", 1000),
                ("9007199254740993", 9007199254740993),
                ("true", True),
                ("null", None),
                ("hello", "hello"),
                ("", ""),
            ]:
                with self.subTest(draft=draft, recovery=recovery):
                    ctx = self._capture_render({"value": None})
                    ctx.eval("var __draft = " + json.dumps(draft) + ";")
                    ctx.eval("""
                        var row = document.createElement("div");
                        renderPrimitiveControl(row, null, function (v) {
                          editorState.data.value = v;
                        });
                        var input = findByClass(row, "json-value")[0];
                        input.value = __draft;
                        input.dispatchEvent({type: "change"});
                    """)
                    self.assertIsNone(ctx.eval("editorState.data.value"))
                    self.assertEqual(self._returned_value(ctx), {"value": None})
                    self.assertEqual(ctx.eval("__emissionCount"), 1)
                    self.assertTrue(ctx.eval("input.validationMessage"))
                    ctx.eval(
                        "input.value = "
                        + json.dumps(recovery)
                        + '; input.dispatchEvent({type: "change"});'
                    )
                    self.assertEqual(self._returned_value(ctx), {"value": expected})
                    self.assertEqual(ctx.eval("__emissionCount"), 2)
                    self.assertEqual(ctx.eval("input.validationMessage"), "")

    def test_invalid_numeric_edits_keep_last_value_and_report_error(self):
        for original in [12, 0, -1.5, 9007199254740993]:
            for draft in ["", "   ", "invalid", "Infinity", "1e999", "0x10"]:
                with self.subTest(original=original, draft=draft):
                    ctx = self._capture_render({"count": original})
                    ctx.eval("var __draft = " + json.dumps(draft) + ";")
                    result = json.loads(
                        ctx.eval(
                            """
                        JSON.stringify((function () {
                          var row = document.createElement("div");
                          renderPrimitiveControl(row, editorState.data.count, function (v) {
                            editorState.data.count = v;
                          });
                          var input = findByClass(row, "json-value")[0];
                          input.value = __draft;
                          input.dispatchEvent({type: "change"});
                          return { error: input.validationMessage, emissions: __emissionCount };
                        })())
                    """
                        )
                    )
                    self.assertEqual(self._returned_value(ctx), {"count": original})
                    self.assertEqual(result["emissions"], 1)
                    self.assertTrue(result["error"])

    def test_numeric_edit_recovers_after_empty_draft(self):
        for text, expected in [("0", 0), ("-2.5", -2.5), ("1e3", 1000), (".5", 0.5)]:
            with self.subTest(text=text):
                ctx = self._capture_render({"count": 7})
                ctx.eval("var __draft = " + json.dumps(text) + ";")
                result = json.loads(
                    ctx.eval(
                        """
                    JSON.stringify((function () {
                      var row = document.createElement("div");
                      renderPrimitiveControl(row, editorState.data.count, function (v) {
                        editorState.data.count = v;
                      });
                      var input = findByClass(row, "json-value")[0];
                      input.value = "";
                      input.dispatchEvent({type: "change"});
                      input.value = __draft;
                      input.dispatchEvent({type: "change"});
                      return { error: input.validationMessage, emissions: __emissionCount };
                    })())
                """
                    )
                )
                self.assertEqual(self._returned_value(ctx), {"count": expected})
                self.assertEqual(result["emissions"], 2)
                self.assertEqual(result["error"], "")

    def test_multiline_strings_keep_breaks_when_displayed_and_edited(self):
        for original in [
            "first\nsecond",
            "\nfirst\n\nlast\n",
            'quote " and \\\nnext',
            "first",
        ]:
            with self.subTest(original=original):
                ctx = self._capture_render({"note": original})
                edited = original + "\nthird"
                ctx.eval("var __draft = " + json.dumps(edited) + ";")
                result = json.loads(
                    ctx.eval(
                        """
                    JSON.stringify((function () {
                      var row = document.createElement("div");
                      renderPrimitiveControl(row, editorState.data.note, function (v) {
                        editorState.data.note = v;
                      });
                      var input = findByClass(row, "json-value")[0];
                      var initial = input.value;
                      input.value = __draft;
                      input.dispatchEvent({type: "change"});
                      return { initial: initial };
                    })())
                """
                    )
                )
                self.assertEqual(result["initial"], original)
                self.assertEqual(self._returned_value(ctx), {"note": edited})

    def test_readonly_multiline_string_keeps_breaks(self):
        ctx = self._capture_render({"note": "first\nsecond"})
        result = json.loads(
            ctx.eval("""
            JSON.stringify((function () {
              editorState.valueEditable = false;
              var row = document.createElement("div");
              renderPrimitiveControl(row, editorState.data.note, function () {});
              return { value: findByClass(row, "json-value")[0].value, readonly: findByClass(row, "json-value")[0].readOnly };
            })())
        """)
        )
        self.assertEqual(result["value"], "first\nsecond")
        self.assertTrue(result["readonly"])

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
              return { addEventListener: function () {}, setAttribute: function () {} };
            };
            createBooleanSelect = function (value, editable) {
              __calls.push(["boolean", value, editable]);
              return { addEventListener: function () {}, setAttribute: function () {} };
            };
            createTextInput = function (value, className, editable) {
              __calls.push(["text", value, className, editable]);
              return { addEventListener: function () {}, setAttribute: function () {} };
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
                      var input = findByClass(container, "json-key")[0];
                      input.value = "__proto__";
                      input.dispatchEvent({type: "change"});
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
            var input = findByClass(container, "json-key")[0];
            input.value = "__proto__";
            input.dispatchEvent({type: "change"});
        """)
        self.assertEqual(self._returned_value(ctx), data)
        self.assertEqual(ctx.eval("input.value"), "__proto__")

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

                  var keyInput = findByClass(container, "json-key")[0];
                  keyInput.value = "new_key";
                  keyInput.dispatchEvent({type: "change"});

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
                  var firstKeyInput = findByClass(container, "json-key")[0];

                  firstKeyInput.value = "   ";
                  firstKeyInput.dispatchEvent({type: "change"});

                  var keysAfterEmpty = Object.keys(obj).sort();

                  firstKeyInput.value = "second";
                  firstKeyInput.dispatchEvent({type: "change"});

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
