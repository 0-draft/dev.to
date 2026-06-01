---
title: 'WebAuthn を py_webauthn 抜きで書く: CBOR / COSE / attestation を手で組むハンズオン'
published: false
description: 'WebAuthn / Passkey の RP が裏で何をしてるか、py_webauthn と fido2 ライブラリを一切使わず、CBOR デコーダから signature 検証まで全部自分で書いて registration と authentication を完走する。GitHub: 0-draft/webauthn-the-hard-way'
tags:
  - webauthn
  - passkey
  - python
  - security
---

## Introduction

WebAuthn のサーバ側のチュートリアルは、だいたいこの一行で終わる。

```python
from webauthn import verify_registration_response

result = verify_registration_response(
    credential=credential,
    expected_challenge=challenge,
    expected_rp_id="localhost",
    expected_origin="http://localhost:5000",
)
```

`py_webauthn` も `fido2` (Yubico) も、SimpleWebAuthn (JS) も、API はだいたいこんな形をしている。これで動く。動くんだけど、中で何が起きてるかは見えない。

「attestationObject の CBOR を parse して、authData の byte レイアウトを切って、COSE_Key を ECDSA P-256 の公開鍵に変換して、attStmt の signature を 検証する」。文字としては知ってる。でも `verify_registration_response()` の一行に押し込められると、その手順を一度も手で追ったことがない自分に気づく。

そこで全部書いた。CBOR デコーダから書いた。`py_webauthn` も `fido2` も使わない。外部依存は `flask` と `cryptography` の primitive (ECDSA verify) だけ。レポジトリは `0-draft/webauthn-the-hard-way`。47 テストが通る MVP まで持っていって、その過程で分かったことを書く。

ゴール。

- WebAuthn ceremony の 2 つ (registration / authentication) を最初から最後まで byte レベルで追える
- CBOR / COSE / authenticatorData がそれぞれ何で、なぜ別々の層が必要なのか説明できる
- `fmt=none`, `fmt=packed`, `fmt=fido-u2f` の違いを signature base の違いとして区別できる
- なぜ Passkey の検証は意外にシンプルで、なぜチュートリアルはそれを見せないかが分かる

## 登場人物

WebAuthn は仕様書を読むとアクターが多くて頭が混乱する。まず絵にする。

![登場人物](./assets/webauthn-the-hard-way/diagrams/01-actors.png)

- **User**: 人間。指紋を当てるか、PIN を打つか、YubiKey に触る。
- **Authenticator**: 鍵を作って保管する箱。Touch ID / Windows Hello / YubiKey / Android。鍵そのものは絶対に外に出さない。
- **Browser**: `navigator.credentials.create()` と `.get()` を呼べる唯一の主体。仕様で要求される origin チェックを browser がやる。
- **Relying Party (RP)**: 私たちが書くサーバ。今回は `localhost:5000` で動く Flask。challenge を生成して、authenticator が返してきた attestation を verify する。

Registration の一往復はこうだ。

1. ブラウザが RP に「登録始めるよ」と POST する
2. RP が 32 バイトの challenge を返す
3. ブラウザが `navigator.credentials.create({publicKey: ...})` を呼ぶ
4. authenticator が鍵を作り、user の consent を取り、attestationObject と clientDataJSON を返す
5. ブラウザがそれを RP に POST する
6. RP は attestationObject を **CBOR としてデコードし**、authData を **byte レイアウトでパースし**、credentialPublicKey を **COSE_Key として解釈し**、attStmt を **format ごとに verify する**

この 6 のステップが「全部見せない」のがチュートリアルの世界。ここを開ける。

## CBOR を最初に書く理由

WebAuthn は CBOR (RFC 8949) 漬けだ。

- `attestationObject` 全体が CBOR の 3-key map (`fmt`, `authData`, `attStmt`)
- `credentialPublicKey` は CBOR map (COSE_Key)
- `extensions` も CBOR map

つまり CBOR デコーダが無いと WebAuthn は一行も読めない。逆に CBOR が読めると、authData の中の COSE_Key も extensions も一気に読める。だから最初に書く。

CBOR は読みやすい。バイトの上位 3 ビットが major type、下位 5 ビットが additional info (argument length)。

```text
0xa3  -> 0b101 00011 -> major type 5 (map), 3 entries
0x18 1864  -> major type 0 (uint), 1-byte arg, value=100
0x44 01 02 03 04  -> major type 2 (byte string), length 4, then 4 bytes
```

100 行強で書ける。リポジトリの `server/cbor.py` を読むと、`_read_argument` 関数が `additional info` を読んで「次の何バイトが値か」を返してるだけだと分かる。

RFC 8949 Appendix A はテストベクタ集。`0x00 -> 0`, `0x18 18 -> 24`, `0xa2 01 02 03 04 -> {1: 2, 3: 4}`、合計 30 個以上。これを通せば「とりあえずデコーダは仕様通り」と言える。実装後にこれをそのまま `tests/test_cbor.py` のパラメタライズドテストに流し込んだ。全通過した。

