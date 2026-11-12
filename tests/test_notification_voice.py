import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/macrodroid-notification-voice/skills/macrodroid-notification-voice"
spec = importlib.util.spec_from_file_location("nv", SKILL / "scripts/notification_voice.py")
nv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nv)


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.p = nv.read_json(SKILL / "assets/profile.example.json")

    def matches(self, text):
        return bool(re.fullmatch(nv.pattern(self.p), text))

    def test_example_cases(self):
        self.assertFalse(nv.run_cases(self.p, nv.read_json(SKILL / "assets/cases.example.json"))["failed_case_numbers"])

    def test_groups_exclusion_multiline_and_word_boundaries(self):
        self.p["groups"] = [["склад", "офис"], ["курьер", "доставка"]]
        for value in ("СКЛАД\nдоставка", "курьер: офис!", "(склад) доставка"):
            self.assertTrue(self.matches(value), value)
        for value in ("склад", "курьер", "складской доставка", "реклама склад доставка", "склад доставка РЕКЛАМА", "склад2 доставка", "_склад доставка"):
            self.assertFalse(self.matches(value), value)

    def test_literal_metacharacters(self):
        self.p["groups"] = [["a+b", "(заказ)", "C:\\data", "[ok]", "x.y"]]
        self.p["whole_words"] = False
        for term in self.p["groups"][0]:
            self.assertTrue(self.matches("Получен " + term), term)
        self.assertFalse(self.matches("ab"))
        self.assertFalse(self.matches("xay"))

    def test_case_and_substring_options(self):
        self.p["ignore_case"] = False
        self.assertFalse(self.matches("КУРЬЕР"))
        self.p["whole_words"] = False
        self.assertTrue(self.matches("курьерская"))

    def test_reject_unsupported_or_unsafe_profiles(self):
        changes = [dict(groups=[]), dict(groups=[[]]), dict(alarm_seconds=-1), dict(alarm_seconds=True),
                   dict(alarm_seconds=601), dict(whole_words="yes"), dict(id="../x"), dict(schedule="night"),
                   dict(applications=[{"package": "a.b;id", "name": "x"}]),
                   dict(applications=[{"package": nv.PACKAGE, "name": "x"}]),
                   dict(applications=[{"package": "com.android.shell", "name": "x"}])]
        for change in changes:
            p = copy.deepcopy(self.p)
            p.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                nv.validate_profile(p)

    def test_stable_identity_and_disabled_import(self):
        first = nv.make_macro(self.p)
        self.p["groups"] = [["посылка"]]
        second = nv.make_macro(self.p)
        self.assertEqual(first["m_GUID"], second["m_GUID"])
        self.assertFalse(second["m_enabled"])
        self.assertEqual(len(second["m_actionList"]), 1)
        self.assertTrue(second["m_triggerList"][0]["m_textContent"].startswith("(?Uisu)"))
        self.p["id"] = "other"
        self.assertNotEqual(nv.make_macro(self.p)["m_GUID"], first["m_GUID"])

    def test_fixed_speech_and_alarm(self):
        self.p["speech"].update(mode="fixed", text="Пришла посылка")
        self.p["alarm_seconds"] = 3
        macro = nv.make_macro(self.p)
        self.assertEqual(macro["m_actionList"][1]["m_textToSay"], "Пришла посылка")
        self.assertNotIn("m_fileUri", macro["m_actionList"][3])
        self.p["speech"]["text"] = "{notification}"
        with self.assertRaises(ValueError):
            nv.validate_profile(self.p)

    def test_build_checksum_wav_and_no_overwrite(self):
        self.p["alarm_seconds"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle"
            nv.build(self.p, out)
            nv.bundle_files(out)
            with wave.open(str(out / "alarm.wav")) as wav:
                self.assertEqual(wav.getnframes() / wav.getframerate(), 3)
            before = nv.sha(out / "notification.macro")
            with self.assertRaises(ValueError):
                nv.build(self.p, out)
            self.assertEqual(before, nv.sha(out / "notification.macro"))
            (out / "notification.macro").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ValueError):
                nv.bundle_files(out)

    def test_export_detects_changed_trigger_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            macro = nv.make_macro(self.p)
            macro["m_enabled"] = True
            nv.write_json(path, macro)
            self.assertTrue(nv.verify_export(self.p, path, True)["verified"])
            macro["m_triggerList"][0]["m_excludeApps"] = True
            nv.write_json(path, macro)
            self.assertFalse(nv.verify_export(self.p, path)["verified"])
            nv.write_json(path, {"macroList": [macro, macro]})
            with self.assertRaises(ValueError):
                nv.verify_export(self.p, path)

    def test_alarm_export_requires_uri_and_checks_nested_stop(self):
        self.p["alarm_seconds"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            macro = nv.make_macro(self.p)
            nv.write_json(path, macro)
            self.assertFalse(nv.verify_export(self.p, path)["verified"])
            macro["m_actionList"][3]["m_fileUri"] = "content://example/audio"
            nv.write_json(path, macro)
            self.assertTrue(nv.verify_export(self.p, path)["verified"])
            button = macro["m_actionList"][4]["notificationActionButtons"][0]
            action = json.loads(button["actionJson"])
            action["m_selectedIndex"] = 0
            button["actionJson"] = json.dumps(action)
            nv.write_json(path, macro)
            self.assertFalse(nv.verify_export(self.p, path)["verified"])

    def test_failed_case_and_cli_errors_are_nonzero(self):
        result = nv.run_cases(self.p, [{"text": "курьер", "expected": False}])
        self.assertEqual(result["failed_case_numbers"], [1])
        self.assertEqual(nv.main(["test", "--profile", "missing-file.json", "--cases", "missing.json"]), 2)

    def test_export_rejects_operational_root_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            for key, value in (("isActionBlock", True), ("m_completed", False), ("loggingLevel", 3)):
                macro = nv.make_macro(self.p)
                macro[key] = value
                nv.write_json(path, macro)
                self.assertFalse(nv.verify_export(self.p, path)["verified"], key)

    def test_malformed_alarm_export_returns_mismatch(self):
        self.p["alarm_seconds"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            for actions in (None, {}, [None] * 5):
                macro = nv.make_macro(self.p)
                macro["m_actionList"] = actions
                nv.write_json(path, macro)
                self.assertFalse(nv.verify_export(self.p, path)["verified"])

    def test_missing_adb_and_no_implicit_device(self):
        with patch.object(nv.shutil, "which", return_value=None):
            with self.assertRaises(ValueError):
                nv.Adb()
        with patch.object(nv.shutil, "which", return_value="adb"):
            adb = nv.Adb()
            with self.assertRaises(ValueError):
                adb.run("shell", "getprop", "ro.product.model")

    def test_push_rejects_traversal_and_tampering_before_device_access(self):
        class NoDevice:
            def ready(self):
                raise AssertionError("device should not be accessed")
        for root in ("/sdcard/../private", "/sdcard/x;id", "/data/local/tmp", "/sdcard/x y"):
            with self.assertRaises(ValueError):
                nv.push(NoDevice(), "unused", root)

    def test_push_checks_transferred_hash_and_explicit_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "bundle"
            nv.build(self.p, folder)
            calls = []
            class FakeAdb:
                def ready(self):
                    calls.append(("ready",))
                def run(self, *args):
                    calls.append(args)
                    if "sha256sum" in args:
                        return nv.sha(folder / "notification.macro") + "  file"
                    return ""
            result = nv.push(FakeAdb(), folder, "/sdcard/Download/NotificationVoice")
            self.assertTrue(result["transferred"])
            self.assertFalse(result["imported"])
            self.assertEqual(calls[0], ("ready",))
            self.assertTrue(any(c[0] == "push" for c in calls))


if __name__ == "__main__":
    unittest.main()
