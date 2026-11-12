# Compatibility and diagnosis v1.0

The template originates from MacroDroid 5.67.8 single-macro JSON exports, historically exercised on several Android manufacturers. This is evidence for the predecessor workflow, not certification of this new generator or all Android versions. The new code must pass a fresh phone test. We do not claim an official stable MacroDroid export schema or headless import API.

The official MacroDroid wiki URLs were checked during development but returned HTTP 403. Internal field meanings therefore rely on the observed export and must be verified in the live UI when the version differs:
- https://macrodroidforum.com/wiki/index.php/Trigger:_Notification
- https://macrodroidforum.com/wiki/index.php/Action:_Speak_Text

## Diagnose by layer

| Symptom | Check before changing architecture |
|---|---|
| ADB missing | Actual executable/PATH; official platform-tools installation |
| Unauthorized / offline | Owner's RSA prompt, cable, driver, selected serial; do not reset all ADB sessions by default |
| Wi-Fi stopped connecting | Same network, current pairing/connection ports, phone wireless debugging; never reuse stale IP as identity |
| MacroDroid version differs | Disabled single-macro import/export round trip; compare fields and nested Stop actions; runtime tests |
| No trigger | Source-app/chat permissions and visible notification text, MacroDroid notification access, keyword truth table |
| Manual run works, incoming doesn't | Trigger/app package/available notification text; manual action tests are insufficient |
| Text sounds wrong | Installed TTS language/voice; body truncation; locale/speed; offline voice if required |
| No alarm | File selected through system picker, current URI access, alarm volume and DND |
| Stop missing | MacroDroid notification permission/channel and collapsed notification group; the Stop control is in Android notifications |
| Stops in background | Manufacturer battery/autostart settings; test screen-off and reboot rather than assuming exemption suffices |
| Repeated or overlapping sounds | Other active rules, duplicate import, suppression option, burst behavior; v1 has no mutex/queue guarantee |

## Safe version adaptation

Keep a private backup. Start with a disabled macro created/exported by the target version. Compare only the relevant trigger/action structures, including JSON embedded in Stop buttons. Adapt the template with a versioned change and meaningful tests; do not copy full application settings, account data, device paths or UI coordinates. Re-export after every material edit. Support new requirements explicitly rather than accepting unknown profile fields.

Installation/publication of the Codex plugin and configuration of a phone are separate stages. An installed plugin does not install MacroDroid, grant Android permissions, or prove notification delivery. MacroDroid licensing/features are governed by the installed app; no paid edition or unlimited macro allowance is assumed.
