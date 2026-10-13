# Talk To protocol 1.0

The phone (client) and the computer (server) speak this protocol. Every implementation (Linux, Android,
later Windows) MUST follow it; the tests of each side check it against the same files:

- [`protocol/messages.json`](protocol/messages.json): every message and its fields (the table below is generated from it).
- [`protocol/vectors.json`](protocol/vectors.json): test vectors for the hashes, proofs, frames and the QR code.

MUST / SHOULD / MAY as in RFC 2119. Units: time in milliseconds (`*_ms`) or seconds (`*_s`, `seconds`),
sizes in bytes, battery and volume in percent (0–100). Text is UTF-8. Field names are `snake_case`.
Binary data inside JSON is base64 (RFC 4648, with padding). Hashes are lowercase hex.

## 1. Transport

| | |
|---|---|
| Server | the computer, TCP port **47600**, TLS 1.2 or newer |
| Wi-Fi | server listens on `0.0.0.0:47600` |
| USB | the computer runs `adb reverse tcp:47600 tcp:47600`; the phone connects to `127.0.0.1:47600`. A loopback connection from a process of the same user counts as `usb` |
| Bluetooth | RFCOMM, service UUID `a3c5e9d4-7b1f-4c6e-9d2a-5f8b3e1c7a90`, devices bonded in the OS; TLS runs over the stream, the rest is identical |
| Certificate | self-signed EC P-256, created once per computer. The phone does not verify a chain; it pins the **SHA-256 fingerprint of the DER certificate** (`fp`, 64 hex) at pairing and MUST refuse a changed one |

## 2. Discovery (UDP 47601)

The phone sends `{"talkto":1,"type":"probe"}` to `255.255.255.255:47601`. The computer (Wi-Fi on) answers
every probe and also broadcasts every 3 s: `{"talkto":1,"type":"announce","app":"talk-to-android","id","name","port","fp","password"}`.
An announcement is only a hint; trust comes from the fingerprint seen in TLS.

## 3. Frames

```
1 byte kind | 4 bytes length (big-endian) | body
'J' (0x4A)  | n                           | UTF-8 JSON object with a "type" string; n ≤ 4 MiB
'B' (0x42)  | 4 + n                       | 4-byte transfer id (big-endian) + n bytes of file data; n ≤ 1 MiB
```

Binary frames interleave with JSON frames on the same connection. Before authentication only JSON frames of
at most 64 KiB are allowed.

## 4. Handshake and authentication

```
phone → hello   {proto:1, app:"talk-to-linux", device_id, name, model, platform:"android", token|null,
                 features:["pair2","pw2","qr1"], commit: SHA-256(secret), qr?: true}
pc    → hello   {proto:1, app:"talk-to-android", device_id, name, platform:"linux", version, features:[…]}
```

`secret` is 32 random bytes (hex) the phone makes for every connection. If the computer's `device_id` is
already stored with a different fingerprint, the phone MUST stop here.

1. **Token.** If `token` matches the stored one (the computer keeps only SHA-256 of it) → `welcome {}`.
   A phone that sent no token and did no step below MUST reject a `welcome`.
2. Otherwise the computer picks one method and sends `auth_required {method, nonce}` (`nonce`: 16 random bytes, hex):

| method | when | phone answers | check |
|---|---|---|---|
| `qr` | phone sent `qr:true`, both have `qr1` | `auth_qr {proof}` | `proof = HMAC-SHA256(key=k, "qr:nonce:fp:device_id")` with the key `k` of the QR code shown now |
| `password` | Wi-Fi and a password is set | `auth_password {proof}` | `key = PBKDF2-HMAC-SHA256(password, salt="talkto:fp", 100000, 32)`, `proof = HMAC-SHA256(key, "nonce:fp")` |
| `approval` (`pair:2`) | otherwise | `pair_reveal {secret}` | `SHA-256(secret) == commit`; both screens show `code` = first 4 bytes of `SHA-256("nonce:secret:fp:device_id")` mod 10⁶, 6 digits; the user confirms on the computer |

   `fp` is always the fingerprint the phone **sees** in TLS, so a proof cannot be relayed by a man in the
   middle. A QR key is valid 10 minutes and only once.
