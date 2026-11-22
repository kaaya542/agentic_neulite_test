# 使い方

リポジトリをエージェントで開き、目的、対象のtutorial・モデル・資料、実行条件を伝える。

> BMTKのtutorial 2をNeuliteで動かせるようにして。BioNetとの比較結果も見せて。

実装・検証の共通手順は`AGENTS.md`とそこから案内するスキルにある。依頼ごとに同じ手順を追記する必要はない。対象資料だけでは決まらない科学的条件は、エージェントと相談して決める。

## 環境準備

Python、Cコンパイラ、makeが必要。使えるPython環境がすでにあれば再利用する。新しく作る場合は以下を実行する。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

NEURONや描画用パッケージは各実例の手順で追加する。同梱のKv1_1例は参照MODとモデルパラメータを含むため、外部の作業フォルダを必要としない。

BMTKの別のtutorialやMODを参照する場合は、原典を取得する。例えば以下は、同梱例の出典と同じ版を取得するコマンドである。依頼で別の版が指定されている場合はそちらを使う。

```sh
git clone https://github.com/AllenInstitute/bmtk.git .references/bmtk
git -C .references/bmtk checkout 2403909fe597021c2c275311d60c79461bbc75d9
```

マシン固有のパスは、ルートの`LOCAL_ENV.md`に一度記録する。

```sh
cp LOCAL_ENV.md.example LOCAL_ENV.md
```

雛形を編集して、実際に使うPython実行ファイルと参照資料のパスを記入する。`LOCAL_ENV.md`はGit管理対象外で、エージェントは`AGENTS.md`から参照する。別のマシンへ移した場合はパスを確認する。このファイル自体は仮想環境の作成・有効化やパッケージのインストールを行わない。

温度、密度、乱数seed、モデルの選択、許容差など、依頼に固有の条件は依頼文や仕様に書く。環境設定へ共通の既定値として入れない。

準備したPythonで基準実行を確認する。以下の`python`は使用する環境の実行ファイルに読み替え、出力先は未使用のディレクトリを指定する。

```sh
python tools/run_baseline.py --output _runs/baseline-01
```

## エージェントでの実行

このリポジトリを作業ディレクトリとして、Codexなら`codex`、Claude Codeなら`claude`で起動し、目的を入力する。

共通の方針とスキルに、それぞれの入口からアクセスする。

```text
AGENTS.md                              共通の作業方針・環境案内
CLAUDE.md                              @AGENTS.mdで共通方針を読み込む
.agents/skills/                        スキルの実体（Codexの探索先）
  neulite-extend/SKILL.md
  neulite-add-ion-channel/SKILL.md
.claude/skills/                        Claude Codeの探索先
  neulite-extend -> ../../.agents/skills/neulite-extend
  neulite-add-ion-channel -> ../../.agents/skills/neulite-add-ion-channel
```

方針の変更は`AGENTS.md`、スキルの変更は`.agents/skills/`へ行う。`.claude/skills/`は同じ実体への相対シンボリックリンクなので、両方で同じ内容を使える。フォルダをコピーするときは、リンクとリンク先を一緒に保持する。

Claude Codeでは必要に応じて`/neulite-extend`、`/neulite-add-ion-channel`でもスキルを指定できる。`CLAUDE.md`の`@`による読み込みとスキルフォルダのシンボリックリンクは、Claude Codeの[指示ファイル](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools)・[スキル配置](https://code.claude.com/docs/en/skills#choose-where-skills-load)の仕様に従う。

図・元データ・再現コマンドと検証範囲は、通常の[拡張手順](extension_workflow.md)に沿って保存し、完了時に所在を報告する。

[実例](../examples/README.md) · [拡張手順](extension_workflow.md) · [テスト](testing.md)
