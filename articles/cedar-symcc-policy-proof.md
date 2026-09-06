---
title: 'Cedar のポリシーを SMT で証明する: 「このリファクタは権限を広げていない」を 0.01 秒で保証する'
published: false
description: 認可ポリシーのリファクタが怖いのは、テストが通っても「テストしていないケース」が残るからだ。Cedar 4.12.0 の symcc は、ポリシーを SMT にコンパイルして等価性や包含関係を全称的に証明する。デフォルトのバイナリには入っていない罠、CLI から呼べるソルバが CVC5 だけな件も含めて、実際に反例を出すまでを全部やった
tags:
  - authorization
  - cedar
  - security
  - rust
series: Authorization
id: 4589222
---

認可ポリシーのリファクタは怖い。

3本に分かれた `permit` を1本の `||` にまとめる。読みやすくなる。テストも全部通る。それでも、こう思う。

**「テストしていない入力で、権限が広がっていないと言い切れるか?」**

言い切れない。テストは「この入力ではこう動く」という存在証明しかできない。`Long` の全域や、全ユーザー属性の組み合わせは列挙できない。

Cedar は AWS が公開した認可ポリシー言語で、`permit` と `forbid` の集合としてポリシーを書く。その Cedar に、これを全称的に証明する道具がある。`cedar-policy-symcc` (Symbolic Cedar Compiler) だ。ポリシーを SMT 式にコンパイルして、ソルバに投げる。

SMT (Satisfiability Modulo Theories) ソルバは、整数や真偽値や文字列といった「理論」を理解したうえで、与えられた論理式を成立させる値の組み合わせが存在するかを機械的に判定する道具だ。ここでの使い方はこうなる。「2つのポリシーの判定が食い違う入力は存在するか」をソルバに聞く。「存在しない」と返れば、それがそのまま等価性の証明になる。「存在する」なら、その具体的な値が反例として返ってくる。代表的な実装が Z3 と CVC5 で、Cedar の CLI が呼ぶのは後者だ。

2026年7月28日にリリースされた cedar-policy 4.12.0 と cedar-policy-symcc 0.6.0、そして CLI 4.12.0 で、これがコマンドラインから使えるようになっている。

実際にやってみた。結論から言うと、リファクタの等価性が0.01秒で証明できて、わざと入れたオフバイワンには具体的な反例が返ってきた。

ただし、そこに至るまでに1時間半を無駄にした。先に書いておくので、同じ穴に落ちないでほしい。

## リリースページを最後まで見ていなかった

まず CLI を落とす。公式のリリースページに Apple Silicon のバイナリがある。

```bash
curl -sL -o cedar.tar.xz \
  "https://github.com/cedar-policy/cedar/releases/download/cedar-policy-cli-v4.12.0/cedar-policy-cli-aarch64-apple-darwin.tar.xz"
tar xf cedar.tar.xz
./cedar-policy-cli-aarch64-apple-darwin/cedar --version
```

```text
cedar-policy-cli 4.12.0
```

`--help` を見ると、確かに `symcc` がある。

```text
Commands:
  authorize            Evaluate an authorization request
  validate             Validate a policy set against a schema
  ...
  tpe                  Partially evaluate an authorization request in a type-aware manner
  symcc                Symbolic analysis of Cedar policies using SymCC
  language-version     Print Cedar language version
```

ところが `cedar symcc --help` を見ると、オプションが `--error-format` と `--help` しかない。実行すると理由が分かる。

```bash
./cedar-policy-cli-aarch64-apple-darwin/cedar symcc
```

```text
Error: subcommand `symcc` is experimental, but this executable was not built
with `analyze` experimental feature enabled
```

サブコマンドは `--help` に出るのに、中身が入っていない。experimental feature としてコンパイル時にゲートされている。

ここで僕はソースから自分でビルドした。`cedar-policy-cli/Cargo.toml` に feature の定義があるからだ。

```toml
analyze = ["dep:cedar-policy-symcc", "dep:tokio", "dep:itertools"]
```

