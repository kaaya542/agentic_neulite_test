#!/usr/bin/env python3
"""Run BMTK Tutorial 2 with BioNet and Neulite from the same network and spike inputs.

Sections 1-3 follow docs/tutorial/tutorial_02_single_cell_syn.ipynb of BMTK. Only the
NetworkBuilder import differs, and the Poisson generator has a fixed seed.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
NEULITE_FILES = ['mcortex_population.csv', 'mcortex_mcortex_connection.csv',
                 'mthalamus_mcortex_connection.csv', 'mthalamus_spikes.csv']


def run_neulite(neulite_dir):
    """Build the spike_input flavor beside the generated config.h and run it."""
    kernel = neulite_dir / 'kernel'
    shutil.copytree(ROOT / 'flavors/spike_input', kernel, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.o', 'nl', '*.dat', 'config.h'))
    with (neulite_dir / 'build.log').open('w') as log:
        subprocess.run(['make', '-j2'], cwd=kernel, stdout=log, stderr=subprocess.STDOUT, check=True)
    with (neulite_dir / 'run.log').open('w') as log:
        subprocess.run(['./kernel/nl', *NEULITE_FILES], cwd=neulite_dir,
                       stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    # bionetlite reads base_dir='sim_ch02' from the running script, so keep its path valid after chdir.
    sys.argv[0] = os.path.abspath(sys.argv[0])
    os.chdir(output)
    # build_env_bionet compiles the MOD files with nrnivmodl of this Python environment.
    os.environ['PATH'] = os.path.dirname(sys.executable) + os.pathsep + os.environ['PATH']
    sys.path.insert(0, str(ROOT / 'bionetlite'))

    # 1: Building the network.
    from bionetlite import NeuliteBuilder as NetworkBuilder

    cortex = NetworkBuilder('mcortex')
    cortex.add_nodes(
        cell_name='Scnn1a_473845048',
        potental='exc',
        model_type='biophysical',
        model_template='ctdb:Biophys1.hoc',
        model_processing='aibs_perisomatic',
        dynamics_params='472363762_fit.json',
        morphology='Scnn1a_473845048_m.swc'
    )
    cortex.build()
    cortex.save_nodes(output_dir='sim_ch02/network')

    thalamus = NetworkBuilder('mthalamus')
    thalamus.add_nodes(
        N=10,
        pop_name='tON',
        potential='exc',
        model_type='virtual'
    )
    thalamus.add_edges(
        source={'pop_name': 'tON'}, target=cortex.nodes(),
        connection_rule=5,
        syn_weight=0.001,
        delay=2.0,
        weight_function=None,
        target_sections=['basal', 'apical'],
        distance_range=[0.0, 150.0],
        dynamics_params='AMPA_ExcToExc.json',
        model_template='exp2syn'
    )
    thalamus.build()
    thalamus.save_nodes(output_dir='sim_ch02/network')
    thalamus.save_edges(output_dir='sim_ch02/network')

    from bmtk.utils.reports.spike_trains import PoissonSpikeGenerator

    psg = PoissonSpikeGenerator(population='mthalamus', seed=0)
    psg.add(
        node_ids=range(10),  # Have 10 nodes to match mthalamus
        firing_rate=10.0,    # 10 Hz, we can also pass in a nonhomoegenous function/array
        times=(0.0, 3.0)    # Firing starts at 0 s up to 3 s
    )
    psg.to_sonata('sim_ch02/inputs/mthalamus_spikes.h5')

    # 2: Setting up BioNet environment
    from bmtk.utils.sim_setup import build_env_bionet

    build_env_bionet(
        base_dir='sim_ch02',
        config_file='config.json',
        network_dir='sim_ch02/network',
        tstop=3000.0, dt=0.1,
        report_vars=['v', 'cai'],    # Record membrane potential and calcium (default soma)
        spikes_inputs=[('mthalamus', # Name of population which spikes will be generated for
                        'sim_ch02/inputs/mthalamus_spikes.h5')],
        include_examples=True,       # Copies components files
        compile_mechanisms=True      # Will try to compile NEURON mechanisms
    )
    # build_env_bionet logs and ignores a failed compilation.
    if not list(Path('sim_ch02/components/mechanisms').glob('*/libnrnmech*')):
        raise RuntimeError('NEURON mechanisms were not compiled under sim_ch02/components/mechanisms')

    # 3. Running the simulation
    from bmtk.simulator import bionet

    conf = bionet.Config.from_json('sim_ch02/config.json')
    conf.build_env()
    net = bionet.BioNetwork.from_config(conf)
    sim = bionet.BioSimulator.from_config(conf, network=net)
    sim.run()

    # Neulite: the same spike file through bionetlite, then the spike_input flavor.
    from bionetlite import convert_spike_inputs

    convert_spike_inputs('sim_ch02/config.json', 'sim_ch02_nl')
    run_neulite(output / 'sim_ch02_nl')
    print(f'BioNet output: {output / "sim_ch02/output"}')
    print(f'Neulite output: {output / "sim_ch02_nl"} (v.dat, s.dat)')


if __name__ == '__main__':
    main()
