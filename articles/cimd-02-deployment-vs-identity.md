---
title: "client_id を URL にした代償: CIMD -02 と、デプロイ管理が識別子管理になる問題"
published: false
description: "CIMD の draft -02 が2026年7月に出た。用語は Client Identifier URL に変わり、比較規則が明文化され、Privacy Considerations が新設された。だが issue tracker で本当に揉めているのは別のところだ。URL が識別子である以上 URL は変えられず、CIMD は設定値を publish している。この2つが合わさると、設定を変えたいだけなのに既存ユーザーの同意が全部飛ぶ。?iss= 論争の正体を追う"
tags: ["oauth", "security", "identity", "mcp"]
series: OAuth
# cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/cimd-02-deployment-vs-identity/cover.png"
---

以前、[CIMD と DCR を比べる記事](https://dev.to/kanywst/the-day-clientid-becomes-a-url-client-id-metadata-documents-vs-dynamic-client-registration-dcr-dhi)を書いた。あのとき僕は、CIMD の中心にある考え方を綺麗だと思っていた。

**そのドメインにコンテンツを置けるのは、そのドメインを支配している者だけだ。だからドメイン支配が本人証明になる。**

今もこれは綺麗だと思っている。ただ、あれを書いたのは draft -01 の時点だった。その後 -02 が2026年7月6日に出て、issue tracker では40本超の open issue が動いている (2026年9月時点)。読み直したら、あの綺麗さが何と引き換えだったのかが見えてきた。

前の記事を読んでいなくても最後まで読めるように、仕組みだけ先に置いておく。

CIMD (Client ID Metadata Document) は、OAuth の `client_id` に不透明な文字列ではなく URL を使う仕組みだ。クライアントは `https://app.example.com/client.json` のような自分が管理する URL に、メタデータ (`redirect_uris` や `client_name`) を JSON で置く。認可サーバ (Authorization Server、以下 AS) は、`client_id` として渡されたその URL をそのまま GET して中身を読み、書かれている設定でクライアントを扱う。事前登録も、AS 側のレコードも要らない。

対する DCR (Dynamic Client Registration、RFC 7591) は逆向きだ。クライアントが AS の登録エンドポイントを叩き、AS に `client_id` を発行してもらう。メタデータは AS の DB にレコードとして残る。

この「AS が client_id の URL を無条件に取りに行く」性質が、そのまま SSRF (Server-Side Request Forgery) の入口になる。`client_id` は攻撃者が完全に選べる値なので、`http://169.254.169.254/` のような内部アドレスを指定すれば、AS にそこへリクエストを飛ばさせられる。仕様が SSRF 対策に紙面を割いているのはこのためだ。

結論から書く。CIMD の代償は、その SSRF ではない。SSRF は仕様が真面目に潰しにいっている。本当の代償はこれだ。

URL が識別子である以上、URL は変えられない。そして CIMD が publish しているのは「設定値」だ。だから設定を変えたいだけなのに、識別子を変えるしかなくなる。

## まず -02 で何が変わったか

[draft-ietf-oauth-client-id-metadata-document-02](https://www.ietf.org/archive/id/draft-ietf-oauth-client-id-metadata-document-02.txt) の Document History から、実質的な変更を拾う。

### 構造が2つに割れた

いちばん大きいのは、文書の骨格が変わったことだ。

> Split "what is in the document" and "how to fetch the document" into separate top-level sections

「ドキュメントに何が入っているか」と「AS がどう取得するか」が別の章になった。これに伴って `200 OK` 要件も、ドキュメントの定義側から**取得プロセス側**へ移された。

地味だが効く整理だ。-01 では「文書の性質」と「HTTP のやりとり」が混ざっていて、実装者がどこを読めばいいのか分かりにくかった。

### 用語が "Client Identifier URL" になった

> Renamed "client identifier" to "Client Identifier URL" to avoid implying all OAuth client identifiers are URLs

CIMD の文脈で "client identifier" と書くと「OAuth の client_id は全部 URL である」と読めてしまう。当然そんなことはない。用語を分けたのは良い判断で、後述する議論でもこの区別が効いてくる。

### 比較規則が明文化された: ここが面白い

> Clarified that Client Identifier URL comparison uses simple string comparison **without default port normalization**

デフォルトポートの正規化をしない。つまりこうなる。

```text
https://app.example.com/client.json        これらは
https://app.example.com:443/client.json    別の client_id
```

URL としては同じリソースを指すのに、client_id としては別物として扱われる。

一見すると乱暴に見えるが、これは意図的な設計だ。正規化を許すと「どこまで正規化するか」の解釈が実装ごとにずれる。パーセントエンコード、末尾スラッシュ、大文字小文字、IDN。ひとつでも解釈が割れると、ある AS では通る client_id が別の AS では通らないという相互運用の地獄になる。

「一切正規化しない、バイト列として一致させる」は、その解釈のズレを構造的に消す。認可における正規化の失敗は、それ自体が独立した脆弱性クラスになるほど厄介だ。CIMD はそこを規則を単純化することで回避している。

### SSRF 周りは締まった

-01 の時点でも SSRF 対策は書かれていたが、-02 でさらに絞られている。

| 変更 | 中身 |
| --- | --- |
| loopback 例外の縮小 | **開発・テスト環境のデプロイにのみ**適用されると明記 |
| レスポンスサイズ上限の明確化 | ファイルサイズではなく「AS が読み込むデータ量」の上限 |
| URL 短縮サービス | リダイレクト禁止要件と**非互換**であると明記 |
| ドメイン allowlist | Client ID Domain Trust の節に議論を追加 |

「AS が読み込むデータ量」への言い換えは実装上重要だ。`Content-Length` を信じてサイズを判断すると、嘘の `Content-Length` を返すサーバに無限に読まされる。読んだバイト数でカウントしろ、という指示になっている。

URL 短縮サービスの件は、`bit.ly/xxx` を client_id にできないという話だ。リダイレクトの自動追従が MUST NOT なので、短縮 URL は原理的に機能しない。

### 開発用 CIMD が appendix に降格した

> Moved Client ID Metadata Documents for Development Purposes to a non-normative appendix, and added discussion of its security and reputation implications

ローカル開発中のクライアントは公開 URL を持てない。この救済策として「開発用の CIMD ホスティングサービス」という案が -01 では本文にあったが、non-normative な appendix に降格された。

Introduction にも、適用範囲を明示する文が入っている。

> This approach works best for clients that have an established, stable, and publicly accessible web presence... Clients that do not control a stable public URL, such as clients under active development on a developer's local machine, or clients that cannot guarantee the longevity of a URL, are **less well served by this mechanism**.

CIMD が自分の適用限界を仕様本文で認めた形になる。issue #95 では Andrii Deinega が「ネイティブクライアントとそのリダイレクト URL にとっての正解は、CIMD から (遠く) 離れていることだ」とまで書いている。

### Privacy Considerations が新設された

-02 で新しい章が1つ増えた。CIMD では AS がクライアントのドメインに HTTP リクエストを飛ばすので、クライアント側のサーバは「どの AS が、いつ、自分のクライアントを使おうとしたか」を観測できてしまう。DCR にはない性質だ。

## ここからが本題: issue #78

-02 の変更は、どれも順当な磨き込みだ。仕様として悪くなっている箇所はない。

問題は、**-02 に入らなかった議論**のほうにある。

2026年5月1日、njwatson32 が [issue #78](https://github.com/oauth-wg/draft-ietf-oauth-client-id-metadata-document/issues/78) を立てた。提案自体は素朴に見える。

> For example, if `client_id=https://example.com/oauth/client_id.json`, the AS would `GET https://example.com/oauth/client_id.json?iss=https://example-as.com`.

AS が CIMD を取りに行くとき、自分の issuer をクエリパラメータで名乗ってはどうか。理由は2つ挙げられている。

1. 段階的ロールアウト。「client_id への変更をグローバルに一度に適用するのは、本番運用の観点からは悪い慣習だ」
2. AS ごとのメタデータ。実運用では「同じ値をある AS は受け入れ、別の AS は拒否する」が起きる

共著者の Emelia Smith (ThisIsMissEm) は即座に反対した。1時間50分後の返信だ。

> This goes against the nature of CIMDs, which is explicitly to not be variable, they're meant to be static files.

そして51秒後、同じコメント連打の中でこう続けている。

> CIMDs also do not know anything about their AS's, they are just presenting data to an AS when the AS requests it. **They shouldn't know the difference.**

CIMD は非中央集権の世界から来た考え方で、クライアントと AS の間に関係が存在しない many-to-many の生態系を前提にしている。クライアントが AS を識別できてしまうと、その前提が崩れる。

この反論は仕様の哲学としては正しい。それでも議論は終わらなかった。

## 論点が変質する: 「設定値」か「能力」か

5月19日、mcguinness の投稿で議論の中身が変わる。

> The harder problem is that even a single ecosystem is operationally heterogeneous during rollout, migration, experimentation, and recovery. **Modern SaaS systems are almost never upgraded atomically.**

具体例が挙げられている。クライアントが DPoP (トークンを鍵に縛る)、PAR (認可リクエストを事前に AS へ預ける)、JAR (認可リクエストを署名付き JWT で送る)、`private_key_jwt` (秘密鍵署名によるクライアント認証) を有効化しはじめたとする。エコシステム内の AS のうち、対応済みなのは一部だけだ。

per-iss メタデータがないと、こうなる。

- CIMD がグローバルに変わる
- 全 AS が即座に新しいメタデータを見る
- 古い、あるいは部分的にしかアップグレードされていない AS が、それを拒否するか誤処理する

itsvs がもっともな反論をしている。「それは AS メタデータがある理由では? クライアントが AS のメタデータを見て `private_key_jwt` 非対応と分かれば、client assertion を使わなければいい」。

これに対する mcguinness の返答が、この issue の核心を突いている。

> **CIMD is currently publishing configured values and not just supported capabilities** by reusing client registration metadata params that was originally intended as part of a single client registration (configured values). Change management of these values is very risky as currently defined. A CIMD publisher can't just publish a new capability is supported without changing the configured value which may have broad impact across the eco[system]

読み解くと、こういうことだ。

CIMD は RFC 7591 (DCR) のメタデータ語彙をそのまま流用している。ところが **RFC 7591 の語彙は「1つの登録における設定値」を表すために設計されている**。`token_endpoint_auth_method` は単一の値であって、対応している方式のリストではない。`dpop_bound_access_tokens` は boolean であって、能力の宣言ではない。

DCR ならこれで問題ない。登録は (クライアント × AS) の組ごとに存在するので、AS ごとに違う設定値を持てるからだ。

CIMD は1つの文書が全 AS に対して使われる。そこに「設定値」を書くと、全 AS に同じ設定を強制することになる。

Emelia Smith 自身も、この問題は認めている。

> So instead of negotiating the CIMD based on the AS, and having: [...] maybe for CIMD we would actually need an array of supported values by the client.

ただし直後に自分でツッコミを入れている。

> (I'm not sure how that'd work with DPoP though, due to it being a boolean value, a `dpop_bound_access_tokens: [false, true]` would be kinda weird)

boolean を「能力の集合」にする自然な書き方が存在しない。 語彙が設定値のために作られているから、能力を表現しようとすると型が壊れる。

この議論は IETF 126 (2026年7月) の場にも持ち込まれた。そこでの空気は「やるとしてもクエリパラメータではなく HTTP ヘッダで」に寄っていて、Emelia Smith と Arndt Schwenkschuster が明確にヘッダ派、Aaron Parecki も「ヘッダを使うだけにするかもしれない」と述べている。Justin Richer の反応が一番正直だった。「これは良いのだが、嫌いだ。列挙攻撃を作りはじめる」。結論は出ていない。

派生した issue がもう1本ある。#89 は、クエリ文字列に応じて中身が変わる動的な CIMD を禁じる security consideration を求めるものだ。仕様上、Client Identifier URL にクエリを含めることは SHOULD NOT どまりで、MUST NOT ではない。だから「`?redirect_uri=` を見て中身を差し替える CIMD」が原理的には書けてしまう。

![CIMD が抱える構造: 設定値の語彙を、全 AS 共有の文書に載せてしまった](./assets/cimd-02-deployment-vs-identity/diagrams/01-configured-vs-capability.png)

## 「新しい URL を使えばいい」がなぜ答えにならないか

素直な解決策はこう見える。「AS ごとに設定を変えたいなら、AS ごとに別の CIMD URL を使えばいい」。

njwatson32 がこれを潰している。

> Creating a new client id is going to have far broader implications in many cases, **including invalidation of existing user consent**. Suppose a client starts out with a single global CIMD `https://client.example.com`, and then a year later it wants to modify its config for AS1. If it starts passing `https://client.example.com/as1` to AS1, AS1 will treat this as a **brand new client_id** which will force all users of the client to consent again.

そして、この issue でいちばん引用されるべき一文は njwatson32 が Karl McGuinness から引いたこれだ。

> I do not think "just publish a new CIMD URL" solves this cleanly because a new CIMD URL effectively creates a new client_id. **That turns deployment management into identifier management.**

これが「client_id を URL にする」ことの代償だ。URL は識別子なので、URL を変えると identity が変わる。identity が変わると、その identity に紐づいたものが全部飛ぶ。ユーザーの同意、発行済みのトークン、監査ログ上の連続性。

普通のシステムでは、設定変更とデプロイは identity と無関係だ。設定ファイルを書き換えても、そのサービスが誰であるかは変わらない。CIMD ではこれが結合している。

### DCR にはこの問題がない

比べると構造がはっきりする。

| | DCR (RFC 7591 / 7592) | CIMD |
| --- | --- | --- |
| client_id の出どころ | AS が発行する不透明な文字列 | クライアントが選ぶ URL |
| メタデータの置き場所 | AS の DB のレコード | その URL にある文書 |
| **identity とメタデータの関係** | **分離している**。RFC 7592 で metadata だけ更新できる | **結合している**。文書の場所が identity |
| AS ごとに設定を変える | できる。登録が AS ごとに独立 | できない。1文書が全 AS に使われる |
| 設定を変えると同意はどうなるか | 残る。client_id が変わらないので | URL を変えれば飛ぶ |

DCR の `registration_access_token` は、しばしば「余計な秘密が増える」と批判される。実際そのとおりで、漏れたら `redirect_uris` を書き換えられる高価値なクレデンシャルだ。

だが、あれが存在する理由がここにある。**identity を変えずにメタデータを更新する経路**が要るからだ。CIMD にはそれに対応するものがない。「文書を書き換えればいい」と言えるが、書き換えると全 AS に同時に効く。

これは CIMD の欠陥というより、「状態をどちらに置くか」の選択に必ずついてくる裏返しだ。CIMD は状態をクライアント側に集約することで AS の書き込みストレージを不要にした。その代わり、AS ごとに違う状態を持つ手段を失った。

## issue #88 と、外側からの決着

per-issuer CIMD が欲しい理由のひとつに、mix-up 攻撃対策があった。

mix-up 攻撃は、クライアントが複数の AS を相手にしているときに起きる。攻撃者が「どの AS からのレスポンスなのか」をすり替えて、A 用に取った認可コードを B に渡させる。レスポンスに発行元 (issuer) が入っていないと、クライアントには見分けがつかない。**CIMD を使うクライアントは定義上たくさんの AS を相手にする**ので、この攻撃が現実的になりやすい。

max-stytch の指摘だ。

> Per-issuer CIMD documents would also enable a client to reveal a unique callback URL per-issuer, which is one of the mitigation strategies for issuer mix-up attacks.

これを受けて itsvs が2026年7月9日に [issue #88](https://github.com/oauth-wg/draft-ietf-oauth-client-id-metadata-document/issues/88) を分離した。提案は逆方向だ。

> As an easier way to enable mix-up prevention, we could **require that ASes that build CIMD support also include the `iss` parameter** in the response redirect... Pulling this requirement into the CIMD draft would ensure that ASes don't have to implement all of 2.1 just to enable mix-up prevention.

per-AS の CIMD を作らせるのではなく、AS に `iss` を返させる。RFC 9207 の issuer identification だ。

Emelia Smith は「RFC 9207 と RFC 9700 に既にあるのだから CIMD に書く必要はない、書くとしても non-normative な security consideration が限界」という立場。Aaron Parecki (aaronpk) は必須化を推した。

> Worth noting that **MCP is making `iss` mandatory for the same reasons**. It feels like it should be mandatory here because most if not all uses of CIMD have the same property that makes `iss` the better solution for the mixup attack.
>
> It is also likely that **`iss` will be mandatory for the AS in OAuth 2.1**, so is not that much of a stretch then here either.

Aaron の予測は当たった。2026年9月3日に出た [draft-ietf-oauth-v2-1-16](https://www.ietf.org/archive/id/draft-ietf-oauth-v2-1-16.txt) の Document History に、こう書かれている。

```text
   -16

   *  Remove PKCE plain method

   *  Mention PAR in the authorization endpoint definition section

   *  Added security consideration section about OAuth consent phishing

   *  Make iss response parameter required to be sent by the AS (let
      clients choose the mix-up mitigation still)

   *  Consolidated text about lengths of values into a new "Value Sizes"
      section

   *  Clarified authorization endpoint error response behavior
```

AS が `iss` を返すことが OAuth 2.1 で必須になった。 クライアント側がそれを mix-up 対策に使うかは自由、という書き分けになっている。

つまり issue #88 の論点は、CIMD の中で決着したのではなく、OAuth 2.1 側で決着した。CIMD が独自に MUST を書く必要はなくなった。

ついでに PKCE の `plain` メソッドも -16 で削除されている。IETF 125 (2026年3月16日) で John Bradley が削除を提案し、その場で合意が取れたものだ。

## そして WGLC はまだ一度も無い

ここが一番押さえておくべき事実かもしれない。

CIMD は2025年10月8日に WG 文書として採用された。それから11ヶ月、**datatracker 上で `changed_state` イベントが一度も発生していない**。

IETF の文書が RFC になるまでの道のりは、おおまかにこうなっている。個人ドラフト → WG 採用 → WGLC (WG Last Call、WG として「これで完成でいいか」を問う最終確認) → IETF 全体への Last Call → IESG (IETF の運営グループ) の承認 → RFC Editor のキュー → RFC 番号。途中で shepherd (文書の面倒を見る担当者) と responsible AD (エリアディレクタ) が割り当てられる。

CIMD は、この列の2段目で止まっている。WGLC は開かれておらず、予定にも入っていない。shepherd も responsible AD も未割当だ。

比較のために、同じ OAuth WG の他の文書を並べる。

| ドラフト | 版 | 状態 |
| --- | --- | --- |
| `identity-chaining` | -17 | **IESG 承認済み (2026-06-22)、RFC Editor キュー** |
| `transaction-tokens` | -11 | **3回目の WGLC を経て Waiting for Write-Up** |
| `attestation-based-client-auth` | -11 | shepherd 割当済み、「WGLC 目前」 |
| `v2-1` | -16 | WGLC 未着手。IESG 提出目標が2026年末 |
| **`client-id-metadata-document`** | **-02** | **WGLC なし。shepherd なし** |

一方で、実装側の採用は先行している。

- MCP (Model Context Protocol、LLM にツールを繋ぐプロトコル) の 2026-07-28 仕様が DCR を Deprecated にし、CIMD を推奨にした
- Bluesky / AT Protocol は2024年から URL ベースの client_id を採用している

しかも MCP の仕様書が引用しているのは CIMD の draft-00 だ。IETF 側はすでに -02。用語も (`Client Identifier URL`) 、SSRF 要件の細部も、-00 とは違っている。

仕様がまだ動いている状態で、エコシステムが先に乗った。 これは CIMD 特有の話ではなく、実装が標準化を追い越すときに毎回起きることだ。ただ、CIMD の場合は「URL が identity である」という変更不能な決定が中心にあるぶん、後から効いてくる可能性がある。

![議論の構造: 素朴な提案が、仕様の根本的な非対称を掘り当てた](./assets/cimd-02-deployment-vs-identity/diagrams/02-issue-78-structure.png)

## 今 CIMD を採用するなら知っておくこと

批判だけして終わりたくないので、実務的な整理をする。CIMD は筋のいい仕様で、多くのケースで DCR より良い。ただし以下は設計時に効く。

1. **client_id の URL は、一生変えられないつもりで決める**。パス設計で `/v1/` のようなバージョンを入れたくなるが、それは「バージョンを上げたら別のクライアントになる」ことを意味する。同意も飛ぶ
2. デフォルトポートを書かない。`https://app.example.com:443/client.json` と `https://app.example.com/client.json` は別の client_id になる。片方に統一して、コード上でも定数にする
3. AS ごとに違う設定が必要になったら、それは CIMD の適用外。素直に事前登録か DCR を併用する。仕様も「両方をサポートする AS」を Implementation Considerations で認めている
4. URL 短縮サービスは使えない。リダイレクト追従が MUST NOT なので原理的に動かない
5. ネイティブ / CLI / IDE プラグインには向かない。仕様の Introduction が明示的にそう書いている
6. クライアント側のサーバは、AS からのアクセスログを取れてしまう。-02 の Privacy Considerations が指摘している。取得できるということは、漏らす責任も発生する

## まとめ

- CIMD -02 (2026-07-06) は順当な磨き込み。用語が `Client Identifier URL` になり、文書定義と取得プロセスが分離され、SSRF の loopback 例外が開発環境限定に絞られ、Privacy Considerations が新設された
- 比較はデフォルトポートの正規化なしの単純文字列比較。`:443` の有無で別の client_id になる。乱暴に見えるが、正規化の解釈ずれによる相互運用崩壊を構造的に防ぐ判断
- 仕様が自分の適用限界を本文で認めた。安定した公開 URL を持てないクライアント (ローカル開発、ネイティブ、CLI) には向かないと Introduction に明記された
- 本当の争点は SSRF ではない。issue #78 で掘り当てられたのは「CIMD は RFC 7591 の語彙を流用しているが、あの語彙は**設定値**を表すために作られていて、能力の宣言ではない」という構造的な非対称
- 「新しい URL を使えばいい」は答えにならない。新しい CIMD URL は新しい client_id であり、既存ユーザーの同意が全部無効になる。デプロイ管理が識別子管理になる
- DCR にこの問題がないのは、identity とメタデータが分離しているから。しばしば批判される `registration_access_token` は、その分離を実現するために存在している
- issue #88 は OAuth 2.1 側で決着した。draft-ietf-oauth-v2-1-16 (2026-09-03) で `iss` レスポンスパラメータが AS に必須化された。同じ版で PKCE の `plain` も削除された
- CIMD は採用から11ヶ月、WGLC が一度も開かれていない。それなのに MCP 2026-07-28 は DCR を Deprecated にして CIMD を推奨にした。しかも MCP が引用しているのは draft-00

「ドメイン支配が本人証明になる」という発想は、今でも綺麗だと思う。ただ、identity と設定を同じ URL に束ねたことで、identity を変えずに設定を変える手段が失われた。DCR が余計な秘密 (`registration_access_token`) を抱えてまで守っていたのは、その手段だった。

どちらが正しいという話ではない。何を分離し、何を束ねるかの選択があって、CIMD は束ねる側を選んだ。その代償が今、issue tracker に積み上がっている。

_最終確認: 2026-09-04_
