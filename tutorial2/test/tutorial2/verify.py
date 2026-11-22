#!/usr/bin/env python3
"""Verify the Tutorial 2 input path, input event delivery and vanilla regression of spike_input.

Run examples/tutorial2/run.py first and pass its output as --run-dir.
"""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import h5py
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TEST = Path(__file__).resolve().parent
FLAVOR = ROOT / 'flavors/spike_input'
DT = 0.1
INPUT_FILES = ['mcortex_population.csv', 'mcortex_mcortex_connection.csv', 'mthalamus_mcortex_connection.csv']


def bionet_synapses(config):
    """Child process: build the BioNet network and list each synapse actually created."""
    from bmtk.simulator import bionet
    conf = bionet.Config.from_json(config)
    conf.build_env()
    net = bionet.BioNetwork.from_config(conf)
    bionet.BioSimulator.from_config(conf, network=net)
    rows = []
    for cell in net.get_local_cells().values():
        sec_ids = {sec.hname(): i for i, sec in enumerate(cell.get_sections_id())}
        for conn in cell.connections():
            seg = conn._syn.get_segment()
            sec_x = conn._edge_prop.afferent_section_pos
            rows.append({'source': int(conn.source_node.node_id), 'sec_id': sec_ids[seg.sec.hname()],
                         'sec_x': sec_x, 'in_segment_of_sec_x': seg.x == seg.sec(sec_x).x,
                         'tau1': conn._syn.tau1, 'tau2': conn._syn.tau2, 'erev': conn._syn.e,
                         'weight': conn._connector.weight[0], 'delay': conn._connector.delay})
    print(json.dumps(rows))


def bionet_run(config):
    """Child process: run BioNet for one configuration."""
    from bmtk.simulator import bionet
    conf = bionet.Config.from_json(config)
    conf.build_env()
    net = bionet.BioNetwork.from_config(conf)
    bionet.BioSimulator.from_config(conf, network=net).run()


def case_config(sim, case, spike_file):
    """BioNet config of the tutorial run with its own spike input and output directory."""
    config = json.loads((sim / 'simulation_config.json').read_text())
    config['manifest']['$BASE_DIR'] = str(sim)
    config['manifest']['$OUTPUT_DIR'] = str(case / 'bionet')
    config['inputs']['mthalamus_spikes']['input_file'] = str(spike_file)
    config['network'] = str(sim / 'circuit_config.json')
    (case / 'config.json').write_text(json.dumps(config, indent=2))
    return case / 'config.json'


