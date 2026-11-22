#!/usr/bin/env python3
"""Create voltage/current figures, a PDF, and a Japanese result report."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import tempfile
import zipfile
import sys

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'neulite-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from run_baseline import sha256

BEFORE, AFTER = '#3274a1', '#d95f02'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.recording_dir.resolve(), args.output.resolve()
    report = json.loads((source / 'report.json').read_text())
    traces, spikes = {}, {}
    for name in ['zero', 'active']:
        folder = source / name / 'on'
        for filename, digest in report['runs'][name]['data_sha256'].items():
            assert sha256(folder / filename) == digest
        traces[name] = np.genfromtxt(folder / 'currents.csv', delimiter=',', names=True)
        spikes[name] = np.loadtxt(folder / 's.dat', ndmin=2)[:, 0]
    output.mkdir(parents=True, exist_ok=False)
    z, a = traces['zero'], traces['active']
    np.testing.assert_array_equal(z['time_ms'], a['time_ms'])
    np.testing.assert_array_equal(z['I_inject_nA'], a['I_inject_nA'])
    t = a['time_ms']
    dt = report['runs']['active']['dt_ms']
    stimulation = a['I_inject_nA'] != 0
    start, end = float(t[stimulation][0]), float(t[stimulation][-1] + dt)
    first = [float(s[0]) for s in spikes.values() if len(s)]
    zoom = (max(0, min(first) - 10), min(float(t[-1]), max(first) + 25)) if first else (start, min(end, start + 100))
    channels = report['channels'] + ['leak']
    currents = {name: {ch: trace[f'I_{ch}_uA'] * 1000 for ch in channels}
                for name, trace in traces.items()}  # uA -> nA for all figures
    nonzero = [ch for ch in channels if any(np.max(np.abs(currents[name][ch])) > 1e-10 for name in traces)]
    rows = []
    for name in traces:
        for ch in channels:
            y = currents[name][ch][stimulation]
            rows.append({'condition': name, 'channel': ch, 'window_start_ms': start,
                         'window_end_ms': end, 'min_nA': float(y.min()), 'max_nA': float(y.max()),
                         'peak_abs_nA': float(np.max(np.abs(y))), 'mean_nA': float(y.mean()),
                         'signed_charge_pC': float(np.sum(y) * dt)})
    with (output / 'current_summary.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {'source_recording': str(source), 'source_verification': report['source_verification'],
               'stimulus_window_ms': [start, end], 'zoom_window_ms': list(zoom),
               'plot_units': 'nA (raw ionic/leak CSV is uA)',
               'charge_definition': 'Left-endpoint sum during stimulus; signed nA * ms = pC',
               'nonzero_channels_shown': nonzero, 'conditions': {}}
    for name in traces:
        summary['conditions'][name] = {'spikes_total': len(spikes[name]),
                                      'first_spike_latency_ms': float(spikes[name][0] - start) if len(spikes[name]) else None,
                                      'gbar_S_cm2': report['runs'][name]['gbar_S_cm2']}
    summary['new_current_during_stimulus'] = next(row for row in rows if row['condition'] == 'active' and row['channel'] == 'Kv1_1')

    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titlesize': 11, 'legend.fontsize': 9, 'savefig.facecolor': 'white'})
    figures = []
    title = 'Kv1_1 addition | Allen 472363762 | soma | 34 C | E_K = -107 mV'
    density = report['runs']['active']['gbar_S_cm2']
    before_label = 'Before: Kv1_1 = 0 (voltage equals vanilla)'
    after_label = f'After: Kv1_1 = {density:g} S/cm2'

    def decorate(ax, xlim, ylabel):
        ax.set_xlim(*xlim)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.18)
        ax.axvspan(start, end, color='#777777', alpha=0.06)

    with PdfPages(output / 'voltage_and_currents.pdf') as pdf:
        def save(fig, name):
            fig.savefig(output / f'{name}.png', dpi=160)
            pdf.savefig(fig)
            figures.append(name)
            plt.close(fig)

        fig, ax = plt.subplots(4, 1, figsize=(12, 9), sharex=True,
                               gridspec_kw={'height_ratios': [0.65, 1.4, 1.4, 1]})
        fig.suptitle(title, y=0.985)
        ax[0].plot(t, a['I_inject_nA'], color='#333333')
        ax[0].set_title('Same input in both runs; positive injected current is inward', loc='left')
        ax[1].plot(t, z['v_mV'], color=BEFORE, lw=0.8)
        ax[1].set_title(f'{before_label} | {len(spikes["zero"])} spikes', loc='left')
        ax[2].plot(t, a['v_mV'], color=AFTER, lw=0.8)
        ax[2].set_title(f'{after_label} | {len(spikes["active"])} spikes', loc='left')
        for axis in ax[1:3]: axis.set_ylim(-110, 55)
        ax[3].plot(t, currents['active']['Kv1_1'], color=AFTER, lw=0.8)
        ax[3].plot(t, currents['zero']['Kv1_1'], color=BEFORE, lw=0.7, ls='--')
        ax[3].set_title('Added Kv1_1 current; positive ionic current is outward', loc='left')
        for axis, label in zip(ax, ['Input (nA)', 'V (mV)', 'V (mV)', 'I_Kv1_1 (nA)']):
            decorate(axis, (0, t[-1] + dt), label)
        ax[-1].set_xlabel('Time (ms)')
        fig.tight_layout(rect=(0, 0.01, 1, 0.96))
        save(fig, 'overview')

        fig, ax = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
        fig.suptitle(title + '\nFirst-spike detail; same time axis in both conditions', y=0.99)
        ax[0].plot(t, z['v_mV'], color=BEFORE, label='Before')
        ax[0].plot(t, a['v_mV'], color=AFTER, label='After')
        ax[0].legend(loc='upper right')
        ax[1].plot(t, currents['active']['Kv1_1'], color=AFTER, label='Kv1_1 after')
        ax[1].plot(t, currents['zero']['Kv1_1'], color=BEFORE, ls='--', label='Kv1_1 before = 0')
        ax[1].legend(loc='upper right')
        potassium = ['Kv2like', 'Kv3_1', 'K_P', 'K_T', 'Kd', 'Im', 'Im_v2', 'SK']
        for name, color in [('zero', BEFORE), ('active', AFTER)]:
            y = sum(currents[name][ch] for ch in potassium)
            ax[2].plot(t, y, color=color, label=f'Existing K channels: {"before" if name == "zero" else "after"}')
        ax[2].plot(t, currents['active']['Kv1_1'], color='#7d4095', ls='--', label='New Kv1_1')
        ax[2].legend(loc='upper right')
        for axis, label in zip(ax, ['V (mV)', 'I_Kv1_1 (nA)', 'Current (nA)']): decorate(axis, zoom, label)
        ax[-1].set_xlabel('Time (ms)')
        fig.tight_layout(rect=(0, 0.01, 1, 0.93))
        save(fig, 'spike_detail')

        for label, limits in [('all', (0, t[-1] + dt)), ('zoom', zoom)]:
            nrows = math.ceil(len(nonzero) / 3)
            fig, axes = plt.subplots(nrows, 3, figsize=(13, 2.35 * nrows + 1), squeeze=False)
            fig.suptitle(title + '\nIndividual currents: blue = before, orange = after | outward positive', y=0.99)
            mask = (t >= limits[0]) & (t <= limits[1])
            for axis, ch in zip(axes.flat, nonzero):
                for name, color in [('zero', BEFORE), ('active', AFTER)]:
                    axis.plot(t[mask], currents[name][ch][mask], color=color, lw=0.85, alpha=0.9)
                axis.axhline(0, color='#777777', lw=0.5)
                axis.set_title(ch + (' (new)' if ch == 'Kv1_1' else ''), loc='left')
                decorate(axis, limits, 'nA')
                axis.set_xlabel('Time (ms)')
                axis.ticklabel_format(axis='y', style='sci', scilimits=(-2, 3))
            for axis in list(axes.flat)[len(nonzero):]: axis.set_visible(False)
            fig.text(0.5, 0.01, 'Each panel has its own vertical scale; before and after share that scale. Zero currents omitted.', ha='center', fontsize=9)
            fig.tight_layout(rect=(0, 0.03, 1, 0.93))
            save(fig, f'individual_currents_{label}')
    summary['figures'] = figures
    summary['plot_script_sha256'] = sha256(__file__)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / 'recording_verification.json').write_text(json.dumps(report, indent=2) + '\n')
    with zipfile.ZipFile(output / 'raw_data.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in traces:
            for filename in ['currents.csv', 'v.dat', 's.dat']:
                archive.write(source / name / 'on' / filename, f'{name}/{filename}')
        archive.write(output / 'recording_verification.json', 'recording_verification.json')
        archive.write(source / 'source-verification.json', 'source-verification.json')
        archive.write(output / 'current_summary.csv', 'current_summary.csv')
        # Preserve the verified implementation and inputs as well as
        # traces, so the report does not depend on an ephemeral /tmp workspace.
        verified = Path(report['source_verification'])
        archive.write(source / 'source-verification.json', 'verified-example/report.json')
        for name in ['vanilla', 'zero', 'active']:
            archive.write(verified / name / 'example.json', f'verified-example/{name}/example.json')
            for path in sorted((verified / name / 'neulite').rglob('*')):
                if path.is_file() and path.suffix != '.o' and path.name not in ('nl', 'currents.csv'):
                    archive.write(path, str(Path('verified-example') / name / 'neulite' / path.relative_to(verified / name / 'neulite')))
    new = summary['new_current_during_stimulus']
    latency = {name: (f"{c['first_spike_latency_ms']:.1f} ms" if c['first_spike_latency_ms'] is not None else '発火なし')
               for name, c in summary['conditions'].items()}
    text = f'''# Kv1_1の膜電位と電流

Allen 472363762、体細胞、34℃、E_K=−107 mV、密度0と{density:g} S/cm²。
刺激は{start:g}〜{end:g} ms、{a['I_inject_nA'].max():g} nA。記録間隔{dt:g} ms。

- 発火数：{len(spikes['zero'])} → {len(spikes['active'])}。
- 刺激開始から最初の発火まで：{latency['zero']} → {latency['active']}（s.datの時刻）。
- 刺激中のKv1_1電流：最大{new['max_nA']:.5g} nA、平均{new['mean_nA']:.5g} nA。

[図](index.html) · [PDF](voltage_and_currents.pdf) · [元データ](raw_data.zip) · [集計](current_summary.csv)

青は追加前、橙は追加後。全時間とスパイク付近を表示する。
電流はnA、イオン・漏れ電流は外向き、注入電流は内向きが正。
各パネルで縦軸は異なるが、同一チャネルの追加前後は共通。

## 記録・検証

各ステップの更新直前の電圧・ゲート・Ca濃度による瞬時電流。
16チャネルの実際の計算寄与、Kv1_1の式・更新時点と照合済み。
記録あり・なし・元のv.dat/s.datはバイト単位で一致。追加前の膜電位はvanillaと一致する。

容量性・軸方向・シナプス電流は含まない。電流比は発火への寄与率ではない。
既存機構の参照MODとの同等性と生理学的適合性は未評価。

元CSVのイオン・漏れ電流はµA、図・集計はnA。電荷は刺激区間の左端和（nA×ms=pC）。
[検証JSON](recording_verification.json)に条件・誤差を記載。
ZIP内の`verified-example/`を`record_currents.py --verification-dir`へ指定すると再記録できる。
'''
    (output / 'README.md').write_text(text)
    captions = ['全時間の膜電位と追加電流', '最初のスパイク付近の比較', '各チャネルの電流：全時間', '各チャネルの電流：拡大']
    panels = ''.join(f'<h2>{caption}</h2><a href="{name}.png"><img src="{name}.png" alt="{caption}"></a>'
                     for caption, name in zip(captions, figures))
    (output / 'index.html').write_text('''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Kv1_1 膜電位・電流比較</title>
<style>body{max-width:1100px;margin:40px auto;padding:0 20px;color:#24313d;font:16px/1.8 system-ui}img{width:100%}h2{margin-top:48px}a{color:#1768a0}.note{background:#f1f5f8;padding:16px;border-radius:8px}</style>
<h1>Kv1_1追加前後の膜電位と電流</h1>
''' + f'<p>Allen 472363762の体細胞。34℃、E_K=−107 mV、Kv1_1は0と{density:g} S/cm²。{a["I_inject_nA"].max():g} nAを{start:g}〜{end:g} msに注入。</p>' + f'<p>発火数：<strong>{len(spikes["zero"])} → {len(spikes["active"])}</strong>。刺激中のKv1_1最大電流：<strong>{new["max_nA"]:.5g} nA</strong>。</p>' + '''
<p><a href="voltage_and_currents.pdf">PDF（全4ページ）</a> · <a href="raw_data.zip">時系列の元データ</a> · <a href="current_summary.csv">電流の集計CSV</a> · <a href="README.md">条件・検証・再現の記録</a></p>
<p class="note">青＝追加前、橙＝追加後。電流はnA。イオン・漏れ電流は外向きが正、注入電流は内向きが正です。記録の有無で膜電位・発火出力が変わらないことを確認しています。</p>
''' + panels + '''
<p class="note">個別電流の縦軸はパネルごとに異なります。電流の大きさの比は発火への寄与率ではありません。軸方向・容量性・シナプス電流は含みません。既存チャネルの変化には膜電位・ゲート状態の変化も含まれます。</p></html>''')
    print(json.dumps(summary['new_current_during_stimulus'], indent=2))
    print(output / 'index.html')


if __name__ == '__main__':
    main()
