# 4d-plugin-etpan
Email client based on the [EtPan](http://www.etpan.org/libetpan.html) library

### Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|||

### Version

<img src="https://cloud.githubusercontent.com/assets/1725068/18940649/21945000-8645-11e6-86ed-4a0f800e5a73.png" width="32" height="32" /> <img src="https://cloud.githubusercontent.com/assets/1725068/18940648/2192ddba-8645-11e6-864d-6d5692d55717.png" width="32" height="32" />

## Syntax

```
result:=etpan smtp send (params;messages;callback)
```

Parameter|Type|Description
------------|------------|----
params|TEXT|Connection paramters in JSON (in)
messages|TEXT|Messages in JSON (in)
callback|TEXT|Callback method name (in)
result|TEXT|Results in JSON (in)

## Params

Atrribute|Type|Description
------------|------------|----
authentication|TEXT|``LOGIN``, ``PLAIN``, ``CRAM-MD5``, ``DIGEST-MD5``, ``NTLM``, ``SRP``, ``GSSAPI``, ``KERBEROS_V4``, ``AUTO``
user|TEXT|
pass|TEXT|
port|LONGINT|Default = ``25``
tls|BOOLEAN|Default = ``true``
allowInsecure|BOOLEAN|Default = ``false``
timeout|LONGINT|Default = ``0`` (no timeout)
host|TEXT|Default = ``localhost``
sender|TEXT|
accessToken|TEXT|OAuth (experimental)
authentication|TEXT|OAuth (experimental)

``AUTO`` authentication means ``DIGEST-MD5`` > ``CRAM-MD5`` > ``LOGIN`` > ``PLAIN`` (not recommneded, slow because of multiple retries). Other possible values (experimental) are ``GMAIL`` and ``OUTLOOK``

## Message

Atrribute|Type|Description
------------|------------|----
contentType|TEXT|Default = ``text/plain``
charset|TEXT|Default = ``utf-8`` currently supports ``shift_jis``, ``iso-2022-jp``, ``windows-31j``
subject|TEXT|
body|TEXT|
from|ARRAY TEXT|``NAME <name@domain.com>``
to|ARRAY TEXT|``NAME <name@domain.com>``
cc|ARRAY TEXT|``NAME <name@domain.com>``
bcc|ARRAY TEXT|``NAME <name@domain.com>``
replyTo|ARRAY TEXT|``NAME <name@domain.com>``

``Content-Transfer-Encoding`` is managed automatically.

### 各エンコーディングで同一のメールを送信する例
```
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
"authentication";"NTLM";\
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

ISO-2022-JPが指定された場合，件名は``Quoted-Printable``でエンコードしますが，宛先は``Base64``でエンコードします。これは，``Quoted-Printable``を使用した場合，``""name"" <name@domain.com>``のように表示名にダブルクオートがライブラリによって付けられ，ヘッダーが折り返された場合，開いたままとなってしまうことを回避するためです。

ISO-2022-JP, Shift_JIS, UTF-8ともに，折り返しが文字の途中で発生しないように配慮しています。また，ISO-2022-JPは折り返しの手前でステートをASCIIに戻しています。いずれも，長いヘッダーで文字化けが発生しないようにするためです。
