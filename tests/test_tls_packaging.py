import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app
from tls_resources import build_tls_policy, POLICY_NAME


class TlsPackagingTests(unittest.TestCase):
    def test_stock_python_needs_no_codex_specific_resource(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'ssl.py';source.write_text('class SSLContext: pass')
            self.assertIsNone(build_tls_policy(SimpleNamespace(__file__=str(source))))

    def test_required_resource_is_copied_from_actual_interpreter_and_missing_fails_build(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'ssl.py';source.write_text("open('"+POLICY_NAME+"')")
            module=SimpleNamespace(__file__=str(source))
            with self.assertRaisesRegex(RuntimeError,'missing TLS'):build_tls_policy(module)
            policy=source.with_name(POLICY_NAME);policy.write_bytes(b'isolated-policy-fixture')
            before=policy.read_bytes();self.assertEqual(build_tls_policy(module),policy);self.assertEqual(policy.read_bytes(),before)

    def test_online_check_reports_real_translation_outcome_without_gui(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'result.json'
            with patch.object(sys,'argv',['app.py','--check-online',str(output)]),patch('free_online.translate_unit',return_value={'network-check':{'translation':'打开舱门','issues':[]}}):
                app.main()
            data=json.loads(output.read_text());self.assertTrue(data['ok']);self.assertEqual(data['translation'],'打开舱门')

    def test_online_check_refuses_existing_output_and_scan_flags_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'existing.json';path.write_text('preserved')
            for args in [[str(path)], [str(Path(temp)/'new.json'),'--raw']]:
                with self.subTest(args=args),patch.object(sys,'argv',['app.py','--check-online',*args]),patch('free_online.translate_unit') as network:
                    with self.assertRaises(SystemExit):app.main()
                    network.assert_not_called()
            self.assertEqual(path.read_text(),'preserved')

    def test_online_check_does_not_overwrite_file_created_during_request(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'result.json'
            def translate(*a,**k):
                path.write_text('created by another process')
                return {'network-check':{'translation':'打开舱门','issues':[]}}
            with patch.object(sys,'argv',['app.py','--check-online',str(path)]),patch('free_online.translate_unit',side_effect=translate):
                with self.assertRaises(SystemExit):app.main()
            self.assertEqual(path.read_text(),'created by another process')
