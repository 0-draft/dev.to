---
title: "Rego に and と or が入った: 値を返さない演算子という設計判断と、実測1.88倍の短絡評価"
published: false
description: "OPA v1.20.0 で Rego に and と or が入った。長年「Rego に or はない、ルールを分けろ」が定石だったので、これは言語としてはかなり大きい追加になる。値を返さない、変数を作れない、and が先にまとまる。この3つの制約が何を守っているのかを実際に動かして確かめ、短絡評価の効果を opa bench で測った"
tags: ["opa", "rego", "authorization", "policy"]
series: Authorization
# cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/rego-and-or-keywords/cover.png"
---

Rego を書きはじめた人がほぼ全員つまずくのが、これだ。

**「or はどう書くんですか?」**

答えは長らく「ルールを分けてください」だった。同じ名前のルールを2本書くと、それが暗黙の OR になる。慣れれば納得できる設計なのだが、条件が3つ4つに増えると、本体1行のヘルパールールが延々と並ぶことになる。

2026年8月27日にリリースされた OPA v1.20.0 で、これが変わった。

> **New Rego keywords: `and` and `or`**, for combining conditions inside a single rule body

リリースノートは「長年の要望であり、この言語への追加としてはここしばらくで最大級のもの」と書いている。

面白いのは入り方だ。普通に `&&` と `||` を足したのではない。値を返さない演算子として入っている。この制約が何を守っているのかを、実際に OPA 1.20.1 を動かして確かめた。

## なぜ今まで無かったのか

Rego のルール本体は、式を改行で並べる。この並びが**暗黙の AND** だ。

```rego
allow if {
	input.method == "GET"
	input.user.role == "admin"
	input.user.mfa == true
}
```

3つすべてが成立したときだけ `allow` が真になる。

では OR は、というと、同じ名前のルールを複数書く。

```rego
allow if input.user.admin

allow if {
	input.user.owner
	input.resource.public
}
```

どちらか一方が成立すれば `allow` は真。

これは Datalog 系の論理プログラミング言語としては素直な設計で、実際、慣れると読みやすい。問題は、条件のごく一部を OR にしたいときも、ルールを外に切り出さないといけないことだ。

OPA のリリースノートが挙げている before の例が、その痛みそのものだ。

```rego
package example

allow if {
	input.method == "GET"
	admin_or_public_owner
}

admin_or_public_owner if input.user.admin

admin_or_public_owner if {
	input.user.owner
	input.resource.public
}
```

`admin_or_public_owner` という名前を考えることに意味はない。制御フローの都合で生まれた名前だ。しかも `allow` を読んでいる人は、この定義を探しに別の場所へ飛ばされる。

v1.20.0 の after はこうなる。

```rego
package example

import future.keywords.and
import future.keywords.or

# the and groups first, so this reads as:
# an admin, or an owner of a public resource
allow if {
	input.method == "GET"
	input.user.admin or input.user.owner and input.resource.public
}
```

リリースノートの表現を借りると、「これまでヘルパールールに分割せざるを得なかった制御フローが、読まれる場所に留まれる」ようになった。

## opt-in である

まず確認しておくべきは、これが自動で有効にならないことだ。`rego.v1` だけでは使えない。

```rego
package t

import rego.v1

new_allow contains u if {
	some u, info in users
	info.role == "admin" and info.mfa == true
}
```

(`contains ... if` は「集合に要素を足すルール」、`some x in xs` は「集合をイテレートする」を意味する Rego v1 の書き方で、`import rego.v1` がそれを有効にする宣言だ。)

```text
1 error occurred: rego/a.rego:18: rego_parse_error: unexpected identifier token: expected \n or ; or }
	info.role == "admin" and info.mfa == true
	                     ^
```

`import future.keywords.and` / `import future.keywords.or` (または両方まとめて `import future.keywords`) が要る。

既存のポリシーで `and` や `or` を変数名やキー名に使っていても壊れない、という配慮だ。

## 制約1: 値を返さない

ここがこの機能の設計の核心だ。リリースノートの一文。

> An `and`/`or` expression either succeeds or fails; **it never produces a value.** So you can't assign one to a variable, pass one to a function, or use one as the head of a comprehension.

3つとも実際に試した。全部パースエラーになる。

**変数に代入できない。**

```rego
bad_assign := (x == 1 or x == 2)
```