def child(mode, config, cwd):
    return subprocess.run([sys.executable, __file__, mode, str(config)], cwd=cwd, check=True,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout


def check_input_generation(run_dir, work):
    sim, nl = run_dir / 'sim_ch02', run_dir / 'sim_ch02_nl'
    with h5py.File(sim / 'network/mthalamus_mcortex_edges.h5') as f:
        pop = f['edges/mthalamus_to_mcortex']
        edges = pd.DataFrame({'source': pop['source_node_id'][()], 'target': pop['target_node_id'][()],
                              **{k: pop['0'][k][()] for k in ['sec_id', 'sec_x', 'bmtk_swc_id', 'neulite_post_cid']}})
    csv = pd.read_csv(nl / 'mthalamus_mcortex_connection.csv')
    synapse = json.loads((sim / 'components/synaptic_models/AMPA_ExcToExc.json').read_text())
    assert len(edges) == len(csv) == 50, (len(edges), len(csv))
    assert Counter(edges['source']) == Counter({i: 5 for i in range(10)})
    assert Counter(zip(edges['source'], edges['target'], edges['neulite_post_cid'])) == \
        Counter(zip(csv['#pre nid'], csv['post nid'], csv['post cid']))
    expected = {'weight': 0.001, 'tau_decay': synapse['tau2'], 'tau_rise': synapse['tau1'],
                'erev': synapse['erev'], 'delay': 2.0, 'e/i': 'e'}
    for column, value in expected.items():
        assert (csv[column] == value).all(), column

    # The Neulite compartment is the same SWC point as the BMTK target, and lies on a basal/apical dendrite.
    names = ['id', 'type', 'x', 'y', 'z', 'r', 'parent']
    original = pd.read_csv(sim / 'components/morphologies/Scnn1a_473845048_m.swc', sep=r'\s+', comment='#', names=names)
    converted = pd.read_csv(nl / 'data/Scnn1a_473845048_m.swc', sep=r'\s+', comment='#', names=names)
    a = original.set_index('id').loc[edges['bmtk_swc_id'], ['type', 'x', 'y', 'z']].to_numpy()
    b = converted.set_index('id').loc[edges['neulite_post_cid'], ['type', 'x', 'y', 'z']].to_numpy()
    np.testing.assert_allclose(a, b, atol=1e-5)
    assert set(a[:, 0]) <= {3, 4}
    soma = original[original['type'] == 1].iloc[0][['x', 'y', 'z']].to_numpy(float)
    soma_distance = np.linalg.norm(a[:, 1:].astype(float) - soma, axis=1)

    # BioNet places each synapse in the preselected section and segment.
    case = work / 'bionet_synapses'
    case.mkdir()
    config = case_config(sim, case, sim / 'inputs/mthalamus_spikes.h5')
    # BMTK and NEURON also print to stdout; the synapse list is the last line.
    created = pd.DataFrame(json.loads(child('--bionet-synapses', config, case).splitlines()[-1]))
    assert len(created) == 50
    assert Counter(zip(created['source'], created['sec_id'], created['sec_x'])) == \
        Counter(zip(edges['source'], edges['sec_id'], edges['sec_x']))
    assert created['in_segment_of_sec_x'].all()
    assert np.allclose(created[['tau1', 'tau2', 'erev', 'weight', 'delay']].to_numpy(),
                       [synapse['tau1'], synapse['tau2'], synapse['erev'], 0.001, 2.0])
    return {'synapses': 50, 'per_source': 5, 'post_cid_matches_bmtk_swc_point': True,
            'section_types': sorted(int(t) for t in set(a[:, 0])),
            'swc_point_distance_from_soma_um': [float(soma_distance.min()), float(soma_distance.max())],
            'bionet_sections_match_edges': True, 'parameters': expected}


def expected_events(conn_csv, spike_csv, n_steps):
    conns = pd.read_csv(conn_csv)
    spikes = np.loadtxt(spike_csv, delimiter=',', comments='#', ndmin=2)
    events = Counter()
    for k, (pre, delay) in enumerate(zip(conns['#pre nid'], conns['delay'])):
        for time_ms in spikes[spikes[:, 1] == pre, 0]:
            step = math.ceil((time_ms + delay) / DT - 0.5)  # NEURON fixed step: te <= t + dt/2
            if step <= n_steps:
                events[(k, step)] += 1
    return events


def check_event_delivery(run_dir, work):
    nl = run_dir / 'sim_ch02_nl'
    probe = work / 'event_probe'
    sources = [FLAVOR / f for f in ['popl.c', 'neuron.c', 'conn.c', 'synapse.c', 'ion.c', 'misc.c']]
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-I', str(nl / 'kernel'), str(TEST / 'event_probe.c'),
                    *map(str, sources), '-lm', '-o', str(probe)], check=True)
    n_steps = round(3000.0 / DT)
    # Tutorial spikes, plus repeated and close spikes on one source: none may be lost.
    synthetic = work / 'synthetic_spikes.csv'
    synthetic.write_text('#time_ms,node_id\n10.0,0\n10.0,0\n10.5,0\n11.04,0\n11.06,0\n2997.96,0\n2997.94,0\n')
    result = {}
    for name, spike_csv in [('tutorial', nl / 'mthalamus_spikes.csv'), ('synthetic', synthetic)]:
        out = subprocess.run([str(probe), *INPUT_FILES, str(spike_csv)], cwd=nl, check=True, text=True,
                             stdout=subprocess.PIPE).stdout
        delivered = Counter(tuple(map(int, line.split(','))) for line in out.split())
        expected = expected_events(nl / 'mthalamus_mcortex_connection.csv', spike_csv, n_steps)
        assert delivered == expected, (name, delivered - expected, expected - delivered)
        result[name] = {'delivered_events': sum(delivered.values()), 'multiple_events_in_one_step':
                        sum(1 for n in delivered.values() if n > 1)}
    return result


