"""Validate the distributable plugin tree v1.0.0 without reading private outputs."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    assert catalog["name"] == "notification-voice"
    entry, = catalog["plugins"]
    plugin = (ROOT / entry["source"]["path"]).resolve()
    assert plugin.is_relative_to(ROOT)
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == entry["name"] == "macrodroid-notification-voice"
    assert manifest["version"] == "1.0.0"
    skill = plugin / "skills/macrodroid-notification-voice"
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---\nname: macrodroid-notification-voice\ndescription: ")
    for link in re.findall(r"\]\(([^)]+)\)", body):
        if "://" not in link:
            target = (skill / link).resolve()
            assert target.is_relative_to(plugin) and target.is_file(), f"Broken/escaping skill reference: {link}"
    scanned = 0
    forbidden = (r"[A-Z]:[\\/]Users[\\/]", r"E:[\\/]AI[\\/]", r"192\.168\.\d+\.\d+",
                 r"gh[pousr]_[A-Za-z0-9]{20,}", r"sk-[A-Za-z0-9]{20,}", "Стародуб", "Десятуха", "Ивайтенки")
    for file in plugin.rglob("*"):
        if not file.is_file() or "__pycache__" in file.parts:
            continue
        assert not file.is_symlink(), "Symlinks not permitted in release"
        text = file.read_text(encoding="utf-8")
        assert not any(re.search(pattern, text, re.I) for pattern in forbidden), f"Potential personal/secret data in {file.name}"
        scanned += 1
    baseline = json.loads((skill / "assets/base.macro").read_text(encoding="utf-8"))
    assert not baseline["m_enabled"]
    assert len(baseline["m_triggerList"]) == 1
    assert "m_fileUri" not in baseline["m_actionList"][3]
    print(f"Package OK: v{manifest['version']}, {scanned} distributable files; references and privacy patterns checked")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Package validation failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
