# 4d-plugin-etpan
Email client based on the [EtPan](http://www.etpan.org/libetpan.html) library

### Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|

### Version

<img src="https://cloud.githubusercontent.com/assets/1725068/18940649/21945000-8645-11e6-86ed-4a0f800e5a73.png" width="32" height="32" /> <img src="https://cloud.githubusercontent.com/assets/1725068/18940648/2192ddba-8645-11e6-864d-6d5692d55717.png" width="32" height="32" />

The plugin sends email over SMTP with [libetpan](http://www.etpan.org/libetpan.html). One call opens one SMTP session (plain, STARTTLS or SSL on connect), authenticates, sends every message in a JSON array, and returns a JSON text that reports each step. Subjects, display names and bodies can be encoded as UTF-8, ISO-2022-JP, Shift_JIS or Windows-31J. You can pass a callback method that receives the SMTP conversation as it happens.

| Command | Returns | Purpose |
|---|---|---|
| [etpan smtp send](#etpan-smtp-send) | Text (JSON) | Connect to an SMTP server, authenticate, send one or more messages |

**Platforms:** macOS (universal arm64 + x86_64 build, macOS 11.5 or later) and Windows (64-bit).

---

## Requirements & platform notes

- **libetpan and OpenSSL are linked statically** (current source, 2026): libetpan 1.10.1 and OpenSSL 3.5.9 (the long-term support line) on both platforms. The bundle no longer carries `libetpan.20.dylib`, `libssl.1.0.0.dylib`, `libcrypto.1.0.0.dylib` (macOS, libetpan 1.7 and OpenSSL 1.0.2k, Intel only) or `libetpan.dll` (Windows, OpenSSL 1.0.1j). The libraries are not in the repository: `scripts/build-macos-deps.sh` and `scripts/build-windows-deps.ps1` build them from pinned sources, and the CI and release workflows run them (see [Building](#building)).
- **SASL mechanisms differ by platform.** On macOS, libetpan uses the system Cyrus SASL, so every method in `authentication` is available. On Windows it is built without SASL: `LOGIN`, `PLAIN`, `GMAIL` and `OUTLOOK` work, while `CRAM-MD5`, `DIGEST-MD5`, `NTLM`, `SRP`, `GSSAPI` and `KERBEROS_V4` fail with "not implemented" (code `5`).
- **The command blocks the calling process** until the whole session is over: DNS lookup, connection, TLS handshake, authentication and every message. Call it from a dedicated process (`New process`, or a worker) if the user interface must stay responsive. The plugin is not declared thread-safe, so it can't run in a preemptive process.
- **The server certificate is checked** (current source, 2026; release 1.0 didn't check it). After the TLS handshake (SSL on connect, or `STARTTLS`), the plugin checks the certificate chain and the host name against the system's trusted certificates (the macOS Keychain, the Windows certificate store). A certificate that isn't trusted, has expired, or is for another host stops the session; the reason is in `certificate_error`. The plugin also sends the host name in the handshake (SNI), so servers that host several certificates present the right one. Pass `"verifyCertificate":0` to turn the check off, for example for a test server with a self-signed certificate.
- **Parameters are JSON text**, not objects: build them with `JSON Stringify` and `JSON Stringify array`, and parse the result with `JSON Parse`.
- **Failures are reported in the result, never as a 4D error.** Check `session.success` and each `messages[i].success`.

---

## etpan smtp send

### Syntax

```
result := etpan smtp send ( params ; messages {; callback} )
```

| Parameter | Type | Description |
|---|---|---|
| `params` | Text | Connection parameters, a JSON object (see [Connection parameters](#connection-parameters)) |
| `messages` | Text | Messages to send, a JSON array of objects (see [Message object](#message-object)) |
| `callback` | Text | Name of a project method that receives the SMTP conversation. Optional: pass `""` or omit it for no callback |
| Result | Text | JSON object describing the session and each message (see [Result object](#result-object)) |

### Description

`etpan smtp send` parses `params`; if it is not valid JSON, nothing is sent and the result is `{"messages":[],"session":{}}`. It then parses `messages`; if that is not valid JSON or not an array, nothing is sent either (same result).

Otherwise it connects to `host`:`port`, says `EHLO` (falling back to `HELO` when allowed), switches to TLS if requested, authenticates with the chosen method, and then, for each message in order: `MAIL FROM` with the address part of `sender`, `RCPT TO` for every `to`, `cc` and `bcc` address, `DATA`, and `RSET`. A message whose `MAIL FROM` fails, or an array element that is not an object, is skipped and does not appear in `messages` of the result. A failed `RCPT TO` does not stop the message: `DATA` is still attempted.

If the session fails (connection, greeting or authentication), no message is sent: `session.success` is `false` and `messages` is empty.

#### Connection parameters

| Property | Type | Description |
|---|---|---|
| `host` | Text | SMTP server. Default `localhost` |
| `port` | Longint | Default `25`. Common values: `587` (submission + STARTTLS), `465` (SSL on connect) |
| `tls` | Longint (`1`/`0`) or Boolean | `1` (default): connect in plain text, then `STARTTLS`. `0`: SSL on connect (SMTPS, usually port `465`) |
| `allowInsecure` | Longint (`1`/`0`) or Boolean | `1`: with `tls` = `1`, skip `STARTTLS` and stay in plain text; also allows the `HELO` fallback. Default `0` |
| `verifyCertificate` | Longint (`1`/`0`) or Boolean | `1` (default): stop the session when the server certificate isn't trusted for `host`. `0`: accept any certificate. Not used when no TLS is negotiated (`allowInsecure` = `1`) |
| `timeout` | Longint | Network timeout in seconds. `0` (default) uses libetpan's built-in default, it is **not** "no timeout" |
| `user` | Text | User name for authentication |
| `pass` | Text | Password |
| `authentication` | Text | `LOGIN`, `PLAIN`, `CRAM-MD5`, `DIGEST-MD5`, `NTLM`, `SRP`, `GSSAPI`, `KERBEROS_V4`, `GMAIL`, `OUTLOOK` or `AUTO`. Case-insensitive. Empty or unknown = `AUTO` |
| `accessToken` | Text | OAuth 2 access token, used with `GMAIL` / `OUTLOOK` (experimental) |
| `sender` | Text | Envelope sender, `Name <name@example.com>` or `name@example.com`. Only the address goes into `MAIL FROM` |
| `context` | Object | Any object; it is passed to the callback as JSON text in `$4`. Other types are ignored |

`tls`, `allowInsecure` and `verifyCertificate` accept a number or a Boolean (`True`/`False` in `OB SET`, `true`/`false` in JSON). Any other type gives the default. Release 1.0 read only numbers and ignored Booleans.

Authentication methods:
- `LOGIN` and `PLAIN` use `user` and `pass`, on both platforms.
- `CRAM-MD5`, `DIGEST-MD5`, `NTLM`, `SRP`, `GSSAPI`, `KERBEROS_V4` go through SASL with `user` and `pass`: macOS only (see [Requirements](#requirements--platform-notes)).
- `GMAIL` and `OUTLOOK` use the `XOAUTH2` mechanism with `user` and `accessToken`.
- `AUTO` tries the methods the server announces in its `EHLO` reply, in the order `DIGEST-MD5`, `CRAM-MD5`, `LOGIN`, `PLAIN`, and stops at the first that succeeds. If the server announces none, or `user` is empty, the plugin doesn't authenticate and the step succeeds (a relay that needs no login). If every announced method fails, the step fails with the last method's error. (Current source, 2026: release 1.0 stopped after a failed `DIGEST-MD5` and could report success without having authenticated.)

#### Message object

| Property | Type | Description |
|---|---|---|
| `subject` | Text | Subject |
| `body` | Text | Plain text body |
| `contentType` | Text | MIME type of the body. Default `text/plain`. Parsed by libetpan, so it can carry parameters (`text/plain; format=flowed; delsp=yes`) |
| `charset` | Text | Default `utf-8`. Also `iso-2022-jp`, `shift_jis` (or `shift-jis`), `windows-31j` (or `windows_31j`, `cp932`). Case-insensitive |
| `from` | Text array | `From:` header, each element `Name <name@example.com>` |
| `to` | Text array | `To:` header and recipients |
| `cc` | Text array | `Cc:` header and recipients |
| `bcc` | Text array | Recipients that get the message through `RCPT TO` only. No `Bcc:` header is written (current source, 2026; release 1.0 wrote one, so every recipient could see the Bcc addresses) |
| `replyTo` | Text array | `Reply-To:` header |

How `charset` is applied:

| `charset` | Body | Subject and display names |
|---|---|---|
| `utf-8` | UTF-8, Base64 | `=?utf-8?B?…?=` |
| `iso-2022-jp` | ISO-2022-JP, 7bit | Subject `=?iso-2022-jp?Q?…?=`, display names `=?iso-2022-jp?B?…?=` |
| `shift_jis` | Shift_JIS (JIS X 0213), Base64 | `=?shift_jis?B?…?=` |
| `windows-31j` | Windows-31J (CP932), Base64 | `=?windows-31j?B?…?=` |
| anything else | UTF-8, Base64, but labelled with the given name | as `utf-8` |

The body's `Content-Type` always carries `charset` exactly as you wrote it (`cp932`, `Shift-JIS`, …).

Characters that have no equivalent in the target Japanese encoding are dropped (the conversion is lossy, it doesn't stop). A recipient string that libetpan can't parse as a single mailbox (for example a group `Team: a@x, b@y;`) is skipped for `RCPT TO`.

#### Result object

```json
{
  "session": {
    "success": true,
    "details": [
      {"operation": "connection", "ssl": false, "host": "smtp.example.com", "port": 587, "verify_certificate": true, "library_error": "…", "library_error_code": 0},
      {"operation": "identification", "tls": true, "allow_insecure": false, "verify_certificate": true, "library_error": "…", "library_error_code": 0},
      {"operation": "authentication", "method": "LOGIN", "server": "smtp.example.com", "tls": true, "library_error": "…", "library_error_code": 0}
    ]
  },
  "messages": [
    {
      "success": true,
      "details": [
        {"operation": "mail", "from": "name@example.com", "library_error": "…", "library_error_code": 0},
        {"operation": "rcpt", "to": "someone@example.com", "library_error": "…", "library_error_code": 0},
        {"operation": "data", "size": 1234, "library_error": "…", "library_error_code": 0}
      ]
    }
  ]
}
```

| Property | Type | Description |
|---|---|---|
| `session.success` | Boolean | Connection, greeting and authentication all succeeded |
| `session.details` | Collection | One entry each for `connection`, `identification` and `authentication`. The three entries are present even when an earlier step failed |
| `messages` | Collection | One entry per message that got past `MAIL FROM`, in order |
| `messages[i].success` | Boolean | The server accepted the message data |
| `messages[i].details` | Collection | `mail`, then one `rcpt` per recipient (property `to`, `cc` or `bcc` holds the address), then `data` (`size` = bytes sent) when `DATA` was accepted |
| `library_error` / `library_error_code` | Text / Longint | libetpan's message and code for that step (`0` = no error) |
| `certificate_error` | Text | In `connection` (SSL on connect) or `identification` (`STARTTLS`): why the server certificate was rejected. Present only then; `library_error_code` is `27` |

The result never contains the password or the OAuth 2 token (current source, 2026; release 1.0 put the token in the `authentication` entry).

#### Callback method

If `callback` names a project method, the plugin calls it for every chunk of the SMTP conversation (data sent and received):

```4d
MyCallback ( index ; total ; log ; context )
```

| Parameter | Type | Description |
|---|---|---|
| `$1` | Longint | Index of the message being sent (1-based), `0` during connection and authentication |
| `$2` | Longint | Number of messages in `messages` |
| `$3` | Text | Raw SMTP traffic for this chunk (commands, replies, message data) |
| `$4` | Text | `context` from `params`, as JSON text (`""` if none) |

The method is looked up by name; if no project method has that name, the plugin falls back to `EXECUTE METHOD` with the same parameters. It runs in the calling process, during the send. What the plugin sends during authentication (the Base64-encoded user name and password, the OAuth 2 token) reaches `$3` as `[authentication data not shown]`; the server's replies are passed unchanged (current source, 2026; release 1.0 passed the credentials).

### Example

From the original README: the same message sent once in each supported encoding.

```4d
C_OBJECT($m;$o)
ARRAY OBJECT($mm;0)

//params
OB SET($o;\
"user";"keisuke.miyako";\
"pass";"**********";\
"port";587;\
"tls";True;\
"allowInsecure";False;\
"host";"exchange.4d.com";\
"sender";"株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>";\
"authentication";"LOGIN";\
"timeout";0)

//messages
OB SET($m;"contentType";"text/plain";"charset";"utf-8")
OB SET($m;\
"subject";("日本語ですよ")*10;\
"body";(Char(0x203E)+Char(0x00A5)+"日本語ですよｶｷｸｹｺ髙橋")*100)

ARRAY TEXT($from;1)
$from{1}:=("日本語ですよ"*10)+" <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"from";$from)

ARRAY TEXT($to;1)
$to{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"to";$to)

ARRAY TEXT($cc;1)
$cc{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"cc";$cc)

ARRAY TEXT($bcc;1)
$bcc{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"bcc";$bcc)

ARRAY TEXT($replyTo;1)
$replyTo{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"replyTo";$replyTo)

//utf-8
APPEND TO ARRAY($mm;OB Copy($m))

//shift_jis
OB SET($m;"contentType";"text/plain";"charset";"shift_jis")
APPEND TO ARRAY($mm;OB Copy($m))

//iso-2022-jp
OB SET($m;"contentType";"text/plain; format=flowed; delsp=yes; ";"charset";"iso-2022-jp")
APPEND TO ARRAY($mm;OB Copy($m))

//windos-31j
OB SET($m;"contentType";"text/plain";"charset";"windows-31j")
APPEND TO ARRAY($mm;OB Copy($m))

$params:=JSON Stringify($o)
$messages:=JSON Stringify array($mm)

$result:=etpan smtp send ($params;$messages)

$info:=JSON Parse($result)
```

From the original README: progress through a callback. The `context` object is passed to `MyCallback` as `$4`.

```4d
C_OBJECT($m;$o)
ARRAY OBJECT($mm;0)

//params
OB SET($o;\
"user";"keisuke.miyako";\
"pass";"**********";\
"port";587;\
"tls";True;\
"allowInsecure";False;\
"host";"exchange.4d.com";\
"sender";"株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>";\
"authentication";"LOGIN";\
"timeout";0)

//messages
OB SET($m;"contentType";"text/plain";"charset";"utf-8")
OB SET($m;\
"subject";("日本語ですよ")*10;\
"body";(Char(0x203E)+Char(0x00A5)+"日本語ですよｶｷｸｹｺ髙橋")*100)

ARRAY TEXT($from;1)
$from{1}:=("日本語ですよ"*10)+" <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"from";$from)

ARRAY TEXT($to;1)
$to{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"to";$to)

ARRAY TEXT($cc;1)
$cc{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"cc";$cc)

ARRAY TEXT($bcc;1)
$bcc{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"bcc";$bcc)

ARRAY TEXT($replyTo;1)
$replyTo{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
OB SET ARRAY($m;"replyTo";$replyTo)

//utf-8
APPEND TO ARRAY($mm;OB Copy($m))

$p:=Progress New 
Progress SET PROGRESS ($p;0)

$w:=Open form window("Form1")

C_OBJECT($context)
OB SET($context;\
"progress";$p;\
"window";$w)

OB SET($o;"context";$context)

$params:=JSON Stringify($o)
$messages:=JSON Stringify array($mm)

$result:=etpan smtp send ($params;$messages;"MyCallback")

$info:=JSON Parse($result)

Progress QUIT ($p)
```

A callback that updates the progress bar. It uses only the documented parameters; check the Progress component's commands for your version:

```4d
  // MyCallback
C_LONGINT($1;$2)
C_TEXT($3;$4)
C_OBJECT($context)

$context:=JSON Parse($4)
If ($2>0)
	Progress SET PROGRESS (OB Get($context;"progress");$1/$2)
End if 
```

SSL on connect (port 465): `tls` must be the number `0`.

```4d
C_OBJECT($o)
OB SET($o;"host";"smtp.example.com";"port";465;"tls";0;"authentication";"PLAIN")
OB SET($o;"user";"name@example.com";"pass";$password;"sender";"name@example.com")

$result:=etpan smtp send (JSON Stringify($o);$messages)
$info:=JSON Parse($result)
If (Not(OB Get(OB Get($info;"session");"success")))
	  // inspect the "details" collection of "session"
End if 
```

---

## Error handling & troubleshooting

- **Nothing happens and the result is `{"messages":[],"session":{}}`**: `params` or `messages` is not valid JSON, or `messages` is not an array. Build them with `JSON Stringify` / `JSON Stringify array`.
- **The session fails with `certificate_error`**: the server certificate isn't trusted by the system, has expired, or doesn't match `host` (connect with the name in the certificate, not an IP address or an alias). For a test server with a self-signed certificate, add the certificate to the system's trusted certificates or pass `"verifyCertificate":0`.
- **`library_error_code` is `5` ("not implemented") for authentication on Windows**: the method needs SASL, which the Windows build doesn't have. Use `LOGIN`, `PLAIN`, `GMAIL`/`OUTLOOK`, or `AUTO`.
- **`library_error_code` is `1` for connection, identification or authentication with release 1.0**: release 1.0 kept only "failed / not failed" for these three steps. The current source returns libetpan's real code.
- **The connection hangs for a long time on an unreachable host**: `timeout` `0` means libetpan's default, not a short timeout. Set `timeout` (seconds), and run the command in its own process.
- **Bcc recipients are visible, or UTF-8 subjects lose characters (`Hello World` arriving as `Hello orld`)**: both are release 1.0 bugs, fixed in the current source (2026). The UTF-8 header encoder now keeps every character, never splits one between two encoded words, and keeps each encoded word within 75 characters (RFC 2047).
- **A message is missing from `messages`**: its `MAIL FROM` was refused, or the array element was not an object. The `mail` entry with the error is not returned either; use the callback to see the reply.
- **A recipient is silently not used**: the string couldn't be parsed as one mailbox (`Name <addr>` or `addr`). Groups are not supported.
- **Credentials in logs with release 1.0**: its callback received the authentication exchange and its result contained the OAuth token. The current source hides both.

---

## Building

The libraries are built from pinned sources by two scripts; their output is ignored by git.

- **macOS**: `scripts/build-macos-deps.sh` builds OpenSSL and libetpan once per architecture and merges them into universal archives in `a/` (`libetpan.a`, `libssl.a`, `libcrypto.a`), and copies libetpan's headers to `include/mac/`. It needs the Xcode command line tools and `brew install autoconf automake libtool`. The Xcode project then links those archives plus `-lsasl2 -lz -liconv` and `Security.framework`.
- **Windows**: `scripts\build-windows-deps.ps1` builds OpenSSL (static, `/MT`) and libetpan from its `build-windows` Visual Studio project, turned into a static library without SASL or zlib, into `lib\windows64\` (`libetpan.lib`, `libssl.lib`, `libcrypto.lib`), and copies the headers to `include\windows\`. It needs Visual Studio 2022 with the C++ tools and Strawberry Perl.

`.github/workflows/ci.yml` runs both scripts and builds the plugin, unsigned, on every push; `release.yml` does the same before signing. Both cache the libraries under the hash of the script, so changing a pinned version rebuilds them.

### Independent Bump and Build

The two release-related Actions are independent manual operations:

- **Bump version** takes one required `mode` (`patch`, `minor`, or `major`, default `patch`). Select a branch with the built-in ref selector. It validates the selected immutable source, commits only version-source files as the Actions bot, and pushes one direct child to that same branch. It never tags, builds, publishes, or dispatches another workflow.
- **Build** has no custom inputs. Select the desired ref; the selected immutable commit supplies the canonical `X.Y.Z` version. It builds Windows x64, then the universal macOS plugin, preserves resources, signs, notarizes, staples, and creates a new `vX.Y.Z` tag and release with ZIP and DMG assets. It does not increment source versions. There is no default-branch-only restriction.

The coordinated source authority is the three project-level
`MARKETING_VERSION` and `CURRENT_PROJECT_VERSION` settings in
`etpan.xcodeproj/project.pbxproj` (Development, Deployment, Default),
`Info.plist`'s required `CFBundleShortVersionString` (and `CFBundleVersion`
only if present), and the version fields in the copied source
`English.lproj/InfoPlist.strings`. Known Xcode version references are preserved.
The original Bump header introduced in `8b84ad3e32d2cc66cdee500530391039ddd7ed95`
explicitly coordinates marketing/build/plist versions; its marketing-only
implementation left the build settings behind when
`1b81b7977f009889fab154879d3793b4234a6c02` bumped to `1.1.0`.
This migration keeps that existing `1.1.0` authority, aligns only stale
coordinated source tokens, and leaves committed destination metadata untouched.
Destination bundle plists/localizations are generated output, not authority.
Build validates freshly built metadata, including compiled localization plists.

Both operations fail closed on invalid, duplicated, unresolved, or drifting
source metadata. Bump requires the committed executable pre-push guard before
editing and immediately before pushing; the actual advertised old branch SHA
must still equal the selected event SHA. It never force-pushes or follows tags.
Build serializes publication across refs with a constant repository-wide
concurrency group and `cancel-in-progress: false` (not a FIFO guarantee).
Authenticated availability checks run before native work and again after all
native/signing/notarization work. Existing tags or draft/published releases,
including same-SHA collisions, abort rather than being reused.

Publication uses separate create-only tag, release, and asset requests. Release
notes remain empty, with generated notes disabled, matching the original
release policy. A failure retains any created tag, release, or uploaded assets.
**Manual recovery is required:** inspect the reported tag/release ID and
partial assets, reconcile the state explicitly, and only then choose a new
source version or deliberately remove the failed publication outside this
workflow. Do not retry expecting overwrite, rollback, or automatic cleanup.

Build requires an initially clean checkout, then preserves exact generated
bytes at its final gate while independently checking immutable HEAD, index,
and raw nongenerated source/configuration bytes. Unexpected untracked or
ignored files and hidden index flags are rejected. No output is reset merely
to make the worktree appear clean.

Install the offline test dependency with
`python3 -m pip install -r tests/requirements.txt`. Workflow regressions run with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`;
`actionlint .github/workflows/*.yml` checks all workflows. Native-command
regressions use closed-PATH stubs, not real native or credential commands.
The unrelated **CI** retains its original branch-push, pull-request, and manual
triggers and therefore still performs real unsigned native builds on push/PR.

---

## Quick reference

```4d
C_OBJECT($o;$m)
ARRAY OBJECT($mm;0)

OB SET($o;"host";"smtp.example.com";"port";587;"tls";1;"allowInsecure";0;"timeout";30)
OB SET($o;"authentication";"LOGIN";"user";$user;"pass";$password)
OB SET($o;"sender";"Me <me@example.com>")

OB SET($m;"subject";"Hello";"body";"Body text";"charset";"iso-2022-jp")
ARRAY TEXT($to;1)
$to{1}:="You <you@example.com>"
OB SET ARRAY($m;"to";$to)
APPEND TO ARRAY($mm;$m)

$info:=JSON Parse(etpan smtp send (JSON Stringify($o);JSON Stringify array($mm)))
```

---

## Notes on Japanese encodings

From the original README (Japanese). For UTF-8 the claim that headers are never split inside a character holds since the 2026 fix of the UTF-8 encoder; release 1.0 could split one.

### ISO-2022-JPについて

* 4D Internet Commandsよりも優れている点

1. オーバーラインをチルダに変換しない
1. 円記号をバックスラッシュに変換しない
1. 半角カタカナを全角カタカナに変換しない
1. Windowsの機種依存文字をサポート
1. 長い宛先・件名のサポート

* 78行でソフト改行が挿入されることを回避するためには，``format=flowed; delsp=yes;``が必要です。

* 1~3は，機種依存，かつメールサーバー依存です。

* Microsoftのメールサーバーを経由した場合，Shift_JISと同じように変換（チルダ・バックスラッシュ・全角カタカナ）されるかもしれません。

### Shift_JISについて

* 4D Internet Commandsよりも優れている点

1. 変換できない文字でストップしない（lossy変換）
1. Windowsの機種依存文字をサポート
1. JIS X 0213拡張文字をサポート
1. Shift_JISとWindows-31Jを区別する
1. 長い宛先・件名のサポート

* 文字コード``windows-31j``, ``windows_31j``, ``cp932``を指定した場合，Microsoft仕様のShift_JIS（X 0213含む）が使用されます。「はしごたか」は0xEEE0（NECコード）に変換され，はしごだかとして表示されます。（メールクライアント依存）

* 文字コード``shift-jis``, ``shift_jis``を指定した場合，標準仕様のShift_JIS（X 0213含む）が使用されます。「はしごたか」は標準の「高」に変換されます。（メールクライアント非依存）

### メモ

* 文字数

``Shift_JIS`` / ``Windows-31J``: ``14605``文字（``11233`` + 機種依存）

``ISO-2022-JP``: ``7518``文字（``6879`` + 機種依存）

* 長いヘッダーについて

ISO-2022-JPが指定された場合，件名は``Quoted-Printable``でエンコードしますが，宛先は``Base64``でエンコードします。これは，``Quoted-Printable``を使用した場合，``"name" <name@domain.com>``のように表示名にダブルクオートがライブラリによって付けられ，ヘッダーが折り返された場合，開いたままとなってしまうことを回避するためです。

ISO-2022-JP, Shift_JIS, UTF-8ともに，折り返しが文字の途中で発生しないように配慮しています。また，ISO-2022-JPは折り返しの手前でステートをASCIIに戻しています。いずれも，長いヘッダーで文字化けが発生しないようにするためです。