def run_neulite(nl, spike_csv, output):
    shutil.copytree(nl / 'data', output / 'data')
    for name in INPUT_FILES:
        shutil.copy(nl / name, output / name)
    subprocess.run([str(nl / 'kernel/nl'), *INPUT_FILES, str(spike_csv)], cwd=output, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return np.loadtxt(output / 'v.dat')[:, 1]


def check_single_spike_timing(run_dir, work):
    """EPSP onset of one input spike starts at the same step in BioNet and Neulite."""
    sim, nl = run_dir / 'sim_ch02', run_dir / 'sim_ch02_nl'
    from bmtk.utils.reports.spike_trains import SpikeTrains
    traces = {}
    for name, time_ms in [('a', 500.04), ('b', 500.06), ('late', 600.04)]:
        case = work / f'spike_{name}'
        case.mkdir()
        spikes = SpikeTrains()
        spikes.add_spike(node_id=0, timestamp=time_ms, population='mthalamus')
        spikes.to_sonata(str(case / 'spikes.h5'))
        (case / 'spikes.csv').write_text(f'#time_ms,node_id\n{time_ms!r},0\n')
        child('--bionet-run', case_config(sim, case, case / 'spikes.h5'), case)
        with h5py.File(case / 'bionet/v_report.h5') as f:
            v_bmtk = f['report/mcortex/data'][:, 0]
        (case / 'neulite').mkdir()
        traces[name] = (v_bmtk, run_neulite(nl, case / 'spikes.csv', case / 'neulite'))

    def onset_ms(simulator, name):
        """Time of the first sample that differs from the run without an input before 600 ms."""
        diff = np.abs(traces[name][simulator] - traces['late'][simulator])
        # BioNet sample k is at (k+1)*dt (initial state not saved); Neulite row k is at k*dt.
        return round((int(np.argmax(diff > 1e-9)) + (1 if simulator == 0 else 0)) * DT, 6)
    result = {}
    for name, time_ms in [('a', 500.04), ('b', 500.06)]:
        result[f'spike_{time_ms}ms'] = {'event_step': math.ceil((time_ms + 2.0) / DT - 0.5),
                                        'onset_bmtk_ms': onset_ms(0, name), 'onset_neulite_ms': onset_ms(1, name)}
        assert onset_ms(0, name) == onset_ms(1, name), result
    assert math.isclose(result['spike_500.06ms']['onset_bmtk_ms'], result['spike_500.04ms']['onset_bmtk_ms'] + DT)
    return result


def check_vanilla_regression(work):
    """Without input events, spike_input reproduces vanilla on the bundled single-cell input."""
    outputs = {}
    for name, source in [('vanilla', ROOT / 'kernel'), ('spike_input', FLAVOR)]:
        case = work / f'regression_{name}'
        shutil.copytree(source, case / 'kernel', ignore=shutil.ignore_patterns('*.o', 'nl', '*.dat'))
        shutil.copy(ROOT / 'kernel/config.h', case / 'kernel/config.h')
        shutil.copytree(ROOT / 'test/kernel-test/data', case / 'data')
        (case / 'p.csv').write_text('1,3682,Scnn1a,data/Scnn1a_473845048_m_c.swc,data/472363762.csv\n')
        (case / 'c.csv').write_text('# no synapses\n')
        (case / 'input_c.csv').write_text('# no input connections\n')
        (case / 'input_spikes.csv').write_text('#time_ms,node_id\n')
        subprocess.run(['make', '-j2'], cwd=case / 'kernel', check=True, stdout=subprocess.DEVNULL)
        args = ['p.csv', 'c.csv'] + (['input_c.csv', 'input_spikes.csv'] if name == 'spike_input' else [])
        subprocess.run(['./kernel/nl', *args], cwd=case, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        outputs[name] = [(case / f).read_bytes() for f in ['v.dat', 's.dat']]
    assert outputs['vanilla'] == outputs['spike_input']
    return {'v_dat_and_s_dat_identical': True, 'spikes': outputs['vanilla'][1].count(b'\n')}


def main():
    if len(sys.argv) == 3 and sys.argv[1] in ('--bionet-synapses', '--bionet-run'):
        (bionet_synapses if sys.argv[1] == '--bionet-synapses' else bionet_run)(sys.argv[2])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run_dir, work = args.run_dir.resolve(), args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    os.environ['PATH'] = os.path.dirname(sys.executable) + os.pathsep + os.environ['PATH']
    report = {
        'input_generation': check_input_generation(run_dir, work),
        'event_delivery': check_event_delivery(run_dir, work),
        'single_spike_timing': check_single_spike_timing(run_dir, work),
        'vanilla_regression': check_vanilla_regression(work),
    }
    (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
