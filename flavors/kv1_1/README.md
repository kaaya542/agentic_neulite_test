# Kv1_1 flavor

Neulite update/v1.2.0のvanilla `38c2f926e2862e61e784fd3569bf3fc30e2bf1bb`から派生した、体細胞Kv1_1イオン電流を追加する単一プロセス版。

参照はBMTK同梱の`Kv11.mod`、gateCurrent=0。温度34℃、E_K=−107 mVを固定する。既存チャネルの後ろにKv1_1を追加し、ion CSVは24列を使う。対応する`NeuliteBuilder(kernel_flavor="kv1_1")`で入力を再生成する。

[仕様](../../docs/extensions/kv1_1.md)と[実行・検証手順](../../docs/agent_usage.md)を参照する。`ALLACTIVE=1`はこのflavorではサポートしない。
