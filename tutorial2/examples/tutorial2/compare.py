#!/usr/bin/env python3
"""Compare somatic membrane potential and spikes of BioNet and Neulite for Tutorial 2.

Criteria are fixed in docs/extensions/tutorial2.md before the comparison.
"""
import argparse
import json
from pathlib import Path

import h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

SPIKE_WINDOW_MS = 2.0          # a spike in the other simulator within ±2 ms matches
EXCLUDE_MS = (-2.0, 20.0)      # excluded around every spike for the subthreshold RMSE
MATCH_FRACTION_MIN = 0.9
RMSE_MAX_MV = 1.0
COLORS = {'BMTK': '#2a78d6', 'Neulite': '#eb6834'}


def load(run_dir):
    with h5py.File(run_dir / 'sim_ch02/output/v_report.h5') as f:
        start, stop, step = f['report/mcortex/mapping/time'][()]
        v_bmtk = f['report/mcortex/data'][:, 0]
    with h5py.File(run_dir / 'sim_ch02/output/spikes.h5') as f:
        s_bmtk = np.sort(f['spikes/mcortex/timestamps'][()])
    neulite = np.loadtxt(run_dir / 'sim_ch02_nl/v.dat')
    # BioNet records after each fadvance and does not save the initial state, so sample k is at (k+1)*dt
    # (BioSimulator.post_fadvance). Neulite row k is the state at k*dt, starting from v_init.
    if len(neulite) != len(v_bmtk) or not np.allclose(neulite[:, 0], start + step * np.arange(len(neulite)), atol=1e-6):
        raise ValueError(f'Time axes differ: BioNet {len(v_bmtk)} samples, Neulite {len(neulite)} samples')
    t = neulite[1:, 0]
    s_neulite = np.sort(np.atleast_2d(np.loadtxt(run_dir / 'sim_ch02_nl/s.dat'))[:, 0])
    return t, v_bmtk[:-1], neulite[1:, 1], s_bmtk, s_neulite


def matched(spikes, others):
    """Signed time from each spike to the nearest spike of the other simulator (other - spike, ms)."""
    if len(others) == 0:
        return np.full(len(spikes), np.inf)
    delta = others[None, :] - spikes[:, None]
    return delta[np.arange(len(spikes)), np.argmin(np.abs(delta), axis=1)]


def evaluate(t, v_bmtk, v_neulite, s_bmtk, s_neulite):
    signed = matched(s_bmtk, s_neulite)
    d_bmtk, d_neulite = np.abs(signed), np.abs(matched(s_neulite, s_bmtk))
    within = d_bmtk <= SPIKE_WINDOW_MS
    subthreshold = np.ones(len(t), dtype=bool)
    for s in np.concatenate([s_bmtk, s_neulite]):
        subthreshold &= ~((t >= s + EXCLUDE_MS[0]) & (t <= s + EXCLUDE_MS[1]))
    diff = v_neulite - v_bmtk
    count_tolerance = max(1, 0.1 * len(s_bmtk))
    result = {
        'spikes': {
            'bmtk': len(s_bmtk), 'neulite': len(s_neulite),
            'count_difference': len(s_neulite) - len(s_bmtk), 'count_tolerance': count_tolerance,
            'bmtk_matched_fraction': float(np.mean(d_bmtk <= SPIKE_WINDOW_MS)),
            'neulite_matched_fraction': float(np.mean(d_neulite <= SPIKE_WINDOW_MS)),
            'matched_time_difference_neulite_minus_bmtk_ms': {
                'mean': float(np.mean(signed[within])),
                'median': float(np.median(signed[within])),
                'max_abs': float(np.max(d_bmtk[within])),
            },
        },
        'membrane_potential_mV': {
            'subthreshold_rmse': float(np.sqrt(np.mean(diff[subthreshold] ** 2))),
            'subthreshold_fraction': float(np.mean(subthreshold)),
            'subthreshold_max_abs_difference': float(np.max(np.abs(diff[subthreshold]))),
            'subthreshold_mean_difference': float(np.mean(diff[subthreshold])),
            'all_samples_rmse': float(np.sqrt(np.mean(diff ** 2))),
        },
    }
    result['criteria'] = {
        'spike_count': abs(result['spikes']['count_difference']) <= count_tolerance,
        'bmtk_spikes_matched': result['spikes']['bmtk_matched_fraction'] >= MATCH_FRACTION_MIN,
        'neulite_spikes_matched': result['spikes']['neulite_matched_fraction'] >= MATCH_FRACTION_MIN,
        'subthreshold_rmse': result['membrane_potential_mV']['subthreshold_rmse'] <= RMSE_MAX_MV,
    }
    result['passed'] = all(result['criteria'].values())
    return result, subthreshold


def plot(t, v_bmtk, v_neulite, s_bmtk, s_neulite, subthreshold, output):
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#52514e', 'axes.labelcolor': '#0b0b0b'})
    fig, axes = plt.subplots(4, 1, figsize=(10, 9), gridspec_kw={'height_ratios': [3, 3, 1.6, 1]})
    for ax, (lo, hi) in zip(axes[:2], [(0, 3000), (1550, 1720)]):
        sel = (t >= lo) & (t <= hi)
        for name, v in [('BMTK', v_bmtk), ('Neulite', v_neulite)]:
            ax.plot(t[sel], v[sel], color=COLORS[name], lw=1.0 if hi - lo > 500 else 1.5, label=name)
        ax.set_xlim(lo, hi)
        ax.set_ylabel('Soma V (mV)')
        ax.grid(axis='y', color='#e4e3df', lw=0.6)
    axes[0].set_title('Tutorial 2: somatic membrane potential, BMTK (BioNet) vs Neulite', loc='left')
    axes[0].legend(loc='upper right', frameon=False, ncol=2)
    axes[1].set_title('Zoom 1550–1720 ms', loc='left')
    diff = np.where(subthreshold, v_neulite - v_bmtk, np.nan)
    axes[2].plot(t, diff, color='#52514e', lw=0.6)
    axes[2].axhline(0, color='#b5b4ae', lw=0.6)
    axes[2].set_ylabel('Neulite − BMTK\n(mV, subthreshold)')
    axes[2].set_xlim(0, 3000)
    for row, (name, spikes) in enumerate([('BMTK', s_bmtk), ('Neulite', s_neulite)]):
        axes[3].vlines(spikes, row + 0.6, row + 1.4, color=COLORS[name], lw=1.2)
    axes[3].set_yticks([1, 2], ['BMTK', 'Neulite'])
    axes[3].set_ylim(0.4, 2.6)
    axes[3].set_xlim(0, 3000)
    axes[3].set_xlabel('Time (ms)')
    axes[3].set_title('Spikes', loc='left')
    fig.tight_layout()
    for suffix in ['png', 'pdf']:
        fig.savefig(output / f'tutorial2_comparison.{suffix}', dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True, help='output of examples/tutorial2/run.py')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    t, v_bmtk, v_neulite, s_bmtk, s_neulite = load(args.run_dir)
    result, subthreshold = evaluate(t, v_bmtk, v_neulite, s_bmtk, s_neulite)
    result['run_dir'] = str(args.run_dir.resolve())
    plot(t, v_bmtk, v_neulite, s_bmtk, s_neulite, subthreshold, args.output)
    np.savetxt(args.output / 'traces.csv', np.column_stack([t, v_bmtk, v_neulite]), delimiter=',',
               fmt='%.6f', header='time_ms,v_bmtk_mV,v_neulite_mV')
    (args.output / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit('Comparison criteria not met')


if __name__ == '__main__':
    main()
