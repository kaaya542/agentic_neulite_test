# Agentic Neulite

作業環境は[使い方](docs/agent_usage.md)を参照する。ルートに`LOCAL_ENV.md`があれば、既存のPython環境と参照資料の所在を確認する。

[設計](docs/architecture.md)と[拡張手順](docs/extension_workflow.md)を読み、依頼に必要な変更を調べる。
一般の拡張は[neulite-extend](.agents/skills/neulite-extend/SKILL.md)、チャネル追加は[専用skill](.agents/skills/neulite-add-ion-channel/SKILL.md)を使う。

- 入力の解釈・検証・前処理はbionetlite、数値計算はカーネルに置く。
- 入力時の単位換算はbionetliteまたは`popl_func.h`に集める。計算中の換算には単位を示す。
- 既存機能を調べ、カーネル変更が必要な場合にflavorを作る。派生元を記録する。
- CSV形式を変更したら、対応するbionetliteで元データから再生成する。
- 未指定の科学的条件は根拠付きで相談する。既知の条件や通常の実装判断は再確認しない。
- 参照条件・期待値・許容差を実装前に定める。合格に合わせて基準を緩めない。
- 観測コードを加えたら、膜電位・発火などの計算結果が変わらないことを確認する。
- 結果には比較条件、図・元データ、再現コマンド、検証範囲を添える。個別例の条件を他の題材へ引き継がない。
- 実行出力は`_runs/`へ置く。基準実行：`python tools/run_baseline.py --output _runs/baseline-01`。
