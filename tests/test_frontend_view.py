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
            var container = document.getElementById("json-container");
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
                        return findAll(row, "json-key").includes(key) || row.children.includes(key);
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
                'findAll(container, "json-row").find(row => findAll(row, "json-key").some(child => child.value === "renamed")).children[0].getAttribute("aria-expanded")'
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
              types: findAll(container, "json-field").map(e => findAll(e, "json-type")[0].value),
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
            ctx.eval('document.getElementById("copy-json").textContent'),
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

    def test_rejected_edits_are_explained_inline_and_clear_on_correction(self):
        for original, draft, valid in [
            (3, "", "0"),
            (9007199254740993, "Infinity", "42"),
            (None, "1e999", "hello"),
        ]:
            with self.subTest(original=original, draft=draft):
                ctx = self._ctx({"value": original})
                ctx.eval('var input = findAll(container, "json-value")[0];')
                ctx.eval(
                    "input.value = "
                    + json.dumps(draft)
                    + '; input.dispatchEvent({type: "change"});'
                )
                self.assertEqual(ctx.eval('input.getAttribute("aria-invalid")'), "true")
                self.assertTrue(
                    ctx.eval(
                        'findAll(container, "json-error").some(e => !e.hidden && e.textContent.length > 0)'
                    )
                )
                self.assertEqual(self.harness._returned_value(ctx), {"value": original})
                self.assertEqual(ctx.eval("__emissionCount"), 1)
                ctx.eval(
                    "input.value = "
                    + json.dumps(valid)
                    + '; input.dispatchEvent({type: "change"});'
                )
                self.assertIsNone(ctx.eval('input.getAttribute("aria-invalid")'))
                self.assertFalse(
                    ctx.eval('findAll(container, "json-error").some(e => !e.hidden)')
                )

    def test_key_rejections_explain_empty_and_duplicate_names(self):
        for draft, message in [("   ", "empty"), ("second", "already exists")]:
            with self.subTest(draft=draft):
                ctx = self._ctx({"first": 1, "second": 2})
                ctx.eval(
                    'editorState.keyEditable = true; container.innerHTML = ""; renderNode(container, editorState.data, 0); var input = findAll(container, "json-key")[0];'
                )
                ctx.eval(
                    "input.value = "
                    + json.dumps(draft)
                    + '; input.dispatchEvent({type: "change"});'
                )
                self.assertEqual(ctx.eval("input.value"), draft)
                errors = ctx.eval(
                    'findAll(container, "json-error").filter(e => !e.hidden).map(e => e.textContent).join(" ")'
                )
                self.assertIn(message, errors)
                self.assertEqual(
                    self.harness._returned_value(ctx), {"first": 1, "second": 2}
                )
                ctx.eval(
                    'input.value = "renamed"; input.dispatchEvent({type: "change"});'
                )
                self.assertEqual(
                    self.harness._returned_value(ctx), {"renamed": 1, "second": 2}
                )
                self.assertEqual(ctx.eval("editorState.rejections.size"), 0)

    def test_rejected_drafts_survive_reruns_but_clear_with_new_source(self):
        ctx = self._ctx({"count": 5})
        ctx.eval(
            'var input = findAll(container, "json-value")[0]; input.value = ""; input.dispatchEvent({type: "change"});'
        )
        event = {"detail": {"args": {"json_str": json.dumps({"count": 5})}}}
        ctx.eval("onRender(" + json.dumps(event) + ");")
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-value")[0].value'
            ),
            "",
        )
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-value")[0].getAttribute("aria-invalid")'
            ),
            "true",
        )
        event["detail"]["args"]["json_str"] = json.dumps({"count": 7})
        ctx.eval("onRender(" + json.dumps(event) + ");")
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-value")[0].value'
            ),
            "7",
        )
        self.assertEqual(ctx.eval("editorState.rejections.size"), 0)

    def test_copy_uses_valid_data_while_a_rejected_draft_is_visible(self):
        ctx = self._ctx({"count": 5})
        ctx.eval("""
            var input = findAll(container, "json-value")[0];
            input.value = "";
            input.dispatchEvent({type: "change"});
            var navigator = {clipboard: {writeText: function (text) {window.copied = text; return Promise.resolve();}}};
            document.getElementById("copy-json").dispatchEvent({type: "click"});
        """)
        self.assertEqual(json.loads(ctx.eval("window.copied")), {"count": 5})

    def test_rejected_child_draft_follows_a_renamed_parent(self):
        ctx = self._ctx({"parent": {"count": 5}})
        ctx.eval("""
            editorState.keyEditable = true;
            container.innerHTML = "";
            renderNode(container, editorState.data, 0);
            var input = findAll(container, "json-value")[0];
            input.value = "";
            input.dispatchEvent({type: "change"});
            var key = findAll(container, "json-key")[0];
            key.value = "renamed";
            key.dispatchEvent({type: "change"});
        """)
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-value")[0].value'
            ),
            "",
        )
        self.assertEqual(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-value")[0].getAttribute("aria-invalid")'
            ),
            "true",
        )
        self.assertEqual(self.harness._returned_value(ctx), {"renamed": {"count": 5}})

    def test_collapsed_summary_uses_a_readable_ellipsis(self):
        for data, expected in [({}, "\u2026 }"), ([], "\u2026 ]")]:
            with self.subTest(data=data):
                ctx = self._ctx(data)
                self.assertEqual(
                    ctx.eval('findAll(container, "json-collapsed-end")[0].textContent'),
                    expected,
                )

    def test_null_conversion_refreshes_the_control_before_a_rerun(self):
        cases = [
            ('"hi"', "hi", "string", "textarea"),
            ("hello", "hello", "string", "textarea"),
            ('"first\\nsecond"', "first\nsecond", "string", "textarea"),
            ("true", True, "boolean", "select"),
            ("false", False, "boolean", "select"),
            ("42", 42, "number", "input"),
            ("9007199254740993", 9007199254740993, "number", "input"),
        ]
        for location in ["root", "object", "array"]:
            for draft, expected, kind, tag in cases:
                with self.subTest(location=location, draft=draft):
                    data = (
                        None
                        if location == "root"
                        else {"optional": None}
                        if location == "object"
                        else [None]
                    )
                    ctx = self._ctx(data)
                    ctx.eval('var input = findAll(container, "json-value")[0];')
                    ctx.eval(
                        "input.value = "
                        + json.dumps(draft)
                        + '; input.dispatchEvent({type: "change"});'
                    )
                    self.assertEqual(
                        ctx.eval(
                            'findAll(findAll(container, "json-field")[0], "json-type")[0].value'
                        ),
                        kind,
                    )
                    self.assertIn(
                        "json-field-" + kind,
                        ctx.eval('findAll(container, "json-field")[0].className'),
                    )
                    self.assertEqual(
                        ctx.eval('findAll(container, "json-value")[0].tagName'), tag
                    )
                    expected_data = (
                        expected
                        if location == "root"
                        else {"optional": expected}
                        if location == "object"
                        else [expected]
                    )
                    self.assertEqual(self.harness._returned_value(ctx), expected_data)
                    self.assertEqual(ctx.eval("__emissionCount"), 2)

    def test_null_to_string_uses_string_editing_for_followup_changes(self):
        ctx = self._ctx({"optional": None, "other": "unchanged"})
        ctx.eval("""
            var other = findAll(container, "json-value")[1];
            var input = findAll(container, "json-value")[0];
            input.value = '"hi"';
            input.dispatchEvent({type: "change"});
            var updated = findAll(container, "json-value")[0];
            updated.value = "123";
            updated.dispatchEvent({type: "change"});
        """)
        self.assertEqual(
            self.harness._returned_value(ctx), {"optional": "123", "other": "unchanged"}
        )
        self.assertTrue(ctx.eval('other === findAll(container, "json-value")[1]'))
        self.assertEqual(
            ctx.eval(
                'findAll(findAll(container, "json-field")[0], "json-type")[0].value'
            ),
            "string",
        )

    def test_numeric_storage_changes_refresh_the_numeric_control(self):
        for original, draft, expected_type, expected in [
            (1, "9007199254740993", "text", 9007199254740993),
            (9007199254740993, "1.5", "number", 1.5),
        ]:
            with self.subTest(original=original):
                ctx = self._ctx({"number": original})
                ctx.eval('var input = findAll(container, "json-value")[0];')
                ctx.eval(
                    "input.value = "
                    + json.dumps(draft)
                    + '; input.dispatchEvent({type: "change"});'
                )
                self.assertEqual(
                    ctx.eval('findAll(container, "json-value")[0].type'), expected_type
                )
                self.assertEqual(
                    self.harness._returned_value(ctx), {"number": expected}
                )

    def test_quoted_strings_are_decoded_only_when_converting_null(self):
        for initial, draft, expected in [
            (None, '"null"', "null"),
            (None, '"123"', "123"),
            (None, '"say \\"hi\\""', 'say "hi"'),
            (None, '"#abc"', "#abc"),
            (None, '""', ""),
            ("text", '"hi"', '"hi"'),
            (None, 'say "hi"', 'say "hi"'),
        ]:
            with self.subTest(initial=initial, draft=draft):
                ctx = self._ctx({"value": initial})
                ctx.eval('var input = findAll(container, "json-value")[0];')
                ctx.eval(
                    "input.value = "
                    + json.dumps(draft)
                    + '; input.dispatchEvent({type: "change"});'
                )
                self.assertEqual(self.harness._returned_value(ctx), {"value": expected})
                self.assertEqual(
                    json.loads(ctx.eval("stringifyJson(editorState.data, true)")),
                    {"value": expected},
                )

    def test_invalid_quoted_null_conversion_keeps_null_with_inline_feedback(self):
        for draft in ['"unfinished', '"bad\\q"', '"first" trailing']:
            with self.subTest(draft=draft):
                ctx = self._ctx({"optional": None})
                ctx.eval('var input = findAll(container, "json-value")[0];')
                ctx.eval(
                    "input.value = "
                    + json.dumps(draft)
                    + '; input.dispatchEvent({type: "change"});'
                )
                self.assertEqual(self.harness._returned_value(ctx), {"optional": None})
                self.assertEqual(ctx.eval('input.getAttribute("aria-invalid")'), "true")
                self.assertIn(
                    "quoted",
                    ctx.eval(
                        'findAll(container, "json-error").filter(e => !e.hidden).map(e => e.textContent).join(" ")'
                    ),
                )

    def test_render_echo_keeps_other_fields_editable_when_an_error_is_visible(self):
        data = {"count": 5, "note": "original"}
        ctx = self._ctx(data)
        ctx.eval("""
            var editor = document.getElementById("json-container");
            var count = findAll(editor, "json-value")[0];
            count.value = "";
            count.dispatchEvent({type: "change"});
            var note = findAll(editor, "json-value")[1];
            note.focus();
            note.value = "draft in progress";
            note.dispatchEvent({type: "input"});
            var messagesBefore = __messages.length;
        """)
        event = {"detail": {"args": {"json_str": json.dumps(data)}}}
        ctx.eval("for (var i = 0; i < 10; i++) onRender(" + json.dumps(event) + ");")
        self.assertTrue(ctx.eval('note === findAll(editor, "json-value")[1]'))
        self.assertTrue(ctx.eval("document.activeElement === note"))
        self.assertEqual(
            ctx.eval('findAll(editor, "json-value")[1].value'), "draft in progress"
        )
        self.assertEqual(ctx.eval("__messages.length"), ctx.eval("messagesBefore"))
        ctx.eval('note.dispatchEvent({type: "change"});')
        self.assertEqual(
            self.harness._returned_value(ctx), {"count": 5, "note": "draft in progress"}
        )
        self.assertEqual(ctx.eval('count.getAttribute("aria-invalid")'), "true")
        ctx.eval('count.value = "0"; count.dispatchEvent({type: "change"});')
        self.assertEqual(
            self.harness._returned_value(ctx), {"count": 0, "note": "draft in progress"}
        )
        self.assertIsNone(ctx.eval('count.getAttribute("aria-invalid")'))

    def test_error_restoration_reports_height_only_after_rendering_finishes(self):
        ctx = self._ctx({"count": 5, "note": "original"})
        ctx.eval("""
            var editor = document.getElementById("json-container");
            var count = findAll(editor, "json-value")[0];
            count.value = "";
            count.dispatchEvent({type: "change"});
            var renderedCounts = [];
            Streamlit.setFrameHeight = function () { renderedCounts.push(findAll(editor, "json-value").length); };
            renderEditor();
        """)
        self.assertEqual(json.loads(ctx.eval("JSON.stringify(renderedCounts)")), [2])

    def test_unchanged_iframe_height_is_not_sent_again(self):
        ctx = self._ctx({})
        ctx.eval("""
            __messages = [];
            Streamlit.setFrameHeight(250);
            Streamlit.setFrameHeight(250);
            Streamlit.setFrameHeight(300);
            Streamlit.setFrameHeight(300);
        """)
        self.assertEqual(
            json.loads(ctx.eval("JSON.stringify(__messages.map(m => m.height))")),
            [250, 300],
        )

    def test_permission_changes_still_update_existing_controls(self):
        ctx = self._ctx({"note": "original"})
        event = {
            "detail": {
                "args": {
                    "json_str": json.dumps({"note": "original"}),
                    "value_editable": False,
                }
            }
        }
        ctx.eval("onRender(" + json.dumps(event) + ");")
        self.assertTrue(
            ctx.eval(
                'findAll(document.getElementById("json-container"), "json-value")[0].readOnly'
            )
        )

    def test_layout_height_changes_do_not_replace_existing_controls(self):
        ctx = self._ctx({"note": "original"})
        ctx.eval(
            'var note = findAll(document.getElementById("json-container"), "json-value")[0]; document.body.scrollHeight = 300;'
        )
        event = {"detail": {"args": {"json_str": json.dumps({"note": "original"})}}}
        ctx.eval("onRender(" + json.dumps(event) + ");")
        self.assertTrue(
            ctx.eval(
                'note === findAll(document.getElementById("json-container"), "json-value")[0]'
            )
        )
        self.assertEqual(ctx.eval("Streamlit.lastFrameHeight"), 320)

    def test_copy_success_appears_only_on_button_for_two_and_a_half_seconds(self):
        ctx = self._ctx({"value": "text"})
        ctx.eval("""
            var navigator = {clipboard: {writeText: () => Promise.resolve()}};
            document.getElementById("copy-json").dispatchEvent({type: "click"});
        """)
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copied JSON"
        )
        self.assertEqual(
            ctx.eval('document.getElementById("copy-status").textContent'), ""
        )
        self.assertTrue(ctx.eval('document.getElementById("copy-fallback").hidden'))
        self.assertFalse(ctx.eval('document.getElementById("copy-json").disabled'))
        ctx.eval("advanceTime(2499);")
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copied JSON"
        )
        ctx.eval("advanceTime(1);")
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copy JSON"
        )

    def test_repeated_copy_restarts_the_button_confirmation_timer(self):
        ctx = self._ctx({"value": "text"})
        ctx.eval("""
            var navigator = {clipboard: {writeText: () => Promise.resolve()}};
            document.getElementById("copy-json").dispatchEvent({type: "click"});
        """)
        ctx.eval(
            'advanceTime(2000); document.getElementById("copy-json").dispatchEvent({type: "click"});'
        )
        ctx.eval("advanceTime(500);")
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copied JSON"
        )
        ctx.eval("advanceTime(2000);")
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copy JSON"
        )
        self.assertEqual(ctx.eval("__timers.size"), 0)

    def test_edits_clear_copy_confirmation_and_failure_keeps_fallback_visible(self):
        ctx = self._ctx({"value": "text"})
        ctx.eval("""
            var navigator = {clipboard: {writeText: () => Promise.resolve()}};
            document.getElementById("copy-json").dispatchEvent({type: "click"});
        """)
        ctx.eval("""
            var input = findAll(container, "json-value")[0];
            input.value = "changed";
            input.dispatchEvent({type: "change"});
        """)
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copy JSON"
        )
        self.assertEqual(ctx.eval("__timers.size"), 0)
        ctx.eval('document.getElementById("copy-json").dispatchEvent({type: "click"});')
        ctx.eval("""
            advanceTime(1000);
            navigator.clipboard.writeText = () => Promise.reject(new Error("denied"));
            document.getElementById("copy-json").dispatchEvent({type: "click"});
        """)
        ctx.eval("advanceTime(3000);")
        self.assertEqual(
            ctx.eval('document.getElementById("copy-json").textContent'), "Copy JSON"
        )
        self.assertIn(
            "Clipboard unavailable",
            ctx.eval('document.getElementById("copy-status").textContent'),
        )
        self.assertFalse(ctx.eval('document.getElementById("copy-fallback").hidden'))
        self.assertEqual(
            json.loads(ctx.eval('document.getElementById("copy-fallback").value')),
            {"value": "changed"},
        )
