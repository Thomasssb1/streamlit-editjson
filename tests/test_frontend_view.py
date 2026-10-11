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
