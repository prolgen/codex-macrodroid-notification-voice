# Windows / Android workflow v1.0

## Prepare the computer and phone

1. Use local Codex with shell/file access. A cloud-only chat cannot directly operate the attached phone. Verify Python 3.11+ and the Codex plugin commands. Use a local venv; no pip dependencies are required.
2. Discover `adb` on PATH or supply `--adb` with the actual executable. If missing, obtain Android SDK Platform Tools from https://developer.android.com/tools/releases/platform-tools. Do not bundle an old ADB binary or reuse someone's fixed path.
3. Prefer USB initially. The owner enables Developer options and USB debugging, unlocks the phone and accepts its RSA dialog. Run `doctor` without serial to list device IDs/states locally. `unauthorized` requires the owner's dialog; `offline` requires connection diagnosis. Never silently select the first device.
4. For an owner-requested wireless connection, use Android's pairing interface. `adb pair host:pairing-port` prompts for the code locally; then `adb connect host:connection-port` if needed. These ports may differ and change. Do not save codes or expose them in chat/logs. Do not enable legacy unauthenticated TCP debugging as a fallback. Official reference: https://developer.android.com/tools/adb.
5. Run `doctor --serial <selected-device> --profile <private-profile>`. It reads model/version, MacroDroid notification-access/battery status and installed source apps, not message content. Device IDs printed by discovery remain local.

Command metavariables below are supplied from discovered local state; use PowerShell variables for paths/serials rather than hardcoded machine settings. `$tool` points to this skill's `scripts/notification_voice.py`; `$python` is the verified venv interpreter. Use `& $python $tool ...`.

## Prepare and install

1. Copy the example profile into a private workspace; edit the requested settings. Obtain package IDs from the phone (e.g. `adb -s <serial> shell pm list packages`, filtered locally to relevant apps). Do not assume unofficial Telegram clients use the official package.
2. Save synthetic test cases with `text` and boolean `expected`. Include exclusions before/after terms, multiline/case, missing groups, partial-word false positives and ordinary unrelated text.
3. Run `test --profile <profile> --cases <cases>`, then `build --profile <profile> --out <new-directory>`. Build refuses existing outputs. Keep real profiles out of version control.
4. Export existing MacroDroid macros through its UI to a private `.mdr` backup. Pull only that selected file to the private backup directory. Parse JSON locally, verify it contains the expected macro list and record its hash. Do not upload the full export: it can contain unrelated app configuration. Keep the latest readable backup. Rollback: disable the new NV rule and restore only the affected previous macro through the normal UI; full-set restore requires deliberate review to preserve unrelated macros.
5. Run `push --serial <serial> --bundle <new-directory>`. Default destination root `/sdcard/Download/NotificationVoice` is configurable. The helper creates a unique child directory and verifies SHA-256 of transferred files. It never imports or enables a macro. If ADB shell tools are unsupported, report the error and use the owner's ordinary file-transfer route.
6. In MacroDroid, import the SINGLE `notification.macro` from the returned directory using the current UI. Preserve all other macros. Inspect any replacement prompt; compare the intended stable name/GUID with the backed-up rule. Never import a whole historical `.mdr` as a shortcut. Do not assume same GUID means the app deduplicates automatically.
7. If alarm is enabled, open the Play Sound action and choose the transferred `alarm.wav` with Android's system file picker. A textual `content://` URI is not a permission grant; each phone needs its own selection. Choose the actual language/voice and verify audible speech. The template uses Android's alarm audio stream; check its current volume and DND behavior, do not assume it bypasses either.
8. The owner grants MacroDroid notification access. Verify MacroDroid's own notifications (needed for Stop), source app notification permission, relevant chat/channel notifications and visible text. Verify battery optimization/autostart settings appropriate to the manufacturer. Do not blanket-grant unrelated permissions.
9. Export the installed macro to a private file and run `verify-export --profile <profile> --export <export>`. This verifies intended trigger/actions, nested Stop action and the selected file URI's presence. It does not prove the URI is accessible or the sound audible. On mismatch, inspect and correct; never dismiss differences automatically.
10. Enable the intended rule and inspect the full local export for duplicate names/GUIDs. Run the verifier again with `--require-enabled`. Keep old rules disabled only with authorization; do not delete them automatically. Inspect other active macros for overlapping conditions manually.

## Acceptance and evidence

Record PASS / FAIL / NOT TESTED separately, with date, app/version and synthetic case identifier:

- Rule truth table locally; Android trigger positive/negative including exclusions and word boundaries.
- Actual incoming notification from EACH selected app. Sending a message to oneself or manually running actions does not prove reception.
- Audible intended phrase/body; selected voice and sound route.
- If alarm enabled: full requested duration, stop notification tap and button, and behavior after natural completion.
- Locked screen, screen off, and after reboot (owner authorizes reboot).
- Several notifications close together and duplicate updates; disclose overlaps rather than reporting serialized processing.
- Computer disconnected: phone continues processing. Test over an agreed observation period before calling background reliability measured.

The owner can arrange incoming messages. Do not contact real people or send test messages without authorization. Avoid arbitrary notification dumps. If Shell notification tests are used by a capable operator, create a separately named disabled test macro with synthetic input only, keep production app filters intact, and disable that test macro afterward; deletion follows owner permissions. Shell tests supplement rather than replace genuine app delivery tests.

Finish with the actual verification stages, location of private backup/report, remaining limitations, and disable instructions: MacroDroid → Macros → `NV_<id>` → off. Wireless/USB debugging can be disabled afterward. Revoking notification access affects other MacroDroid rules too, so do not do it silently.