```text
rego_parse_error: non-terminated expression
	bad_assign := (x == 1 or x == 2)
	                      ^
rego_parse_error: unexpected or keyword: expected rule value term
```

内包表記の head にできない。

```rego
bad_comp := [n == 1 or n == 2 | some n in nums]
```

```text
rego_parse_error: unexpected or keyword: expected "," or "]"
```

関数の引数にできない。

```rego
bad_arg := count([x == 1 or x == 2])
```

```text
rego_parse_error: unexpected or keyword: expected "," or "]"
```

### なぜこの制約が正しいのか

一般的な言語なら `a || b` は boolean 値を返す。Rego でそれをやらなかった理由は、Rego の式が最初から boolean を返すものではないからだ。

Rego の式は「成功する」か「失敗する」かのどちらかで、失敗した式は未定義になる。`false` になるのではない。

```rego
# input.user.admin が存在しないとき、これは false ではなく未定義
allow if input.user.admin
```

ここに「boolean を返す or」を持ち込むと、言語の中に2つの真偽の体系が同居することになる。「成功/失敗」と「true/false」だ。そして Rego には `false` という値も普通に存在するので、「失敗した」と「false という値が返った」の区別が式のあらゆる場所で必要になってしまう。

値を返さないと決めたことで、`and`/`or` は既存の「式は成功か失敗か」という枠に完全に収まる。言語の意味論を1つも増やしていない。

これは機能を削ったのではなく、言語の一貫性を守るための設計だと思う。

![値を返す or を入れると、Rego に2つの真偽体系が同居することになる](./assets/rego-and-or-keywords/diagrams/01-no-value.png)

## 制約2: オペランドの中で変数を作れない

リリースノートのもう一文。

> Operands can read variables from the rule body around them, but **can't create new ones for the rest of the rule to use** — wrap an operand in braces to give it a body of its own, and any variables it creates stay inside those braces.

これも試した。

```rego
newvar if {
	x := 1 or x := 2
}
```

```text
rego_compile_error: cannot assign vars inside implicit or operand
```

パースエラーではなく**コンパイルエラー**で、メッセージが専用に用意されている。想定された誤りだということだ。

理由を考えると当然で、`x := 1 or x := 2` を許すと、このあと `x` は 1 なのか 2 なのかが決まらない。短絡評価するなら 1 だが、それは実行順序に依存する意味になる。宣言的な言語でそれは持ち込みたくない。

### 波括弧を使えば作れる、ただし外に出ない

逃げ道は用意されている。オペランドを `{ }` で囲むと、そこが独立した本体になる。

```rego
package scope2

import rego.v1
import future.keywords.and
import future.keywords.or

vals := [1, 2, 3]

braced contains v if {
	some v in vals
	{ y := v * 2; y > 4 } or v == 1
}
```

```text
[
  1,
  3
]
```

読み解くと、こうなっている。

- `v = 1`: 左辺は `y = 2`、`2 > 4` は偽で失敗。右辺 `v == 1` が成功 → 採用
- `v = 2`: 左辺は `y = 4`、`4 > 4` は偽で失敗。右辺も失敗 → 不採用
- `v = 3`: 左辺は `y = 6`、`6 > 4` が真 → 採用

`y` は波括弧の中だけで生きていて、外には漏れない。スコープが構文で明示される設計だ。

## 制約3: and が先にまとまる

リリースノートのコメントに、さらっと書いてある。

> the `and` groups first, so this reads as: an admin, or an owner of a public resource

つまり `a or b and c` は `a or (b and c)` と解釈される。多くの言語と同じ優先順位だが、確かめておく価値がある。4つのケースで検証した。

```rego
package prec

import rego.v1
import future.keywords.and
import future.keywords.or

cases := [
	{"admin": true,  "owner": false, "public": false},
	{"admin": false, "owner": true,  "public": true},
	{"admin": false, "owner": true,  "public": false},
	{"admin": false, "owner": false, "public": true},
]

# 括弧なし
implicit contains i if {
	some i, c in cases
	c.admin or c.owner and c.public
}

# and を先にまとめた版
explicit contains i if {
	some i, c in cases
	c.admin or (c.owner and c.public)
}

# もし or が先だったらこうなるはず
other contains i if {
	some i, c in cases
	(c.admin or c.owner) and c.public
}
```

結果。

```text
"explicit": [0, 1]
"implicit": [0, 1]
"other":    [1]
```

`implicit` と `explicit` が一致し、`other` は違う。**`and` のほうが強く結合する**ことが確認できた。

