import json
import unittest

import test_frontend_view as view


class TestTypeSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        view.TestFrontendView.setUpClass()
        cls.harness = view.TestFrontendView()

    def _ctx(self, data):
        ctx = self.harness._ctx(data)
        ctx.eval("""
            function typeAt(path) {
              return findAll(container, "json-type").find(e => e.getAttribute("data-path") === JSON.stringify(path));
            }
            function changeType(path, type) {
              var select = typeAt(path);
              select.value = type;
              select.dispatchEvent({type: "change"});
            }
            function confirmType() {
              findAll(container, "json-type-apply").find(e => !e.parentElement.hidden).dispatchEvent({type: "click"});
            }
        """)
        return ctx

    def _value(self, ctx):
        return self.harness.harness._returned_value(ctx)

    def test_every_node_offers_all_six_types_including_collections(self):
        ctx = self._ctx({"items": ["hello", 42, True, None, {}]})
        selectors = json.loads(
            ctx.eval("""
            JSON.stringify(findAll(container, "json-type").map(e => ({
              tag: e.tagName, value: e.value, label: e.getAttribute("aria-label"),
              options: e.children.map(o => o.value)
            })))
        """)
        )
        self.assertEqual(
            [s["value"] for s in selectors],
            ["object", "array", "string", "number", "boolean", "null", "object"],
        )
        for selector in selectors:
            self.assertEqual(selector["tag"], "select")
            self.assertTrue(selector["label"])
            self.assertEqual(
                selector["options"],
                ["string", "number", "boolean", "null", "object", "array"],
            )

    def test_preserving_conversions_work_at_root_key_and_array_index(self):
        cases = [
            ("42", "number", 42),
            ("9007199254740993", "number", 9007199254740993),
            ("-1.5e2", "number", -150),
            ("true", "boolean", True),
            ("false", "boolean", False),
            ("null", "null", None),
            ('{"id":9007199254740993}', "object", {"id": 9007199254740993}),
            ('[1,"two",null]', "array", [1, "two", None]),
            ([1, "two", None], "string", '[1,"two",null]'),
            ({"id": 9007199254740993}, "string", '{"id":9007199254740993}'),
            (9007199254740993, "string", "9007199254740993"),
            (False, "string", "false"),
            (True, "number", 1),
            (0, "boolean", False),
            (None, "string", "null"),
            (None, "number", 0),
            (None, "boolean", False),
            (None, "object", {}),
            (None, "array", []),
            ('{"__proto__":{"safe":true}}', "object", {"__proto__": {"safe": True}}),
        ]
        for location in ["root", "key", "index"]:
            for initial, target, expected in cases:
                with self.subTest(location=location, initial=initial, target=target):
                    wrap = lambda value, location=location: (
                        value
                        if location == "root"
                        else {"value": value}
                        if location == "key"
                        else [value]
                    )
                    path = (
                        []
                        if location == "root"
                        else ["value"]
                        if location == "key"
                        else [0]
                    )
                    ctx = self._ctx(wrap(initial))
                    ctx.eval(
                        "changeType("
                        + json.dumps(path)
                        + ","
                        + json.dumps(target)
                        + ");"
                    )
                    self.assertEqual(self._value(ctx), wrap(expected))
                    self.assertEqual(
                        ctx.eval("typeAt(" + json.dumps(path) + ").value"), target
                    )
                    self.assertEqual(ctx.eval("__emissionCount"), 2)
                    self.assertFalse(
                        ctx.eval(
                            'findAll(container, "json-type-confirm").some(e => !e.hidden)'
                        )
                    )

    def test_replacing_incompatible_values_requires_apply_and_can_be_cancelled(self):
        for initial, target, expected in [
            ("hello", "number", 0),
            ("hello", "boolean", False),
            ("hello", "null", None),
            ("hello", "object", {}),
            ("hello", "array", []),
            ([1, 2], "object", {}),
            ({"x": 1}, "array", []),
            ("1e999", "number", 0),
            ('{"x":1e999}', "object", {}),
            ("", "number", 0),
            ("0x10", "number", 0),
        ]:
            with self.subTest(initial=initial, target=target):
                ctx = self._ctx({"value": initial, "other": "keep"})
                command = 'changeType(["value"], ' + json.dumps(target) + ");"
                ctx.eval(command)
                self.assertEqual(self._value(ctx), {"value": initial, "other": "keep"})
                self.assertEqual(ctx.eval("__emissionCount"), 1)
                self.assertTrue(
                    ctx.eval(
                        'findAll(container, "json-type-confirm").some(e => !e.hidden)'
                    )
                )
                ctx.eval(
                    'findAll(container, "json-type-cancel").find(e => !e.parentElement.hidden).dispatchEvent({type:"click"});'
                )
                self.assertFalse(
                    ctx.eval(
                        'findAll(container, "json-type-confirm").some(e => !e.hidden)'
                    )
                )
                self.assertEqual(self._value(ctx), {"value": initial, "other": "keep"})
                ctx.eval(command + "confirmType();")
                self.assertEqual(self._value(ctx), {"value": expected, "other": "keep"})
                self.assertEqual(ctx.eval("__emissionCount"), 2)

    def test_conversion_uses_latest_edit_and_replacement_remains_editable(self):
        ctx = self._ctx({"value": "old"})
        ctx.eval("""
            var input = findAll(container, "json-value")[0];
            input.value = "123";
            input.dispatchEvent({type: "change"});
            changeType(["value"], "number");
            var number = findAll(container, "json-value")[0];
            number.value = "456";
            number.dispatchEvent({type: "change"});
        """)
        self.assertEqual(self._value(ctx), {"value": 456})
        self.assertEqual(ctx.eval('typeAt(["value"]).value'), "number")
        self.assertTrue(ctx.eval('document.activeElement === typeAt(["value"])'))

    def test_type_change_clears_replaced_errors_and_keeps_unrelated_drafts(self):
        ctx = self._ctx({"child": {"count": 5}, "other": 7})
        ctx.eval("""
            findAll(container, "json-value").forEach(input => {
              input.value = "";
              input.dispatchEvent({type: "change"});
            });
            changeType(["child"], "string");
        """)
        self.assertEqual(self._value(ctx), {"child": '{"count":5}', "other": 7})
        self.assertEqual(ctx.eval("editorState.rejections.size"), 1)
        self.assertEqual(ctx.eval('findAll(container, "json-value")[1].value'), "")
        ctx.eval('changeType(["other"], "string");')
        self.assertEqual(ctx.eval("editorState.rejections.size"), 0)
        self.assertEqual(self._value(ctx), {"child": '{"count":5}', "other": "7"})

    def test_type_changes_respect_readonly_and_same_type_does_not_emit(self):
        ctx = self._ctx({"value": "123"})
        ctx.eval('changeType(["value"], "string");')
        self.assertEqual(ctx.eval("__emissionCount"), 1)
        ctx.eval("editorState.valueEditable = false; renderEditor();")
        self.assertTrue(
            ctx.eval('findAll(container, "json-type").every(e => e.disabled)')
        )
        ctx.eval('changeType(["value"], "number"); changeType([], "string");')
        self.assertEqual(self._value(ctx), {"value": "123"})
        self.assertEqual(ctx.eval("__emissionCount"), 1)

    def test_conversion_handles_proto_keys_and_renamed_paths(self):
        ctx = self._ctx({"__proto__": {"value": "123"}})
        ctx.eval("""
            editorState.keyEditable = true;
            renderEditor();
            var key = findAll(container, "json-key")[1];
            key.value = "renamed";
            key.dispatchEvent({type: "change"});
            changeType(["__proto__", "renamed"], "number");
            changeType(["__proto__"], "string");
        """)
        self.assertEqual(self._value(ctx), {"__proto__": '{"renamed":123}'})
        self.assertTrue(
            ctx.eval("Object.getPrototypeOf(editorState.data) === Object.prototype")
        )

    def test_new_source_and_readonly_permissions_cancel_pending_replacement(self):
        ctx = self._ctx("hello")
        ctx.eval(
            'changeType([], "number"); var apply = findAll(container, "json-type-apply")[0];'
        )
        event = {
            "detail": {"args": {"json_str": json.dumps("new"), "value_editable": False}}
        }
        ctx.eval(
            "onRender(" + json.dumps(event) + "); apply.dispatchEvent({type: 'click'});"
        )
        self.assertEqual(self._value(ctx), "new")
        self.assertFalse(
            ctx.eval('findAll(container, "json-type-confirm").some(e => !e.hidden)')
        )

    def test_all_type_pairs_can_be_selected_and_used_again(self):
        cases = [
            ("string", "text"),
            ("number", 2),
            ("boolean", True),
            ("null", None),
            ("object", {"id": 1}),
            ("array", [1]),
        ]
        for source, original in cases:
            for target, _ in cases:
                with self.subTest(source=source, target=target):
                    ctx = self._ctx(original)
                    ctx.eval("changeType([], " + json.dumps(target) + ");")
                    if ctx.eval(
                        'findAll(container, "json-type-confirm").some(e => !e.hidden)'
                    ):
                        ctx.eval("confirmType();")
                    self.assertEqual(ctx.eval("typeAt([]).value"), target)
                    self.assertEqual(
                        ctx.eval("__emissionCount"), 1 if source == target else 2
                    )
                    ctx.eval('changeType([], "string");')
                    self.assertIsInstance(self._value(ctx), str)

    def test_pending_replacement_survives_echo_and_keeps_other_fields_editable(self):
        data = {"name": "original", "other": "keep"}
        ctx = self._ctx(data)
        ctx.eval('changeType(["name"], "null");')
        event = {"detail": {"args": {"json_str": json.dumps(data)}}}
        ctx.eval("onRender(" + json.dumps(event) + ");")
        ctx.eval("""
            var other = findAll(container, "json-value")[1];
            other.value = "updated";
            other.dispatchEvent({type: "change"});
            confirmType();
        """)
        self.assertEqual(self._value(ctx), {"name": None, "other": "updated"})

    def test_stale_confirmation_does_not_discard_a_newer_value(self):
        ctx = self._ctx("old")
        ctx.eval("""
            changeType([], "null");
            var input = findAll(container, "json-value")[0];
            input.value = "new";
            input.dispatchEvent({type: "change"});
            confirmType();
        """)
        self.assertEqual(self._value(ctx), "new")
        self.assertFalse(
            ctx.eval('findAll(container, "json-type-confirm").some(e => !e.hidden)')
        )

    def test_type_change_preserves_its_key_error_and_sibling_collapse(self):
        ctx = self._ctx({"name": "123", "sibling": {"count": 1}})
        ctx.eval("""
            editorState.keyEditable = true;
            renderEditor();
            var key = findAll(container, "json-key")[0];
            key.value = "sibling";
            key.dispatchEvent({type: "change"});
            findAll(container, "json-toggle")[1].dispatchEvent({type: "click"});
            changeType(["name"], "number");
        """)
        self.assertEqual(self._value(ctx), {"name": 123, "sibling": {"count": 1}})
        self.assertEqual(
            ctx.eval('findAll(container, "json-key")[0].getAttribute("aria-invalid")'),
            "true",
        )
        self.assertEqual(
            ctx.eval(
                'findAll(container, "json-toggle")[1].getAttribute("aria-expanded")'
            ),
            "false",
        )
