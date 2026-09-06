---
title: 'OAuth WG の採用文書は15本、個人ドラフトは80本: エージェント委任の標準化が意図的に進まない理由'
published: false
description: datatracker を数えた。OAuth WG が採用している active な文書は15本。その周りに個人ドラフトが80本あり、うち32本がエージェントか委任のものだった。2026年に採用されたのは2本だけ。WG は Clustering of OAuth WG Work という triage 戦略で応じ、9月に4本の interim を組んだ。9月28日の回のタイトルは Anthropic & OpenAI Agentic Use Cases。標準化が遅いことが失敗ではない理由を、一次資料から追う
tags:
  - oauth
  - security
  - ietf
  - ai
series: OAuth
id: 4589229
---

「AI エージェントの認可はまだ標準がない」という話をよく見る。それは正しいのだが、**「標準化が進んでいない」と「誰も提案していない」はまったく別のこと**だ。

提案は溢れている。むしろ溢れすぎている。

数えてみた。IETF の datatracker API に直接聞いた結果がこれだ。

```bash
curl -s "https://datatracker.ietf.org/api/v1/doc/document/\
?type=draft&states__slug__in=active&name__contains=oauth&format=json&limit=300"
```

```text
total: 95 | WG: 15 | individual: 80
individual oauth drafts matching agent/delegation: 32
```

前提を1つ置いておく。IETF では誰でもドラフトを投稿できる。`draft-<著者名>-oauth-*` という名前のものが個人ドラフトで、査読も合意も要らない。それが `draft-ietf-oauth-*` に変わるのが「WG 採用」で、ここで初めて WG が「この問題は自分たちの仕事だ」と引き受ける。以降の改訂は WG の合意で進む。つまり以下の数字の差は、提案された量と、WG が引き受けた量の差だ。

- OAuth WG が採用している active な文書は15本
- その周りに個人ドラフトが80本浮いている
- うち32本がエージェント / 委任 / actor / 減衰トークンに関するもの

IETF 全体まで広げると、タイトルに "agent" を含む active なドラフトは 420本超ある (日々増えるので、この記事の数字は2026年9月上旬のもの)。

そして 2026年に OAuth WG が採用したのは2本だけだ。しかも、そのどちらも「AI エージェント」を名乗る文書ではない。

この記事では、この非対称がなぜ生まれているのか、WG がそれにどう対処しているのかを、議事録とスライドと datatracker の実データから追う。結論を先に書くと、これは機能不全ではなく、意図的な減速だ。

## まず現状を正確に

### 採用されている15本

2026年9月4日時点の `draft-ietf-oauth-*` の active な文書、全部だ。

| ドラフト | 版 | 最終更新 |
| --- | --- | --- |
| `attestation-based-client-auth` | -11 | 2026-09-03 |
| `client-id-metadata-document` | -02 | 2026-07-06 |
| `first-party-apps` | -04 | 2026-08-26 |
| `identity-assertion-authz-grant` | -04 | 2026-05-21 |
| `identity-chaining` | -17 | 2026-08-21 |
| `rar-metadata-remediation` | **-00** | **2026-08-23** |
| `refresh-token-expiration` | -03 | 2026-07-06 |
| `rfc7523bis` | -11 | 2026-08-13 |
| `rfc8725bis` | -10 | 2026-08-31 |
| `sd-jwt-vc` | -19 | 2026-09-01 |
| `security-topics-update` | -03 | 2026-07-06 |
| `spiffe-client-auth` | -02 | 2026-06-15 |
| `status-list` | -21 | 2026-08-13 |
| `transaction-tokens` | -11 | 2026-08-21 |
| `v2-1` | -16 | 2026-09-03 |

2026年に新しく採用されたのは、この2本。

