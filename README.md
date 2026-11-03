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

- **The prebuilt libraries in this repository are not universal yet.** `Contents/MacOS/libetpan.20.dylib`, `libssl.1.0.0.dylib` and `libcrypto.1.0.0.dylib` are i386 + x86_64 only (libetpan 1.7, OpenSSL 1.0.2k). Until they are rebuilt, the plugin only runs in an Intel (or Rosetta) 4D on macOS, and the release workflow stops at its library check. On Windows, `Contents/Windows64/libetpan.dll` (libetpan with OpenSSL 1.0.1j linked in) must stay next to `etpan.4DX`.
- **The command blocks the calling process** until the whole session is over: DNS lookup, connection, TLS handshake, authentication and every message. Call it from a dedicated process (`New process`, or a worker) if the user interface must stay responsive. The plugin is not declared thread-safe, so it can't run in a preemptive process.
- **The server certificate is not checked.** The plugin doesn't ask libetpan to verify the certificate or host name for SSL or STARTTLS connections, so the connection is encrypted but not authenticated (inferred from the code: no verification call is made; libetpan doesn't verify by default).
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
| `tls` | Longint (`1`/`0`) | `1` (default): connect in plain text, then `STARTTLS`. `0`: SSL on connect (SMTPS, usually port `465`). See the note below about Boolean values |
| `allowInsecure` | Longint (`1`/`0`) | `1`: with `tls` = `1`, skip `STARTTLS` and stay in plain text; also allows the `HELO` fallback. Default `0` |
| `timeout` | Longint | Network timeout in seconds. `0` (default) uses libetpan's built-in default, it is **not** "no timeout" |
| `user` | Text | User name for authentication |
| `pass` | Text | Password |
| `authentication` | Text | `LOGIN`, `PLAIN`, `CRAM-MD5`, `DIGEST-MD5`, `NTLM`, `SRP`, `GSSAPI`, `KERBEROS_V4`, `GMAIL`, `OUTLOOK` or `AUTO`. Case-insensitive. Empty or unknown = `AUTO` |
| `accessToken` | Text | OAuth 2 access token, used with `GMAIL` / `OUTLOOK` (experimental) |
| `sender` | Text | Envelope sender, `Name <name@example.com>` or `name@example.com`. Only the address goes into `MAIL FROM` |
| `context` | Object | Any object; it is passed to the callback as JSON text in `$4`. Other types are ignored |

**`tls` and `allowInsecure` are read only when they are numbers.** A Boolean (`True`/`False` in `OB SET`, `true`/`false` in JSON) is ignored and the default applies (`tls` = `1`, `allowInsecure` = `0`). Pass `1` or `0`.

Authentication methods:
- `LOGIN`, `PLAIN`, `CRAM-MD5`, `DIGEST-MD5`, `NTLM`, `SRP`, `GSSAPI`, `KERBEROS_V4` go through SASL with `user` and `pass`. **On Windows**, `NTLM` is known to fail.
- `GMAIL` and `OUTLOOK` use the `XOAUTH2` mechanism with `user` and `accessToken`.
- `AUTO` tries `DIGEST-MD5` first. **It does not reliably fall back to the other methods** and can report success without having authenticated (see [Error handling](#error-handling--troubleshooting)); name the method explicitly.

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
| `bcc` | Text array | Recipients. **Also written as a `Bcc:` header** in the message every recipient receives (see [Error handling](#error-handling--troubleshooting)) |
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
      {"operation": "connection", "ssl": false, "host": "smtp.example.com", "port": 587, "library_error": "…", "library_error_code": 0},
      {"operation": "identification", "tls": true, "allow_insecure": false, "library_error": "…", "library_error_code": 0},
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

With `GMAIL` / `OUTLOOK`, the `authentication` entry holds `oauth2_access_token` (the token itself) instead of `server`: don't log the result as is.

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

The method is looked up by name; if no project method has that name, the plugin falls back to `EXECUTE METHOD` with the same parameters. It runs in the calling process, during the send. **`$3` includes the authentication exchange**, i.e. the Base64-encoded user name and password for `LOGIN`/`PLAIN` and the token for `GMAIL`/`OUTLOOK`: don't write it to a log as is.

### Example

From the original README: the same message sent once in each supported encoding. Note that `tls` and `allowInsecure` are Booleans here, so they are ignored and the defaults (STARTTLS required) apply, which happens to match.

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
- **`library_error_code` is `1` ("unexpected error code") for connection, identification or authentication**: the plugin keeps only "failed / not failed" for these three steps, not libetpan's real code. Use the callback (`$3`) to see the server's actual reply. The codes for `mail`, `rcpt` and `data` are the real ones.
- **`AUTO` authentication reports success but the server then refuses `MAIL FROM` or `RCPT TO`**: `AUTO` tries `DIGEST-MD5`, and when that fails it doesn't fall back as intended; the session can be marked as successful without being authenticated. Set `authentication` explicitly.
- **`tls` / `allowInsecure` seem to have no effect**: they were passed as Booleans. Pass `1` or `0`.
- **The connection hangs for a long time on an unreachable host**: `timeout` `0` means libetpan's default, not a short timeout. Set `timeout` (seconds), and run the command in its own process.
- **Bcc recipients are visible**: the `bcc` addresses are written into a `Bcc:` header of the message, so every recipient can see them. Until this is changed, send the Bcc copies as a separate message, or don't use `bcc` when that matters.
- **UTF-8 subjects or display names lose characters**: the UTF-8 header encoder drops some bytes (for example `Hello` arrives as `ello`, and a multi-byte character near the end of the text can be cut). This affects the default `charset` `utf-8` only. The Japanese encodings are not affected.
- **A message is missing from `messages`**: its `MAIL FROM` was refused, or the array element was not an object. The `mail` entry with the error is not returned either; use the callback to see the reply.
- **A recipient is silently not used**: the string couldn't be parsed as one mailbox (`Name <addr>` or `addr`). Groups are not supported.
- **Credentials in logs**: the callback's `$3` contains the authentication exchange, and the result contains the OAuth token for `GMAIL`/`OUTLOOK`. Filter both before logging.
- **`NTLM` fails on Windows**: known issue; use another method.
- **Certificate errors are never reported**: the server certificate is not verified, so a TLS connection to the wrong server succeeds. Only use the plugin on networks where that risk is acceptable.

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

From the original README (Japanese). The claim that UTF-8 headers are never split inside a character does not hold for the current UTF-8 encoder, see [Error handling](#error-handling--troubleshooting).

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
