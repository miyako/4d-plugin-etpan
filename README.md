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

## Example of sending email in ISO-2022-JP

```
C_OBJECT($m;$o)
ARRAY OBJECT($mm;0)

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

OB SET($m;\
"contentType";"text/plain; format=flowed; delsp=yes; ";\
"charset";"iso-2022-jp")

OB SET($m;\
"subject";"日本語ですよ";\
"body";(Char(0x203E)+Char(0x00A5)+"日本語ですよｶｷｸｹｺ")*100)

ARRAY TEXT($from;1)
$from{1}:="株式会社フォーディー・ジャパン <keisuke.miyako@4d.com>"
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

APPEND TO ARRAY($mm;OB Copy($m))
  //APPEND TO ARRAY($mm;OB Copy($m))
  //APPEND TO ARRAY($mm;OB Copy($m))

$params:=JSON Stringify($o)
$messages:=JSON Stringify array($mm)

$result:=etpan smtp send ($params;$messages)

ARRAY OBJECT($results;0)
JSON PARSE ARRAY($result;$results)
```

## Params

Atrribute|Type|Description
------------|------------|----
authentication|TEXT|``LOGIN``, ``PLAIN``, ``CRAM-MD5``, ``DIGEST-MD5``, ``NTLM``, ``SRP``, ``GSSAPI``, ``KERBEROS_V4``, ``AUTO``


``AUTO`` authentication means ``DIGEST-MD5`` > ``CRAM-MD5`` > ``LOGIN`` > ``PLAIN`` (not recommneded, slow because of multiple retries).
