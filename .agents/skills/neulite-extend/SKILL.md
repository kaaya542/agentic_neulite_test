---
name: neulite-extend
description: Neuliteのtutorial再現、入力・接続・計算機構の拡張を、既存実装の調査から比較検証まで進める。
---

# Neuliteの拡張

[設計](../../../docs/architecture.md)と[拡張手順](../../../docs/extension_workflow.md)を読む。

1. 目的、対象資料・モデルの版、入力・出力、科学的条件を確認する。
2. 入力生成から実行まで追い、入力例・bionetlite・カーネルの変更箇所を決める。カーネル変更が必要ならflavorを作る。
3. [仕様](../../../docs/extension_spec_template.md)に比較条件・期待値・許容差を定めて実装する。
4. 機能・統合・回帰を検証し、図・元データ・再現コマンド・検証範囲を示す。

外部入力はイベントが実行まで届くことを確認する。[実例](../../../examples/README.md)の条件を他の題材へ流用しない。
チャネル追加には[専用手順](../neulite-add-ion-channel/SKILL.md)を使う。