```bash
git clone --depth 1 --branch cedar-policy-cli-v4.12.0 \
  https://github.com/cedar-policy/cedar.git
cd cedar
cargo build --release -p cedar-policy-cli --features analyze   # 1m 39s
```

**これは全部無駄だった。** 同じリリースページに、experimental feature を有効にしたバイナリが最初から置いてある。

```bash
gh api repos/cedar-policy/cedar/releases/tags/cedar-policy-cli-v4.12.0 \
  --jq '.assets[].name' | grep experimental
```

```text
cedar-policy-cli-experimental-aarch64-apple-darwin.tar.xz
cedar-policy-cli-experimental-aarch64-unknown-linux-gnu.tar.xz
cedar-policy-cli-experimental-x86_64-apple-darwin.tar.xz
cedar-policy-cli-experimental-x86_64-pc-windows-msvc.zip
cedar-policy-cli-experimental-x86_64-unknown-linux-gnu.tar.xz
```

5ターゲット分ある。`.github/workflows/build_experimental.yml` が `--features analyze,tpe` でビルドしている。落として実行したら、そのまま動いた。

だから正しい手順はこれだけだ。`experimental` が付いたほうを落とす。

```bash
curl -sL -o cedar-exp.tar.xz \
  "https://github.com/cedar-policy/cedar/releases/download/cedar-policy-cli-v4.12.0/cedar-policy-cli-experimental-aarch64-apple-darwin.tar.xz"
tar xf cedar-exp.tar.xz
xattr -dr com.apple.quarantine cedar-policy-cli-experimental-aarch64-apple-darwin
```

こちらなら `symcc --help` の中身が出てくる。

```text
Usage: cedar symcc [OPTIONS] --principal-type <PRINCIPAL_TYPE> --action <ACTION>
                   --resource-type <RESOURCE_TYPE> --schema <FILE> <COMMAND>

Commands:
  never-errors        Verify that a policy never produces runtime errors
  always-matches      Verify that a policy always matches (is always true)
  never-matches       Verify that a policy never matches (is always false)
  matches-equivalent  Check if two individual policies have equivalent match conditions
  matches-implies     Check if one policy's match condition implies another's
  matches-disjoint    Check if two policies' match conditions are disjoint
  always-allows       Verify that policy set always allows all well-formed requests
  always-denies       Verify that policy set always denies all well-formed requests
  equivalent          Verify that two policy sets are logically equivalent
  implies             Verify that one policy set implies another (subsumption)
  disjoint            Verify that two policy sets are disjoint (no overlapping permissions)
```

## CLI が呼べるソルバは CVC5 だけ

「SMT ソルバを使う」と読んで、反射的に Z3 を入れた。オプションを見ると違った。

```text
Options:
      --cvc5-path <CVC5_PATH>
          Path to CVC5 solver executable
          [env: CVC5=]
```

**CLI から指定できるのは CVC5 だけ**で、Z3 のパスを渡すオプションはない。

ライブラリのほうは Z3 も扱える。`cedar-policy-symcc/src/symcc/solver.rs` には「公式にサポートするのは cvc5 だが、Z3 のような他の SMT ソルバも」という趣旨のコメントがあり、`LocalSolver::from_command(Command::new("z3")...)` の例も載っている。0.6.0 の変更履歴にも "Fix errors decoding models from Z3" がある。Rust から使うなら Z3 でも動く。CLI 経由だと CVC5 一択になる、という切り分けだ。

CVC5 は Homebrew には無かったので、GitHub のリリースから落とした。

```bash
curl -sL -o cvc5.zip \
  "https://github.com/cvc5/cvc5/releases/download/cvc5-1.3.4/cvc5-macOS-arm64-static.zip"
unzip -q cvc5.zip
xattr -dr com.apple.quarantine cvc5-macOS-arm64-static   # macOS の隔離属性を外す
./cvc5-macOS-arm64-static/bin/cvc5 --version
```

```text
cvc5 1.3.4 [git f3b21c4 on branch HEAD]
```

環境変数 `CVC5` にパスを入れておけば、`--cvc5-path` は省略できる。

## 題材: 3本を1本にまとめるリファクタ

