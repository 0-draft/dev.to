---
title: "仕様は Final になった。それでも OPA には入らなかった: 自分で出した AuthZEN 対応 issue が5日で閉じるまで"
published: false
description: "OpenID AuthZEN Authorization API 1.0 は2026年1月に Final Specification になった。3月、OPA に対応を入れる issue を立てて実装まで出したが、5日後に自分でPRを閉じた。決め手はメンテナの1つの質問だった。「標準が Final になること」と「開発者が使うこと」の間にある距離を、interop の実データと他プロジェクトの判断から測る"
tags: ["authorization", "openid", "opa", "security"]
series: Authorization
# cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/authzen-final-but-not-adopted/cover.png"
---

2026年3月27日、Open Policy Agent のリポジトリに issue を立てた。[#8449 "Support for OpenID AuthZEN Authorization API 1.0"](https://github.com/open-policy-agent/opa/issues/8449)。

5日後の4月1日、自分で出した PR を自分で閉じた。コメントはこれだけだった。

> Since there doesn't seem to be much demand, I'll close this for now.

issue のほうも同じ日に `not planned` で閉じられた。

負け惜しみを書くつもりはない。むしろこの5日間は、自分が持っていた前提が一つ壊れた期間として記録しておく価値がある。壊れた前提はこれだ。

**「仕様が Final になれば、実装は追いかけてくる」**

追いかけてこなかった。しかも、追いかけてこない理由をいちばん正確に言語化したのは、メンテナからの1行の質問に対する自分自身の答えだった。

この記事では、その5日間を日付順に追い、そのあとで「誰も使っていない」という主張が実際どこまで正しいのかを、AuthZEN の interop リポジトリの実データと他プロジェクトの判断記録から検証する。AuthZEN を知らない前提から書くので、前半は仕様の説明になる。

## 前提: AuthZEN Authorization API とは何だったのか

認可の実装は **PDP / PEP** に分けるのが定石になっている。

- PEP (Policy Enforcement Point): 実際に通す / 止めるところ。API ゲートウェイ、アプリのミドルウェア、サービスメッシュのサイドカー
- PDP (Policy Decision Point): 判断するところ。OPA、Cedar、Cerbos、SpiceDB、各種 SaaS

この分離自体は XACML の時代からある。問題は、PEP と PDP の間のプロトコルが標準化されていなかったことだ。OPA には `/v1/data` があり、Cedar には Cedar の API があり、SaaS ベンダはそれぞれ独自の形を持っていた。PDP を入れ替えるには PEP を全部書き直す。ベンダロックインが構造的に発生する。

AuthZEN Authorization API 1.0 は、ここを標準化した。リクエストは4要素、頭文字を取って SARC と呼ばれる。

```json
{
  "subject":  { "type": "user",     "id": "alice@example.com" },
  "action":   { "name": "can_read" },
  "resource": { "type": "document", "id": "q4-plan" },
  "context":  { "ip": "10.0.0.1" }
}
```

レスポンスは、最小形だとこれだけだ。

```json
{ "decision": true }
```

エンドポイントは `POST /access/v1/evaluation`。仕様としては小さい。小さいことは欠点ではなく、意図された設計だった。この点はあとで効いてくる。

### Final Specification になったのは2026年1月11日

ここは正確に押さえておきたい。AuthZEN Authorization API 1.0 は draft ではない。

| 段階 | 日付 |
| --- | --- |
| Implementer's Draft 01 承認 | 2024-11-15 (賛成82 / 反対2 / 棄権22) |
| 60日間のパブリックレビュー | 2025-10-23 から 2025-12-22 |
| メンバー投票 | 2025-12-23 から 2026-01-06 |
| **Final Specification 発行** | **2026-01-11** |

OpenID Foundation の Final Specification は、その先に「もっと安定した版」がない終点だ。RFC でいえば Proposed Standard が出た状態に近い。

そして Final の中身は、僕が最初に思っていたより広い。

| 章 | 機能 |
| --- | --- |
| 6 | Access Evaluation API (単発) |
| 7 | Access **Evaluations** API (バッチ。`execute_all` / `deny_on_first_deny` / `permit_on_first_permit`) |
| 8 | **Search API 3種** (subject 検索 / resource 検索 / action 検索) |
| 9 | PDP メタデータ (`/.well-known/authzen-configuration`) |
| 10 | HTTPS + JSON のトランスポートバインディング |

バッチも検索もディスカバリも、全部 Final に入っている。「まず評価エンドポイントだけ出して、検索は次の版で」ではない。

これを見て、僕は「OPA がこれを喋れないのは損だ」と思った。それが issue を立てた動機だった。

## Day 0 (3月27日): 何を提案したのか

issue の本文はこう書いた。

> OPA is a natural fit as a PDP, but it only exposes its own Data API (`/v1/data`). Users wanting to build a standard-compliant PEP against OPA have to write a translation layer themselves.

提案は2段構えにした。

1. **理想**: OPA が `/access/v1/evaluation` (と、できれば `/access/v1/search/*`) をネイティブに生やす。既存の Rego ポリシーはそのまま使う
2. 十分: `contrib` に公式アダプタを置く、もしくは AuthZEN のリクエスト/レスポンス形式を扱う Rego ヘルパライブラリを出す

最後に、実装を手伝う意思があること、そのうえで OPA のロードマップに乗るのかを聞いた。

## Day 1 (3月28日): メンテナは前向きだった

OPA メンテナの [anderseknert](https://github.com/anderseknert) からの反応は、拒否ではなかった。

> Agreed, it would be nice if we made this easy to do with OPA alone. OTOH, OPA is used for so many things that adding endpoints to the server for a specific use case feels like the wrong approach to me, or at least as a default.

そのうえで3案を出してきた。

1. サーバ設定で「AuthZEN モード」を有効化し、対応しているエンドポイントを生やす
2. **ルートを汎用的に設定できるようにする**。`/foobar` でも `/access/v1/evaluation` でも、内部の好きな場所に向けられる
3. Envoy プラグインのような「AuthZEN ディストリビューション」を作る

そして、こう続けた。

> Option 2 appeals to me as it's the most general purpose approach, and one that potentially has use cases outside of a single spec.

これは重要な設計判断だ。「AuthZEN 対応」を仕様固有の機能として入れるのではなく、仕様に依存しない汎用機能に一般化して、その結果として AuthZEN が喋れるようにする。OPA のコードベースに AuthZEN の文字列が一切入らない。しかも案2は AuthZEN と無関係な要望としても過去に何度か出ていたという。

筋が良いと思った。実装した。

## Day 2 (3月29日): route aliases を実装する

翌日、案2のプロトタイプを出した。[PR #8451 "server: add configurable route aliases"](https://github.com/open-policy-agent/opa/pull/8451)。

設定はこれだけだ。

```yaml
server:
  route_aliases:
    /access/v1/evaluation: /v1/data/authzen/allow
```

やっていることは単純で、リクエストパスを書き換えて既存の mux に再ディスパッチするだけ。AuthZEN 固有のものは何もコードに入らない。任意のパスを任意の既存エンドポイントに向けられる。

同じ日、別のメンテナ [srenatus](https://github.com/srenatus) から、見落としの指摘があった。

> Just in case you missed it, there's something here: <https://github.com/open-policy-agent/contrib/tree/main/authzen/authzen-proxy>

`contrib` にすでに AuthZEN プロキシがあった。これは知らなかった。ただ、これは OPA の前段に**別プロセスを1つ立てる**構成になる。OPA をサイドカーで動かしている環境だと、サイドカーがもう1つ増える。route alias なら設定1行で済む。そう返した。

anderseknert の反応は、まだ扉が開いていた。

> I think this warrants input from more maintainers / users before we go on to implementation, but as a prototype, that could certainly come in handy for a POC!

「他のメンテナとユーザの意見が要る」。ここまでは順調だった、と当時は思っていた。

## Day 4 (3月31日): 質問が飛んでくる

srenatus からのコメントは、技術的な指摘ではなかった。

> @kanywst I have yet to see anyone adopting authzen for real -- are you? If so, I'd be curious to know how you're using it, and what's most valuable for you in adopting it. Also, what's your stack that plays nice with authzen?

嘘をつく選択肢はなかったし、つく気もなかった。こう答えた。

> I'm not using AuthZEN in production yet. The spec was just formally published and I was exploring what OPA support could look like. I don't have a concrete use case driving this beyond technical interest and the fact that the spec is now final.

33分後、srenatus の返信。

> I'm leaning towards separating this into a plugin or wrapper of some sort (in contrib). Without concrete interest in adopting this, it'll be a ready option for anyone looking into adopting it. And if the demand for authzen some day warrants it, we could still bring it into mainline OPA.

翌日、anderseknert が締めた。

> Agreed, let's hold for now. Thanks though @kanywst! Keep the ideas coming 😃

issue は `not planned` で閉じた。僕は PR を閉じた。

**この判断は正しい。** 誰も採用していない仕様のために、CNCF Graduated プロジェクトのコアに恒久的なメンテナンス負債を追加する理由はない。もし僕がメンテナ側だったら同じことを言う。

引っかかったのはそこではなくて、「仕様が Final になった」が理由として一切通用しなかったことだ。

## 「誰も使っていない」は本当か

srenatus の主張を、雰囲気ではなくデータで検証したい。AuthZEN の interop リポジトリには、シナリオごとにどの PDP が参加しているかが JSON で入っている。

todo シナリオ ([`interop/authzen-todo-backend/src/pdps.json`](https://github.com/openid/authzen/blob/main/interop/authzen-todo-backend/src/pdps.json)) の中身を数えた。

```bash
gh api repos/openid/authzen/contents/interop/authzen-todo-backend/src/pdps.json \
  --jq '.content' | base64 -d | python3 -c "
import sys, json
d = json.load(sys.stdin)
for ver, v in d['pdps'].items():
    print(ver, len(v), sorted(v.keys()))
"
```

結果。

```text
authorization-api-1_0-01 17 ['AVP', 'Aserto', 'Axiomatics', 'Cerbos', 'EmpowerID',
 'HexaOPA', 'Indykite', 'Kogito', 'Open Policy Agent', 'OpenFGA', 'Permit.io',
 'PingAuthorize', 'PlainID', 'Rock Solid Knowledge', 'SGNL', 'Topaz', 'WSO2']
authorization-api-1_0-02 17 [同じ17件]
```

同じファイルの `gatewayPdps` は12件、`gateways` は8件 (Pass Through, AWS API Gateway, Envoy, Kong, Layer7, Tyk, WSO2, Zuplo) だった。

**17実装ある。** これは「誰も使っていない」と真っ向から矛盾する数字に見える。

しかも、このリストには `Open Policy Agent` と `HexaOPA` が両方載っている。OPA プロジェクトが「入れない」と決めた仕様の interop に、OPA という名前の PDP が参加している。これは矛盾ではない。interop に出ている OPA は `contrib` のプロキシや Hexa 側の実装であって、OPA プロジェクト本体がメンテナンスの約束をしたものではない。この捻れが、この話の本質を一番よく表している。

### 数字を層で割ると景色が変わる

17という数字を、実装者の性質で分けてみる。

| 層 | 顔ぶれ | AuthZEN 対応 |
| --- | --- | --- |
| 商用 IAM / 認可ベンダ | Axiomatics, PlainID, SGNL, EmpowerID, IndyKite, PingAuthorize, WSO2, Rock Solid Knowledge, Aserto/Topaz, Permit.io, Cerbos | 積極的。interop の常連 |
| クラウドベンダ | AVP (AWS Verified Permissions) | 参加はしている |
| OSS 認可エンジン | OpenFGA (参加), OPA (本体は不採用), **SpiceDB (不参加)**, Ory Keto (不参加) | 薄い |

PDP を製品として売っている会社は乗る。開発者が `docker run` で立てるエンジンは乗らない。 これが17という数字の正体だ。

理由もはっきりしている。ベンダにとって AuthZEN 対応は販売上の機能だ。「うちの PDP は標準準拠なのでロックインしません」と言える。実装コストは HTTP ハンドラ1本ぶんで、既存の評価エンジンの前に薄い変換層を置くだけで済む。

OSS エンジンにとっては違う。エンドポイントが1本増えると、それは永久にサポートする API 表面が1本増えることを意味する。仕様が改訂されれば追随義務が生まれる。対価は「標準に準拠している」という評判だけで、それは誰も要求していない。

### 他のプロジェクトも同じ判断をしている

OPA だけが特殊だったわけではない。

MCP (Model Context Protocol) でも同じことが起きた。[ext-auth#14 "AuthZEN integration"](https://github.com/modelcontextprotocol/ext-auth/issues/14) は2026年2月2日に立ち、メンテナの Nate Barbettini と Den Delimarsky が押し返した。論旨は「MCP サーバはすでに AuthZEN の PEP になれるので、プロトコル側に変更は要らない」。issue は今も open のまま、最終活動が2026年2月19日で止まっている。

この判断は OPA のケースと構造が同じだ。「やりたければ外側でできる。コアに入れる理由がない」。

そして、この行き場のなくなった要望の受け皿として COAZ (Compatible with OpenID AuthZEN、読みは「コージー」) が AuthZEN WG 側に作られた。MCP のツール呼び出しをパラメータ単位で認可できるようにするバインディングで、Framework と MCP Binding の2本、どちらも2026年2月13日付。標準化団体側が、実装側に断られた分をプロファイルとして引き取った構図になっている。

### Search API の採用はさらに薄い

もう1つ、Final の中身と実装のズレを示す差がある。ただしこちらは、evaluation ほどきれいには数えられない。

evaluation シナリオの参加 PDP はリポジトリに `pdps.json` としてコミットされていて、誰でも数えられる。17だった。search シナリオにはそれがない。`interop/authzen-search-demo/app/data/pdps.server.ts` を見ると、参加 PDP は `PDP_CONFIG` という base64 の環境変数から実行時に読み込まれる。README に載っているのは Cerbos と Topaz の設定例だけで、参加者の一覧はリポジトリにも interop サイトのドキュメントにも公開されていない。

つまり evaluation は「誰が対応しているか」を検証できて、search は検証できない。数字で殴れないので断定は避けるが、公開された参加者リストが片方にしかないこと自体が、注力度の差を表しているとは思う。

Search API は仕様の第8章に正式に入っている。draft ではない。

理由は実装コストの非対称性にある。evaluation は「1件について yes/no」なので、既存のポリシーエンジンの前に変換層を置けば実装できる。search は「alice が delete できるレコードを全部返せ」であり、ポリシーエンジンの評価方向が逆になる。Rego でいえば partial evaluation が要るし、ReBAC エンジンなら reverse index が要る。既存エンジンに薄く被せられる機能ではない。

つまり Final に入っていることと、実装可能なコストで実装できることは別だ。

### 適合性認証はまだ存在しない

もう1点。AuthZEN の PDP 向け適合性認証プログラムは、[シナリオ定義](https://github.com/openid/authzen/blob/main/certification/authorization-api-1_0-scenario.md)までは書かれているが、認証済み実装は現時点で1つも発表されていない。

OpenID Connect が普及した歴史を振り返ると、認証プログラムは「準拠している」を検証可能な主張に変えるための装置だった。それがまだない。つまり今の時点で「AuthZEN 準拠」は自己申告でしかない。

![AuthZEN の採用が止まっている層](./assets/authzen-final-but-not-adopted/diagrams/02-adoption-layers.png)

## それでも仕様の側は止まっていない

ここまで読むと AuthZEN が失敗しているように見えるかもしれないが、仕様の開発速度は2026年に入って**上がっている**。しかも方向がはっきりしている。全部エージェント向けだ。

| 成果物 | 日付 | 中身 |
| --- | --- | --- |
| COAZ Framework 1.0 / COAZ-MCP Binding 1.0 | 2026-02-13 | 任意のプロトコルの情報モデルを CEL で SARC にマップする。第一の対象が MCP |
| **ARAP / AARP** (Access Request and Approval Profile) | 2026-06-15 に WG Draft 承認 | 「拒否だが申請可能」を標準化する |
| Obligations Profile 1.0 | 2026-07-03 | PDP が PEP に義務を課すモデル |
| OAuth プロファイル4本 | **2026-09-02 マージ** | JWT アクセストークンへの認可クレーム、token exchange、token issuance、AROP |
| `draft-gazitt-oauth-authzen-token-exchange-01` | 2026-09-02 | IETF 側。RFC 8693 / identity chaining / ID-JAG / transaction tokens を AuthZEN 評価にマップ |

ARAP については名前の罠がある。OpenID Foundation のブログとスペック一覧は「AARP」と書き、仕様ソースの `abbrev` は「ARAP」になっている。同じ文書だ。仕様を引用するなら ARAP、プレスリリースを引用するなら AARP。

そして ARAP は WG 内部で揉めている。issue [#520 "ARAP does too many things"](https://github.com/openid/authzen/issues/520) と #610 "inconsistencies and over-stepping" がどちらも2026年8月時点で active だ。

コアの採用が薄いまま、プロファイルの面積だけが増えている。これは仕様の生存戦略としてはあり得る形で、「エージェント認可という新しい需要に、既存の Final を土台として応える」という賭けになっている。うまくいくかは、その需要が本物かどうかにかかっている。

## 学んだこと

### 1. 「Final」は採用曲線の始点ですらない

僕は issue の中で「the spec is now final」を採用の理由として書いた。メンテナには一切通用しなかった。当然だった。

標準化のライフサイクルと、実装のライフサイクルは、そもそも駆動されている力が違う。

| | 何で動くか |
| --- | --- |
| 標準化団体 | 参加ベンダの相互運用ニーズ、WG のコンセンサス、投票 |
| OSS プロジェクト | 実際のユーザからの要望、メンテナンスコスト、既存ユーザへの影響 |

Final になるかどうかは前者のプロセスの結果であって、後者に対する入力としては**ほぼ何の重みも持たない**。

### 2. メンテナが本当に聞いているのは「誰が困っているか」

srenatus の質問は "are you [adopting it]?" だった。「仕様は正しいか」でも「実装は綺麗か」でもない。

僕は実装を先に出した。route alias の PR は動くものだった。でも、動くコードは「誰が困っているか」の答えにはならない。ここを取り違えていた。

もし今もう一度やるなら、issue を立てる前にやることが変わる。

- AuthZEN の PEP 側を実際に本番で運用している人を探す。あるいは自分で運用する
- PDP を差し替えた実例を1つでも作る。「Cerbos から OPA に PEP のコードを1行も変えずに移した」なら、それは需要の証拠になる
- 需要がないなら、そもそも issue を立てない

### 3. 「外側でできる」は強い断り文句であり、たいてい正しい

OPA も MCP も、同じ形で断った。「それは外側でできる。コアに入れる理由がない」。

これに対する反論は1つしかない。「外側でやると具体的にこれだけのコストがかかる」を数字で示すことだ。僕は「サイドカーが1つ増える」とは言ったが、それが誰にとってどれだけの痛みなのかを示すデータを持っていなかった。

### 4. 断られたら外に作ればいい

このあと、[opa-authzen-plugin](https://github.com/kanywst/opa-authzen-plugin) を作った。opa-envoy-plugin と同じパターンで、OPA に AuthZEN の Access Evaluation API を足すプラグインだ。あわせて [opa-authzen-interop](https://github.com/kanywst/opa-authzen-interop) で interop シナリオを回して検証した。

これは負け惜しみではなくて、srenatus が提示した着地点そのものだった。

> I'm leaning towards separating this into a plugin or wrapper of some sort (in contrib). Without concrete interest in adopting this, it'll be a ready option for anyone looking into adopting it. And if the demand for authzen some day warrants it, we could still bring it into mainline OPA.

「採用への具体的な関心がないなら、採用を検討する人のためにすぐ使えるオプションとして置いておけばいい。いつか需要が正当化すれば、mainline に持ってくることもできる」

これはコアに入れないという判断であると同時に、将来入れる条件を明示した判断でもある。条件は「需要」だ。プラグインを外に置いておくことは、その需要が現れたときに検証済みの実装が存在している状態を作る、という意味を持つ。

## まとめ

- AuthZEN Authorization API 1.0 は2026年1月11日に Final Specification になった。evaluation、バッチ、search 3種、ディスカバリまで含んだ、思ったより広い仕様
- OPA は2026年4月1日にネイティブ対応を `not planned` で閉じた。決め手は技術的な問題ではなく「採用している人を見たことがない」だった。MCP も2026年2月に同じ論法で in-protocol 対応を断っている
- interop の実装数は17。ただし顔ぶれは商用 IAM ベンダに偏る。開発者が自分で立てる OSS エンジン (OPA 本体、SpiceDB、Ory Keto) はほぼ乗っていない。SpiceDB は一度も参加していない
- Search API は Final に入っているが、参加 PDP の一覧がそもそも公開されていない。evaluation 側は `pdps.json` で17と数えられるのに、search 側は実行時の環境変数で、リポジトリにも interop サイトにも一覧がない
- 適合性認証プログラムはまだ未リリース。「AuthZEN 準拠」は現時点で自己申告
- 仕様側は2026年に加速しているが、方向は全部エージェント向けのプロファイル。COAZ、ARAP、Obligations、OAuth プロファイル4本 (2026-09-02 マージ)。コアの採用は薄いままプロファイルの面積が増えている

仕様書の最終ページに「Final Specification」と書いてあることは、あなたのプロジェクトがそれを実装する理由には**ならない**。理由になるのは、困っている人が実在することだけだ。

_最終確認: 2026-09-04_
