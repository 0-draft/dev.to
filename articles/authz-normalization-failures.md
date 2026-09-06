---
title: '同じものを2通りに書けると、認可は割れる: 正規化の失敗という脆弱性クラス'
published: false
description: 'OpenFGA に in_cidr の1行修正を送った。::ffff:10.1.2.3 と 10.1.2.3 は RFC 4291 上は同じホストなのに、認可判定が割れていた。この形のバグは MySQL の照合順序にも、oauth2-proxy のパス照合にも、同じ顔で出てくる。正規化の失敗が認可でだけ致命傷になる理由と、どこに正規化を置くべきかを4つの実例から整理する'
tags:
  - security
  - authorization
  - go
  - opensource
series: Authorization
id: 4589225
---

2026年6月、OpenFGA に小さな PR を出した。[#3181 "fix: match IPv4-mapped IPv6 addresses in the in_cidr condition"](https://github.com/openfga/openfga/pull/3181)。マージされたのは6月25日、本質的な変更は1行だ。

```go
 func ParseIPAddress(ip string) (IPAddress, error) {
 	addr, err := netip.ParseAddr(ip)
 	if err != nil {
 		return IPAddress{}, err
 	}
-	return IPAddress{addr}, nil
+	// Unmap so an IPv4-mapped IPv6 address matches an IPv4 CIDR.
+	return IPAddress{addr.Unmap()}, nil
 }
```

OpenFGA は Google Zanzibar 系の認可エンジンで、「誰が何にどう関係しているか」を `user:alice, reader, doc:q4` のような**タプル**として RDB に保存し、その集合に対して判定する。この記事の後半で MySQL の話が出てくるのは、タプルが RDB の行だからだ。

直していたのはこういう状況だった。OpenFGA の認可モデルに、CEL (Common Expression Language、Google 製の式言語) でこんな条件を書く。

```text
user_ip.in_cidr("10.0.0.0/8")
```

社内ネットワークからのアクセスだけ許す、よくある条件だ。ここに `10.1.2.3` が来れば `true` になる。`::ffff:10.1.2.3` が来ると `false` になる。

[RFC 4291 の 2.5.5.2](https://www.rfc-editor.org/rfc/rfc4291#section-2.5.5.2) 上、この2つは同じホストだ。IPv4-mapped IPv6 アドレスは、IPv6 のソケットで IPv4 の通信を受けたときに普通に出てくる表記でもある。デュアルスタックのリスナを立てていれば、アプリケーションが受け取るのは点表記ではなくマップ形式になりうる。

つまり、攻撃者が何もしなくても、ネットワーク層の都合で認可判定が反転する。

この記事は、この1件を出発点にして「正規化の失敗」というバグクラスを扱う。同じ形のバグが、OpenFGA の MySQL 照合順序にも、oauth2-proxy のパス照合にも、まったく同じ顔で出てくる。そして認可の文脈でだけ、このクラスは特別に危険になる。

## なぜ `false` になったのか

Go の `net/netip` で追える。`netip.ParseAddr("::ffff:10.1.2.3")` が返す `Addr` は、`Is4In6() == true` かつ `Is4() == false` だ。IPv6 のアドレスとして保持されている。

一方 `in_cidr` の実体は `netip.Prefix.Contains` で、これは**アドレスファミリが違えば無条件に false を返す**。`10.0.0.0/8` は IPv4 のプレフィックスなので、IPv6 として保持されたアドレスは入らない。

`Unmap()` は「IPv4-mapped IPv6 なら IPv4 に戻す、それ以外はそのまま」というメソッドだ。パース時点でこれを通せば、以降は必ず正規形になる。

![同じホストの2つの表記が、認可で別の判定になる](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/authz-normalization-failures/diagrams/01-two-spellings.png)

### 1行では終わらなかった

PR を出したあと、直しきれていない対称のケースがあることに気づいた。CIDR の側もマップ形式で書ける。

```text
user_ip.in_cidr("::ffff:10.0.0.0/104")
```

これは `10.0.0.0/8` と同じ範囲を指す。IPv4-mapped IPv6 は上位96ビットが `::ffff:` で固定なので、残り32ビットが IPv4 部分になる。`/104` は 104 - 96 = 8 ビットぶんのプレフィックスを意味し、`/8` と同じ範囲になる。アドレス側だけ unmap すると、今度はこちらが割れる。

なので比較側にも処理が要る。現在の [`internal/condition/types/ipaddress.go`](https://github.com/openfga/openfga/blob/main/internal/condition/types/ipaddress.go) はこうなっている。

```go
	// Unmap the CIDR too so an IPv4-mapped IPv6 CIDR matches the unmapped address.
	addr := network.Addr().Unmap()
	bits := network.Bits()
	if addr.Is4() && bits >= 96 {
		network = netip.PrefixFrom(addr, bits-96)
	}

	return types.Bool(network.Contains(ipaddr.addr))
```

正規化は片側だけやると新しい非対称を作る。 これがこのバグクラスの厄介なところで、あとで一般則としてまとめる。

修正は v1.18.1 以降に入っている。

### security advisory としては受理されなかった

この件は GitHub の security advisory として報告した。結果は 不受理だ。API で見るとこうなっている。

```bash
gh api repos/openfga/openfga/security-advisories/GHSA-gh2m-42q8-93g6 \
  --jq '{state, accepted: .submission.accepted}'
# {"state":"closed","accepted":false}
```

そして通常の PR としてはマージされた。この線引きは正しいと思っている。理由は、影響の向きを考えると分かる。

| ルールの形 | マップ形式が来たときの挙動 | 危険度 |
| --- | --- | --- |
| `allow if ip.in_cidr(社内網)` | 条件が false になり、正当なユーザーが**拒否**される | fail-closed。可用性の問題 |
| `... but not ip.in_cidr(ブロックリスト)` | 除外条件が false になり、**ブロックが効かない** | fail-open。ここは危険 |

危険な形は存在する。ただし、マップ形式を作るのは攻撃者ではなく、防御側のネットワークスタックだ。攻撃者が任意に選べる入力ではない。だから「バグではあるが、攻撃者制御の脆弱性ではない」という判定になる。

この「攻撃者が表記を選べるか」という軸が、次の話につながる。

## 同じ形で CVE がついた例: MySQL の照合順序

OpenFGA には、まったく同じ構造で**CVE がついた**バグがある。[GHSA-cf98-j28v-49v6 / CVE-2026-55170](https://github.com/openfga/openfga/security/advisories/GHSA-cf98-j28v-49v6)、公開は2026年6月17日。CWE は CWE-178 (Improper Handling of Case Sensitivity)。

advisory の本文は驚くほど短い。

> In OpenFGA, when MySQL is being used as the datastore, two distinct check requests can return the same response.
>
> **Preconditions**
>
> 1. You run OpenFGA with MySQL as the datastore
> 2. Your authorization decisions rely on case-sensitive user strings.

何が起きているか。MySQL のデフォルトの照合順序 (`utf8mb4_0900_ai_ci` など) は case-insensitive だ。`ci` は case-insensitive の略で、そうなるように設定されている。つまり `WHERE user = 'alice'` は `Alice` にも `ALICE` にもマッチする。

OpenFGA はタプルを RDB に置く。同じコードが PostgreSQL や SQLite の上では case-sensitive に振る舞い、MySQL の上でだけ case-insensitive になる。認可判定がストレージエンジンの設定で変わる。

`user:alice` と `user:Alice` を別の主体として扱っている設計なら、MySQL 上では両者が同一視される。これは「2つの異なる表記が同じものとして扱われる」で、`in_cidr` の件の鏡像だ。あちらは「同じものが違うものとして扱われる」だった。

### なぜ片方は CVE で、片方は不受理なのか

| | in_cidr マップ形式 | MySQL 照合順序 |
| --- | --- | --- |
| 表記を選ぶのは誰か | 防御側のネットワークスタック | **攻撃者**。ユーザー名は登録時に選べる |
| ずれる方向 | fail-closed が主 (除外ルールでは open) | **fail-open**。別人として登録した ID が既存 ID と同一視される |
| 判定 | バグ、通常 PR でマージ | **CVE-2026-55170** |

差は攻撃者が表記をコントロールできるかの一点にある。認可のバグを分類するとき、この軸が一番効く。

なお OpenFGA の advisory 一覧を見ると、"OpenFGA Improper Policy Enforcement" というタイトルのものが9本ある。2025年8月から2026年7月までの間だけでだ。ReBAC (関係ベース認可) エンジンは、モデルの表現力が高いぶん「このモデルとこのタプルの組み合わせでだけ判定がずれる」が起きやすい。これは探索空間の広さの話だと思っている。これだけ advisory を出して公開しているのは健全な運用だ。

## プロキシ層でも同じことが起きる: oauth2-proxy

正規化の失敗は、データストア層に限らない。**リクエストパス**という文字列でも同じことが起きる。

oauth2-proxy は2026年4月14日に、認証バイパスの advisory をまとめて5本公開した。そのうち2本がこのクラスだ。

### CVE-2026-40575: パスが2つある

[GHSA-7x63-xv5r-3p2x](https://github.com/oauth2-proxy/oauth2-proxy/security/advisories/GHSA-7x63-xv5r-3p2x)、CVSS 9.1、CWE-290 (Authentication Bypass by Spoofing)。

> OAuth2 Proxy may trust a client-supplied `X-Forwarded-Uri` header when `--reverse-proxy` is enabled and `--skip-auth-route` or `--skip-auth-regex` is configured. An attacker can spoof this header so OAuth2 Proxy evaluates authentication and skip-auth rules against **a different path than the one actually sent to the upstream application**.

「認可を判定した対象」と「実際に実行された対象」が別物になっている。これは正規化の失敗の中でも一番わかりやすい形で、同じリクエストに「パス」が2つ存在することが根本原因だ。1つは実際のリクエストライン、もう1つはクライアントが送ってきたヘッダ。oauth2-proxy は後者を見て、バックエンドは前者を見る。

### CVE-2026-41059: `#` はどこまでがパスか

[GHSA-pxq7-h93f-9jrg](https://github.com/oauth2-proxy/oauth2-proxy/security/advisories/GHSA-pxq7-h93f-9jrg)、CVSS 8.2、CWE-288。

> an unauthenticated attacker can send a crafted request containing a number sign in the path, including the browser-safe encoded form `%23`, so that OAuth2 Proxy matches a public allowlist rule while the backend serves a protected resource.

`#` (と、そのエンコード形 `%23`) を含むパスを送ると、oauth2-proxy は「ここまでがパス、以降はフラグメント」と解釈し、バックエンドは違う解釈をする。同じバイト列に対する解釈が2つある。

修正の説明が、このバグクラスの本質をそのまま言っている。

> A fix has been implemented to **normalize request paths more conservatively** before skip-auth matching so fragment content does not influence allowlist decisions.

### 修正しても閉じない: 後方互換のデフォルト

CVE-2026-40575 の patch セクションに、見逃せない記述がある。

> This issue is addressed as part of the newly introduced `--trusted-proxy-ip` flag in `v7.15.2`. **If you leave it unset, OAuth2 Proxy will continue to trust ALL source IPs (0.0.0.0/0) for backwards compatibility**, which means a client may still be able to spoof forwarded headers.

アップグレードしただけでは塞がらない。 新しいフラグを明示的に設定しないと、デフォルトは全 IP を信頼したままになる。後方互換のためにこうせざるを得なかったのは理解できるが、CVSS 9.1 の修正の既定値が「脆弱なまま」であることは、運用側が知っていないと事故る。

Ory Oathkeeper の [GHSA-p224-6x5r-fjpm](https://github.com/ory/oathkeeper/security/advisories/GHSA-p224-6x5r-fjpm) も同じクラスで、ルールは正規化前の生パスに対して照合され、リクエストは正規化後の保護されたパスに解決される。パストラバーサルによる認可バイパスだ。

![どのバグも「1つのものに2つの表現がある」ところで起きている](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/authz-normalization-failures/diagrams/02-where-normalization-belongs.png)

## バグクラスとして整理する

4件を並べると形が見える。

| 事例 | 2つの表現 | ずれ方 | 攻撃者が表記を選べるか |
| --- | --- | --- | --- |
| OpenFGA `in_cidr` | `10.1.2.3` / `::ffff:10.1.2.3` | 同じものが**別物**になる | 選べない (ネットワーク層由来) |
| OpenFGA MySQL 照合順序 | `alice` / `Alice` | 別物が**同じもの**になる | **選べる** |
| oauth2-proxy X-Forwarded-Uri | リクエストライン / ヘッダ | 判定対象と実行対象が別物 | **選べる** |
| oauth2-proxy / Oathkeeper パス | 生パス / 正規化後パス | 判定対象と実行対象が別物 | **選べる** |

### なぜ認可でだけ致命傷になるのか

正規化の失敗自体は、認可に限らずどこにでもある。表示が崩れる、キャッシュが効かない、検索がヒットしない。だいたいは「動作が変」で済む。

認可で致命傷になるのは、**判定と実行が別のコンポーネントで起きるから**だ。

普通の関数呼び出しなら、値を正規化しようがしまいが、同じ値が最後まで使われる。認可はそうではない。

1. PEP (プロキシ、ミドルウェア) が表現 A を見て判定する
2. バックエンドが表現 B を見て実行する

A と B が同じものを指しているという前提が、どこにも保証されていない。この前提が崩れたときだけ、判定と実行がずれる。マイクロサービスやサイドカーで PEP と実行を物理的に分けるほど、この隙間は広がる。

## どこに正規化を置くべきか

4件から引き出せる設計則を書く。

### 1. 比較の直前ではなく、境界で正規化する

OpenFGA の修正が `ParseIPAddress` に入ったのは正しい。パース関数、つまり**外部の文字列が内部の型になる境界**だ。ここを通れば、以降のコードは正規形しか見ない。

やってはいけないのは、比較の直前で正規化することだ。比較箇所は増える。1箇所忘れれば、そこだけ挙動が変わる。

### 2. 正規化は必ず両側にかける

`in_cidr` の件で1行では足りなかったのがこれだ。アドレス側だけ unmap すると、CIDR 側がマップ形式のときに新しい非対称が生まれる。

片側正規化は、直したつもりで別のずれを作る。 比較の両オペランドが同じ正規化関数を通っているかを、必ず確認する。

### 3. 正規形は1つに決めて、型で強制する

「マップ形式も点表記も受け付ける」ではなく、「内部表現は unmap 済みの `netip.Addr` のみ」と決める。Go なら、正規化を通さないと作れない型にしてしまうのが強い。

```go
// 外から直接 IPAddress{addr} を作れないようにして、
// ParseIPAddress を唯一の入口にする
type IPAddress struct {
	addr netip.Addr // unexported。必ず ParseIPAddress を経由する
}
```

OpenFGA の `IPAddress` はすでにこの形になっている。フィールドが unexported なので、パッケージ外からは `ParseIPAddress` を通るしかない。

### 4. ストレージの照合順序を認可の一部として扱う

MySQL の件はコードを1行も読んでも見つからない。スキーマと DB の設定に脆弱性があるからだ。

認可データを RDB に置くなら、識別子カラムの照合順序を明示する。MySQL なら `utf8mb4_0900_as_cs` のような case-sensitive な照合順序を、カラム単位で指定する。デフォルトに任せない。

```sql
-- 認可の主体を格納するカラムは、照合順序を明示して case-sensitive にする
ALTER TABLE tuple
  MODIFY user_object VARCHAR(256)
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL;
```

### 5. PEP と実行対象が同じものを見ているかを検証する

oauth2-proxy の2件は、これが崩れた例だ。防ぎ方は2つある。

- 判定した対象を実行側に渡す。パスを再解釈させない。トランザクショントークンのように「何を許可したか」を構造化して運ぶ
- 信頼できる境界でヘッダを潰す。`X-Forwarded-*` は、必ず自分のロードバランサが上書きする。クライアントから来たものは無条件に落とす

oauth2-proxy の mitigation もこれを言っている。「リバースプロキシかロードバランサでクライアント由来の `X-Forwarded-Uri` を剥がす。実際のリクエスト URI で明示的に上書きする」。

## 自分のコードで探すためのチェックリスト

認可のコードを見るとき、僕はこの順で見るようにした。

1. **識別子の比較が何箇所あるか**。1箇所でなければ、そのすべてが同じ正規化を通っているか
2. その識別子の表記ゆれは何通りあるか。大文字小文字、Unicode 正規化 (NFC/NFD)、末尾スラッシュ、パーセントエンコード、IPv4-mapped、末尾ドット付き FQDN、Punycode
3. 表記を選ぶのは誰か。ユーザー登録の入力なら攻撃者が選べる。ネットワークスタック由来なら選べない。前者なら深刻度が上がる
4. 判定側と実行側は同じ文字列を見ているか。プロキシを挟んでいるなら、ほぼ確実に見ていない
5. DB の照合順序は明示されているか。デフォルト任せは、DB を差し替えた瞬間に挙動が変わる
6. fail-open になる書き方があるか。`but not` / `unless` / 否定条件の中で正規化が失敗すると、拒否が消える

とくに 6 は見落としやすい。肯定条件で正規化に失敗すると「通らない」で気づくが、否定条件で失敗すると「通ってしまう」ので誰も気づかない。

## まとめ

- `::ffff:10.1.2.3` と `10.1.2.3` は RFC 4291 上は同じホストなのに、OpenFGA の `in_cidr` では判定が割れていた。`netip.Prefix.Contains` がアドレスファミリの違いで false を返すため。修正は `ParseIPAddress` での `Unmap()`、v1.18.1 以降に入っている
- 正規化を片側だけかけると、新しい非対称が生まれる。CIDR 側もマップ形式で書けるので、`/104` を `/8` に補正する処理まで必要だった
- この件は security advisory としては不受理、通常の PR としてマージされた。線引きは「攻撃者が表記を選べるか」。マップ形式を作るのはネットワークスタックであって攻撃者ではない
- 同じ形で CVE がついたのが CVE-2026-55170。MySQL のデフォルト照合順序が case-insensitive なので、`alice` と `Alice` が同一視される。こちらはユーザーが表記を選べるので fail-open になる
- oauth2-proxy の CVE-2026-40575 (CVSS 9.1) と CVE-2026-41059 は、リクエストパスに2つの表現があることが原因。判定対象と実行対象が別物になる。Ory Oathkeeper のパストラバーサルも同じクラス
- CVE-2026-40575 の修正はアップグレードだけでは閉じない。`--trusted-proxy-ip` 未設定時は後方互換のため 0.0.0.0/0 を信用し続ける
- 設計則は5つ。境界で正規化する / 両側にかける / 正規形を型で強制する / DB の照合順序を認可の一部として明示する / PEP と実行対象が同じものを見ているか検証する

4件とも、ポリシーそのものは正しかった。壊れていたのは、比較される2つの文字列が同じ規則で作られているかどうかのほうだ。レビューでそこを見た記憶が、自分にはあまりない。

_最終確認: 2026-09-04_