## COSE_Key の正体

COSE (RFC 8152) は CBOR の上の薄い層。「鍵を CBOR でどう表現するか」のラベル集 + α。WebAuthn の credentialPublicKey はこの形で来る。

ECDSA P-256 公開鍵だとこういう CBOR map になる。

```text
{
    1: 2,        # kty = EC2 (楕円曲線)
    3: -7,       # alg = ES256 (ECDSA with SHA-256)
   -1: 1,        # crv = P-256
   -2: <32 bytes>, # x 座標
   -3: <32 bytes>, # y 座標
}
```

このマップを取り出して、x と y を `cryptography` の `EllipticCurvePublicNumbers` に食わせれば、公開鍵オブジェクトが出来上がる。それが `server/cose.py` の `_parse_ec2()` の中身だ。

RSA (`kty=3`, `alg=-257`) もほぼ同じ。`-1` が modulus、`-2` が exponent。

たったこれだけなのに「COSE_Key を扱う」と言うと急に難しく聞こえる。実体は CBOR map の鍵 5 個ぶんだ。

## authenticatorData の byte レイアウト

ここが WebAuthn の中で一番 byte-level な部分。

![authData layout](./assets/webauthn-the-hard-way/diagrams/03-authdata-layout.png)

固定で 37 バイト、その後は flags 次第で可変。

- **rpIdHash (32 bytes)**: `SHA-256(rp.id)`。今回なら `SHA-256("localhost")`。authenticator は credential をこの RP に **しか** 使わせないために、`get()` のたびにこれを再送してくる。RP は受信した authData の先頭 32 バイトと自分が知ってる rpId のハッシュを比較する。これが「scope を authenticator 側で固定する」WebAuthn の中核。
- **flags (1 byte)**: ビットマップ。UP (user present), UV (user verified), BE (backup eligible / "syncable"), BS (backup state), AT (attested credential data 同梱), ED (extensions 同梱)。BE と BS は WebAuthn L3 で追加された Passkey 同期判定用。
- **signCount (4 bytes)**: 大きくなる counter。クローンされた authenticator を検知するヒント。 (実装してない authenticator も多いから、両端ゼロのままなら無視するルールが §7.2 にある)
- **AAGUID (16 bytes)**: authenticator のモデル ID。Touch ID なら `00000000-0000-0000-0000-000000000000` (Apple は意図的に匿名化する)。YubiKey なら `cb69481e-...`。FIDO MDS で照合できる。
- **credentialId**: 可変長。authenticator が作った credential の識別子。
- **credentialPublicKey**: COSE_Key (CBOR)。これがさっきの map。

リポジトリの `server/parsers.py` の `parse_authenticator_data` は仕様の表をそのまま `struct.unpack` で切り出してる。

```python
rp_id_hash = bytes(buf[0:32])
flags = buf[32]
sign_count = struct.unpack(">I", buf[33:37])[0]
```

仕様書を見ながら順番に切るだけ。意外に簡単だ。

## attestationObject と signature base

外側の `attestationObject` も CBOR の map で、たった 3 key。

![attestationObject](./assets/webauthn-the-hard-way/diagrams/02-attestation-object.png)

- `fmt`: 文字列。`"none"` / `"packed"` / `"fido-u2f"` / `"tpm"` / `"apple"` ...
- `authData`: 上で見た byte string
- `attStmt`: format ごとに違う map

ここの分岐が WebAuthn を「ややこしい」と感じさせる元凶。でも本質はひとつ。

**「authenticator が `何か` に対して signature を作っている。その `何か` の組み立て方だけが format 違いで違う」**

これを並べると一目で分かる。

![signature bases](./assets/webauthn-the-hard-way/diagrams/04-signature-bases.png)

`fmt=packed` は modern (CTAP2) のデフォルト。signature base は `authData || SHA-256(clientDataJSON)` の連結。署名鍵が credential 自身なら **self attestation**、別の attestation key + x5c (X.509 cert) で署名なら **full attestation**。

`fmt=fido-u2f` は CTAP1 / U2F 時代の YubiKey が出す。`0x00 || rpIdHash || clientDataHash || credentialId || pubKey` を組み立てて、attestation cert の公開鍵で verify する。pubKey は X9.62 の uncompressed form (`0x04 || x || y` の 65 バイト)。COSE_Key じゃなくて生バイトに戻すのがポイント。

`fmt=none` は signature 自体が無い。`attStmt` が空 map。attestation が要らない (RP 側で `attestation: "none"` を要求した) ときに来る。Touch ID も Windows Hello も、デフォルトはこれを返す。

そして **assertion (毎回のログイン)** は format を問わず `authData || SHA-256(clientDataJSON)` を credential の秘密鍵で署名する。registration の packed と同じ式だ。だから一度 packed が読めるとログイン側はすぐ書ける。

## Registration の 19 ステップ