- **`spiffe-client-auth`** (2026年3月採用)。`draft-schwenkschuster-oauth-spiffe-client-auth` からの昇格。ワークロード ID を OAuth のクライアント認証に使う
- `rar-metadata-remediation` (-00 が2026-08-23 に投稿、WG 最新。採用そのものは IETF 126 の場で「Call for adoption? Yes」と決まっている)。`draft-zehavi-oauth-rar-metadata` からの昇格。RAR (Rich Authorization Requests、RFC 9396。scope の文字列では表せない「この口座から150ドルまで」のような細かい権限を JSON で書く仕組み) の `authorization_details` をディスカバリで公開し、足りないときに `insufficient_authorization` で差分を返す

後者は AI エージェントの文脈で議論された。IETF 126 で Nick Watson が挙げた例が的確だった。「150ドルの grant は100ドルの grant を許すのか、それとも LLM 自身に RAR を組み立てさせるほうがいいのか」。エージェントが自分の権限の範囲を問い合わせて、足りなければ追加を要求するという発想だ。

### 浮いている80本のうち32本

個人ドラフトのほうを、エージェント / 委任のキーワード (`agent|delegat|on-behalf|actor|attenuat` を名前とタイトルに対して) で絞った32本のうち、28本を挙げる。

```text
draft-agnihotri-oauth-agent-impl-status
draft-araut-oauth-transaction-tokens-for-agents
draft-aravind-oauth-decision-subject
draft-aravind-oauth-operator-of-record
draft-chen-oauth-agent-authz-use-cases
draft-chen-oauth-agent-revocation
draft-chen-oauth-rar-agent-extensions
draft-coetzee-oauth-spt-txn-tokens
draft-embesozzi-oauth-agent-native-authorization
draft-emerson-oauth-user-mediated-delivery
draft-gco-oauth-delegate-sd-jwt
draft-hamr-oauth-agent-delegation
draft-jia-oauth-scope-aggregation
draft-jiang-oauth-intent-admission
draft-kavian-aep-oauth-session-credential
draft-li-oauth-delegated-authorization
draft-liu-oauth-chain-delegation
draft-mcguinness-oauth-actor-profile
draft-mcguinness-oauth-actor-proofs
draft-mcguinness-oauth-actor-receipts
draft-mcguinness-oauth-ai-agent-instance
draft-mishra-oauth-agent-grants
draft-mw-oauth-actor-chain
draft-ni-oauth-batch-authorization-delegation
draft-niyikiza-oauth-attenuating-agent-tokens
draft-sharma-oauth-identity-propagation-context
draft-song-oauth-ai-agent-collaborate-authz
draft-valverde-oauth-pact
```

眺めていて気づくことが2つある。

1. 同じ人が複数出している。`mcguinness-*` だけで4本 (actor-profile / actor-proofs / actor-receipts / ai-agent-instance)。`chen-*` が3本
2. 問題設定が明らかに重複している。`actor-chain`、`chain-delegation`、`agent-delegation`、`delegated-authorization`、`attenuating-agent-tokens` は、どれも「エージェントが別のエージェントに権限を渡す」を扱っている

この重複こそが、WG が困っている当のものだ。

![採用15本と個人ドラフト80本の量的な差。80のうち32 (黄) がエージェント / 委任](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/oauth-wg-draft-flood-clustering/diagrams/01-15-80-32.png)

## WG chairs の反応

