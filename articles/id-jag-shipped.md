---
title: 'ID-JAG が製品になった日: IETF の draft が Okta の GA 機能として出荷されるまで'
published: false
description: '2026年3月に ID-JAG を読んだときは、まだ IETF の WG ドラフトだった。6月17日に MCP の Enterprise-Managed Authorization が Stable になり、8月24日に Okta Agent SSO が GA になって追加費用なしで同梱された。3層のプロファイル構造、token_type: N_A という珍しい値、そして「IdP が管理者ポリシーを評価する」という一行が何を変えたのかを仕様本文から追う'
tags:
  - oauth
  - identity
  - mcp
  - ai
series: AI Agent Identity
id: 4589227
---

2026年3月、[ID-JAG の記事](https://dev.to/kanywst/id-jag-deep-dive-1mhp)を書いた。あのとき ID-JAG は IETF の WG ドラフトで、「面白い仕組みだが、実際に使われるのはまだ先だろう」と思っていた。

半年で状況が変わった。日付を並べるとこうなる。

| 日付 | 出来事 |
| --- | --- |
| 2026-05-21 | `draft-ietf-oauth-identity-assertion-authz-grant` が **-04** に |
| 2026-06-17 | MCP の Enterprise-Managed Authorization が **Stable に昇格** (commit `877b4fdf`)。同日 `id-jag-04` に整合 |
| 2026-06-22 | 土台の `draft-ietf-oauth-identity-chaining` が **IESG 承認** (IETF の運営グループによる承認。RFC になる直前の最後の関門)、RFC Editor キューへ |
| 2026-07-28 | MCP 2026-07-28 仕様がリリース |
| **2026-08-24** | **Okta Agent SSO が GA**。Cross App Access が core Okta SSO に追加費用なしで同梱 |

**まだ RFC になっていない仕組みが、エンタープライズ IdP の標準機能として出荷された。**

この記事では、ID-JAG が何を解いているのかを仕様本文から確認し直して、なぜこれだけ速く製品化されたのか、そしてその速さが何を意味するのかを整理する。

## 前提: N個の MCP サーバに N回同意する問題

社内で MCP を本格的に使いはじめると、すぐこうなる。

Claude を MCP クライアントとして、社内の MCP サーバに繋ぐ。Slack の MCP サーバ、Notion の MCP サーバ、Jira の、Datadog の、社内 DB の。

素の OAuth でやると、**ユーザーはサーバの数だけ同意画面を踏む**。しかもトークンには有効期限があるので、切れるたびにまた踏む。

管理者側から見るとさらに悪い。

- 誰がどの MCP サーバに繋いだのか、把握する手段がない
- 「この MCP サーバは社内利用禁止」を強制する手段がない
- 退職者のトークンを一括で失効させる手段がない

同意はユーザーの手元で完結していて、組織が介在する場所がどこにもない。

ID-JAG が入れたのは、その介在点だ。

![N回の同意が、管理者が一度定義したポリシーの評価に置き換わる](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/id-jag-shipped/diagrams/01-consent-vs-policy.png)

## 3層のプロファイル構造

ID-JAG まわりは仕様が3つ重なっていて、最初これで混乱した。IETF でいう「プロファイル」は、一般的な仕様のパラメータを特定の用途向けに固定した仕様のことだ。整理するとこうなる。

```text
draft-ietf-oauth-identity-chaining
  「信頼ドメインをまたいで identity をつなぐ」一般論
  IESG 承認済み、RFC Editor キュー (2026-06-22)
        |
        | のプロファイル
        v
draft-ietf-oauth-identity-assertion-authz-grant  (= ID-JAG)
  「SSO で得た identity assertion を、別ドメインの
    アクセストークンに換える」具体化
  -04 (2026-05-21)、WG 文書
        |
        | のプロファイル
        v
MCP Enterprise-Managed Authorization (EMA)
  「その Client が MCP Client、
    Resource Server が MCP Server である」と固定
  Stable (2026-06-17)
```

EMA の仕様書は、この関係を冒頭で明示している。

> This document defines an application of the "Identity Assertion JWT Authorization Grant" for use within enterprise deployments of the Model Context Protocol (MCP).

そして役割の対応表が続く。

| ID-JAG の役割 | MCP EMA での実体 |
| --- | --- |
| Client | MCP Client |
| Resource Server | MCP Server |
| Resource Authorization Server | MCP Server の RFC 9728 Protected Resource Metadata が示す AS |
| IdP Authorization Server | SSO に使うエンタープライズ IdP |

**プロファイルが3段重なっている**ことは、実装するときに効いてくる。エラーの原因を追うとき、どの層の要件に違反したのかを切り分ける必要がある。

![identity-chaining から MCP EMA までの3層。それぞれの標準化ステータスが違う](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/id-jag-shipped/diagrams/02-three-layers.png)

## フローを仕様の HTTP で追う

抽象的な説明より、実際に飛ぶリクエストを見たほうが早い。EMA の仕様本文から引く。

### 1. SSO して ID Token をもらう

普通の OIDC だ。

```text
POST /token HTTP/1.1
Host: acme.idp.example
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=.....
```

```json
{
  "id_token": "eyJraWQiOiJzMTZ0cVNtODhwREo4VGZCXzdrSEtQ...",
  "token_type": "Bearer",
  "access_token": "7SliwCQP1brGdjBtsaMnXo",
  "scope": "openid"
}
```

MCP Client はこの ID Token を保持する。ここまでは何も新しくない。

### 2. ID Token を ID-JAG に交換する

ここが本体だ。RFC 8693 のトークン交換を IdP に対して行う。

トークン交換は「今持っているトークン (`subject_token`) を AS に渡して、別の用途向けのトークンに引き換える」仕組みだ。`requested_token_type` で「何が欲しいか」、`audience` で「どの AS 向けか」、`resource` で「どのリソース向けか」を指定する。**ID-JAG はこの交換に、新しい `requested_token_type` の値を1つ足しただけ**だと思っていい。

```text
POST /oauth2/token HTTP/1.1
Host: acme.idp.example
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&requested_token_type=urn:ietf:params:oauth:token-type:id-jag
&audience=https://auth.chat.example/
&resource=https://mcp.chat.example/
&scope=chat.read+chat.history
&subject_token=eyJraWQiOiJzMTZ0cVNtODhwREo4VGZCXzdrSEtQ...
&subject_token_type=urn:ietf:params:oauth:token-type:id_token
&client_id=2ec954a1d60620116d36d9ceb7
&client_secret=a26d84873504215a34a86d52ef5cd64f4b76
```

EMA が加えている制約は2つ。

- `audience` は MUST で Resource Authorization Server の issuer 識別子
- `resource` は OPTIONAL だが、設定するなら RFC 9728 で定義される MCP Server の Resource Identifier でなければならない

`audience` (どの AS 向けか) と `resource` (どの MCP サーバ向けか) が別のパラメータなのが要点だ。1つの AS が複数の MCP サーバのトークンを発行する構成を許している。

### 3. そして、この一行がすべてを変えている

仕様の 4.1 Processing Rules に、短く書かれている。

> The IdP **evaluates administrator-defined policies** for the token exchange request and determines if the MCP Client should be granted access to act on behalf of the user for the target MCP Server and scopes.

IdP が管理者定義のポリシーを評価する。

ユーザーの同意画面は、この設計にはどこにも出てこない。代わりに、管理者が事前に定義したポリシーが評価される。「このクライアントは、このユーザーの代理として、この MCP サーバに、このスコープでアクセスしてよいか」。

これが EMA の掲げる利点そのものだ。仕様の Introduction にこう書かれている。

> - For end users, this **removes the need to manually connect and authorize** the MCP Client to each MCP Server for use within the organization.
> - For enterprise admins, this enables **visibility and control over which MCP Servers are able to be used** within the organization.
> - For MCP clients, this enables the client to automatically obtain access tokens for any connected MCP servers **without user interaction**.

同意の主体が、エンドユーザーから組織の管理者に移った。 これは技術的な変更というより、統治の変更だ。

### 4. ID-JAG が返ってくる

```json
{
  "issued_token_type": "urn:ietf:params:oauth:token-type:id-jag",
  "access_token": "eyJhbGciOiJIUzI1NiIsI...",
  "token_type": "N_A",
  "scope": "chat.read chat.history",
  "expires_in": 300
}
```

`token_type: "N_A"` に注目してほしい。RFC 8693 が定義している値で、「このトークンは HTTP の認証スキームとして使うものではない」という意味だ。

これは重要な安全策になっている。ID-JAG を `Authorization: Bearer <id-jag>` として API に投げても意味がない。次のステップの入力にしかならない。用途が型で縛られている。

`expires_in: 300` (5分) も短い。中間生成物なので、長生きさせる理由がない。

ID-JAG そのものの中身はこうだ。

```json
{
  "typ": "oauth-id-jag+jwt"
}
.
{
  "jti": "9e43f81b64a33f20116179",
  "iss": "https://acme.idp.example",
  "sub": "U019488227",
  "email": "user@example.com",
  "aud": "https://auth.chat.example/",
  "resource": "https://mcp.chat.example/",
  "client_id": "f53f191f9311af35",
  "exp": 1311281970,
  "iat": 1311280970,
  "scope": "chat.read chat.history"
}
```

`typ` が `oauth-id-jag+jwt` で固定されている。JWT の混同 (confusion) 攻撃を防ぐための型タグで、ID Token としてもアクセストークンとしても解釈されないようにしている。

`sub` (ユーザー)、`client_id` (どのクライアントが)、`resource` (どの MCP サーバ向けか) が同居しているのがポイントだ。「誰の代理で、誰が、どこに」が1枚に入っている。

### 5. ID-JAG をアクセストークンに換える

最後は RFC 7523 の JWT Authorization Grant だ。

```text
POST /oauth2/token HTTP/1.1
Host: auth.chat.example

grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
&assertion=eyJhbGciOiJIUzI1NiIsI...
&client_id=https://client.example.com/client.json
```

`client_id` が URL になっている。EMA はここで CIMD に触れている。

> If the MCP Client is not pre-registered with the Resource Authorization Server, then it can use its Client ID Metadata Document as its client ID, and optionally authenticate using `private_key_jwt`.

この例が CIMD を使うように更新されたのは、Stable 昇格と同じ日 (2026-06-17、commit `9c25bbe8` "update example RAS client auth to use CIMD") だ。EMA と CIMD は同時に整備された。

そして 5.1 の処理規則に、もう1つ重要な MUST がある。

> In this profile, the issued access token **MUST** be audience-restricted to the MCP Server identified by the `resource` claim in the ID-JAG.

発行されるアクセストークンは、ID-JAG の `resource` クレームが示す MCP サーバに audience 制限されなければならない。 Slack 用に取ったトークンを Notion の MCP サーバに投げても通らない。MCP 本体が禁じているトークンのパススルーと、同じ方向の防御だ。

### 6. Discovery

AS がこのプロファイルに対応しているかは、AS メタデータで分かる。

```json
{
  "authorization_grant_profiles_supported": [
    "urn:ietf:params:oauth:grant-profile:id-jag"
  ]
}
```

## なぜこれだけ速く製品化されたのか

RFC になっていない仕組みが半年で GA になった。理由は3つあると思っている。

**1. 部品がすべて既存の RFC だった。** ID-JAG が新規に発明したものは、実はほとんどない。

| ステップ | 使っている既存仕様 |
| --- | --- |
| SSO | OpenID Connect / SAML |
| ID Token → ID-JAG | **RFC 8693** (Token Exchange) |
| ID-JAG → アクセストークン | **RFC 7523** (JWT Authorization Grant) |
| AS 発見 | **RFC 9728** (Protected Resource Metadata) |
| クライアント識別 | CIMD (draft) |

新しいのは `requested_token_type` に `id-jag` という値を足したことと、`typ: oauth-id-jag+jwt` の JWT を定義したこと、そして「IdP がポリシーを評価する」という接続点を決めたことだ。IdP ベンダにとって、実装は既存機能の組み合わせに近い。

**2. 解いている問題が緊急だった。** 企業が MCP を導入しようとして、最初にぶつかるのが統治の欠如だ。「どの MCP サーバに繋がっているか分からない」は、セキュリティ部門が導入を止める理由になる。これを解く仕組みへの需要は、標準化の完了を待たない。

**3. MCP 側に受け皿があった。** EMA は MCP のコア仕様ではなく拡張として作られている。`modelcontextprotocol/ext-auth` リポジトリに置かれていて、そこにある拡張は現時点で2本だけだ (EMA と、Draft 状態の `oauth-client-credentials`)。

拡張として切り出したのは賢い判断だった。コア仕様に入れると、MCP 全実装がエンタープライズ向けの複雑さを背負う。拡張なら、必要な人だけが実装する。

## Okta Agent SSO と Cross App Access

2026年8月24日、Okta が Agent SSO を GA にした。プレスリリースから重要な点を拾う。

- **Agent SSO は core Okta SSO に追加費用なしで同梱される**
- Cross App Access (XAA) の agent を first-class identity として Universal Directory に登録し、保存された認証情報ではなく短命のトークンを発行する
- XAA は MCP の公式な Enterprise-Managed Authorization 拡張として正式に組み込まれた
- 別サブスクリプションの「Okta for AI Agents」は、XAA 非対応のエージェントまで含めた discovery とガバナンス (アクセス認証、承認ワークフロー、エージェントの無効化) を担う

XAA 対応として名指しされている統合先はこれだ。Anthropic (Claude)、Archestra.AI、Asana、Atlassian、Canva、Datadog、Figma、Glean、Granola、Linear、MintMCP、Notion、Slack、Supabase。

なお IETF 125 (2026年3月16日) の議事録に、この点についてのやりとりが残っている。Pamela が「ドラフトの中で Cross-App-Access (XAA) という語が出てくるが、well defined ではない」と指摘し、Aaron が「明確にする」と答えている。製品名と仕様の用語がずれている状態が、そこから続いている。

## 標準化の状態と、実際の落差

ここで冷静に現在地を確認しておく。

| 層 | 標準化ステータス (2026-09-04) | 実装ステータス |
| --- | --- | --- |
| `identity-chaining` | **IESG 承認済み、RFC Editor キュー**。RFC 番号は未割当 | 土台として使われている |
| `identity-assertion-authz-grant` (ID-JAG) | **-04、WG 文書**。WGLC 未実施 | Okta が GA、Descope が対応 |
| MCP EMA | MCP の拡張として **Stable** | Okta の XAA が公式実装 |

**一番下の土台が RFC になっておらず、真ん中は WGLC すら通っていないのに、一番上は Stable で製品出荷されている。**

これはリスクでもあり、利点でもある。

リスク。 ID-JAG が -05 で非互換な変更を入れたら、出荷済みの実装が置いていかれる。過去に OAuth 界隈で何度も起きたことだ。特に IETF 126 では、著者たちが2つの未決事項について WG に方向性を求めていた。「Resource Server での JIT プロビジョニング」と「交換全体でのキーバインディング」だ。どちらも入れば構造が変わりうる。

利点。 実装が先行すると、仕様の穴が実運用で見つかる。IETF 126 の議事録で、MCP 側の Paul がまさにそれを報告している。

> Paul: We adopted that in MCP. 1/ Need more granular Error Code 2/ Ability to expose the capability

「MCP で採用した。1: もっと細かいエラーコードが要る。2: 能力を公開できる必要がある」。これは実装した者にしか出せないフィードバックで、仕様の質を上げる。

IETF が個人ドラフトの洪水に対して意図的に減速している一方で、ID-JAG のような「既存 RFC の組み合わせ」で解ける問題は速く進んでいる。この対比は示唆的だと思う。速く進むのは、新しい暗号や新しいトークン形式を発明しなくていい提案だ。

## 実装する側が見るべきところ

これから EMA を実装するなら、この順で読むのがいいと思う。

1. **RFC 8693 (Token Exchange)** を先に理解する。ID-JAG の中核はこれのプロファイルなので、`subject_token` / `requested_token_type` / `audience` / `resource` の関係が分かっていないと仕様が読めない
2. RFC 9728 (Protected Resource Metadata) で AS を発見する部分。MCP 2026-07-28 ではサーバ側が MUST で実装する
3. EMA 本文 を読む。分量は多くない
4. `authorization_grant_profiles_supported` を AS メタデータに出す。ここが対応の宣言になる
5. audience 制限を必ず実装する。5.1 の MUST。ここを守らないと、あるサーバ向けのトークンが別のサーバで通ってしまう

そして運用側で押さえるべきなのは、ポリシーの置き場所が IdP に移ったという点だ。誰がどの MCP サーバに繋げるかは、もはやアプリ側の設定ではなく IdP の管理画面にある。監査もそこを見る。

## まとめ

- ID-JAG は3層のプロファイル構造。`identity-chaining` (IESG 承認済み、RFC 待ち) → `identity-assertion-authz-grant` (-04、WG 文書) → **MCP EMA (Stable)**
- MCP EMA は2026-06-17 に Stable 昇格。同日に `id-jag-04` へ整合され、クライアント認証の例が CIMD を使うよう更新された
- 仕様の核心は一行。「IdP が管理者定義のポリシーを評価する」。同意の主体がエンドユーザーから組織の管理者に移った
- `token_type: "N_A"` で ID-JAG が HTTP 認証スキームとして使えないことを明示し、`typ: oauth-id-jag+jwt` で JWT 混同を防ぎ、発行されるアクセストークンは `resource` クレームの MCP サーバに audience 制限が MUST
- 速く製品化できた理由は、部品がすべて既存 RFC だったから。RFC 8693 + RFC 7523 + RFC 9728 + OIDC/SAML の組み合わせで、IdP ベンダにとっては既存機能の再配線に近い
- Okta Agent SSO が2026-08-24 に GA、core Okta SSO に追加費用なしで同梱。XAA が MCP EMA の公式実装として位置づけられ、Anthropic / Slack / Notion / Atlassian / Datadog / Figma など14の統合先が名指しされた
- 土台が RFC になる前に、その上の製品が出荷されている。非互換変更のリスクはあるが、実装からのフィードバック (「もっと細かいエラーコードが要る」) が仕様を良くしている面もある

エージェント認可の標準化全体が意図的に減速しているなかで、ID-JAG だけが速い。既にある RFC を組み合わせて、接続点を1つ決めただけだからだ。新しい暗号もトークン形式も持ち込んでいない。

_最終確認: 2026-09-04_
