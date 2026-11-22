# Kv1_1チャネルの追加

Allenモデル472363762の体細胞に、BMTKのKv11.modに基づくKv1_1を追加する例。
単一プロセス、34℃、E_K=−107 mV、密度0と0.004 S/cm²を比較する。

リポジトリのルートで実行する。

```sh
python -m pip install -r examples/kv1_1/requirements.txt
python test/kv1_1/verify.py --output _runs/kv1_1-check-01
python examples/kv1_1/record_currents.py --verification-dir _runs/kv1_1-check-01 --output _runs/currents-01
python examples/kv1_1/plot_currents.py --recording-dir _runs/currents-01 --output _runs/figures-01
```

`_runs/figures-01/index.html`に膜電位・電流の図、PDF、元データを出力する。

[仕様](../../docs/extensions/kv1_1.md) · [実行手順](../../docs/extensions/kv1_1-usage.md) · [電流記録](../../docs/extensions/kv1_1-recording.md) · [テスト](../../docs/testing.md) · [コード差分](../../docs/extensions/kv1_1-diff.md)
