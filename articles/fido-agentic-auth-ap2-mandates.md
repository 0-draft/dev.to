---
title: 'エージェントに何を許したかを、暗号的に証明可能な形で持ち歩く: AP2 の Mandate を JSON Schema から読む'
published: false
description: エージェントのツール呼び出しを値ごとに認可するゲートを手で書いたら、同じものが AP2 の Open Payment Mandate として標準化されていた。allowed_payees、amount_range、budget、reference。2026年4月28日に FIDO Alliance が2つの WG を発表し、Google の AP2 と Mastercard の Verifiable Intent は決済側の Payments TWG に寄贈された。JSON Schema を実際に読んで、何が新しくて何が既存部品の再利用なのかを分ける
tags:
  - security
  - ai
  - identity
  - payments
series: AI Agent Identity
id: 4589226
---

エージェントのツール呼び出しを「引数の値まで見て」認可するゲートを、自分で書いたことがある。送金ツールに対して、こういう段を並べた。

1. このツールはこのセッションの付与に含まれるか (scope)
2. この振込先は許可リストにあるか (allowlist)
3. この金額はこの主体の上限内か (ceiling)
4. この呼び出し ID は実行済みでないか (idempotency)
5. どれにも当てはまらなければ拒否 (default deny)

書きながら「これは誰かが標準化しているはずだ」と思っていた。していた。しかも、**ほぼ同じ項目名で**。

Google の AP2 (Agent Payments Protocol) の Open Payment Mandate スキーマにある制約の型を並べるとこうなる。

```text
payment.allowed_payees                 振込先の許可リスト
payment.amount_range                   金額の有効範囲
payment.budget                         繰り返し利用時の総額上限
payment.reference                      特定の checkout への紐付け
payment.agent_recurrence               再利用の条件
payment.execution_date                 実行の時間窓
payment.allowed_payment_instruments    使ってよい決済手段
payment.allowed_pisps                  仲介してよい決済事業者 (PISP)
```

そして2026年4月28日、FIDO Alliance がこれを標準化の軌道に乗せた。

この記事では、FIDO がどの枠でこれを進めようとしているのかを確認し、AP2 の実際の JSON Schema を読んで、何が本当に新しくて、何が既存部品の組み合わせなのかを分ける。

## 2026年4月28日、FIDO Alliance が動いた

