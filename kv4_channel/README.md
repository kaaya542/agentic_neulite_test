# Agentic Neulite

Neuliteをエージェントと協働して拡張するためのリポジトリです。モデルや資料を指定して、入力生成・Cカーネルの変更・数値検証を進めます。

同梱するのは標準カーネル、MPI flavor、および単一細胞の体細胞Kv1_1追加例です。新しいチャネルやtutorialは、対象を指定して実装・検証します。Kv1_1例の条件と検証範囲は[仕様](docs/extensions/kv1_1.md)に記載しています。

## 始め方

Python、Cコンパイラ、makeを用意し、リポジトリのルートで実行してください。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tools/run_baseline.py --output _runs/baseline-01
```

このフォルダで`codex`または`claude`を起動し、目的と参照資料を伝えます。両方で共通の作業方針・スキルを使います。既存のPython環境や外部の参照資料を使う場合は、[環境設定](docs/agent_usage.md#環境準備)を行ってください。

- [使い方](docs/agent_usage.md)
- [アーキテクチャ](docs/architecture.md)
- [実例：Kv1_1チャネルの追加](examples/kv1_1/README.md)
- [テストと検証範囲](docs/testing.md)
- [配布するソースと検証用コピー](docs/repository.md)

[v1.0.0](VERSION) · Neulite / bionetlite [1.2.0](upstream.json)

Neulite: Neulite Core Team · [公式サイト](https://numericalbrain.org/ja/neulite) · [ライセンス](COPYING)