ケース0 (admin だが public でない) が `other` から落ちているのが、違いの現れどころだ。

## 短絡評価を目で見る

リリースノートにはこう書かれている。

> **Only as much is evaluated as needed**: if the left side settles the outcome, the right side is skipped. And when both sides of an `or` succeed, you still get a single result; evaluation doesn't split in two.

Rego は純粋なので、普通は評価回数を観測できない。`print()` を使うと見える。

```rego
package sc

import rego.v1
import future.keywords.and
import future.keywords.or

vals := [1, 2, 3]

with_or contains x if {
	some x in vals
	trace_left(x) or trace_right(x)
}

trace_left(x) if {
	print("  left evaluated for", x)
	x < 3
}

trace_right(x) if {
	print("  right evaluated for", x)
	x < 10
}
```

実行結果。

```text
  left evaluated for 1
  left evaluated for 2
  left evaluated for 3
  right evaluated for 3
[
  1,
  2,
  3
]
```

**`x = 1` と `x = 2` では、右辺が一度も評価されていない。** 左辺 (`x < 3`) が成功したからだ。右辺が動くのは、左辺が失敗した `x = 3` のときだけ。評価は合計4回。

同じことを従来の「ルールを2本書く」方式でやると、こうなる。

```rego
package sc2

import rego.v1

without_or contains x if {
	some x in vals
	trace_left(x)
}

without_or contains x if {
	some x in vals
	trace_right(x)
}
```

```text
  left evaluated for 1
  left evaluated for 2
  left evaluated for 3
  right evaluated for 1
  right evaluated for 2
  right evaluated for 3
[
  1,
  2,
  3
]
```

評価は6回。 結果は同じ `[1, 2, 3]` だが、右辺が3回とも評価されている。

複数のルール本体は独立した命題として全部評価される。論理的には正しいが、短絡はしない。

## どれくらい速いのか: 実測

「右辺が高コスト」という現実的な状況で測った。ユーザー2000件に対して、admin ならすぐ通し、そうでなければ400要素の集合を組み立てて調べる。

```rego
package bench

import rego.v1
import future.keywords.and
import future.keywords.or

expensive(u) if {
	s := {x | some x in numbers.range(1, 400)}
	u.id in s
}

allow_or contains u.id if {
	some u in input.users
	u.role == "admin" or expensive(u)
}
```

比較対象は、同じロジックをルール2本で書いたもの。`opa bench` で測る。

```bash
opa bench -i big.json -d rego/bench_or.rego 'count(data.bench.allow_or)'
opa bench -i big.json -d rego/bench_multi.rego 'count(data.bench2.allow_multi)'
```

環境は OPA 1.20.1 / darwin-arm64 / Go 1.27.0。どちらも結果は `1200` で一致した。

| 書き方 | median | mean | min | stddev |
| --- | --- | --- | --- | --- |
| `or` (短絡あり) | **77.67 ms** | 77.81 ms | 76.79 ms | 0.60 ms |
| ルール2本 (短絡なし) | **146.10 ms** | 145.95 ms | 144.80 ms | 0.65 ms |

**1.88倍**速い。stddev が 0.6ms 程度なので、ノイズではない。

なぜこうなるかは短絡評価の観測どおりで、2000人のうち1000人 (admin) については `expensive()` が一度も呼ばれない。ルール2本の書き方では、admin であっても2本目のルールが独立に評価されるので、2000回すべて `expensive()` が走る。

注意: これは `expensive()` が本当に高い場合の話だ。両辺が軽い条件なら、差はほぼ出ない。速度目的で `or` に書き換えるのは、コストの非対称がある場所に限るべきだと思う。

## いつ使い、いつ使わないか

実際に触ってみて、こう整理した。

**使うとよい場面。**

- 条件のごく一部だけを OR にしたいとき。ヘルパールールの名前を考えずに済む
- 左右のコストが非対称で、安いほうを左に置けるとき。短絡が効く
- 読み手がその場で全条件を見たいとき。`admin_or_public_owner` を探しに飛ばさなくていい

使わないほうがよい場面。

- 分岐そのものに名前を付ける価値があるとき。`is_break_glass_access` のような名前は、それ自体がドキュメントになる。制御フローを平坦にすると、その名前が失われる
- オペランドが3つ以上に増えるとき。`a or b and c or d and e` は、括弧を付けても読みにくい。ここはルールを分けたほうがいい
- 既存ポリシーの一括書き換え。ルール2本の書き方は今も完全に有効で、意味も変わらない。動いているものを触る理由はない