WebAuthn L3 §7.1 は "Registering a New Credential" として 19 ステップの手順を箇条書きしている。実装してみると 5 グループに整理できる。

```text
[1] clientDataJSON チェック        : type, challenge, origin
[2] authData をパース             : 上の byte レイアウト
[3] flags チェック                : UP 必須、(設定により) UV 必須
[4] credentialPublicKey の alg 確認 : 自分が頼んだ alg のリストにある?
[5] attStmt を fmt 別に verify     : packed / fido-u2f / none
```

意外に短い。`server/verify.py` の `verify_registration` がだいたい 80 行。ここを書いていくと、ライブラリが「黒魔術」じゃないのが分かる。

## Authentication の 22 ステップ (§7.2)

毎回のログイン側はもっとシンプル。

```text
[1] credentialId で stored を引く  : RP の DB
[2] clientDataJSON チェック        : type=webauthn.get, challenge, origin
[3] authData をパース             : 今度は AT フラグなし
[4] flags チェック                : UP, UV
[5] 署名検証                      : authData || SHA-256(clientDataJSON) を stored の公開鍵で
[6] signCount が増えてる?         : クローン検知 (両端 0 なら skip)
```

ECDSA P-256 の signature verification を `cryptography.hazmat` に投げて終わり。本質的に「外側の checks + 1 回の verify」。これが Passkey の login が「速く、シンプル」と言われる理由の正体。

## ハンズオン: 実際に動かす

リポジトリを clone して動かす。

```bash
git clone https://github.com/0-draft/webauthn-the-hard-way.git
cd webauthn-the-hard-way
./run.sh
```

`run.sh` が venv を作って `flask` + `cryptography` を入れて Flask を `http://localhost:5000` で立ち上げる。ブラウザが自動で開く。

Mac で Chrome / Safari なら Touch ID が、Windows なら Windows Hello が呼ばれる。USB の YubiKey でも動く。`Register` を押して指紋を当てると、ターミナル側で `authData` の中身がパースされる様子が `cryptography` の例外なしに完走するはず。続けて `Authenticate` を押すと、サーバ側で signature 検証が走って `newSignCount` が増える。

何も認証器が手元にない場合は Chrome DevTools の "WebAuthn" タブで仮想 authenticator を enable できる。タブを開いて `Enable virtual authenticator environment` -> `Add` で `internal` / `resident keys` を有効化すると、ブラウザ内で Touch ID 相当の動作になる。

不正をシミュレートしたい場合は `tests/test_e2e.py` を読む。clientDataJSON の `origin` を `https://evil.example` に変えると `verify_registration` が `origin mismatch` で 400 を返す。signature の最後の 1 bit を反転させると `signature failed` で落ちる。signCount を増やさずに同じ assertion を再送すると `signCount did not increase` で reject される。仕様書の各 step の「これがなぜ要るか」を例外メッセージで体感できる。

## 学んだこと

書き終わって振り返ると、WebAuthn は「**仕様書の見た目より圧倒的に簡単な**」プロトコルだった。

CBOR を恐れていたが、major type 7 種 + additional info の table を見ながら 100 行書けば終わる。RFC 8949 Appendix A をテストベクタとして使えるので「自分の decoder が仕様通りか」が客観的に分かる。

COSE は CBOR の上の極薄レイヤ。「鍵を CBOR で書くときラベルを揃えとこう」というだけ。

authenticatorData は固定 37 バイト + 可変。`struct.unpack` で切れる。

attestation の format 違いは「**signature base の組み立て方が違う**」だけ。それ以外は全て同じ ECDSA P-256 over SHA-256。 (RSA も使える authenticator もあるが少数派)

Passkey の登録と検証は、本質的には次の式で説明できる。

```text
register: 公開鍵を保管する
login:    sig = sign(authData || SHA-256(clientDataJSON), 秘密鍵)
          verify with 保管した公開鍵
```

これが核。残りは layout の話。ライブラリは layout を hide してくれていたが、その結果 layout が見えなくなって、何が起きてるか説明できなくなる。一度自分で書くと、`py_webauthn` の API ドキュメントも仕様書も透けて見えるようになる。

## まとめ

- WebAuthn の RP は CBOR デコーダ + COSE_Key parser + authData byte slicer + format-specific signature verifier の 4 層で書ける
- 外部依存は signature primitive の `cryptography` だけで足りる
- WebAuthn L3 §7.1 / §7.2 はそれぞれ 19 / 22 ステップだが、実装すると意外に短い (合わせて 150 行未満)
- リポジトリ: <https://github.com/0-draft/webauthn-the-hard-way>。MIT。47 テストが通る MVP まで作った
- 次のステップ: `fmt=tpm` (Windows Hello with hw TPM) と `fmt=apple` (iCloud Keychain Passkey) を足すと、Passkey の本番運用とほぼ等価な実装になる

Passkey のチュートリアルで分からなかった人が、もう一度仕様書を開けるようになれば書いた価値があった。