3. Success → `welcome {token}` (32 random bytes, hex). The phone stores it with `fp`.
4. Failure → `auth_failed {reason}` and the connection closes. Reasons: `wrong_password`, `rejected`
   (refused or 60 s passed), `qr_expired`, `wrong_qr`, `too_many_attempts` (5 failures per IP in 10 min;
   20 for local connections), `protocol`.

Old peers: a phone without `features` gets the old approval code (`SHA-256("nonce:fp:device_id")`) and old
password proof (`HMAC-SHA256(password, "nonce:fp")`). A phone MUST NOT use those (it reports
`server_outdated` instead), otherwise a fake server could ask for the weaker method.

Limits: at most 16 unauthenticated connections, 2 handshakes per IP at once, 3 open approval dialogs.

## 5. QR code

`talkto://pair?v=1&h=<IPv4,…>&p=<port>&fp=<64 hex>&k=<32 hex>&n=<name, URL-encoded>`

The computer lists home/office addresses first, Tailscale (100.64/10) next, virtual bridges last. The phone
MUST accept only local addresses (10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10), tries them in order,
and MUST compare the TLS fingerprint with `fp` before sending a proof. If the link is opened by another app
(the phone's camera), the phone MUST ask the user first.

## 6. Messages

After `welcome` both sides MAY send any message below. Rules:

- A receiver MUST ignore unknown message types and unknown fields (newer peer).
- The computer checks every message against the phone's **current** profile; without permission it ignores
  the message or refuses it (`file_reject`, `command_result {ok:false}`).
- Either side sends `ping` every 15 s; after 50 s of silence the connection counts as lost.
- New messages or fields are added only behind a new `features` entry or as optional fields.

<!-- messages: generated from protocol/messages.json by protocol/table.py; do not edit by hand -->
| Type | Direction | Fields | Meaning |
|---|---|---|---|
| `ping` | both | — | every 15 s; 50 s of silence = lost |
| `pong` | both | — | answer to `ping` (MAY be ignored) |
| `bye` | pc → phone | `reason` enum:disconnected\|forgotten | the computer closes; the phone does not reconnect by itself, and on `forgotten` deletes its token |
| `battery` | phone → pc | `level` int:0..100, `charging` bool | on change |
| `phone_status` | phone → pc | `flavor` enum:full\|play\|lite, `sdk` int, `notif_access` bool, `listener` bool, `player` str\|null, `notifications_sent` int, `version` str | app state, so the computer can explain why notifications or music don't arrive; on connect and on change. `lite` has no notification access, `play` has no overlay permission |
| `phone_info` | phone → pc | `manufacturer` str, `model` str, `android` str, `sdk` int, `security_patch` str, `fingerprint` str?, `app_version` str, `uptime_s` int, `battery` obj?, `storage` obj?, `ram` obj?, `network` enum:none\|wifi\|cellular\|ethernet\|other? | on connect and on `phone_info_request`. `battery` {level, charging, temp_c, health: good/overheat/dead/over_voltage/cold/null}, `storage` and `ram` {total, free} bytes. No personal data |
| `phone_info_request` | pc → phone | — | ask for `phone_info` |
| `crash_report` | phone → pc | `text` str | stack trace of the last crash (≤ 20 000 chars), once after connecting |
| `notification` | phone → pc | `key` str, `package` str, `app` str, `title` str, `text` str, `time_ms` int | a phone notification (not ongoing ones) |
| `notification_removed` | phone → pc | `key` str | removed on the phone |
| `app_icon` | phone → pc | `package` str, `data` b64 | PNG icon, once per app and connection |
| `call` | phone → pc | `key` str, `package` str, `app` str, `caller` str, `text` str, `state` enum:ringing\|ongoing, `actions` list:{i:int,title:str} | a call (phone, WhatsApp, …) with the app's own buttons; sent again on change |
| `call_ended` | phone → pc | `key` str | the call notification is gone |
| `call_action` | pc → phone | `key` str, `action` int | press button `i` of `call.actions` |
| `call_volume` | pc → phone | `dir` int:-1..1 | call volume one step up (1) or down (-1) |
| `call_result` | phone → pc | `kind` enum:action\|volume, `title` str\|null?, `error` str\|null?, `before` int?, `after` int?, `max` int?, `mode` enum:in_call\|in_communication\|ringtone\|normal? | what `call_action` or `call_volume` did (for diagnosis) |
| `media_state` | both | `active` bool, `player` str?, `title` str?, `artist` str?, `album` str?, `playing` bool?, `position_ms` int?, `duration_ms` int?, `volume` int:0..100\|null?, `can_seek` bool?, `art_id` hex:16\|null? | what is playing on the sender; `{active:false}` when nothing |
| `media_art` | both | `art_id` hex:16, `mime` enum:image/jpeg\|image/png, `data` b64 | cover image, only when `art_id` changes |
| `media_control` | both | `action` enum:play_pause\|play\|pause\|next\|previous\|seek\|volume, `value` int\|null | to the owner of the player; `value`: ms for seek, 0–100 for volume, else null |
| `clipboard` | both | `text` str | ≤ 1 000 000 chars (the phone keeps ≤ 100 000) |
| `open_url` | phone → pc | `url` str | open in the computer's browser; http/https only |
| `ring` | pc → phone | — | find my phone: ring even when silent, 30 s |
| `ring_stop` | pc → phone | — | stop ringing |
| `timer` | pc → phone | `seconds` int, `label` str | countdown on the phone (seconds > 0, label ≤ 80 chars) |
| `timer_cancel` | pc → phone | — | cancel the timer |
| `notify` | pc → phone | `title` str, `text` str | show a notification on the phone |
| `profile` | pc → phone | `id` str, `name` str, `permissions` obj, `vibrate` bool | what this phone may do; on connect and on change. `permissions`: notifications, media, files, clipboard, open_url, commands, power, screenshot (bool) |
| `commands` | pc → phone | `items` list:{id:str,name:str,icon:str,power:bool} | commands the profile allows; `id` is opaque, `icon` lock/sleep/restart/power/terminal |
| `run_command` | phone → pc | `id` str | run a listed command (the command text never travels) |
| `command_result` | pc → phone | `id` str, `name` str?, `ok` bool, `code` int?, `output` str | `output`: last 8000 chars, human-readable |
| `sysinfo_request` | phone → pc | — | ask for `sysinfo` |
| `sysinfo` | pc → phone | `host` str, `os` str, `cpu` num\|null, `cores` int, `load` num, `mem_used` int, `mem_total` int, `disk_used` int, `disk_total` int, `battery` obj\|null, `uptime` int, `time` int, `volume` int\|null, `muted` bool | computer state; also the answer to `pc_volume`. `uptime`, `time` in seconds, `battery` {level, charging} |
| `pc_volume` | phone → pc | `value` int:0..100\|null, `toggle_mute` bool | set the computer's volume |
| `setup_request` | phone → pc | — | USB only: the computer grants this app's permissions over adb |
| `setup_result` | pc → phone | `items` list:{key:str,title:str,ok:bool\|null,message:str}, `summary` str | result per step (`ok` null: not needed); texts are human-readable |
| `screenshot_request` | phone → pc | — | the computer sends a screenshot with `file_offer` |
| `file_offer` | both | `transfer_id` int, `name` str, `size` int, `mime` str | section 7 |
| `file_accept` | both | `transfer_id` int | section 7 |
| `file_reject` | both | `transfer_id` int, `reason` str? | section 7; `reason` human-readable |
| `file_done` | both | `transfer_id` int, `sha256` hex:64 | all binary frames sent |
| `file_result` | both | `transfer_id` int, `ok` bool, `reason` str? | the receiver's verdict |
| `file_cancel` | both | `transfer_id` int, `direction` enum:in\|out, `reason` str? | `in`: a transfer to the receiver of this message, `out`: one it sends (both sides count from 1) |
<!-- /messages -->

## 7. Files

`file_offer` → `file_accept` | `file_reject` → binary frames → `file_done {sha256}` → `file_result {ok}`.
Transfer ids are counted per sender, from 1. The receiver writes to a temporary file and keeps it only if
size and SHA-256 match. A received name is reduced to a single file name (`../../.bashrc` → `_.._.bashrc`) and
never overwrites an existing file (`name (1).ext`).
