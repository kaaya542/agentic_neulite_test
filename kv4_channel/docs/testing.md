# テストと検証範囲

リポジトリのルートで実行する。出力先は未使用のディレクトリを指定する。

## 標準カーネル

```sh
python tools/run_baseline.py --output _runs/baseline-01
```

同梱の単一細胞入力を使い、Cカーネルのビルドと2000 msの計算を確認する。膜電位の有限性・20000サンプル・元のカーネルが変更されていないことを検証し、`report.json`に発火数とファイルのハッシュを保存する。参照シミュレータとの科学的な一致を検証するテストではない。

## Kv1_1例

```sh
python -m pip install -r examples/kv1_1/requirements.txt
python test/kv1_1/verify.py --output _runs/kv1_1-check-01
python examples/kv1_1/record_currents.py --verification-dir _runs/kv1_1-check-01 --output _runs/currents-01
python examples/kv1_1/plot_currents.py --recording-dir _runs/currents-01 --output _runs/figures-01
```

検証は独立式・同梱MODとの比較、入力生成、無効時回帰、有効時の実行、故障注入を含む。電流記録では観測を追加しても膜電位と発火が変わらないことを確認する。結果は各出力先のJSONと`_runs/figures-01/index.html`に保存する。

科学的条件・許容差は[仕様](extensions/kv1_1.md)を参照する。全細胞のBioNet等価性、MPI版、別温度、他の機構へ結果を一般化しない。

## Kv4_3例

```sh
python -m pip install -r examples/kv4_3/requirements.txt
python test/kv4_3/verify.py --output _runs/kv4_3-check-01
python examples/kv4_3/record_currents.py --verification-dir _runs/kv4_3-check-01 --output _runs/kv4_3-currents-01
python examples/kv4_3/plot_currents.py --recording-dir _runs/kv4_3-currents-01 --output _runs/kv4_3-figures-01
```

検証項目はKv1_1例と同様で、故障注入に積分法の誤りを加える。科学的条件・許容差は[仕様](extensions/kv4_3.md)、結果は[結果](results/kv4_3.md)を参照する。

## 配布したソースでの確認

[ソースの書き出し](repository.md)で作ったコピーに移動し、上記のコマンドを実行する。コピー内に過去の結果やローカル環境設定がなくても、同梱例は実行できる。使用したPython・依存パッケージ・コンパイラの版と実行結果を記録する。

エージェントへの新しい依頼では、実行完了・機能テスト合格・参照結果との比較基準達成を区別して報告する。
