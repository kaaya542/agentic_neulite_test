# Kv1_1の実行

Python、Cコンパイラ、makeが必要。リポジトリのルートで実行する。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/kv1_1/requirements.txt
```

## 再実行する

出力先は未使用のディレクトリを指定する。

```sh
python test/kv1_1/verify.py --output _runs/kv1_1-check-01
python examples/kv1_1/record_currents.py --verification-dir _runs/kv1_1-check-01 --output _runs/currents-01
python examples/kv1_1/plot_currents.py --recording-dir _runs/currents-01 --output _runs/figures-01
```

独立式・参照MOD・入力生成・無効時回帰・故障注入を検証し、膜電位と電流の図、PDF、元データを生成する。NEURONは参照MODの実行に使う。

## 入力生成とシミュレーション

```sh
python examples/kv1_1/build.py --serial --output _runs/example-01 --gbar 0.004
make -C _runs/example-01/neulite/kernel
(cd _runs/example-01/neulite && ./kernel/nl cell_population.csv cell_cell_connection.csv)
```

`--serial`はBMTKの単一プロセス経路を使う。`v.dat`は時刻ms・体細胞電位mV、`s.dat`は発火時刻ms・細胞ID。

[仕様](kv1_1.md) · [電流記録](kv1_1-recording.md)
