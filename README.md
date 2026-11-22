# agentic_neulite_test

2026年11月19日に試した Agentic Neulite の拡張を保存する個人用リポジトリ。
各ディレクトリは独立した作業ツリーで、それぞれの変更・共通コードを保持する。

| ディレクトリ | 内容 | 手順・結果 |
| --- | --- | --- |
| `kv4_channel/` | Kv4_3チャネルの追加と膜電位・電流の比較 | [実行例](kv4_channel/examples/kv4_3/README.md) · [結果](kv4_channel/docs/results/kv4_3.md) |
| `tutorial2/` | BMTK Tutorial 2の外部スパイク入力とBioNet比較 | [実行例](tutorial2/examples/tutorial2/README.md) · [結果](tutorial2/docs/results/tutorial2.md) |

## 実行

対象のディレクトリへ移動して、同梱の手順に従う。

```sh
cd kv4_channel  # または tutorial2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp LOCAL_ENV.md.example LOCAL_ENV.md
```

`LOCAL_ENV.md`に使用する環境を記録する。NEURONや描画などの追加依存は各実行例を参照する。
生成結果は各ディレクトリの`_runs/`へ保存する。

## 保存対象

ソース、テスト、必要な参照データ、依存パッケージ一覧、仕様・結果の文書、共通エージェント設定とスキルを含む。
各作業ツリーの`tools/export_repository.py`で書き出したソースを基にしている。

以下はGit管理対象外とする。

- `movie/`と`share/`の動画・共有用書き出し
- `_runs/`の計算結果、生成図、ログ
- `.venv/`などのPython環境、`.references/`の外部リポジトリ
- `LOCAL_ENV.md`、`.env`、ローカルのエージェント設定
- コンパイル済みバイナリ、キャッシュ、OSの管理ファイル

ルート直下はこのREADME、`.gitignore`、2つの作業ツリーのみを追跡する設定になっている。
新しい題材を追加する際はルートの`.gitignore`も更新する。

元コードのライセンスはそれぞれの[COPYING](kv4_channel/COPYING)（[tutorial2](tutorial2/COPYING)）、
参照データの出典とライセンスは各テストの`reference/`に保持している。
