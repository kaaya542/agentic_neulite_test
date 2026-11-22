# Tutorial 2（外部スパイク入力）の仕様

BMTK Tutorial 2「Single Cell Simulation with External Feedforward Input」をNeuliteで再現し、BioNetと膜電位・発火を比較する。[実行手順](../../examples/tutorial2/README.md)

## 目的・参照

- 基盤：Neulite 1.2.0、`38c2f926e2862e61e784fd3569bf3fc30e2bf1bb`。
- 参照：BMTK `2403909fe597021c2c275311d60c79461bbc75d9`の`docs/tutorial/tutorial_02_single_cell_syn.ipynb`。BMTK 1.1.3、NEURON 9.0.1のBioNetを比較対象とする。
- 対象：Scnn1a_473845048（Allenモデル472363762、`aibs_perisomatic`）1細胞。`virtual`ノード10個（mthalamus）から、1組あたり5シナプス、合計50個の`exp2syn`入力を受ける。

## 条件

ノートブックのセルに従う。`from bmtk.builder.networks import NetworkBuilder`を`from bionetlite import NeuliteBuilder as NetworkBuilder`へ変える以外は変更しない。

| 項目 | 値 | 出典 |
| --- | --- | --- |
| 実行 | tstop=3000 ms、dt=0.1 ms、dL=20 µm、閾値−15 mV、34 ℃、v_init=−80 mV | ノートブックの`build_env_bionet`、BMTKの既定値 |
| 記録 | 体細胞の`v`、`cai`。比較対象は`v`と発火 | 同上 |
| 電流注入 | なし | 同上 |
| 入力 | 10 Hz Poisson、0–3 s、10ノード。SONATA h5 | `PoissonSpikeGenerator` |
| シナプス | `AMPA_ExcToExc.json`：tau1=1 ms、tau2=3 ms、erev=0 mV。syn_weight=0.001 µS、delay=2 ms、weight_function=None | `add_edges` |
| 配置 | basal・apical、細胞体からの距離0–150 µm | 同上 |

ノートブックでは指定されない条件は、比較のために以下のように定める。

- 入力スパイクの乱数seedは0に固定する。BMTKとNeuliteは同じh5ファイルを読む。
- シナプス位置は、bionetliteがBMTKの`find_sections`と同じ候補・確率から事前に選び、`sec_id`・`sec_x`としてSONATAエッジへ書き出す。BioNetはこれを`afferent_section_id/pos`として使う（実行時の無作為配置は使わない）。Neuliteは同じ位置を、変換後SWCの区画IDへ対応させて使う。seedは`preselect_synapse_seed`の既定値。

## 実装

| 場所 | 変更 |
| --- | --- |
| `bionetlite/bionetlite.py` | `virtual`ノードをSONATAへ保存する。同じネットワーク内でbiophysicalノードと混在する場合は拒否する。virtual→biophysicalのエッジで事前配置を行い、`{src}_{trg}_connection.csv`を出力する。`convert_spike_inputs`でSONATAスパイクを`{population}_spikes.csv`へ変換する。電流注入の指定がない設定では`I_AMP=0`とする。`sim_ch02`の自動設定をノートブックの値に合わせる |
| `flavors/spike_input/` | vanillaから派生。外部入力の接続とスパイク時刻を読み、イベントをシナプスへ届ける |

外部接続CSVの形式は内部接続と同じ9列（`pre nid`はvirtualノードのID）。スパイクCSVの列は`time_ms,node_id`。

イベントの時刻は以下のように扱う。到着時刻`te = ts + delay`に対し、配送するステップを`n = ceil(te/dt − 0.5)`とする。これはNEURONの固定刻みと同じ規則で、事前にNEURONで確認した（te=7.049→n=70、te=7.051→n=71）。ステップ`n−1`の終了時に両指数の状態へ1を加え、ステップ`n`から使う。NEURONの`Exp2Syn`と同様、到着したステップでは`g=0`、次のステップから減衰する。同じシナプスに複数のイベントが届いても失われない。内部接続の伝播はvanillaのまま変更しない。

## 検証

| 検証 | 条件・基準 |
| --- | --- |
| 入力生成 | 50シナプスすべてについて、エッジh5の`sec_id`・`sec_x`、BioNetで実際に作られたシナプスの区画・位置、Neuliteの`post cid`が対応する。重み・tau・erev・delayがCSVと一致する |
| イベント伝達 | 入力スパイク数×5（tstop内に届くもの）が、Neuliteのシナプスへ到着として加算される。単発入力でEPSPの立ち上がりのステップがBioNetと一致する |
| 発火 | 発火数の差 ≤ max(1, BMTK発火数の10%)。BMTKの各スパイクのうち、±2 ms以内にNeuliteのスパイクがあるものの割合 ≥ 90%。逆方向も同じ基準 |
| 時刻の対応 | BioNetの膜電位レポートは初期状態を保存しないため、sample kは時刻(k+1)·dt（`BioSimulator.post_fadvance`）。Neuliteの`v.dat`の行kは時刻k·dt。同じ時刻のサンプルどうしを比較する |
| 膜電位 | 両者の各スパイク時刻の−2〜+20 msを除いた閾値下区間で、RMSE ≤ 1 mV |
| 回帰 | vanillaの基準実行が変わらない。外部入力なし（空のスパイクCSV）ではspike_inputとvanillaのv.dat・s.datが一致する |

許容差の根拠：Neuliteの区画はSWC点単位で、積分にはCrank–Nicolson型を使う。BioNetはdL=20 µmで分割し、後退Euler法を使う。このため、両者は完全には一致しない。基準は、機能的に同じ結果になっているかを判定するものとして利用者と合意した。

## 結果

[結果](../results/tutorial2.md)に記録する。
