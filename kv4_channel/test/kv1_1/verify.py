#!/usr/bin/env python3
"""Verify the real C flavor against independent equations, pinned MOD and a full input path."""
import argparse
import importlib.metadata
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from oracle import rates, gate, current

ROOT = Path(__file__).resolve().parents[2]
TEST = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from run_baseline import run_logged, sha256, voltage_summary


def table(command, cwd=None):
    return np.loadtxt(io.StringIO(subprocess.check_output([str(x) for x in command], cwd=cwd, text=True)), delimiter=',')


def check(actual, expected, tolerance=1e-10):
    np.testing.assert_allclose(actual, expected, rtol=tolerance, atol=tolerance)
    return float(np.max(np.abs(np.asarray(actual) - expected)))


def compile_probe(kernel, binary):
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-I', str(kernel), str(TEST / 'probe.c'),
                    '-lm', '-o', str(binary)], check=True)


def compile_parser(kernel, binary):
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-I', str(kernel), str(TEST / 'parser_probe.c'),
                    str(kernel / 'popl.c'), str(kernel / 'misc.c'), '-lm', '-o', str(binary)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '_runs/kv1_1-verification')
    parser.add_argument('--skip-mutations', action='store_true',
                        help='Run fixed numerical/integration checks without the exemplar-specific mutation adapters')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    kernel = ROOT / 'flavors/kv1_1'
    report = {'checks': {}, 'versions': {name: importlib.metadata.version(name) for name in
              ['numpy', 'pandas', 'bmtk', 'neuron', 'h5py', 'scikit-learn']}}
    sources = json.loads((TEST / 'reference/sources.json').read_text())
    for source in sources['files']:
        assert sha256(ROOT / source['local_path']) == source['sha256'], source
    report['source_hashes_verified'] = True

    compile_probe(kernel, output / 'probe')
    actual = table([output / 'probe', 'rates'])
    expected = np.array([[v, *rates(v)] for v in range(-120, 61)])
    report['checks']['rates_max_abs_error'] = check(actual, expected, 1e-12)
    assert np.all((actual[:, 1] >= 0) & (actual[:, 1] <= 1)) and np.all(actual[:, 2] > 0)

    # Build and run the unchanged upstream MOD, without loading the C flavor.
    reference = output / 'reference'
    reference.mkdir()
    shutil.copyfile(TEST / 'reference/Kv11.mod', reference / 'Kv11.mod')
    nrnivmodl = shutil.which('nrnivmodl') or str(Path(sys.executable).parent / 'nrnivmodl')
    run_logged([nrnivmodl, '.'], reference, reference / 'build.log')
    run_logged([sys.executable, str(TEST / 'oracle_neuron.py'), '--mechanisms', str(reference),
                '--output', str(reference / 'result.json')], reference, reference / 'run.log')
    nrn = json.loads((reference / 'result.json').read_text())
    report['reference_version'] = nrn['version']
    report['checks']['mod_rates_max_abs_error'] = check(actual, nrn['rates'], 1e-12)
    dynamic_error, mod_error = 0, 0
    for protocol in nrn['protocols']:
        hold, voltage, dt = [protocol[k] for k in ['hold', 'voltage', 'dt']]
        ref = np.array(protocol['rows'])
        check(ref[:, 3], voltage, 1e-12)
        for area in [1e-5, 4e-5]:
            result = table([output / 'probe', hold, voltage, dt, area, 20])
            n = np.array([gate(t, hold, voltage) for t in result[:, 0]])
            j = np.array([current(x, voltage) for x in n])
            density_current = result[:, 3] / (1000 * area)  # uA -> mA/cm²
            dynamic_error = max(dynamic_error, check(result[:, 1], n), check(density_current, j),
                                check(result[:, 2], 0.004 * n**4 * area * 1000))
            mod_error = max(mod_error, check(result[:, 1], ref[:, 1]), check(density_current, ref[:, 2]))
    report['checks']['analytic_steps_max_abs_error'] = dynamic_error
    report['checks']['mod_steps_max_abs_error'] = mod_error
    print('PASS: independent equations, actual C update/current and original MOD', flush=True)

    run_logged([sys.executable, str(TEST / 'check_frontend.py')], ROOT, output / 'frontend.log')
    report['checks']['frontend'] = json.loads((output / 'frontend.log').read_text().splitlines()[-1])
    simulations = {}
    for name, flavor, gbar in [('vanilla', 'vanilla', 0), ('zero', 'kv1_1', 0), ('active', 'kv1_1', 0.004)]:
        directory = output / name
        run_logged([sys.executable, str(ROOT / 'examples/kv1_1/build.py'), '--serial', '--output',
                    str(directory), '--flavor', flavor, '--gbar', str(gbar)], ROOT, output / f'{name}-input.log')
        run = directory / 'neulite'
        run_logged(['make', '-j2'], run / 'kernel', directory / 'build.log')
        run_logged(['./kernel/nl', 'cell_population.csv', 'cell_cell_connection.csv'], run, directory / 'run.log')
        simulations[name] = {**voltage_summary(run / 'v.dat'),
                             'spikes': len((run / 's.dat').read_text().splitlines()),
                             'v_sha256': sha256(run / 'v.dat'), 's_sha256': sha256(run / 's.dat')}
        assert simulations[name]['samples'] == 20000
    assert simulations['vanilla']['v_sha256'] == simulations['zero']['v_sha256']
    assert simulations['vanilla']['s_sha256'] == simulations['zero']['s_sha256']
    active = np.loadtxt(output / 'active/neulite/v.dat')
    zero = np.loadtxt(output / 'zero/neulite/v.dat')
    voltage_difference = float(np.max(np.abs(active[:, 1] - zero[:, 1])))
    assert voltage_difference > 1e-6, 'Nonzero new channel had no effect'
    report['checks']['disabled_bitwise_regression'] = True
    report['checks']['active_max_voltage_difference_mV'] = voltage_difference
    report['simulations'] = simulations

    compile_parser(kernel, output / 'parser')
    active_run = output / 'active/neulite'
    area, total = table([output / 'parser', 'cell_population.csv'], active_run)
    report['checks']['parsed_gbar_mS_error'] = check(total, 0.004 * area * 1000, 1e-12)
    report['soma_area_cm2'] = float(area)
    report['parsed_gbar_mS'] = float(total)
    # Wrong-format input should fail at the parser boundary; avoid core dumps.
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with (output / 'old-csv.log').open('w') as log:
        old_input = subprocess.run([str(output / 'parser'), 'cell_population.csv'],
                                   cwd=output / 'vanilla/neulite', stdout=log, stderr=subprocess.STDOUT)
    assert old_input.returncode != 0, 'Vanilla 23-column input was silently accepted by the 24-column flavor'
    report['checks']['old_csv_rejected'] = True
    print('PASS: frontend rejection cases, generated-input integration and zero-channel regression', flush=True)

    # Three deliberate mistakes, confined to throwaway copies of the flavor.
    mutations = [
        ('power', 'ion.c',
         'gbar [ G_KV11 ] * ion [ N_KV11 ] * ion [ N_KV11 ] * ion [ N_KV11 ] * ion [ N_KV11 ]',
         'gbar [ G_KV11 ] * ion [ N_KV11 ] * ion [ N_KV11 ] * ion [ N_KV11 ]'),
        ('temperature', 'ion_func.h', 'pow ( 2.7, ( 34.0 - 22.0 ) / 10.0 )', '1.0'),
        ('unit', 'popl_func.h', 'f[i] * area * 1e3', 'f[i] * area'),
    ]
    detected = []
    for name, filename, before, after in ([] if args.skip_mutations else mutations):
        mutated = output / f'mutation-{name}'
        shutil.copytree(kernel, mutated, ignore=shutil.ignore_patterns('*.o', 'nl'))
        path = mutated / filename
        content = path.read_text()
        assert content.count(before) == 1, f'Update mutation adapter for {name}; do not silently skip'
        path.write_text(content.replace(before, after))
        if name == 'unit':
            compile_parser(mutated, mutated / 'parser')
            _, value = table([mutated / 'parser', 'cell_population.csv'], active_run)
            differs = not np.isclose(value, total, rtol=1e-12, atol=1e-12)
        else:
            compile_probe(mutated, mutated / 'probe')
            if name == 'temperature':
                values = table([mutated / 'probe', 'rates'])
                differs = not np.allclose(values, expected, rtol=1e-12, atol=1e-12)
            else:
                values = table([mutated / 'probe', -90, -40, 0.1, 1e-5, 20])
                predicted = np.array([current(gate(t, -90, -40), -40) for t in values[:, 0]])
                differs = not np.allclose(values[:, 3] / 0.01, predicted, rtol=1e-10, atol=1e-10)
        assert differs, f'Validation did not detect {name} mutation'
        detected.append(name)
    report['checks']['detected_mutations'] = detected
    report['source_sha256'] = {str(p.relative_to(ROOT)): sha256(p) for p in
        [ROOT / 'bionetlite/bionetlite.py', *sorted(kernel.glob('*.c')), *sorted(kernel.glob('*.h'))]}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['checks'], indent=2))
    print(f'Full report: {output / "report.json"}')


if __name__ == '__main__':
    main()
