# アーキテクチャ

対象：Neulite [1.2.0](../upstream.json)。

## 責務とflavor

Neuliteは小さな数値計算カーネルと用途に応じたflavorを中心とする。入力処理と数値計算を分け、拡張する機構に必要な変更を対応するflavorへまとめる。

bionetliteはBMTKのモデル定義を読み、入力検証・前処理・ファイル生成を行う。カーネルは数値計算を担う。

`kernel/`は標準カーネル、`flavors/`は派生実装。入力形式に対応するbionetliteと組み合わせる。

## データの流れ

```text
BMTKのモデル・ノード・接続定義、形態、パラメータ、実行設定
  → bionetlite.NeuliteBuilder / NeuliteNetwork
  → SONATAとNeulite用population・connection・ion CSV / config.h
  → population・connection・neuron・ion・synapseの初期化
  → networkの時間ループ → solver → 電位・状態・シナプス更新
  → v.dat / s.dat、および対象flavorが提供する記録
```

MODは数式・パラメータ・初期化を確認する参照実装として使う。自動翻訳には未対応。

## 変更の入口

| 場所 | 主な責務と連動するもの |
| --- | --- |
| `bionetlite/bionetlite.py` | モデル・入力設定の読み取り、形態処理、接続・重みの前処理、CSVとconfig.hの生成 |
| `popl.c`、`popl_func.h` | populationと形態・パラメータの読み込み、配列確保、入力時の単位・面積換算 |
| `conn.c`、`conn.h` | 接続、重み、遅延、シナプスのパラメータ |
| `neuron.c`、`neuron.h` | ニューロンと区画の電位・Ca濃度・外部電流、初期状態 |
| `ion.c`、`ion.h`、`ion_func.h` | イオン機構の状態・式・電流寄与、Ca更新 |
| `synapse.c`、`synapse.h` | シナプス状態の更新 |
| `network.c`、`network.h` | 時間ループ、発火・伝播と記録 |
| `solver.c`、`hines.c` | 行列の組み立てと解法、電位・機構の更新順序 |
| `config.h`、Makefile | 実行条件とビルド。ヘッダー変更後は作業用コピーをクリーンビルド |

接続の変更では、生成側と読み込み側のノードID・区画ID・重み・遅延を揃える。外部イベントは実行中の受け渡しまで確認する。

## パラメータと状態

vanillaのゲート状態はニューロン数×`N_GATEVAL`、体細胞用最大コンダクタンスはpopulation数×`N_GBAR`で保持する。`ion.c`の初期化・電流計算は体細胞の電位とCa濃度を参照する。全区画への機構配置では配列、初期化、更新、計算への接続を見直す。`ALLACTIVE`の定義だけではこれらの構造は切り替わらない。

初期電位は`conditions.v_init` → CSVの`V_INIT` → `population_t.v_init` → `neuron.c`へ渡る。漏れの反転電位`e_pas`とは独立。

反転電位は`ion.h`、温度補正は`ion_func.h`内の定数も使う。可変にする場合は入力から計算まで値を渡す。

`solver.c:solve`の順序は、行列の組み立て・求解、Ca更新、電位更新、イオン状態更新、シナプス更新。新しい状態や観測の時刻はこの順序に合わせる。

## 単位の境界

| 量 | 外部入力 | カーネル内部・換算場所 |
| --- | --- | --- |
| 電圧・時間 | mV・ms | 同じ単位 |
| 形態の長さ・半径 | µm | `popl_func.h`でcm、面積はcm² |
| チャネル・漏れの密度 | S/cm² | `density * area * 1e3` → mS |
| 膜容量密度 | µF/cm² | 面積を掛けてµF |
| 軸方向抵抗率 | Ω·cm | `1e-3`を掛けてkΩ·cm |
| 外部電流 | nA | `solver.c`で`1e-3`を掛けてµA |
| シナプス重み | µS | `solver.c`でmSへ換算 |
| イオン総電流 | mS × mV | µA。参照MODの密度電流との比較には面積換算が必要 |

## 入力経路を拡張する際の確認

`NeuliteNetwork.add_nodes`はbiophysical以外のノードをスキップする。virtualノードのイベント入力には、保存・読み込み・実行時の経路を確認・拡張する必要がある。

MPIは`flavors/mpi/`。拡張時は状態の所有・分割・通信を確認し、直列と比較する。

[拡張手順](extension_workflow.md) · [チャネル追加](../.agents/skills/neulite-add-ion-channel/SKILL.md)
