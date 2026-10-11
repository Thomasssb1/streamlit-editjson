import json
import unittest

import test_frontend_js as frontend


class TestFrontendView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frontend.TestFrontendJS.setUpClass()
        cls.harness = frontend.TestFrontendJS()

    def _ctx(self, data):
        ctx = self.harness._capture_render(data)
        ctx.eval("""
            function findAll(node, className) {
              var found = (node.className || "").split(" ").includes(className) ? [node] : [];
              return found.concat((node.children || []).flatMap(function (child) {
                return findAll(child, className);
              }));
            }
            var container = document.createElement("div");
            renderNode(container, editorState.data, 0);
        """)
        return ctx

    def test_dictionary_opening_brace_shares_the_key_or_index_row(self):
        for data in [
            {"settings": {"enabled": True}},
            {"empty": {}},
            [{"enabled": True}],
        ]:
            with self.subTest(data=data):
                ctx = self._ctx(data)
                result = json.loads(
                    ctx.eval("""
                    JSON.stringify((function () {
                      var key = (Array.isArray(editorState.data) ? findAll(container, "json-index") : findAll(container, "json-key"))[0];
                      var row = findAll(container, "json-row").find(function (row) {
                        return row.children.includes(key);
                      });
                      return row.children.map(function (child) { return child.textContent; });
                    })())
                """)
                )
                self.assertIn("{", result)
                self.assertEqual(self.harness._returned_value(ctx), data)

    def test_collections_toggle_without_emitting_or_changing_data(self):
        for data in [{"child": {"id": 9007199254740993}}, [[1, 2], []], {}, []]:
            with self.subTest(data=data):
                ctx = self._ctx(data)
                result = json.loads(
                    ctx.eval("""
                    JSON.stringify((function () {
                      var toggle = findAll(container, "json-toggle")[0];
                      var body = findAll(container, "json-children")[0];
                      var before = toggle.getAttribute("aria-expanded");
                      toggle.dispatchEvent({type: "click"});
                      var collapsed = body.hidden && toggle.getAttribute("aria-expanded") === "false";
                      toggle.dispatchEvent({type: "click"});
                      return {before: before, collapsed: collapsed, expanded: !body.hidden,
                        emissions: __emissionCount};
                    })())
                """)
                )
                self.assertEqual(
                    result,
                    {
                        "before": "true",
                        "collapsed": True,
                        "expanded": True,
                        "emissions": 1,
                    },
                )
                self.assertEqual(self.harness._returned_value(ctx), data)

    def test_nested_collapse_survives_rerender_and_key_rename(self):
        ctx = self._ctx({"child": {"value": 1}, "other": []})
        ctx.eval("""
            findAll(container, "json-toggle")[1].dispatchEvent({type: "click"});
            editorState.keyEditable = true;
            container.innerHTML = "";
            renderNode(container, editorState.data, 0);
            var key = findAll(container, "json-key")[0];
            key.value = "renamed";
            key.dispatchEvent({type: "change"});
            container.innerHTML = "";
            renderNode(container, editorState.data, 0);
        """)
        self.assertEqual(
            ctx.eval(
                'findAll(container, "json-row").find(row => row.children.some(child => child.value === "renamed")).children[0].getAttribute("aria-expanded")'
            ),
            "false",
        )
        self.assertEqual(
            self.harness._returned_value(ctx), {"renamed": {"value": 1}, "other": []}
        )

    def test_new_source_starts_expanded_and_reports_collection_counts(self):
        ctx = self._ctx({"items": [1, 2]})
        ctx.eval('findAll(container, "json-toggle")[0].dispatchEvent({type: "click"});')
        event = {"detail": {"args": {"json_str": json.dumps([1, 2, 3])}}}
        ctx.eval("onRender(" + json.dumps(event) + ");")
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-toggle")[0].getAttribute("aria-expanded")'
            ),
            "true",
        )
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-count")[0].textContent'
            ),
            "3 items",
        )

    def test_rows_label_values_and_keep_readonly_keys_selectable(self):
        ctx = self._ctx({"name": "Ada", "count": 3, "enabled": True})
        result = json.loads(
            ctx.eval("""
            JSON.stringify({
              keys: findAll(container, "json-key").map(k => ({readonly: k.readOnly, disabled: k.disabled})),
              values: findAll(container, "json-value").map(v => v.getAttribute("aria-label"))
            })
        """)
        )
        self.assertEqual(result["keys"], [{"readonly": True, "disabled": False}] * 3)
        self.assertEqual(
            result["values"], ["Value for name", "Value for count", "Value for enabled"]
        )

    def test_value_types_are_distinct_without_changing_their_contents(self):
        data = {
            "empty": "",
            "quoted": '"hello"\nworld',
            "number": 9007199254740993,
            "yes": True,
            "no": False,
            "missing": None,
            "text": "null",
        }
        ctx = self._ctx(data)
        result = json.loads(
            ctx.eval("""
            JSON.stringify({
              types: findAll(container, "json-type").map(e => e.textContent),
              quotes: findAll(container, "json-quote").length,
              values: findAll(container, "json-value").map(e => e.value)
            })
        """)
        )
        self.assertEqual(
            result["types"],
            ["string", "string", "number", "boolean", "boolean", "null", "string"],
        )
        self.assertEqual(result["quotes"], 6)
        self.assertEqual(
            result["values"],
            ["", '"hello"\nworld', "9007199254740993", "true", "false", "null", "null"],
        )
        self.assertEqual(self.harness._returned_value(ctx), data)

    def test_readonly_values_remain_selectable_and_keep_their_type(self):
        ctx = self._ctx({"note": "hello\nworld", "count": 5, "missing": None})
        ctx.eval("""
            editorState.valueEditable = false;
            container.innerHTML = "";
            renderNode(container, editorState.data, 0);
        """)
        result = json.loads(
            ctx.eval(
                'JSON.stringify(findAll(container, "json-value").map(e => ({readonly: e.readOnly, disabled: e.disabled})))'
            )
        )
        self.assertEqual(result, [{"readonly": True, "disabled": False}] * 3)

    def test_hex_previews_accept_only_complete_css_hex_strings(self):
        valid = ["#abc", "#AbC8", "#123456", "#aAbBcC80"]
        invalid = [
            "#12",
            "#12345",
            "#1234567",
            "#ggg",
            " #abc ",
            "text #abc",
            "rgb(0,0,0)",
        ]
        ctx = self._ctx(valid + invalid)
        result = json.loads(
            ctx.eval(
                'JSON.stringify(findAll(container, "json-color").filter(e => !e.hidden).map(e => e.getAttribute("aria-label")))'
            )
        )
        self.assertEqual(result, ["Colour preview " + colour for colour in valid])
        self.assertEqual(self.harness._returned_value(ctx), valid + invalid)

    def test_hex_preview_tracks_drafts_without_saving_or_normalizing(self):
        ctx = self._ctx({"colour": "#abc"})
        ctx.eval(
            'var input = findAll(container, "json-value")[0]; var swatch = findAll(container, "json-color")[0];'
        )
        ctx.eval('input.value = "#xx"; input.dispatchEvent({type: "input"});')
        self.assertTrue(ctx.eval("swatch.hidden"))
        self.assertEqual(ctx.eval("__emissionCount"), 1)
        ctx.eval('input.value = "#AbCd"; input.dispatchEvent({type: "input"});')
        self.assertFalse(ctx.eval("swatch.hidden"))
        self.assertEqual(
            ctx.eval('swatch.getAttribute("aria-label")'), "Colour preview #AbCd"
        )
        ctx.eval('input.dispatchEvent({type: "change"});')
        self.assertEqual(self.harness._returned_value(ctx), {"colour": "#AbCd"})

    def test_copy_json_preserves_large_integers_and_current_edits(self):
        ctx = self._ctx(
            {"id": 9007199254740993, "values": [None, "hello\nworld"], "empty": {}}
        )
        ctx.eval("""
            var navigator = {clipboard: {writeText: function (text) {
              window.copied = text;
              return Promise.resolve();
            }}};
            editorState.data.values[0] = true;
            document.getElementById("copy-json").dispatchEvent({type: "click"});
        """)
        copied = ctx.eval("window.copied")
        self.assertEqual(
            json.loads(copied),
            {"id": 9007199254740993, "values": [True, "hello\nworld"], "empty": {}},
        )
        self.assertIn('\n  "id": 9007199254740993', copied)
        self.assertEqual(
            ctx.eval('document.getElementById("copy-status").textContent'),
            "Copied JSON",
        )
        self.assertEqual(ctx.eval("__emissionCount"), 1)

    def test_clipboard_failure_offers_selectable_exact_json(self):
        for mode in ["unavailable", "denied"]:
            with self.subTest(mode=mode):
                ctx = self._ctx({"id": -9007199254740993})
                ctx.eval(
                    "var navigator = {};"
                    if mode == "unavailable"
                    else 'var navigator = {clipboard: {writeText: function () { return Promise.reject(new Error("denied")); }}};'
                )
                ctx.eval(
                    'document.getElementById("copy-json").dispatchEvent({type: "click"});'
                )
                self.assertFalse(
                    ctx.eval('document.getElementById("copy-fallback").hidden')
                )
                self.assertEqual(
                    json.loads(
                        ctx.eval('document.getElementById("copy-fallback").value')
                    ),
                    {"id": -9007199254740993},
                )
                self.assertIn(
                    "copy",
                    ctx.eval(
                        'document.getElementById("copy-status").textContent'
                    ).lower(),
                )
                self.assertFalse(
                    ctx.eval('document.getElementById("copy-json").disabled')
                )
                ctx.eval("emitChange();")
                self.assertTrue(
                    ctx.eval('document.getElementById("copy-fallback").hidden')
                )
                self.assertEqual(
                    ctx.eval('document.getElementById("copy-status").textContent'), ""
                )
