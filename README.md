# Agentic Neulite

Neuliteをエージェントと協働して拡張するための出発点です。このリポジトリを作業フォルダへcloneし、モデルや資料を指定して、入力生成・Cカーネルの変更・数値検証を進めます。

同梱するのは標準カーネル、MPI flavor、および単一細胞の体細胞Kv1_1追加例です。新しいチャネルやtutorialは、対象を指定して実装・検証します。Kv1_1例の条件と検証範囲は[仕様](docs/extensions/kv1_1.md)に記載しています。

## 始め方

Python、Cコンパイラ、makeを用意します。題材ごとに作業フォルダを作り、そのフォルダで実装・検証します。

```sh
git clone https://github.com/kaaya542/agentic_neulite_test.git my-neulite-project
cd my-neulite-project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tools/run_baseline.py --output _runs/baseline-01
```

このリポジトリはprivateのため、cloneにはアクセス権のあるGitHubアカウントでの認証が必要です。

このフォルダで`codex`または`claude`を起動し、目的と参照資料を伝えます。両方で共通の作業方針・スキルを使います。既存のPython環境や外部の参照資料を使う場合は、[環境設定](docs/agent_usage.md#環境準備)を行ってください。

## 拡張を依頼する例

チャネル追加なら、たとえば次のように依頼します。

> BMTKのKv43.modを参照して、Kv4_3チャネルを追加して。追加前後の膜電位と電流を比較し、検証結果と再現手順をまとめて。

tutorialへの対応なら、次のように依頼します。

> BMTKのTutorial 2をNeuliteで動かせるようにして。外部スパイク入力を実装し、同じ入力でBioNetとの膜電位・発火を比較して。

Kv4_3とTutorial 2は、この共通の土台から別々の作業フォルダで試した拡張の例です。各題材の実装はclone後にエージェントと進めます。参照資料の版、モデル、科学的条件、比較基準を確認してから実装・検証してください。

別の題材を試すときは、再度cloneして始められます。実装や仕様はその作業フォルダに保存し、計算結果は`_runs/`へ出力します。仮想環境、外部参照のcheckout、ローカル設定、実行結果はGit管理対象外です。

## 文書

- [使い方](docs/agent_usage.md)
- [アーキテクチャ](docs/architecture.md)
- [実例：Kv1_1チャネルの追加](examples/kv1_1/README.md)
- [テストと検証範囲](docs/testing.md)
- [配布するソースと検証用コピー](docs/repository.md)

[v1.0.0](VERSION) · Neulite / bionetlite [1.2.0](upstream.json)

Neulite: Neulite Core Team · [公式サイト](https://numericalbrain.org/ja/neulite) · [ライセンス](COPYING)
