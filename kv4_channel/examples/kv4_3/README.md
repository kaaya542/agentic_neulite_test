# Kv4_3チャネルの追加

Allenモデル472363762の体細胞に、BMTKのKv43.modに基づくKv4_3（A型K⁺電流）を追加する例。
単一プロセス、34℃、E_K=−107 mV、密度0と0.0032 S/cm²を比較する。

リポジトリのルートで実行する。

```sh
python -m pip install -r examples/kv4_3/requirements.txt
python test/kv4_3/verify.py --output _runs/kv4_3-check-01
python examples/kv4_3/record_currents.py --verification-dir _runs/kv4_3-check-01 --output _runs/kv4_3-currents-01
python examples/kv4_3/plot_currents.py --recording-dir _runs/kv4_3-currents-01 --output _runs/kv4_3-figures-01
```

入力生成と実行だけを行う場合：

```sh
python examples/kv4_3/build.py --serial --output _runs/kv4_3-example-01 --gkbar 0.0032
make -C _runs/kv4_3-example-01/neulite/kernel
(cd _runs/kv4_3-example-01/neulite && ./kernel/nl cell_population.csv cell_cell_connection.csv)
```

[仕様](../../docs/extensions/kv4_3.md) · [結果](../../docs/results/kv4_3.md) · [テスト](../../docs/testing.md)
