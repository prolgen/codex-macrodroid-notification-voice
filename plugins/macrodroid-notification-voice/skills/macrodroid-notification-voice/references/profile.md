# Profile format v1

All fields in `assets/profile.example.json` are required. Unknown fields are rejected so a requested condition cannot silently disappear.

| Field | Meaning |
|---|---|
| `schema_version` | Exactly 1 |
| `id` | Stable lowercase identifier; drives macro name `NV_<id>` and deterministic GUID. Keep it for updates. |
| `name` | Human-readable rule description |
| `applications` | Explicit Android package/name pairs, OR between apps; 1–20 |
| `groups` | 1–10 nonempty groups; OR within a group, AND between groups |
| `exclude` | Any matching term blocks a new invocation, anywhere in the matched text |
| `whole_words` | Unicode word boundaries; false allows substring matches |
| `ignore_case` | Case-insensitive matching when true |
| `speech.mode` | `notification` reads `{notification}` (body exposed by the app), `fixed` reads `speech.text` |
| `speech.text` | Empty for notification mode; literal phrase without magic-text braces for fixed mode |
| `speech.locale` | Voice language, e.g. `ru`; installed engine/voice still need checking |
| `speech.speed` | 0.5–2.0 |
| `alarm_seconds` | 0: speech only; 1–600: synthesized periodic WAV after speech |
| `suppress_duplicates` | MacroDroid's observed `m_supressMultiples` switch; not a timed cooldown or queue |

Example two groups: `[["офис", "склад"], ["доставка", "курьер"]]` requires a location AND a delivery term. Inflections are explicit alternatives: `"склад", "склада", "складе"`. Punctuation in terms is literal, not regex syntax. Terms span no implicit whitespace normalization. Multiline notification text is supported.

Matching uses the baseline Notification trigger with `separateTitleAndMessage=false`. Exact composition of the text available to that trigger must be checked on the target version/app. v1 does NOT promise separate title/body filtering, sender/channel identity, or access to a full original message. Speech reads the notification body, which may be truncated or hidden by the source app.

The generated Java regex enables Unicode character classes (`U`), Unicode case folding (`u`) and DOTALL (`s`). Offline Python tests approximate these semantics but are not a substitute for Android tests, especially unusual Unicode and composed characters. Empty groups, invalid package names, macro self-notifications and Shell as a production app are rejected.

Alarm behavior follows the observed template: stop existing MacroDroid playback, speak (queued, wait for completion), stop playback again, start WAV, show a stop notification. This can interfere with other MacroDroid audio; check with the owner if they already use sound macros. Bursts can overlap speech/sound. An exclusion does not stop current playback. The stop button stops playback, not necessarily queued TTS. After natural completion the stop notification may remain. No invented queue/cleanup guarantees.