[IETF 126 (2026年7月23日) の OAuth WG 議事録](https://datatracker.ietf.org/meeting/126/materials/minutes-126-oauth-202607231200-00)の冒頭、chairs update がこれだ。

> Massive number of proposals, this will continue from the views of the chairs. If you want to propose something you need to have discussions on the mailing list. There is need to have discussions there to demonstrate interest
>
> **This is not a conference to present stuff, we need to make sure it progresses**

WG の会議枠は有限だ。IETF 126 の OAuth は2セッションで、議事録に残っている発表は合わせて十数本。個人ドラフトが80本ある状況で、順番待ちの列は物理的に捌けない。

## Clustering of OAuth WG Work

同じ IETF 126 で、Aaron Parecki と George Fletcher が [Clustering of OAuth WG Work](https://datatracker.ietf.org/meeting/126/materials/slides-126-oauth-sessb-clustering-of-oauth-wg-work) という提案を出した。2枚目のスライドが全部大文字で「This is just an INITIAL proposal」と断っているのが、いかにも慎重な滑り出しだ。

問題認識のスライドはこう書かれている。

> - Large numbers of new individual drafts are being submitted to the working group. **More than can reasonably be processed.**
> - We need a way to process this new work and determine similarities and overlaps with existing WG drafts as well as **amongst the individual drafts themselves**

提案されたプロセスは4段階。

1. OAuth WG の作業を論理的な「クラスタ」に分ける
2. 新しいドラフトを最も近いクラスタに分類する
3. 既存の作業との重複を評価する
4. 既存ドラフトへの統合か、他の新ドラフトとの統合か、独立文書として残すかを勧告する

### 9つのクラスタ

既存の RFC と採用済み文書は、すべてこの9つのどれかに収まるとされている。

| クラスタ | 主な中身 |
| --- | --- |
| Client / Server API | RFC 6749, 6750, 7636 (PKCE), 8628, 8707, 9101, 9126 (PAR), 9207, 9396 (RAR), 9470, `v2-1`, `first-party-apps` |
| Client Identity, Authentication, and Registration | RFC 7521, 7522, 7523, 7591, 7592, 8705 (mTLS), `rfc7523bis`, `spiffe-client-auth`, `attestation-based-client-auth` |
| Token Formats / Types | RFC 7519 (JWT), 7800, 8176, 9068, 9278, 9901 (SD-JWT), `sd-jwt-vc` |
| Token Lifecycle | RFC 7009, 7662, 9701, `status-list`, `refresh-token-expiration` |
| Security | RFC 6819, 8252, 8725, 9700, `cross-device-security`, `browser-based-apps`, `rfc8725bis`, `security-topics-update` |
| Discovery | RFC 8414, 9728, **`client-id-metadata-document`** |
| Proof of Possession | RFC 8705, 9449 (DPoP) |
| Same-Domain Chaining | RFC 8693 (Token Exchange), `transaction-tokens` |
| Cross-Domain Chaining | RFC 7521, 7522, 7523, `identity-chaining`, `identity-assertion-authz-grant` |

分類を眺めていて2つ引っかかった。

**CIMD が Discovery に入っている。** Client Identity and Registration ではない。DCR (RFC 7591 / 7592) は Registration 側で、CIMD は Discovery 側。名前に "Client ID" が入っているのに、である。

これは分類ミスではなく、CIMD の本質を言い当てていると思う。CIMD がやっているのは登録ではなく、「AS がクライアントのメタデータを発見する」ことだからだ。RFC 8414 (AS メタデータ) と RFC 9728 (RS メタデータ) が並んでいる列に、クライアントメタデータが加わった、という構図になる。

エージェント委任のクラスタが存在しない。 9つのどこにも「委任チェーン」がない。Same-Domain Chaining と Cross-Domain Chaining はあるが、これは既存のトークン交換の話であって、「エージェントが別のエージェントに権限を減衰させて渡す」ではない。

スライド自身がそれを認めている。

> Evaluate individual drafts and slot into a cluster
>
> - **May need to create a new one? Complex-Delegation??**

疑問符2つ付きの `Complex-Delegation??`。ここが今、標準化の地図上で空白になっている場所だ。

### 「もしかして OAuth の話じゃないのでは」

このスライドで一番強い一文は、勧告の分岐にある。

> - Determine overlap with existing work
>   - Possibly recommend merging with existing draft or like individual contributions
>   - **If not related to any cluster or ongoing work - maybe not relevant for OAuth?**

丁寧な言い方をした、強い門番だ。80本のうち相当数がこの分岐で落ちることを想定している。

### 初期レビューは「たぶんロボット」

IETF 127 で発表するための手続きも書かれている。

> - Submit draft for categorization and initial review (**probably robotic**)
> - Depending on recommendation, present at an interim meeting
> - Chairs will take feedback from the interim to make the final decision

`probably robotic`。分類と初期レビューを自動化する想定だ。AI エージェントの認可について書かれたドラフトの洪水を、AI で捌く。量の問題に対する回答としては、これしかないと思う。

![9つのクラスタと、そのどこにも収まらないエージェント委任](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/oauth-wg-draft-flood-clustering/diagrams/02-clusters-and-the-gap.png)

## 4本の interim が組まれた

clustering は提案で終わっていない。すでに実行に移っている。datatracker で2026年の OAuth interim を全部引くと、こうなる。

```bash
curl -s "https://datatracker.ietf.org/api/v1/meeting/meeting/\
?type=interim&number__startswith=interim-2026-oauth&format=json&limit=200"
```

| interim | 日付 | 議題 |
| --- | --- | --- |
| 01 | 2026-05-04 | |
| 02 | 2026-05-11 | |
| 03 | 2026-06-01 | |
| **04** | **2026-09-14** | HTTP Message Signatures for OAuth (`draft-richer-oauth-httpsig`) |
| **05** | **2026-09-21** | OAuth Protected Authorization (`draft-hardt-oauth-protected-authorization`) |
| **07** | **2026-09-28** | **Anthropic & OpenAI Agentic Use Cases** |
| **06** | 2026-10-05 | AAuth Protocol (`draft-hardt-oauth-aauth-protocol`) |

議題はアジェンダ文書から直接取った。番号と日付が入れ替わっている (07 が 06 より先) のは、あとから差し込まれたからだろう。

注目すべきは **2026年9月28日の interim-07** だ。アジェンダに書かれているタイトルは、ドラフト名ではない。

```text
Anthropic & OpenAI Agentic Use Cases
```

ドラフトを持たない2社が、ユースケースを持ち込む枠として組まれている。これは clustering のプロセスとしては正しい順序だ。「まず何が必要なのかを聞く。仕様はそのあと」。

IETF 126 の議事録でも、Aaron の姿勢はそこにあった。個人ドラフトを次々に採用するのではなく、需要の実体を掴もうとしている。

この記事を書いている時点で、この interim はまだ開かれていない。エージェント認可の標準化がどこへ向かうかを知りたいなら、議事録が出たら読む価値がある。

## なぜ意図的に遅いのが正しいのか

OAuth の歴史を見ると、急いで出した標準の後始末に何年もかかっている。

**OAuth 2.0 (RFC 6749) は2012年に出た。** そして2012年から2026年までの14年間、その周りを埋め続ける仕事が続いている。PKCE (RFC 7636, 2015) は、2.0 が公開クライアントの認可コード横取りを塞げていなかったから必要になった。RFC 9207 の `iss` は mix-up 攻撃 (攻撃者がレスポンスの発行元をすり替え、ある AS 用の認可コードを別の AS に渡させる) が後から見つかったから必要になった。Security BCP (RFC 9700) と、その改訂作業 `security-topics-update` は、いまだに動いている。

そして OAuth 2.1 は draft -16 (2026-09-03) の時点で、まだ WGLC (WG Last Call、WG として完成を確認する手続き) すら開かれていない。14年かけて分かったことを1本にまとめ直す作業に、さらに数年かかっている。

エージェント委任は、OAuth 2.0 より難しい問題を含んでいる。

- 委任チェーンが何段も続く。誰が最初に承認したのかを、何段先まで運ぶのか
- 主体が3つ以上ある。ユーザー、エージェント、そのエージェントが呼ぶ別のエージェント、ツール、リソースサーバ
- 権限の減衰が必要。渡すたびに狭くなる、を検証可能にする
- 可用性の問題。1ホップごとに AS へトークン交換に行くと、AS が全マルチエージェント処理の単一障害点になる

最後の点は `draft-niyikiza-oauth-attenuating-agent-tokens` の動機になっている。オフラインで減衰できるトークンを提案していて、チェーンの検証にルート発行者への問い合わせが要らない。筋のいい提案だと思うが、これを間違えると、間違えたまま10年動く。

ここで急いで1本を標準化すると、10年かけて後始末をすることになる。IETF がやっているのは、その後始末のコストを前払いで避ける動きだ。

32本を眺めていると、繰り返し出てくる未解決の問題が1つある。エージェント間の最初の受け渡しで、誰がその操作を承認したのかが落ちることだ。`mcguinness-oauth-actor-profile` が `sub` (認可した主体) と `act.sub` (実際に動いている主体) を分離しようとしているのも、`mw-oauth-actor-chain` や `liu-oauth-chain-delegation` が並んでいるのも、全部ここを狙っている。

これは仕様の細部の話ではない。データモデルの話だ。急いで決められるものではない。

## では実務者は今どうすればいいのか

標準を待っていても仕事は進まないので、現時点の現実的な着地点を書く。

**1. 採用済みの15本の中から使う。** エージェント委任に一番近いのは、すでに動いているこの3本だ。

- `identity-chaining` (-17) は IESG (IETF の運営グループ) の承認まで通り、RFC Editor のキューにいる。RFC になる直前の最後の関門を越えていて、あとは番号が振られるのを待つだけの状態
- `transaction-tokens` (-11) は3回目の WGLC を通過して Waiting for Write-Up
- `identity-assertion-authz-grant` (-04) は通称 ID-JAG。SSO で得た ID トークンを、別ドメイン向けのアクセストークンに交換する仕組みだ。MCP (LLM にツールを繋ぐプロトコル) のエンタープライズ向け認可拡張が Stable としてこれを採用し、Okta が Agent SSO として製品化している

つまり 「まだ標準がない」は、正確には「エージェント固有の標準がない」であって、使える委任の仕組みはある。

**2. 個人ドラフトは実装しない、読む。** 32本は貴重な問題定義集だ。`draft-mcguinness-oauth-actor-profile` の「`client_id` (登録) と `sub` (認可した主体) と `act.sub` (実際に動いている主体) を分離する」という整理は、自分のシステムを設計するときの語彙として今すぐ使える。仕様として実装するのは早い。

**3. 自分のユースケースを、ドラフトではなく list に投げる。** chairs が言っているのはまさにこれだ。「提案したいならメーリングリストで議論しろ。関心があることを示す必要がある」。80本目のドラフトを書くより、既存の1本に「うちではこう困っている」と書くほうが、標準化の役に立つ。

## まとめ

- OAuth WG の active な採用文書は15本、周囲の個人ドラフトは80本、うち32本がエージェント / 委任もの (datatracker、2026-09-04 実測)。IETF 全体ではタイトルに "agent" を含む active draft が422本
- 2026年に採用されたのは2本だけ。`spiffe-client-auth` (3月) と `rar-metadata-remediation` (-00 は8月23日)。どちらも「AI エージェント」を名乗る文書ではない
- chairs の姿勢は明確。「ここは何かを発表する場ではない、進めることを保証する場だ」
- Clustering of OAuth WG Work が triage 戦略として出された。9つのクラスタに分類し、重複を評価し、統合か独立かを勧告する。初期レビューは「たぶんロボット」
- CIMD は Discovery に分類された。Registration ではない。CIMD の本質を言い当てている
- エージェント委任のクラスタは存在しない。スライドに `Complex-Delegation??` と疑問符付きで書かれているのが現在地
- 強い門番の一文: 「どのクラスタにも既存作業にも関係しないなら、そもそも OAuth の話ではないのでは?」
- 9月に4本の interim が組まれ、9月28日の回は "Anthropic & OpenAI Agentic Use Cases"。ドラフトを持たない2社がユースケースを持ち込む枠
- 遅いのは失敗ではない。OAuth 2.0 は2012年に出て、14年たった今も穴を埋める作業が続いている。2.1 はまだ WGLC すら開かれていない。エージェント委任を今急いで固めると、10年かけて後始末することになる

32本が同じ問題を別々に解こうとしていて、それをどう1本にまとめるかが決まっていない。9月28日の interim は、その整理を始める場になる。

_最終確認: 2026-09-04_
