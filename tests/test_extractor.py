import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from extractor import export_report, scan


class ExtractorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "模组 空格"
        self.root.mkdir()

    def write(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def test_visible_fields_do_not_extract_identifiers_or_assets(self):
        self.write("items.xml", '<Items><Item identifier="hiddenid" name="Medkit" description="Heal [target] {0}"><Sprite texture="foo.png"/><StatusEffect tags="hiddenstatus"/></Item></Items>')
        report = scan(self.root)
        self.assertEqual([e.text for e in report.entries], ["Medkit", "Heal [target] {0}"])
        self.assertTrue(all(e.kind == "literal" for e in report.entries))

    def test_multiline_xml_exact_location_and_entities(self):
        self.write("items.xml", '<Items>\n<Item identifier="a"\n name="药 &amp; 绷带"\n description="Heal"/>\n</Items>')
        report = scan(self.root)
        name = report.entries[0]
        self.assertEqual((name.text, name.line, name.column), ("药 & 绷带", 3, 8))

    def test_unknown_names_are_not_claimed_as_display_text(self):
        self.write("a.xml", '<Event><Label name="internal"/><Unknown tooltip="Possibly shown"/></Event>')
        self.assertTrue(all(e.kind == "candidate" for e in scan(self.root).entries))

    def test_language_resolution_preserves_languages_and_duplicates(self):
        self.write("a.xml", '<infotexts language="English"><entityname.a>Probe</entityname.a><event.hello>Hello [name]</event.hello></infotexts>')
        self.write("b.xml", '<infotexts language="简体中文"><entityname.a>探针</entityname.a></infotexts>')
        self.write("c.xml", '<infotexts language="English"><entityname.a>Override?</entityname.a></infotexts>')
        self.write("items.xml", '<Items><Item identifier="a"/><ConversationAction text="event.hello"/></Items>')
        report = scan(self.root)
        refs = [e for e in report.entries if e.kind == "reference"]
        self.assertEqual(len(refs[0].resolved), 3)
        self.assertEqual(refs[1].resolved[0]["text"], "Hello [name]")

    def test_language_cdata_and_multiline_text(self):
        self.write("a.xml", '<infotexts language="English"><a><![CDATA[Hello <captain>!\nReady?]]></a></infotexts>')
        self.assertEqual(scan(self.root).entries[0].text, "Hello <captain>!\nReady?")

    def test_missing_keys_stay_references(self):
        self.write("a.lua", 'local a = Text.Get("missing.key")')
        entry = scan(self.root).entries[0]
        self.assertEqual((entry.kind, entry.key, entry.resolved), ("reference", "missing.key", []))

    def test_dynamic_key_fragments_are_not_resolved_as_complete_keys(self):
        self.write("a.lua", 'local a = Text.Get("prefix." .. suffix)')
        entry = scan(self.root).entries[0]
        self.assertEqual((entry.kind, entry.key, entry.category), ("candidate", "", "动态本地化键片段"))

    def test_lua_comments_long_strings_and_escapes(self):
        self.write("a.lua", '-- "ignore"\n--[=[ "ignore2" ]=]\nGUI.Button(parent, "救援\\n开始")\nlocal a = [=[Long\nmessage]=]')
        entries = scan(self.root).entries
        self.assertEqual([e.text for e in entries], ["救援\n开始", "Long\nmessage"])
        self.assertEqual((entries[0].line, entries[0].category), (3, "脚本显示调用"))

    def test_lua_long_string_newline_normalization(self):
        # Raw bytes exercise every Lua newline sequence on every host OS.
        (self.root / "newlines.lua").write_bytes(b'local x = [=[\r\nA\rB\n\rC\r\nD]=]')
        entry = scan(self.root).entries[0]
        self.assertEqual(entry.text, "A\nB\nC\nD")

    def test_arguments_do_not_promote_hook_names(self):
        self.write("a.lua", 'Hook.Add("roundStart", "myHook", function() GUI.Button(parent, "Start") end)')
        entries = scan(self.root).entries
        self.assertEqual([e.category for e in entries], ["脚本标识符/路径候选", "脚本标识符/路径候选", "脚本显示调用"])

    def test_indirect_variable_is_retained_as_candidate(self):
        self.write("a.lua", 'local warning = "Hull breach!"\nGUI.TextBlock(parent, warning)')
        entry = scan(self.root).entries[0]
        self.assertEqual((entry.text, entry.kind), ("Hull breach!", "candidate"))

    def test_csharp_strings_comments_and_characters(self):
        self.write("a.cs", '// "ignore"\n/* "ignore2" */\nvar x = @"Say ""hello"""; var y = "救命\\u0021"; char c = \'x\';\nnew GUIMessageBox("Title", "Body");')
        entries = scan(self.root).entries
        self.assertEqual([e.text for e in entries], ['Say "hello"', '救命!', 'Title', 'Body'])
        self.assertTrue(all(e.category == "脚本显示调用" for e in entries[-2:]))

    def test_interpolation_and_raw_strings_remain_candidates(self):
        self.write("a.cs", 'var a = $"Hello {name}!"; var b = """Line {x}""";')
        self.assertEqual([e.text for e in scan(self.root).entries], ["Hello {name}!", "Line {x}"])
        self.assertTrue(all(e.kind == "candidate" for e in scan(self.root).entries))

    def test_nested_call_argument_count(self):
        self.write("a.lua", 'GUI.TextBlock(makeparent(a,b), "Visible")')
        self.assertEqual(scan(self.root).entries[0].category, "脚本显示调用")

    def test_malformed_xml_is_diagnostic_without_partial_output(self):
        self.write("a.xml", '<Items><Item name="Partial"/></Bad>')
        report = scan(self.root)
        self.assertFalse(report.entries)
        self.assertEqual(len(report.diagnostics), 1)
        self.assertEqual(report.scanned, 0)

    def test_dtd_is_rejected(self):
        self.write("a.xml", '<!DOCTYPE x [<!ENTITY x "bad">]><Items/>')
        self.assertIn("DTD", scan(self.root).diagnostics[0]["message"])

    def test_unterminated_script_is_diagnostic(self):
        self.write("a.lua", 'local x = "oops')
        self.assertIn("未闭合", scan(self.root).diagnostics[0]["message"])

    def test_encoding_failures_are_not_silently_replaced(self):
        (self.root / "a.lua").write_bytes(b'"\xff"')
        report = scan(self.root)
        self.assertEqual(len(report.diagnostics), 1)
        self.assertFalse(report.entries)

    def test_utf16(self):
        (self.root / "a.xml").write_bytes('<Items><Item name="药品"/></Items>'.encode("utf-16"))
        self.assertEqual(scan(self.root).entries[0].text, "药品")

    def test_symlink_outside_is_not_read(self):
        external = Path(self.temp.name) / "outside.lua"
        external.write_text('local a = "Secret"', encoding="utf-8")
        try:
            (self.root / "link.lua").symlink_to(external)
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows account lacks symbolic-link privilege")
            raise
        report = scan(self.root)
        self.assertFalse(report.entries)
        self.assertIn("符号链接", report.diagnostics[0]["message"])

    def test_unsupported_binary_is_diagnosed(self):
        (self.root / "plugin.dll").write_bytes(b"binary")
        report = scan(self.root)
        self.assertEqual((report.skipped, len(report.diagnostics)), (1, 1))

    def test_json_and_csv_preserve_placeholders_and_locations(self):
        self.write("a.xml", '<Items><Item name="=HYPERLINK(&quot;x&quot;)" description="[name], {0}\nReady?"/></Items>')
        report = scan(self.root)
        output = Path(self.temp.name) / "report.json"
        export_report(report, output)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["entries"][0]["text"], '=HYPERLINK("x")')
        self.assertIn("translation", data["entries"][0])
        output = output.with_suffix(".csv")
        export_report(report, output)
        with output.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows[0]["text"].startswith("'="))
        self.assertEqual(rows[1]["text"], "[name], {0} Ready?")
        self.assertTrue(output.with_suffix(".diagnostics.json").exists())

    def test_source_is_unchanged_and_ids_are_repeatable(self):
        path = self.write("a.xml", '<Items><Item name="Kit"/></Items>')
        before = path.read_bytes()
        self.assertEqual(scan(self.root).entries, scan(self.root).entries)
        self.assertEqual(path.read_bytes(), before)

    def test_cancelled_report_is_marked_incomplete(self):
        self.write("a.lua", 'local a="Hello"')
        report = scan(self.root, cancel=lambda: True)
        self.assertIn("取消", report.diagnostics[0]["message"])

    def test_cli_incomplete_exit_code_and_no_source_export(self):
        self.write("a.xml", "<broken>")
        entrypoint = Path(__file__).resolve().parents[1] / "app.py"
        output = Path(self.temp.name) / "out.json"
        result = subprocess.run([sys.executable, str(entrypoint), str(self.root), "-o", str(output)], capture_output=True,env={**os.environ,'PYTHONIOENCODING':'ascii'})
        self.assertEqual(result.returncode, 2)
        self.assertTrue(output.exists())
        self.assertIn('扫描',result.stdout.decode('utf-8'))
        result = subprocess.run([sys.executable, str(entrypoint), str(self.root), "-o", str(self.root / "a.xml")], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.root / "a.xml").read_text(encoding='utf-8'), "<broken>")


if __name__ == "__main__":
    unittest.main()
