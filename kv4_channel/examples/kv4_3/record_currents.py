#!/usr/bin/env python3
"""Re-run verified Kv4_3 zero/active examples with optional current observation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

from current_recording import CHANNELS, instrument

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from run_baseline import sha256, run_logged
# Channel-independent observer check (iterates over all N_GBAR channels).
CURRENT_PROBE = ROOT / 'test/kv1_1/current_probe.c'
sys.path.insert(0, str(ROOT / 'test/kv4_3'))
from oracle import rates, EK_MV


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verification-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.verification_dir.resolve(), args.output.resolve()
    prior = json.loads((source / 'report.json').read_text())
    # Use the actual source and inputs that produced the reviewed outputs.
    for name in ['vanilla', 'zero', 'active']:
        for file, key in [('v.dat', 'v_sha256'), ('s.dat', 's_sha256')]:
            assert sha256(source / name / 'neulite' / file) == prior['simulations'][name][key]
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source / 'report.json', output / 'source-verification.json')
    report = {'source_verification': str(source), 'sampling': 'Before solve at time_ms, identical state/time to v.dat',
              'current_sign': 'Outward ionic/leak current positive; injected current positive inward',
              'raw_units': {'ionic_and_leak': 'uA', 'injection': 'nA', 'voltage': 'mV', 'time': 'ms', 'calcium': 'mM'},
              'scope': 'Somatic channel and leak currents, not total membrane balance (no axial/capacitive/synaptic currents)',
              'checks': {}, 'runs': {}}
    for name in ['zero', 'active']:
        original = source / name / 'neulite'
        conditions = json.loads((source / name / 'example.json').read_text())
        run = output / name
        run.mkdir()
        original_hashes = {str(p.relative_to(original)): sha256(p) for p in original.rglob('*')
                           if p.is_file() and p.suffix not in ('.o', '.dat') and p.name != 'nl'}
        for relative, digest in original_hashes.items():
            if relative.startswith('kernel/') and Path(relative).name != 'config.h':
                key = 'flavors/kv4_3/' + relative.removeprefix('kernel/')
                if key in prior['source_sha256']:
                    assert digest == prior['source_sha256'][key], f'Verified source changed: {key}'
        for mode in ['off', 'on']:
            shutil.copytree(original, run / mode,
                            ignore=shutil.ignore_patterns('*.o', 'nl', '*.dat', 'currents.csv'))
        kernel = run / 'on/kernel'
        instrument(kernel)
        run_logged(['make', '-j2'], kernel, run / 'build.log')
        subprocess.run(['gcc', '-std=gnu11', '-O2', '-I', str(kernel),
                        str(CURRENT_PROBE), '-lm', '-o', str(run / 'probe')], check=True)
        error = float(subprocess.check_output([str(run / 'probe')], text=True))
        for mode in ['off', 'on']:
            env = os.environ.copy()
            env['NEULITE_RECORD_CURRENTS'] = '1' if mode == 'on' else '0'
            with (run / f'{mode}.log').open('w') as log:
                subprocess.run([str(kernel / 'nl'), 'cell_population.csv', 'cell_cell_connection.csv'],
                               cwd=run / mode, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        for file in ['v.dat', 's.dat']:
            assert sha256(original / file) == sha256(run / 'off' / file) == sha256(run / 'on' / file), file
        assert not (run / 'off/currents.csv').exists()
        trace = np.genfromtxt(run / 'on/currents.csv', names=True, delimiter=',')
        assert all(np.all(np.isfinite(trace[k])) for k in trace.dtype.names)
        assert np.all(trace['cell_id'] == 0), 'This report currently supports one cell'
        voltage = np.loadtxt(original / 'v.dat')
        np.testing.assert_allclose(trace['time_ms'], voltage[:, 0], atol=1e-10, rtol=0)
        np.testing.assert_allclose(trace['v_mV'], voltage[:, 1], atol=5.01e-7, rtol=0)
        dt = float(np.diff(trace['time_ms'])[0])
        density = conditions['gkbar_S_cm2']
        assert (density == 0) if name == 'zero' else (density > 0)
        assert conditions['temperature_C'] == 34 and conditions['ek_mV'] == EK_MV
        a, b = trace['a_Kv4_3'], trace['b_Kv4_3']
        expected = density * trace['area_cm2'] * 1000 * a**3 * b * (trace['v_mV'] - EK_MV)
        np.testing.assert_allclose(trace['I_Kv4_3_uA'], expected, atol=1e-14, rtol=1e-12)
        # Independently replay a, b using the high-precision sampled voltages and
        # the actual update convention (backward Euler at the new V).
        initial = rates(float(trace['v_mV'][0]))
        gate_error = max(abs(initial[0] - a[0]), abs(initial[2] - b[0]))
        inf_tau = np.array([rates(float(v)) for v in trace['v_mV'][1:]])
        for gate, inf, tau in [(a, inf_tau[:, 0], inf_tau[:, 1]), (b, inf_tau[:, 2], inf_tau[:, 3])]:
            predicted = (gate[:-1] + dt * inf / tau) / (1 + dt / tau)
            gate_error = max(gate_error, float(np.max(np.abs(predicted - gate[1:]))))
        assert gate_error < 1e-12
        assert all(sha256(original / p) == h for p, h in original_hashes.items())
        report['runs'][name] = {
            'samples': len(trace), 'dt_ms': dt, 'gkbar_S_cm2': density, 'conditions': conditions,
            'spikes': prior['simulations'][name]['spikes'],
            'recording_on_off_and_original_bitwise_equal': True,
            'channel_observer_max_error_uA': error, 'gate_time_alignment_max_error': gate_error,
            'source_sha256': original_hashes,
            'recorded_kernel_sha256': {str(p.relative_to(kernel)): sha256(p) for p in kernel.rglob('*')
                                       if p.is_file() and p.suffix != '.o' and p.name != 'nl'},
            'data_sha256': {p: sha256(run / 'on' / p) for p in ['currents.csv', 'v.dat', 's.dat']}}
        print(f'PASS {name}: recording on/off == reviewed outputs; currents and timestamps checked', flush=True)
    assert prior['simulations']['zero']['v_sha256'] == prior['simulations']['vanilla']['v_sha256']
    report['checks']['zero_equals_vanilla'] = True
    report['channels'] = [name for _, name in CHANNELS]
    report['tool_sha256'] = {str(p.relative_to(ROOT)): sha256(p) for p in
                            [Path(__file__), ROOT / 'examples/kv4_3/current_recording.py', CURRENT_PROBE]}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(output / 'report.json')


if __name__ == '__main__':
    main()
