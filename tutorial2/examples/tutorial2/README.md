# BMTK Tutorial 2：外部スパイク入力

BMTK Tutorial 2（1細胞、virtualノード10個から50シナプスのexp2syn入力）を、BioNetとNeuliteの`spike_input` flavorで実行し、体細胞の膜電位と発火を比較する。

リポジトリのルートで実行する。出力先には未使用のディレクトリを指定する。

```sh
python -m pip install -r examples/tutorial2/requirements.txt
python examples/tutorial2/run.py --output _runs/tutorial2-01
python test/tutorial2/verify.py --run-dir _runs/tutorial2-01 --output _runs/tutorial2-check-01
python examples/tutorial2/compare.py --run-dir _runs/tutorial2-01 --output _runs/tutorial2-compare-01
```

- `run.py`：ノートブックの1〜3節を実行する（違いはimportとPoissonのseedだけ）。続けて、同じスパイクファイルをbionetliteで変換し、Neuliteを実行する。BioNetの結果は`sim_ch02/output/`、Neuliteの結果は`sim_ch02_nl/v.dat`・`s.dat`に出力される。
- `verify.py`：シナプス位置・パラメータの対応、イベントの配送、単発入力の応答開始時刻、vanillaとの一致を確認する。
- `compare.py`：仕様の基準で判定し、`comparison.json`、`traces.csv`、`tutorial2_comparison.png/pdf`を出力する。

[仕様](../../docs/extensions/tutorial2.md) · [結果](../../docs/results/tutorial2.md) · [flavor](../../flavors/spike_input/README.md)