[FIDO Alliance の発表](https://fidoalliance.org/fido-alliance-to-develop-standards-for-trusted-ai-agent-interactions/)は、**2つ**のワーキンググループについて書かれている。ここを混同すると話がズレるので先に分けておく。

- Agentic Authentication Technical Working Group: ユーザーが AI エージェントに安全かつプライベートに行為を委任する方法を扱う
- Payments Technical Working Group (Mastercard と Visa が議長): エージェント発の商取引の仕様を並行して開発する

AP2 と Verifiable Intent が寄贈されたのは後者、Payments Technical Working Group のほうだ。発表文は「Google と Mastercard からの技術的貢献が、これらの仕様の最初の土台を提供している」と書いており、「これらの仕様」は Payments TWG の agent-initiated commerce の仕様を指している。

つまりこの記事が読む AP2 は、決済側の作業だ。

寄贈の中身はこうだ。

- Google が AP2 (Agent Payments Protocol)。「安全な委任、検証可能な認可、信頼できるトランザクション実行のモデル」
- Mastercard が Verifiable Intent フレームワーク。AP2 と連携して動き、「ユーザーがデジタルエージェントによる代理行為を安全に認可し制御できるようにする」

FIDO は参加企業の一覧を公開していない。以下は発表文の中で名前が挙がった企業を並べたもので、正式なメンバーリストではない。それでも顔ぶれはこの動きの性質をよく表している。

| 陣営 | 企業 |
| --- | --- |
| 決済ネットワーク | Mastercard, Visa, American Express, PayPal |
| 大手プラットフォーム | Google, Amazon, OpenAI |
| ID / 認証 | Okta, Thales, OneSpan, Prove Identity, Egis Technology |
| パスワードマネージャ | 1Password, Dashlane, LastPass |
| 事業会社 | CVS Health |

決済側と認証側が同じテーブルに着いているのが、FIDO でやる理由だ。FIDO は元々「ユーザーの意図を、フィッシング耐性のある形で証明する」ための組織で、エージェントの委任はその延長線上にある。

Andrew Shikiar (executive director and CEO) の言葉。

> To scale this safely, people need to trust that these actions are secure, authorized and **truly reflect their intent**.

Agentic Authentication TWG のスコープは3つに整理されている。

1. Verifiable User Instructions: フィッシング耐性のある仕組みで、ユーザーが AI エージェントを認可できるようにする
2. Agent Authentication: サービス側が「このエージェントは認証済みユーザーの代理として、定められたパラメータの範囲内で動いている」ことを検証できるようにする
3. Trusted Delegation for Commerce: エージェント発のトランザクションが、ユーザーが制御する境界の内側で、検証可能な認可のもとで実行されるようにする

2番目の "within defined parameters" が効いている。検証の対象が「このエージェントは本物か」ではなく「定められた範囲内か」になっている。

## AP2 の中心概念: Mandate

AP2 のリポジトリ ([google-agentic-commerce/AP2](https://github.com/google-agentic-commerce/AP2)) を clone して、実際のスキーマを読んだ。

AP2 の中心にあるのは **Mandate** という単位だ。ドキュメントの定義では、Mandate は VDC (Verifiable Digital Credential) として表現される。「改ざん検知可能で、暗号署名されたデジタルオブジェクトであり、トランザクションの構成要素となるもの」。

Mandate には2種類あり、それぞれ2段階ある。

| Mandate | 誰と共有するか | Open (開いた段階) | Closed (閉じた段階) |
| --- | --- | --- | --- |
| **Checkout Mandate** | マーチャント | カート確定前の、ユーザーの制約と目的 | 確定した具体的な checkout の認可 |
| **Payment Mandate** | クレデンシャルプロバイダ / ネットワーク | 支払いの制約 (予算、使ってよい決済手段) | 確定した checkout に紐づく具体的な金額の認可 |

この Open と Closed の分離が、AP2 の設計の要だと思う。

Open Mandate は「まだ何を買うか決まっていない状態での認可」だ。「エアコンを5万円以内で、この3つの店のどれかから買っていい」がここに入る。ユーザーはこの時点で署名する。

Closed Mandate は「具体的なものが決まった状態での認可」。「A 店の型番 XYZ を 47,800円で買う」。

なぜ分けるのか。エージェントに任せるとき、ユーザーは具体的な商品を知らないからだ。知らないものに署名はできない。だから「制約に署名する」段階と「具体に署名する」段階を分ける。

AP2 のドキュメントはこう書いている。

> These VDCs operate within a defined role-based architecture and are **chained together to provide a complete, verifiable audit trail for both human-present and human-not-present transactions.**

Open から Closed へ鎖でつながり、監査証跡になる。

## スキーマを読む

`code/sdk/schemas/ap2/open_checkout_mandate.json` の冒頭がこれだ。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://ap2-protocol.org/schemas/open_checkout_mandate",
  "title": "Open Checkout Mandate",
  "description": "Agreement between a user and an agent (or chain of agents) to authorize future checkout actions.",
  "type": "object",
  "required": ["vct", "constraints", "cnf"],
  "properties": {
    "vct": {
      "type": "string",
      "description": "Verifiable Credential Type claim as defined in SD-JWT. MUST be 'mandate.checkout.open'.",
      "const": "mandate.checkout.open.1"
    },
    "constraints": { "...": "..." },
    "cnf": {
      "type": "object",
      "description": "Confirmation claim defined in RFC 7800 section 3.1. Used for key binding."
    },
    "iat": { "type": "integer" },
    "exp": { "type": "integer" }
  }
}
```

必須項目は `vct` / `constraints` / `cnf` の3つ。ここに全部詰まっている。

### `vct`: SD-JWT VC である

`vct` は **SD-JWT (Selective Disclosure JWT、クレームを1つずつ隠したり見せたりできる JWT の拡張) で定義される Verifiable Credential Type クレーム**だ。つまり AP2 の Mandate は、独自の署名形式ではなく SD-JWT VC として実装されている。

これは効く選択だ。SD-JWT の selective disclosure (選択的開示) がそのまま使える。実際、スキーマには `x-selectively-disclosable-array` という拡張キーワードが出てくる。

```json
"allowed": {
  "type": "array",
  "description": "Array of allowed Merchant objects.",
  "items": { "$ref": "types/merchant.json" },
  "x-selectively-disclosable-array": true
}
```

許可されたマーチャントのリストを、全部見せずに「この店が含まれている」ことだけ証明できる。決済の文脈では自然な要求で、A 店に対して「B 店と C 店も候補だった」を見せる必要はない。

なお、その土台である `draft-ietf-oauth-sd-jwt-vc` は -19 が2026年9月1日に IETF Last Call (IETF 全体に対する最後の意見募集) に入り、9月15日に終了予定という状態だ。ここで変更が入れば AP2 も追随することになる。AP2 は、まさに今 Last Call 中の仕様の上に乗っている。

### `cnf`: 所持証明が必須

`cnf` は RFC 7800 の confirmation claim。鍵バインディングのために使われ、required に入っている。

つまり Mandate は bearer クレデンシャルではない。持っているだけでは使えず、対応する秘密鍵が要る。

この設計判断が、2026年のあちこちで同時に起きているのが面白い。

| 仕様 | `cnf` の扱い |
| --- | --- |
| **AP2 Mandate** | **required** |
| **SPIFFE WIT-SVID** (2026-07-01 に SPIFFE 標準へマージ) | **MUST**。bearer としての提示を禁止 |
| SPIFFE JWT-SVID (従来) | なし。bearer |

SPIFFE はワークロード (サービスやコンテナ) に ID を配る標準で、その ID を載せた証明書やトークンを SVID と呼ぶ。従来の JWT-SVID は bearer、つまり持っているだけで使えた。2026年7月に標準へ入った WIT-SVID は `cnf` による鍵の所持証明を必須にし、bearer としての提示を禁じている。

「持っていれば使える」を捨てるという同じ方向に、決済もワークロード ID も動いている。

## 制約の一覧が、手で書いたゲートそのものだった

`open_payment_mandate.json` の `$defs` に定義されている制約の型を全部並べる。

| 制約型 | 説明 (スキーマ本文より) |
| --- | --- |
| `payment.allowed_payees` | Defines the set of possible payees |
| `payment.amount_range` | Defines the valid range for the payment amount |
| `payment.budget` | Defines the maximum total amount that can be spent when using the `payment.agent_recurrence` constraint |
| `payment.reference` | Constrains the payment to a specific checkout reference |
| `payment.agent_recurrence` | Provides conditions for the agent to reuse this Payment Mandate multiple times |
| `payment.execution_date` | Defines the valid time window for the payment execution |
| `payment.allowed_payment_instruments` | Defines the set of possible payment instruments |
| `payment.allowed_pisps` | Defines the set of PISPs authorized to facilitate the transaction |

冒頭に書いた手書きゲートと突き合わせる。

| 手で書いた段 | AP2 の制約型 |
| --- | --- |
| 振込先の許可リスト | **`payment.allowed_payees`** |
| 金額の上限 | **`payment.amount_range`** / **`payment.budget`** |
| 冪等性 (実行済み ID の拒否) | **`payment.reference`** (特定の checkout に紐付け) + `payment.agent_recurrence` |
| default deny | `constraints` が required なので、制約なしの Mandate が作れない |
| (書いていなかった) | `payment.execution_date` (時間窓) |
| (書いていなかった) | `payment.allowed_payment_instruments` / `payment.allowed_pisps` |

自分が書き漏らしていたものが2つある。時間窓と、経路の制限だ。

`payment.allowed_pisps` (どの決済仲介事業者を通してよいか) は、決済ドメイン特有に見えて、実は一般化できる。**「どのツールを使うか」だけでなく「どの経路を通るか」も認可の対象になりうる**、という発想だ。エージェントが3つの MCP サーバのどれを経由してもよいわけではない、という制約は普通にありうる。

Payment Mandate 本体のプロパティにも、見逃せないものがある。

```text
payee               支払先のマーチャント
payment_amount      通貨 (ISO 4217) と金額 (最小単位の整数)
payment_instrument  使う決済手段
pisp                Payment Initiation Service Provider
execution_date      ISO8601。省略時は即時実行
risk_data           mandate 作成時に信頼できる面が集めたリスクシグナルのマップ
```

`risk_data` が入っているのが現代的だ。「この Mandate が作られた時点で、どういうリスクシグナルが観測されていたか」を Mandate 自体に埋め込む。あとから紛争になったとき、当時の状況が証跡に残る。

## human-present と human-not-present

AP2 は2つのシナリオを明示的に分けている。

- **Human-Present**: ユーザーがトランザクション実行時にその場にいる
- Human-Not-Present: 自律エージェントがリアルタイムの人間の監督なしに動く

この区別が仕様の一級市民になっているのが良い。従来の決済でも「カード提示あり / なし」で責任分界が違うので、その延長として自然に接続する。

そして Human-Not-Present こそが、Open Mandate が存在する理由になる。人間がいないなら、事前に署名された制約だけが、その場での唯一の権限の根拠になる。

## 何が新しくて、何が新しくないのか

分けて整理する。

**新しくないもの (既存部品の再利用)。**

- 署名形式は SD-JWT VC。新しい暗号や新しいトークン形式を発明していない
- 鍵バインディングは RFC 7800 の `cnf`
- 選択的開示は SD-JWT の機能そのもの
- `iat` / `exp` は JWT の標準クレーム
- 通貨は ISO 4217、日付は ISO 8601

新しいもの。

- Open / Closed の2段階という構造。「制約に署名する」と「具体に署名する」を分けたこと
- 制約の型を標準化したこと。`payment.amount_range` や `payment.budget` に共通の名前が付いたこと自体が成果
- Mandate の鎖による監査証跡。「誰がいつ何を許したか」が非否認な形で残る
- `risk_data` を認可の証跡に含めるという発想

同じ配分が、企業向けエージェント認可の ID-JAG でも起きた。SSO で得た ID トークンを別ドメインのアクセストークンに交換する仕組みで、あれも新しい暗号を持ち込まず、既存の RFC 8693 と RFC 7523 を繋いだだけだ。半年で製品になっている。既存 RFC の組み合わせで解けるものは速く進む。AP2 が FIDO で標準化の軌道に乗れたのは、暗号的に新しいものをほとんど持ち込んでいないからだ。

## 慎重に見るべき点

期待だけ書いても仕方ないので、気になる点も挙げる。

**1. 土台がまだ固まっていない。** `draft-ietf-oauth-sd-jwt-vc` は2026年9月15日終了予定の IETF Last Call 中だ。Last Call で変更が入れば AP2 も追随する。

**2. WG は発足したばかり。** 2026年4月28日に「標準を開発する」と発表された段階で、成果物のスケジュールは公表されていない。今 AP2 を実装するのは、寄贈された仕様に対する実装であって、FIDO 標準に対する実装ではない。

**3. 決済に強く寄っている。** Mandate の語彙は `payee` / `payment_instrument` / `pisp` と、完全に決済のものだ。一般のツール呼び出し認可に転用するには、抽象化の層がもう1枚要る。そこは OpenID AuthZEN の COAZ のような、プロトコルごとの語彙を汎用の認可モデルに翻訳する仕組みが埋める場所になりそうだ。

**4. 標準が乱立する可能性。** エージェントの委任を扱う動きは、FIDO だけではない。IETF OAuth WG には個人ドラフトが積み上がり、W3C には Agent Identity Registry Protocol の CG があり、Linux Foundation の Agentic AI Foundation が MCP と A2A を抱えている。FIDO が決済側から入ってきたことで、地図はむしろ複雑になったとも言える。

ただ、発表文に Visa / Mastercard / Amex / PayPal が揃って出てきて、Google / Amazon / OpenAI / Okta も並んでいるのは効く。決済の相互運用性は、参加者が揃わないと価値がゼロになる領域なので、乱立のインセンティブが構造的に弱い。

## まとめ

- 2026年4月28日、FIDO Alliance が2つの WG について発表。Agentic Authentication TWG (委任の認証) と Payments TWG (エージェント発の商取引)。**AP2 と Verifiable Intent が寄贈されたのは Payments TWG のほう**。Visa / Amex / PayPal / OpenAI / Amazon / Okta / 1Password / LastPass など16社が参加
- WG のスコープは3つ。フィッシング耐性のあるユーザー認可、「定められたパラメータの範囲内で動いている」ことの検証、ユーザーが制御する境界内での商取引
- AP2 の中心は Mandate。Checkout Mandate と Payment Mandate があり、それぞれ Open (制約に署名) と Closed (具体に署名) の2段階に分かれる。エージェントに任せる時点でユーザーは具体的な商品を知らない、という現実に対応した構造
- Mandate は SD-JWT VC。`vct` クレームで型を示し、`x-selectively-disclosable-array` で選択的開示に対応。土台の `draft-ietf-oauth-sd-jwt-vc` は -19 が2026年9月15日終了の IETF Last Call 中
- `cnf` (RFC 7800) が required。bearer ではない。同じ判断が SPIFFE の WIT-SVID でも起きている
- Open Payment Mandate の制約型は、手書きの per-call 認可ゲートとほぼ一致した。`allowed_payees` / `amount_range` / `budget` / `reference` / `agent_recurrence` / `execution_date` / `allowed_payment_instruments` / `allowed_pisps`
- 書き漏らしていたのは時間窓と経路の制限。「どのツールか」だけでなく「どの経路を通るか」も認可の対象になりうる
- `risk_data` を Mandate に埋め込み、認可の時点のリスクシグナルを証跡に残す
- 暗号的に新しいものはほとんどない。SD-JWT VC + RFC 7800 + ISO 4217 + ISO 8601。速く進んだ理由はそこにある
- 懸念: 土台が Last Call 中、WG は発足直後、語彙が決済に強く寄っている、標準が乱立しうる

エージェント認可を自分で実装すると、だいたい同じ制約に行き着く。誰に、いくらまで、いつまで、どの経路で。AP2 の成果は、それに `payment.amount_range` のような共通の名前を与えたことだ。名前が揃えば、実装を突き合わせられる。

_最終確認: 2026-09-04_