よくある形にした。スキーマはこれ。

```text
entity User in [Team] = {
  "isAdmin": Bool,
  "level": Long,
};

entity Team;

entity Doc in [Team] = {
  "public": Bool,
  "classification": Long,
};

action view appliesTo {
  principal: User,
  resource: Doc,
};
```

リファクタ前。3本の `permit` に分かれている。

```text
permit (principal, action == Action::"view", resource)
when { principal.isAdmin };

permit (principal, action == Action::"view", resource)
when { resource.public };

permit (principal, action == Action::"view", resource)
when { principal.level >= resource.classification };
```

リファクタ後。1本にまとめた。

```text
permit (principal, action == Action::"view", resource)
when {
  principal.isAdmin ||
  resource.public ||
  principal.level >= resource.classification
};
```

どちらも `cedar validate` は通る。

```text
╰─▶ no errors or warnings
```

でも、**validate は型が合っているかを見ているだけ**で、2つが同じ意味かどうかは何も言っていない。

## 証明する

`equivalent` を使う。principal / action / resource の型を指定するのが必須なのが特徴的だ (理由は後述)。

```bash
export CVC5=$(pwd)/cvc5-macOS-arm64-static/bin/cvc5

cedar symcc \
  --schema schema.cedarschema \
  --principal-type User \
  --action 'Action::"view"' \
  --resource-type Doc \
  equivalent --policies1 old.cedar --policies2 new.cedar
```

```text
✓ Policy sets are equivalent: VERIFIED
```

**VERIFIED。** これは「テストしたケースで一致した」ではない。`User.level` と `Doc.classification` が取りうる `Long` の全域、`isAdmin` と `public` の全組み合わせにわたって、2つのポリシーセットの判定が一致することの証明だ。

かかった時間を測った。

```text
real 0.07   (初回)
real 0.01
real 0.01
```

0.01秒。 CI に入れて何の問題もない速度だ。

## 1文字壊してみる

`>=` を `>` にする。よくあるオフバイワンだ。

```text
permit (principal, action == Action::"view", resource)
when {
  principal.isAdmin ||
  resource.public ||
  principal.level > resource.classification   // >= から > にした
};
```

同じコマンドを流す。

```text
✗ Policy sets are equivalent: DOES NOT HOLD
  Counterexample found:
principal: User::"", action: Action::"view", resource: Doc::""
context: {}
entities: [
  Doc::"" {
    classification: -1,
    public: false,
  },
  User::"" {
    isAdmin: false,
    level: -1,
  },
  Action::"view",
]
```

**具体的な反例が返ってくる。** `level: -1`、`classification: -1`、`isAdmin: false`、`public: false`。

`User::""` の ID が空文字なのは失敗ではない。判定に ID が関係しないので、ソルバが「何でもいい」と判断して適当に埋めた結果だ。

ソルバは等値の境界を正確に突いてきた。`level == classification` のとき `>=` は真、`>` は偽になる。`isAdmin` と `public` を両方 `false` にして、他の許可経路も塞いでいる。最小の反証になっている。

値が `-1` なのは、`0` でも `100` でも成立するからで、ソルバが選んだだけだ。手でテストを書くとき、境界値として `-1` を選ぶ人は多くないと思う。

## 「権限が広がっていないか」を証明する

等価でないと分かった。次に知りたいのは、**どっちに広いのか**だ。レビューで本当に問いたいのはこれになる。

> このリファクタで、誰かが新しくアクセスできるようになっていないか?

`implies` (包含・subsumption) が答える。「policies1 が許すものは、すべて policies2 も許すか」を調べる。

まず「buggy が old に含まれるか」。

```bash
cedar symcc ... implies --policies1 buggy.cedar --policies2 old.cedar
```

```text
✓ Policy set 1 implies policy set 2: VERIFIED
```

成立。 buggy が許すものは、すべて old も許す。つまり buggy は old より狭い。

逆方向も見る。

```bash
cedar symcc ... implies --policies1 old.cedar --policies2 buggy.cedar
```

