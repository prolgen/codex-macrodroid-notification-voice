---
name: macrodroid-notification-voice
description: Настраивать и проверять озвучивание уведомлений Android через MacroDroid по приложениям, ключевым словам и исключениям; переносить правила на другой телефон и диагностировать несрабатывание.
---

# MacroDroid Notification Voice v1.0.0

Use local Codex on Windows to prepare and apply MacroDroid notification rules. The phone runs the finished macro independently. This package contains its own templates and procedures; do not depend on prior chats, personal skills, paths or another user's device settings.

## Boundaries and inputs

- Read [workflow.md](references/workflow.md) before any phone operation; read [profile.md](references/profile.md) when creating/changing a rule. For failures or a new manufacturer/version, also read [compatibility.md](references/compatibility.md).
- Collect only missing material inputs: target device, apps, required word groups, exclusions, speech and optional alarm. Resolve app package names on the selected phone; display names alone are not identifiers.
- Ordinary v1 settings: OR between apps/terms within a group; AND between groups; exclusions prevent NEW starts only. Literal words/phrases, configurable case/word boundaries. No automatic stemming, arbitrary user regex, schedules, title-only filtering, stop-on-exclusion, or serialized alarm queue in v1. If requested, explicitly explain that adaptation is needed; never silently omit a requirement.
- `assets/profile.example.json` and `assets/cases.example.json` are synthetic starter examples. Store real profiles, exports and generated bundles in an owner-selected PRIVATE working directory, outside the plugin cache and public repository. Never transfer real notification text to cloud tools or publish it.
- Tool entry point: `scripts/notification_voice.py`, resolved relative to THIS skill. Python 3.11+ standard library only; use an existing verified interpreter and a local venv. Do not rely on a personal absolute Python/ADB path. For command syntax run `--help` and subcommand `--help`.
- The bundled `.macro` is derived from an observed MacroDroid 5.67.8 export, not a documented universal format. Newer versions require a disabled import/export round trip and actual Android tests. Never infer successful installation from generation or transfer.

## Repeatable execution

1. Discover available ADB with `doctor`; choose an explicit device serial. Read-only discovery is allowed; authorization/security dialogs stay with the owner. If several devices are connected, do not guess. Read model, Android, MacroDroid and source-app state afresh.
2. Summarize the intended behavior in plain language. Create a private profile with stable `id` and synthetic positive/negative cases. Run `test` before `build`. Python tests do not prove Java/Android regex behavior.
3. Build into a NEW folder. The output macro is disabled. Preserve the same profile ID when updating a rule; use a new ID for an additional independent rule. Do not auto-delete or overwrite existing macros.
4. Before altering the phone's existing macros, export a readable local backup and record rollback. Transfer with `push` only to the explicitly selected device. Its result means FILE TRANSFER, not import. Use the workflow's import and permission procedure.
5. Configure through MacroDroid's normal UI with an available authorized local phone-control surface, or guide the owner. Never edit private app databases, use fixed screen coordinates across phones, replace a complete `.mdr` set, enable root, or copy another device's URI grant.
6. Export the installed single macro. Run `verify-export`. Unknown export changes are a stop-and-inspect condition, not an excuse to weaken checks. Complete missing URI/file-selection setup. Then enable only the intended rule, check duplicate names/GUIDs in the full export locally and run `verify-export --require-enabled`.
7. Test real incoming notifications, exclusions, stop control (when applicable), locked screen, reboot, and a short burst. Do not send messages to others without authorization; the owner can arrange incoming test messages. A manual macro run tests actions only; it does not test the notification trigger. See acceptance checklist in workflow.md.
8. Report separate states: generated / transferred / imported / export verified / Android trigger tested / real delivery tested / background tested. Report untested stages clearly. Give disable/rollback instructions and remaining limits. Never promise a measured reliability percentage without measurement.

## Privacy and recovery

Do not read unrelated messages, dump all Android notifications, log profiles/text/pairing codes, or publish device IDs. The helper performs no network calls; ADB reaches only an authorized phone. Android's chosen TTS engine may use a network voice: select and test an offline voice when privacy matters. Avoid changing DND, other apps' macros or global sound settings without the owner's instruction.

Expected failures return exit code 2, unexpected failures 3, failed tests/export checks 1. Optional `--log-dir` writes rotating operational logs without notification content; default is console only. Never treat a nonzero result as success. If transfer partly fails, preserve its files for diagnosis; retry creates a different directory.
