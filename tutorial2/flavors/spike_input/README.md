# spike_input flavor

Neulite update/v1.2.0のvanilla `38c2f926e2862e61e784fd3569bf3fc30e2bf1bb`から派生した単一プロセス版。virtualノード（外部のスパイク源）からの入力を受け取る。

```sh
./kernel/nl <population_csv> <connection_csv> <input_connection_csv> <input_spike_csv>
```

- `input_connection_csv`：内部接続と同じ9列。`pre nid`はvirtualノードのID。bionetliteが`{src}_{trg}_connection.csv`として出力する。
- `input_spike_csv`：`time_ms,node_id`。`bionetlite.convert_spike_inputs`がSONATAのスパイクファイルから作る。

到着時刻`te = ts + delay`のイベントは、NEURONの固定刻みと同じくステップ`ceil(te/dt − 0.5)`から効く。同じシナプスに複数のイベントが届いても失われない。入力のない場合、v.dat・s.datはvanillaと一致する。変更箇所は`conn.[ch]`、`synapse.[ch]`、`network.[ch]`、`main.c`。

[仕様](../../docs/extensions/tutorial2.md) · [実例](../../examples/tutorial2/README.md)
