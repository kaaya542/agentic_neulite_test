#!/usr/bin/env python3
"""Verify the real Kv4_3 C flavor against independent equations, pinned MOD and a full input path."""
import argparse
import importlib.metadata
import io
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys

import numpy as np
from oracle import rates, implicit_gates, exact_gates, current, GBAR_S_CM2

ROOT = Path(__file__).resolve().parents[2]
TEST = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from run_baseline import run_logged, sha256, voltage_summary

DURATION_MS = 50
AREAS_CM2 = [1e-5, 4e-5]


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


def run_probe(probe, hold, voltage, dt, area):
    return table([probe, hold, voltage, dt, area, DURATION_MS])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    kernel = ROOT / 'flavors/kv4_3'
    report = {'checks': {}, 'information': {}, 'versions': {name: importlib.metadata.version(name) for name in
              ['numpy', 'pandas', 'bmtk', 'neuron', 'h5py', 'scikit-learn']}}
    sources = json.loads((TEST / 'reference/sources.json').read_text())
    for source in sources['files']:
        assert sha256(ROOT / source['local_path']) == source['sha256'], source
    report['source_hashes_verified'] = True

    probe = output / 'probe'
    compile_probe(kernel, probe)
    actual = table([probe, 'rates'])
    expected = np.array([[v, *rates(v)] for v in range(-120, 61)])
    report['checks']['rates_max_abs_error'] = check(actual, expected, 1e-12)
    assert np.all((actual[:, [1, 3]] >= 0) & (actual[:, [1, 3]] <= 1)) and np.all(actual[:, [2, 4]] > 0)

    # Build and run the unchanged upstream MOD, without loading the C flavor.
    reference = output / 'reference'
    reference.mkdir()
    shutil.copyfile(TEST / 'reference/Kv43.mod', reference / 'Kv43.mod')
    nrnivmodl = shutil.which('nrnivmodl') or str(Path(sys.executable).parent / 'nrnivmodl')
    run_logged([nrnivmodl, '.'], reference, reference / 'build.log')
    run_logged([sys.executable, str(TEST / 'oracle_neuron.py'), '--mechanisms', str(reference),
                '--mod', str(reference / 'Kv43.mod'), '--output', str(reference / 'result.json')],
               reference, reference / 'run.log')
    nrn = json.loads((reference / 'result.json').read_text())
    report['reference_version'] = nrn['version']
    exact = nrn['exact']
    report['checks']['mod_rates_max_abs_error'] = check(actual, exact['rates'], 1e-12)
    dynamic_error, mod_error = 0, 0
    discretization = {}
    for protocol in exact['protocols']:
        hold, voltage, dt = [protocol[k] for k in ['hold', 'voltage', 'dt']]
        ref = np.array(protocol['rows'])
        check(ref[:, 4], voltage, 1e-12)
        steps = np.arange(len(ref))
        a, b = np.array([implicit_gates(k, dt, hold, voltage) for k in steps]).T
        j = current(a, b, voltage)
        for area in AREAS_CM2:
            result = run_probe(probe, hold, voltage, dt, area)
            density_current = result[:, 4] / (1000 * area)  # uA -> mA/cm²
            dynamic_error = max(dynamic_error, check(result[:, 1], a), check(result[:, 2], b),
                                check(density_current, j),
                                check(result[:, 3], GBAR_S_CM2 * a**3 * b * area * 1000))
            mod_error = max(mod_error, check(result[:, 1], ref[:, 1]), check(result[:, 2], ref[:, 2]),
                            check(density_current, ref[:, 3]))
        continuous = np.array([exact_gates(t, hold, voltage) for t in ref[:, 0]])
        discretization[f'{hold}->{voltage} mV, dt={dt}'] = float(np.max(np.abs(np.c_[a, b] - continuous)))
    report['checks']['analytic_steps_max_abs_error'] = dynamic_error
    report['checks']['mod_steps_max_abs_error'] = mod_error
    report['information']['backward_euler_vs_continuous_gate_max_abs'] = discretization

    # NEURON's default run differs from the MOD text: nocmodl stores 6-digit defaults and
    # the TABLE clamps outside -100..30 mV. Report, do not gate on, this difference.
    default = nrn['neuron_default']
    default_rates = np.array(default['rates'])
    inside = (default_rates[:, 0] >= -100) & (default_rates[:, 0] <= 30)
    report['information']['neuron_default'] = {
        'rounded_parameters': {k: [nrn['mod_parameters'][k], v] for k, v in nrn['neuron_default_parameters'].items()
                               if v != nrn['mod_parameters'][k]},
        'rates_max_rel_diff_inside_table': float(np.max(np.abs(default_rates[inside, 1:] - actual[inside, 1:])
                                                        / np.abs(actual[inside, 1:]))),
        'rates_max_rel_diff_outside_table': float(np.max(np.abs(default_rates[~inside, 1:] - actual[~inside, 1:])
                                                         / np.abs(actual[~inside, 1:]))),
        'step_gate_max_abs_diff': {f"{p['hold']}->{p['voltage']} mV, dt={p['dt']}":
                                   float(np.max(np.abs(np.array(p['rows'])[:, 1:3] - np.array(q['rows'])[:, 1:3])))
                                   for p, q in zip(default['protocols'], exact['protocols'])}}
    print('PASS: independent equations, actual C update/current and original MOD', flush=True)

    run_logged([sys.executable, str(TEST / 'check_frontend.py')], ROOT, output / 'frontend.log')
    report['checks']['frontend'] = json.loads((output / 'frontend.log').read_text().splitlines()[-1])
    simulations = {}
    for name, flavor, gkbar in [('vanilla', 'vanilla', 0), ('zero', 'kv4_3', 0), ('active', 'kv4_3', GBAR_S_CM2)]:
        directory = output / name
        run_logged([sys.executable, str(ROOT / 'examples/kv4_3/build.py'), '--serial', '--output',
                    str(directory), '--flavor', flavor, '--gkbar', str(gkbar)], ROOT, output / f'{name}-input.log')
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
    report['checks']['parsed_gkbar_mS_error'] = check(total, GBAR_S_CM2 * area * 1000, 1e-12)
    report['soma_area_cm2'] = float(area)
    report['parsed_gkbar_mS'] = float(total)
    # Wrong-format input should fail at the parser boundary; avoid core dumps.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with (output / 'old-csv.log').open('w') as log:
        old_input = subprocess.run([str(output / 'parser'), 'cell_population.csv'],
                                   cwd=output / 'vanilla/neulite', stdout=log, stderr=subprocess.STDOUT)
    assert old_input.returncode != 0, 'Vanilla 23-column input was silently accepted by the 24-column flavor'
    report['checks']['old_csv_rejected'] = True
    print('PASS: frontend rejection cases, generated-input integration and zero-channel regression', flush=True)

    # Deliberate mistakes, confined to throwaway copies of the flavor.
    implicit_a = ('( ion [ A_KV43 ] + dt * inf_a_Kv4_3 ( _v ) / tau_a_Kv4_3 ( _v ) ) / ( 1.0 + dt / tau_a_Kv4_3 ( _v ) )')
    mutations = [
        ('power', 'ion.c', 'ion [ A_KV43 ] * ion [ A_KV43 ] * ion [ A_KV43 ] * ion [ B_KV43 ]',
         'ion [ A_KV43 ] * ion [ A_KV43 ] * ion [ B_KV43 ]'),
        ('temperature', 'ion_func.h', 'pow ( 3.0, ( 34.0 - 25.5 ) / 10.0 )', '1.0'),
        ('integration', 'ion.c', implicit_a,
         'inf_a_Kv4_3 ( _v ) + ( ion [ A_KV43 ] - inf_a_Kv4_3 ( _v ) ) * exp ( - dt / tau_a_Kv4_3 ( _v ) )'),
        ('unit', 'popl_func.h', 'f[i] * area * 1e3', 'f[i] * area'),
    ]
    detected = []
    for name, filename, before, after in mutations:
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
                differs = not np.allclose(table([mutated / 'probe', 'rates']), expected, rtol=1e-12, atol=1e-12)
            else:
                values = run_probe(mutated / 'probe', -90, -40, 0.1, 1e-5)
                a, b = np.array([implicit_gates(k, 0.1, -90, -40) for k in range(len(values))]).T
                differs = not np.allclose(values[:, 4] / 0.01, current(a, b, -40), rtol=1e-10, atol=1e-10)
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
