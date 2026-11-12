"""Notification Voice v1.0.0. Standard-library-only local MacroDroid tooling."""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import wave

VERSION = "1.0.0"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
PACKAGE = "com.arlosoft.macrodroid"
BASELINE = "5.67.8"
LOG = logging.getLogger("notification_voice")


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("JSON exceeds 16 MiB; use a single-macro export")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def keys(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(f"{label}: missing or unsupported fields; see profile.example.json")


def string(value, label, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label}: expected nonempty text without control characters, max {limit}")


def validate_profile(p):
    keys(p, ("schema_version", "id", "name", "applications", "groups", "exclude", "whole_words",
             "ignore_case", "speech", "alarm_seconds", "suppress_duplicates"), "profile")
    if type(p["schema_version"]) is not int or p["schema_version"] != 1:
        raise ValueError("Unsupported schema_version")
    if not isinstance(p["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", p["id"]):
        raise ValueError("id must be 1-40 lowercase ASCII letters/digits/hyphens, starting with a letter")
    string(p["name"], "name", 80)
    apps = p["applications"]
    if not isinstance(apps, list) or not 1 <= len(apps) <= 20:
        raise ValueError("applications: expected 1-20 apps")
    for app in apps:
        keys(app, ("package", "name"), "application")
        string(app["name"], "application name")
        if not isinstance(app["package"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", app["package"]):
            raise ValueError("Invalid Android package")
        if app["package"] in (PACKAGE, "com.android.shell"):
            raise ValueError("Production rules must not listen to MacroDroid itself or Shell")
    if len({a["package"] for a in apps}) != len(apps):
        raise ValueError("Duplicate application package")
    groups = p["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= 10:
        raise ValueError("groups: expected 1-10 required groups")
    for group in groups:
        if not isinstance(group, list) or not 1 <= len(group) <= 50:
            raise ValueError("Each group needs 1-50 literal terms")
        for term in group:
            string(term, "term", 100)
    if not isinstance(p["exclude"], list) or len(p["exclude"]) > 50:
        raise ValueError("exclude: expected up to 50 literal terms")
    for term in p["exclude"]:
        string(term, "excluded term", 100)
    for field in ("whole_words", "ignore_case", "suppress_duplicates"):
        if type(p[field]) is not bool:
            raise ValueError(f"{field}: expected boolean")
    s = p["speech"]
    keys(s, ("mode", "text", "locale", "speed"), "speech")
    if s["mode"] not in ("notification", "fixed"):
        raise ValueError("speech.mode: notification or fixed")
    if s["mode"] == "fixed":
        string(s["text"], "speech.text", 500)
        if "{" in s["text"] or "}" in s["text"]:
            raise ValueError("Fixed speech must not contain MacroDroid magic-text braces")
    elif s["text"] != "":
        raise ValueError("notification mode requires empty speech.text")
    if not isinstance(s["locale"], str) or not re.fullmatch(r"[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?", s["locale"]):
        raise ValueError("Invalid speech locale")
    if type(s["speed"]) not in (int, float) or not 0.5 <= s["speed"] <= 2:
        raise ValueError("speech.speed: 0.5-2")
    if type(p["alarm_seconds"]) is not int or not 0 <= p["alarm_seconds"] <= 600:
        raise ValueError("alarm_seconds: integer 0-600; zero means speech only")
    return p


def pattern(p, java=False):
    def alternatives(terms):
        # Escape only regex metacharacters, avoiding Python-specific escaped punctuation.
        escaped = [re.sub(r"([\\.^$*+?{}\[\]|()])", r"\\\1", t) for t in terms]
        body = "(?:" + "|".join(escaped) + ")"
        return r"(?<!\w)" + body + r"(?!\w)" if p["whole_words"] else body
    flags = "(?" + ("U" if java else "") + ("i" if p["ignore_case"] else "") + "su)"
    result = flags + "\\A"
    if p["exclude"]:
        result += "(?!.*" + alternatives(p["exclude"]) + ")"
    for group in p["groups"]:
        result += "(?=.*" + alternatives(group) + ")"
    return result + ".*"


def run_cases(p, cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError("Test cases must be a nonempty list")
    compiled = re.compile(pattern(p))
    failed = []
    for index, case in enumerate(cases):
        keys(case, ("text", "expected"), "case")
        if not isinstance(case["text"], str) or type(case["expected"]) is not bool:
            raise ValueError("Invalid test case")
        if bool(compiled.fullmatch(case["text"])) != case["expected"]:
            failed.append(index + 1)
    return {"total": len(cases), "failed_case_numbers": failed, "engine": "Python; Android check still required"}


def stable_id(name):
    return -int.from_bytes(hashlib.sha256(("notification-voice/v1/" + name).encode()).digest()[:8], "big") % (2**63 - 1) or 1


def make_macro(p):
    macro = read_json(ASSETS / "base.macro")
    macro["m_GUID"] = stable_id(p["id"])
    macro["m_name"] = "NV_" + p["id"]
    macro["m_description"] = f"Notification Voice {VERSION}: {p['name']}. Exclusions block new starts only."
    macro["m_enabled"] = False
    trigger = macro["m_triggerList"][0]
    trigger.update(m_packageNameList=[a["package"] for a in p["applications"]],
                   m_applicationNameList=[a["name"] for a in p["applications"]],
                   m_textContent=pattern(p, java=True), ignoreCase=p["ignore_case"],
                   m_supressMultiples=p["suppress_duplicates"], disableLogging=True)
    speech = macro["m_actionList"][1]
    speech.update(m_textToSay="{notification}" if p["speech"]["mode"] == "notification" else p["speech"]["text"],
                  m_locale=p["speech"]["locale"], m_speed=p["speech"]["speed"])
    if p["alarm_seconds"] == 0:
        macro["m_actionList"] = [speech]
    else:
        play = macro["m_actionList"][3]
        play["m_fileDisplayName"] = "alarm.wav"
        # URI permission is device-specific: select the transferred file in Android's picker.
        play.pop("m_fileUri", None)
        notice = macro["m_actionList"][4]
        notice["m_notificationText"] = f"Сигнал: {p['alarm_seconds']} с. Нажмите Стоп."
        notice["notificatonId"] = stable_id(p["id"] + "/notification") % 2000000000 + 1
        notice["notificationIdString"] = str(notice["notificatonId"])
        notice["m_overwriteExisting"] = True
    def assign(value, path="root"):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "m_SIGUID":
                    value[key] = stable_id(p["id"] + "/" + path)
                elif key in ("configuredActionJson", "actionJson"):
                    nested = json.loads(item)
                    assign(nested, path + "/" + key)
                    value[key] = json.dumps(nested, ensure_ascii=False, separators=(",", ":"))
                else:
                    assign(item, path + "/" + key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                assign(item, path + "/" + str(i))
    assign(macro)
    return macro


def make_wav(path, seconds):
    rate = 16000
    samples = array.array("h", (int(6500 * math.sin(2 * math.pi * 880 * i / rate)) if i < rate // 4 else 0 for i in range(rate)))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        for _ in range(seconds):
            output.writeframesraw(samples.tobytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(p, target):
    target = Path(target).resolve()
    if target.exists():
        raise ValueError("Output already exists; use a new directory (no overwrites)")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".nv-build-", dir=target.parent))
    try:
        write_json(stage / "profile.json", p)
        write_json(stage / "notification.macro", make_macro(p))
        if p["alarm_seconds"]:
            make_wav(stage / "alarm.wav", p["alarm_seconds"])
        (stage / "INSTALL.md").write_text(
            f"# Notification Voice {VERSION}\n\n"
            "Макрос подготовлен ВЫКЛЮЧЕННЫМ. Это не подтверждение установки.\n\n"
            "1. Экспортируйте существующие макросы в личную резервную копию.\n"
            "2. Импортируйте notification.macro добавлением одного макроса, без замены всего набора.\n"
            "3. Если есть alarm.wav, выберите его в действии воспроизведения через системный выбор файла.\n"
            "4. Проверьте разрешения, голос, громкость и отсутствие дублирующего NV_ правила.\n"
            "5. Экспортируйте установленный макрос и выполните verify-export.\n"
            "6. Включите правило, проверьте реальные положительные/отрицательные уведомления и остановку.\n"
            "7. Проверьте блокировку экрана и перезагрузку; компьютер можно отключить.\n\n"
            "Фильтр проверяет доступный MacroDroid текст уведомления в режиме шаблона. "
            "Раздельные условия для заголовка и тела в v1 не поддержаны. "
            "Исключения запрещают новый запуск, но не отменяют текущий звук. "
            "При серии сообщений возможны наложения; это не гарантия аварийного оповещения.\n",
            encoding="utf-8")
        write_json(stage / "manifest.json", {"version": VERSION, "baseline_macrodroid": BASELINE,
                   "files": {f.name: sha(f) for f in sorted(stage.iterdir())}})
        stage.rename(target)
    except Exception:
        # This directory was created by this invocation and contains no pre-existing user data.
        shutil.rmtree(stage)
        raise
    LOG.info("Build complete; disabled macro; runtime verification pending")
    return {"built": True, "enabled": False, "runtime_verified": False}


def bundle_files(folder):
    folder = Path(folder).resolve()
    manifest = read_json(folder / "manifest.json")
    names = manifest.get("files", {})
    if not isinstance(names, dict) or not {"notification.macro", "profile.json", "INSTALL.md"} <= set(names) or not set(names) <= {"notification.macro", "profile.json", "INSTALL.md", "alarm.wav"}:
        raise ValueError("Invalid bundle manifest")
    for name, digest in names.items():
        item = folder / name
        if item.is_symlink() or item.resolve().parent != folder or sha(item) != digest:
            raise ValueError("Bundle checksum or path check failed")
    return folder, names


def verify_export(p, export, require_enabled=False):
    expected = make_macro(p)
    raw = read_json(export)
    macros = raw.get("macroList", [raw]) if isinstance(raw, dict) else []
    if not isinstance(macros, list):
        raise ValueError("Unrecognized export format")
    matches = [m for m in macros if isinstance(m, dict) and
               (m.get("m_GUID") == expected["m_GUID"] or m.get("m_name") == expected["m_name"])]
    if len(matches) != 1:
        raise ValueError("Expected exactly one managed macro; missing or duplicate name/GUID")
    actual = matches[0]
    errors = []
    volatile = {"m_SIGUID", "m_comment", "m_fileUri", "m_fileDisplayName"}
    def compare(want, got, path):
        if isinstance(want, dict):
            if not isinstance(got, dict):
                errors.append(path)
                return
            for key, value in want.items():
                if key in volatile:
                    continue
                if key in ("configuredActionJson", "actionJson"):
                    try:
                        compare(json.loads(value), json.loads(got.get(key, "")), path + "/" + key)
                    except (TypeError, ValueError):
                        errors.append(path + "/" + key)
                else:
                    compare(value, got.get(key), path + "/" + key)
        elif isinstance(want, list):
            if not isinstance(got, list) or len(want) != len(got):
                errors.append(path)
            else:
                for i, (a, b) in enumerate(zip(want, got)):
                    compare(a, b, path + "/" + str(i))
        elif type(want) is not type(got) and not (type(want) in (float, int) and type(got) in (float, int)) or want != got:
            errors.append(path)
    root_metadata = {"m_enabled", "lastEditedTimestamp", "disabledTimestamp", "m_description",
                     "m_descriptionOpen", "m_category", "m_headingColor", "isFavourite"}
    for key, value in expected.items():
        if key not in root_metadata:
            compare(value, actual.get(key), key)
    if type(actual.get("m_enabled")) is not bool:
        errors.append("m_enabled")
    if require_enabled and actual.get("m_enabled") is not True:
        errors.append("m_enabled")
    if p["alarm_seconds"]:
        actions = actual.get("m_actionList", [])
        if (not isinstance(actions, list) or len(actions) < 4 or not isinstance(actions[3], dict)
                or not str(actions[3].get("m_fileUri", "")).startswith("content://")):
            errors.append("alarm: select WAV through Android file picker")
    return {"verified": not errors, "mismatches": sorted(set(errors)),
            "runtime_verified": False, "note": "Export cannot prove URI access, sound or delivery"}


class Adb:
    def __init__(self, executable="adb", serial=None):
        self.executable = shutil.which(executable)
        if not self.executable:
            raise ValueError("ADB not found. Install Android SDK Platform Tools; use --adb path")
        self.serial = serial

    def run(self, *args, device=True):
        command = [self.executable]
        if device:
            if not self.serial:
                raise ValueError("Explicit --serial required for device operations")
            command += ["-s", self.serial]
        result = subprocess.run(command + list(args), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=25, shell=False)
        if result.returncode:
            raise RuntimeError("ADB command failed; check authorization/connection (raw device output suppressed)")
        return result.stdout.strip()

    def devices(self):
        rows = self.run("devices", device=False).splitlines()[1:]
        return [dict(zip(("serial", "state"), row.split()[:2])) for row in rows if len(row.split()) >= 2]

    def ready(self):
        if not any(d["serial"] == self.serial and d["state"] == "device" for d in self.devices()):
            raise ValueError("Selected device is not authorized/online")


def doctor(adb, p=None):
    devices = adb.devices()
    if not adb.serial:
        return {"devices": devices, "next": "Select an explicit serial, then rerun doctor"}
    adb.ready()
    result = {"model": adb.run("shell", "getprop", "ro.product.model"),
              "android": adb.run("shell", "getprop", "ro.build.version.release")}
    package = adb.run("shell", "dumpsys", "package", PACKAGE)
    version = re.search(r"versionName=([^\s]+)", package)
    result["macrodroid_version"] = version.group(1) if version else None
    result["template_baseline_matches"] = result["macrodroid_version"] == BASELINE
    listeners = adb.run("shell", "settings", "get", "secure", "enabled_notification_listeners")
    result["notification_access"] = any(x.split("/")[0] == PACKAGE for x in listeners.split(":"))
    whitelist = adb.run("shell", "dumpsys", "deviceidle", "whitelist")
    result["battery_whitelist"] = any(PACKAGE in row.split(",") for row in whitelist.splitlines())
    if p:
        result["source_apps_installed"] = {a["package"]: adb.run("shell", "pm", "path", a["package"]).startswith("package:") for a in p["applications"]}
    result["manual_checks"] = ["Notification permissions/channels for source apps and MacroDroid",
                                "Installed offline TTS voice, alarm volume, DND, background/autostart",
                                "Actual incoming notification with visible text"]
    return result


def push(adb, folder, remote_root):
    if not re.fullmatch(r"/sdcard/[A-Za-z0-9_/-]+", remote_root) or "//" in remote_root:
        raise ValueError("remote-root must be a simple /sdcard/ path without spaces or traversal")
    folder, names = bundle_files(folder)
    adb.ready()
    # New random subdirectory every time; refuse an existing path even if its name collides.
    remote = remote_root.rstrip("/") + "/nv-" + uuid.uuid4().hex
    # mkdir without -p on the unique child is atomic and fails on collisions.
    adb.run("shell", "mkdir", "-p", remote_root)
    adb.run("shell", "mkdir", remote)
    for name in sorted(names):
        if name not in ("notification.macro", "alarm.wav"):
            continue
        adb.run("push", str(folder / name), remote + "/" + name)
        output = adb.run("shell", "toybox", "sha256sum", remote + "/" + name)
        if not output or output.split()[0] != names[name]:
            raise RuntimeError("Transferred file checksum mismatch; do not import")
    return {"remote_directory": remote, "transferred": True, "imported": False,
            "note": "Import the single macro in MacroDroid; select WAV via system picker"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--log-dir", help="Optional local rotating logs; no profile/text/device output logged")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "test", "verify-export"):
        sub = commands.add_parser(name)
        sub.add_argument("--profile", required=True)
        if name == "build":
            sub.add_argument("--out", required=True)
        elif name == "test":
            sub.add_argument("--cases", required=True)
        else:
            sub.add_argument("--export", required=True)
            sub.add_argument("--require-enabled", action="store_true")
    for name in ("doctor", "push"):
        sub = commands.add_parser(name)
        sub.add_argument("--adb", default="adb")
        sub.add_argument("--serial", required=name == "push")
        if name == "doctor":
            sub.add_argument("--profile")
        else:
            sub.add_argument("--bundle", required=True)
            sub.add_argument("--remote-root", default="/sdcard/Download/NotificationVoice")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.log_dir:
            Path(args.log_dir).mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(Path(args.log_dir) / "notification-voice.log", maxBytes=262144,
                                          backupCount=10, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            LOG.addHandler(handler)
        p = validate_profile(read_json(args.profile)) if getattr(args, "profile", None) else None
        LOG.info("Starting %s v%s", args.command, VERSION)
        if args.command == "build":
            result = build(p, args.out)
        elif args.command == "test":
            result = run_cases(p, read_json(args.cases))
        elif args.command == "verify-export":
            result = verify_export(p, args.export, args.require_enabled)
        else:
            adb = Adb(args.adb, args.serial)
            result = doctor(adb, p) if args.command == "doctor" else push(adb, args.bundle, args.remote_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("failed_case_numbers") or result.get("verified") is False else 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        LOG.error("%s failed (%s); inspect local inputs/connection", args.command, type(exc).__name__)
        # Validation errors are authored above, not raw notification/device data.
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        LOG.error("Unexpected failure in %s (%s); no device data logged", args.command, type(exc).__name__)
        return 3


if __name__ == "__main__":
    sys.exit(main())