そして忘れがちな点として、短絡評価が入ったことで、オペランドの順序に意味が生まれた。これまで Rego のルール本体は宣言的で、行の順序は (安全性の制約を除けば) 結果に影響しなかった。`or` の左右は、結果には影響しないが性能には影響する。この非対称は、レビューで見るポイントが1つ増えたということでもある。

## v1.20.0 のその他の変更

`and` / `or` が目玉だが、認可の観点で見逃せないものが同じリリースに入っている。

**`allow_net` が JSON Schema のリモート `$ref` 取得を制限するようになった。** `json.match_schema` と `json.verify_schema` が、スキーマ内の `$ref` を辿って外部にリクエストを飛ばすことがある。これが `allow_net` の制御下に入った。ポリシーエンジンが攻撃者の指定した URL を取りに行くのは、[別の記事で扱った CIMD の SSRF](https://dev.to/kanywst/the-day-clientid-becomes-a-url-client-id-metadata-documents-vs-dynamic-client-registration-dcr-dhi) と同じ構造の問題だ。

カバレッジレポートが「なぜその範囲が未カバーなのか」を説明するようになった。 ポリシーのテストで「この行が通っていない」は分かっても、理由が分からないことが多かった。

動的に組み立てた (dynamically composed) ポリシーの partial evaluation が大幅に高速化。 partial evaluation は、入力の一部だけ決まった状態でポリシーを部分的に解き、残りを式として返す評価方式のこと。

なお OPA のリリースは v1.20.1 (2026-08-28)、v1.20.2 (2026-09-03) と続いていて、直近5週間で4リリースある。プロジェクトの速度は落ちていない。

OPA を作ったのは Styra という会社で、創始者3人とメンテナの多くがそこにいた。その Styra がもう存在しない。2025年8月20日、Teemu / Tim / Torin の連名で「OPA の創始者たちが (Styra の多くのチームメンバーとともに) Apple に加わった」という投稿が出た。企業買収があったとはどこにも書かれておらず、Apple も OPA プロジェクトも "acquisition" という語を使っていない。事実として確認できるのは、プロジェクトのガバナンスとライセンスが変わっていないこと、変わったのはメンテナの所属であることだ。Styra の商用製品 (Enterprise OPA、OPA Control Plane、Regal ほか) は CNCF の org に OSS 化された。ただし Enterprise OPA のリポジトリは2026年6月26日に「維持に関心のある方は連絡を」という注記とともにアーカイブされている。この記事を書いている時点で `styra.com` は名前解決しない。

OPA 自体は2021年1月29日に CNCF を Graduated (Sandbox → Incubating → Graduated という成熟度の最上位) していて、その地位は変わっていない。

## まとめ

- OPA v1.20.0 (2026-08-27) で Rego に `and` と `or` が入った。`import future.keywords.and` / `.or` による opt-in で、既存ポリシーは壊れない
- 値を返さない。変数への代入、内包表記の head、関数の引数、いずれもパースエラー。Rego の式が「成功か失敗か」であって boolean 値ではない、という意味論を1つも増やさないための設計
- オペランドの中で変数を作れない。`x := 1 or x := 2` は `cannot assign vars inside implicit or operand` というコンパイルエラー。作りたければ `{ }` で囲む。作った変数は外に漏れない
- `and` のほうが強く結合する。`a or b and c` は `a or (b and c)`。4ケースで検証済み
- 短絡評価する。`print()` で観測すると、左辺が成功した分だけ右辺の評価が消える (4回 vs 6回)
- 実測で 1.88倍。右辺が高コストな状況で median 77.67ms vs 146.10ms (OPA 1.20.1、`opa bench`)。ただしコストが非対称な場合に限る
- 分岐に名前を付ける価値があるなら、今もルールを分けるべき。制御フローを平坦にすると、その名前が失われる
- 同リリースで `allow_net` が `json.match_schema` のリモート `$ref` 取得を制限するようになった。ポリシーエンジンの SSRF 面が1つ塞がっている

10年近く「Rego に or はない」が定石だったので、この追加は歓迎されている。ただ、入り方が丁寧なのが好きだ。**便利にするために言語の意味論を増やさない**、という線をきっちり引いている。値を返さないという一見不便な制約は、その線の引き方そのものだと思う。

_最終確認: 2026-09-04_
