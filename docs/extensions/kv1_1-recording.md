# Kv1_1の電流記録

`verify.py`が出力した`vanilla/`・`zero/`・`active/`と`report.json`を使う。

```sh
python examples/kv1_1/record_currents.py --verification-dir _runs/kv1_1-check-01 --output _runs/currents-01
python examples/kv1_1/plot_currents.py --recording-dir _runs/currents-01 --output _runs/figures-01
```

未使用の出力先を指定する。NumPy・Matplotlibが必要。
HTML、4ページのPDF、PNG、時系列CSV入りZIP、電流集計CSV、検証JSONを生成する。

## 記録値

検証済みカーネルのコピーへ観測コードを加え、`solve`直前の電圧・ゲート・Ca濃度で瞬時電流を記録する。
`ion.c`の実際の式を使い、状態を更新しない。Napは非線形電流、Ca電流は記録時点のCa濃度による反転電位で計算する。

| 列 | 単位 |
| --- | --- |
| `time_ms`, `cell_id` | ms、細胞ID |
| `v_mV`, `ca_mM`, `n_Kv1_1`, `area_cm2` | mV、mM、無次元、cm² |
| `I_<channel>_uA`, `I_leak_uA` | µA、外向きが正 |
| `I_inject_nA` | nA、内向きが正 |

図・集計ではµAを1000倍してnAに換算する。電荷は刺激区間の左端和（nA×ms=pC）。
同一チャネルの追加前後で軸を揃え、全時間とスパイク付近を表示する。ゼロ電流も元CSVに含む。

## 検証・範囲

- ソース・入力・出力のハッシュを照合し、記録あり・なし・元のv.dat/s.datがバイト単位で一致することを確認。
- 16チャネルを個別に有効化し、実際の行列寄与と照合。電圧3条件・Ca濃度2条件、絶対許容差1e−12 µA。
- 時刻はv.datと一致、電圧差は5.01e−7 mV以内。Kv1_1の電流式・初期ゲート・更新時点も照合。

対象は単一細胞の体細胞。容量性・軸方向・シナプス電流と積分中の平均電流は含まない。電流比は発火への寄与率ではない。
既存チャネルは実装との整合を確認し、参照MODとの同等性は評価していない。

ZIPの`verified-example/`を展開し、`--verification-dir`に指定すると再記録できる。
他の機構では`current_recording.py`の記録列・式への接続・検証を変更する。