```text
  Counterexample found:
entities: [
  User::"" { isAdmin: false, level: 9223372036854775807 },
  Doc::""  { classification: 9223372036854775807, public: false },
]
```

成立しない。反例は `level == classification == 9223372036854775807` (`i64::MAX`)。old は許すが buggy は許さないケースだ。

この2つを合わせると、「buggy は old の真部分集合」と結論できる。つまりこの変更は締め付けであって、権限の拡大ではない。

意図した変更ならこれで OK、意図していないなら機能が壊れている。どちらにせよ、レビューで「たぶん大丈夫」と言わずに済む。

面白いのは、同じ問題に対してソルバが2回とも違う反例を出したことだ (`-1` と `i64::MAX`)。反例は「ある1つの witness」であって、正規形ではない。

![equivalent / implies / disjoint がそれぞれ答える問い](https://raw.githubusercontent.com/0-draft/dev.to/main/articles/assets/cedar-symcc-policy-proof/diagrams/02-what-each-check-answers.png)

## 各サブコマンドが答える問い

一通り触ったので、実務でどう使えるかを整理する。

| サブコマンド | 答える問い | 使いどころ |
| --- | --- | --- |
| `equivalent` | 2つのポリシーセットは同じか | リファクタ、記法の書き換え、ポリシー生成器の検証 |
| `implies` | 片方が許すものを、もう片方も全部許すか | **権限が広がっていないかの確認**。移行前後の比較 |
| `disjoint` | 2つのポリシーセットに重なりはないか | テナント分離、ロールの排他性 |
| `always-allows` | すべての整形式リクエストを許可してしまうか | **事故検出**。条件が意図せず常に真になっていないか |
| `always-denies` | すべてを拒否してしまうか | デプロイして「誰も入れない」を事前に潰す |
| `never-errors` | 実行時エラーを絶対に起こさないか | 属性欠落などによる評価エラーの排除 |
| `never-matches` | このポリシーは絶対にマッチしないか | **デッドポリシー検出**。書いたのに一度も効いていないルール |
| `always-matches` | このポリシーは常にマッチするか | 条件が実質的に無意味になっていないか |
| `matches-equivalent` / `matches-implies` / `matches-disjoint` | 上の3つを、ポリシーセットではなく個々のポリシーの条件部について | ポリシー単位の重複整理 |

表に何度か出てくる「整形式 (well-formed) リクエスト」は、**スキーマが許す型の組み合わせ**という意味だ。証明の全称量化はこの範囲に閉じている。スキーマにない属性を持つリクエストは、そもそも検証の対象外になる。

とくに `never-matches` によるデッドポリシー検出は、運用が長いポリシーセットで効くと思う。「なぜか誰も引っかからないルール」がスキーマ変更で生まれるのはよくある。

## テストとの違いを整理する

`cedar run-tests` でテストは書ける。symcc はそれを置き換えるものではない。答えている問いが違う。

| | テスト (`run-tests`) | symcc |
| --- | --- | --- |
| 証明の種類 | **存在証明**。「この入力ではこう動く」 | **全称証明**。「すべての入力でこう動く」 |
| 失敗したときに得るもの | 落ちたケース | **反例** (ソルバが構成した具体的な入力) |
| 意図の表現 | できる。「admin は見られるべき」 | できない。等価性や包含は意図を語らない |
| 網羅性 | 書いた分だけ | スキーマが許す全域 |
| 実行速度 | 速い | 今回の例で0.01秒。複雑になれば増える |

**両方要る。** テストは「何を意図したか」を書き残す。symcc は「意図しないものが混ざっていないか」を保証する。

CI に入れるなら、こう分けるのが素直だと思う。

- PR ごと: 変更前後のポリシーセットで `implies` を両方向。権限が広がっているなら、それを PR の説明に書かせる
- 定期実行: 全ポリシーに `never-matches` と `never-errors`。デッドコードと評価エラーの検出
- デプロイ前: `always-allows` / `always-denies`。事故の最終防波堤

## 限界

万能ではない。触って気づいた制約を書く。

**1. `(principal-type, action, resource-type)` の組を1つずつ指定する。** これが必須引数になっているのが本質的な制約だ。アクションが20個あるスキーマなら、組み合わせの数だけ呼ぶことになる。全網羅したいならスクリプトで回す必要がある。

理由は理解できる。symbolic environment はこの3つ組ごとに構築されるので、全部を1度に扱うと状態空間が跳ね上がる。symcc 0.6.0 で入った `CompiledSchema` 型は、ここを軽くするためのものだ。0.6.0 の変更履歴にこうある。

> `CompiledSchema` type that precomputes symbolic entities once per schema and produces `SymEnv` instances via `sym_env()`, avoiding expensive per-environment rebuilds.

**2. experimental である。** 別ビルドに切り出されている時点で、API も CLI も変わりうる。本番の CI に入れるなら、バージョンを固定して固定したバイナリを使うべきだ。

**3. 反例は1つだけ。** 「他にも壊れているケースがあるか」は分からない。直して再実行、を繰り返すことになる。

**4. 意図は検証できない。** `equivalent` が VERIFIED でも、両方が同じように間違っている可能性は残る。symcc が答えるのは「2つが同じか」であって「正しいか」ではない。

## Cedar のバージョン事情

ここで混乱しやすい点を整理しておく。

- **SDK (crate) のバージョンは 4.12.0** (2026-07-28)
- 言語のバージョンは 4.5。`cedar language-version` で確認できる
- この2つは意図的にずれている。CHANGELOG の `[Unreleased]` には "Cedar Language Version: TBD" と書かれている
- Cedar 5.x は存在しない。検索で出てくる「Cedar 5」は CedarJS という Redwood 系の無関係なプロジェクト
- Cedar は2025年10月8日に CNCF Sandbox に受理された。標準化団体 (IETF / ISO) ではなく、ベンダ中立な財団によるガバナンスへ移行した形

なお AWS 側では、2026年3月3日に Bedrock AgentCore Policy が GA になっている。MCP は LLM にツールを繋ぐプロトコルで、エージェントはそこに並んだツールを呼ぶ。AgentCore Gateway が、エージェントのツール一覧の取得とツールの実行の両方に割り込んで、Cedar ポリシーで評価する。deny-by-default で、一覧のほうは partial evaluation を使った絞り込みとして効く。symcc で検証できる対象が、エージェントのツール認可にも広がったことになる。

## まとめ

- `cedar symcc` はポリシーを SMT にコンパイルして、等価性や包含関係を全称的に証明する。cedar-policy-symcc 0.6.0 / CLI 4.12.0 (2026-07-28)
- デフォルトのバイナリでは動かない。`subcommand symcc is experimental, but this executable was not built with analyze experimental feature enabled` が出る。同じリリースページに `cedar-policy-cli-experimental-*` が5ターゲット分あるので、そちらを落とせばいい。自分でビルドする必要はない
- ソルバは Z3 ではなく CVC5。`--cvc5-path` か環境変数 `CVC5` で指定する
- 3本の `permit` を1本の `||` にまとめるリファクタの等価性が、0.01秒で VERIFIED になった。`Long` の全域を含む全入力にわたる証明
- `>=` を `>` に変えると具体的な反例が出る。`level: -1, classification: -1, isAdmin: false, public: false`。ソルバは等値の境界を正確に突いてくる
- `implies` を両方向に流すと「権限が広がっていない」ことを証明できる。buggy ⊆ old は VERIFIED、逆は `i64::MAX` の反例。つまり真部分集合
- テストは存在証明、symcc は全称証明。置き換えではなく併用する。テストが意図を書き残し、symcc が意図しないものの混入を防ぐ
- `never-matches` によるデッドポリシー検出が、長く運用したポリシーセットでは効きそう
- 限界: `(principal-type, action, resource-type)` を1組ずつ指定する必要がある、experimental、反例は1つだけ、意図の正しさは検証できない

「この変更で誰か新しく入れるようになっていませんか」。認可のレビューで一番答えにくい質問に、`implies` を両方向に流すだけで証明で答えられる。0.01秒で終わる。

_最終確認: 2026-09-04_
