# Kv4_3 flavor

Neulite update/v1.2.0のvanilla `38c2f926e2862e61e784fd3569bf3fc30e2bf1bb`（`kernel/`）から派生した、体細胞Kv4_3イオン電流を追加する単一プロセス版。Kv1_1 flavorとは独立。

参照はBMTK同梱の`Kv43.mod`。温度34℃、E_K=−107 mVを固定する。ゲート`a`・`b`は解析式（MODのTABLEなし）で評価し、MODの`derivimplicit`と同じ後退Euler法で更新する。既存チャネルの後ろにKv4_3を追加し、ion CSVは24列を使う。対応する`NeuliteBuilder(kernel_flavor="kv4_3")`で入力を再生成する。

[仕様](../../docs/extensions/kv4_3.md)を参照する。`ALLACTIVE=1`はこのflavorではサポートしない。
