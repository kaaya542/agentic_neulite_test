# Tutorial 2の結果

[仕様](../extensions/tutorial2.md)の条件でBioNetとNeuliteを比較した。全基準を満たした。

## 比較条件

- BMTK 1.1.3（参照ソース`2403909f`）、NEURON 9.0.1、Python 3.13.4、Apple clang 17.0.0、macOS（Darwin 24.5.0）。
- 入力：Poisson 10 Hz×10ノード、seed=0、0–3 s、294スパイク。50シナプス（1組あたり5個）。位置は事前選択で、両シミュレータ共通。
- tstop=3000 ms、dt=0.1 ms、34 ℃、v_init=−80 mV。電流注入なし。

時刻をそろえて比較した。BioNetの膜電位レポートは初期状態を保存しない（`BioSimulator.post_fadvance`）。このため、sample kの時刻は(k+1)·dtになる（レポートの`mapping/time`はstart=0と記録されている）。Neuliteの`v.dat`の行kは時刻k·dtの値で、初期値から始まる。比較では同じ時刻のサンプルどうしを対応させた。

## 結果

| 項目 | BMTK | Neulite | 基準 | 判定 |
| --- | --- | --- | --- | --- |
| 発火数 | 52 | 52 | 差 ≤ 5.2 | 合格 |
| ±2 ms以内に相手のスパイクがある割合 | 100% | 100% | ≥ 90% | 合格 |
| 閾値下のRMSE | — | 0.093 mV | ≤ 1 mV | 合格 |

参考値（判定には使わない）：

- 発火時刻の差（Neulite−BMTK）：平均−0.16 ms、中央値−0.20 ms、最大の絶対値1.7 ms（BMTK 636.1 ms／Neulite 637.8 ms、ノイズの大きい区間）。
- 閾値下の差：平均−0.042 mV、最大の絶対値0.37 mV。閾値下区間（各スパイクの−2〜+20 msを除いた区間）は全体の63%。
- 全サンプルのRMSEは3.5 mV。主に、活動電位の時刻がサンプル単位でずれることによる。

Neuliteは、閾値を越えたステップの開始時刻を発火時刻として記録する（vanillaと同じ）。中央値−0.2 msの差の一部は、この記録方法による。

膜電位全体・拡大図・閾値下の差・発火のラスターの図は、`compare.py`が`_runs/tutorial2-compare-01/tutorial2_comparison.png`（PDFも）へ出力する。

## 機能検証

`test/tutorial2/verify.py`の結果。すべて合格した。

| 検証 | 結果 |
| --- | --- |
| 入力生成 | 50シナプス（各virtualノードから5個）。エッジh5の`neulite_post_cid`とCSVの`post cid`が一致する。Neuliteの区画は、BMTKが選んだSWC点と同じ座標・種別（basal/apical）で、細胞体から15.9〜136.4 µm。BioNetが作ったシナプスの区画・セグメントは`sec_id`・`sec_x`と一致する。tau1=1、tau2=3 ms、erev=0 mV、重み0.001 µS、delay 2 msがBioNetとCSVで一致する |
| イベント配送 | C probeで`update_synapse`が配送したイベント（接続、ステップ）を、独立に計算した`ceil((ts+delay)/dt−0.5)`の多重集合と照合した。Tutorialの入力では1465件（294×5のうち、tstop内に届く分）が一致した。同じ時刻・近接したスパイクを含む合成入力では35件が一致し、同じステップに複数のイベントが届く5件も失われなかった |
| 単発入力の応答開始 | 500.04 msの入力（イベントのステップ5020）では、BioNetとNeuliteの膜電位がともに502.2 msから変化した。500.06 msの入力（ステップ5021）では、ともに502.3 msから変化した |
| 回帰 | 入力のないspike_inputとvanillaで、同梱の単一細胞入力（電流注入）の`v.dat`・`s.dat`がバイト単位で一致した。vanillaの基準実行の出力ハッシュは変更前と一致した。Kv1_1の検証（`test/kv1_1/verify.py`）も合格した |

## 再現

```sh
python -m pip install -r examples/tutorial2/requirements.txt
python examples/tutorial2/run.py --output _runs/tutorial2-01
python test/tutorial2/verify.py --run-dir _runs/tutorial2-01 --output _runs/tutorial2-check-01
python examples/tutorial2/compare.py --run-dir _runs/tutorial2-01 --output _runs/tutorial2-compare-01
python tools/run_baseline.py --output _runs/baseline-02
```

元データ：`_runs/tutorial2-01/sim_ch02/output/`（BioNet）、`_runs/tutorial2-01/sim_ch02_nl/`（Neulite）、`_runs/tutorial2-compare-01/traces.csv`・`comparison.json`。

## 検証範囲

対象は1細胞・単一プロセス・virtualノード入力・exp2synのみ。以下は検証していない。

- 複数の入力集団（入力CSVは1組）。
- biophysicalとvirtualのノードが混在するネットワーク（bionetliteが拒否する）。
- MPI flavorでの外部入力。
- `wmax`以外の重み関数の外部入力への適用。
- cai（記録対象だが比較対象外）。
- 別のseed・別の入力レート。
- Tutorial 3以降。
