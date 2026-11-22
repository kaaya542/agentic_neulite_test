#!/usr/bin/env python3
"""Generate a single-cell example through the real BMTK/bionetlite builder."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--flavor', choices=['vanilla', 'kv1_1'], default='kv1_1')
    parser.add_argument('--gbar', type=float, default=0.004, help='Kv1_1 density in S/cm2')
    parser.add_argument('--dt', type=float, default=0.1)
    parser.add_argument('--serial', action='store_true', help='Use BMTK without optional mpi4py')
    args = parser.parse_args()
    if args.flavor == 'vanilla' and args.gbar != 0:
        parser.error('vanilla requires --gbar 0')
    if args.dt not in (0.1, 0.05, 0.025):
        parser.error('This example supports dt = 0.1, 0.05, or 0.025 ms')
    if args.serial:
        # Use BMTK's own ImportError fallback (equivalent to mpi4py not installed).
        # No mock communicator or simulator behavior is introduced.
        sys.modules['mpi4py'] = None
    sys.path.insert(0, str(ROOT / 'bionetlite'))
    from bionetlite import NeuliteBuilder

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chdir(output)
    Path('models').mkdir()
    Path('neulite/data').mkdir(parents=True)
    morph = 'Scnn1a_473845048_m_c.swc'
    shutil.copyfile(ROOT / 'test/kernel-test/data' / morph, Path('neulite/data') / morph)
    source = ROOT / ('kernel' if args.flavor == 'vanilla' else 'flavors/kv1_1')
    shutil.copytree(source, 'neulite/kernel', ignore=shutil.ignore_patterns('*.o', 'nl', '*.dat'))
    model = json.loads((ROOT / 'examples/kv1_1/reference/472363762_fit.json').read_text())
    if args.flavor == 'kv1_1':
        model['genome'].append({'section': 'soma', 'mechanism': 'Kv1_1',
                                'name': 'gbar_Kv1_1', 'value': args.gbar})
    Path('models/472363762_fit.json').write_text(json.dumps(model, indent=2) + '\n')
    config = {
        'components': {'morphologies_dir': str(output / 'neulite/data'),
                       'biophysical_neuron_models_dir': str(output / 'models')},
        'run': {'dt': args.dt, 'tstop': 2000.0, 'spike_threshold': -15.0},
        'conditions': {'v_init': model['conditions'][0]['v_init']},
        'inputs': {'current': {'input_type': 'current_clamp', 'module': 'IClamp',
                              'amp': 0.12, 'delay': 500.0, 'duration': 1000.0}},
        'networks': {'nodes': [], 'edges': []},
    }
    Path('config.json').write_text(json.dumps(config, indent=2) + '\n')
    # The bundled morphology is already preprocessed; do not replace its axon again.
    net = NeuliteBuilder('cell', kernel_flavor=args.flavor, convert_morphologies=False)
    net.add_nodes(N=1, pop_name='Scnn1a', model_type='biophysical',
                  model_template='ctdb:Biophys1', model_processing='aibs_perisomatic',
                  morphology=morph, dynamics_params='472363762_fit.json')
    net.build()
    net.save_nodes(output_dir='network')
    Path('example.json').write_text(json.dumps({
        'flavor': args.flavor, 'gbar_S_cm2': args.gbar, 'dt_ms': args.dt,
        'temperature_C': 34.0, 'ek_mV': -107.0, 'mpi_disabled': args.serial,
        'morphology': 'Preprocessed kernel-test morphology, retained unchanged',
        'source_model': '472363762',
    }, indent=2) + '\n')
    print(f'Generated {output}/neulite; build with make -C kernel, then run:')
    print('./kernel/nl cell_population.csv cell_cell_connection.csv')


if __name__ == '__main__':
    main()
