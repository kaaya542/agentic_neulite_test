# Kv1_1のコード差分

`kernel/`と`flavors/kv1_1/`の追加・削除を、説明と行番号付きで表示する。

```sh
python examples/kv1_1/report_diff.py --output _runs/kv1_1-diff-01
```

Pythonで実行でき、Git履歴は不要。未使用の出力先にHTML、patch、比較条件・ハッシュのJSONを生成する。`_runs/kv1_1-diff-01/index.html`を開いて閲覧する。比較対象は実行時の同梱ソースであり、上流コミットとの一致を保証するものではない。

説明は同梱のKv1_1実装専用。想定する差分が変わると停止する。
bionetliteと電流記録コードは[仕様](kv1_1.md)・[記録手順](kv1_1-recording.md)を参照。
