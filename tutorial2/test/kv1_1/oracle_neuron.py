#!/usr/bin/env python3
"""Evaluate the unchanged reference MOD in a separate NEURON process."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mechanisms', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    mechanisms = args.mechanisms.resolve()
    output = args.output.resolve()
    # NEURON auto-loads a compiled library in cwd at import. Keep cwd separate
    # so only the explicitly selected, pinned library is loaded once.
    runtime = mechanisms / 'runtime'
    runtime.mkdir(exist_ok=True)
    os.chdir(runtime)
    os.environ.pop('DISPLAY', None)
    os.environ['NEURON_MODULE_OPTIONS'] = '-nogui'
    from neuron import h, load_mechanisms
    load_mechanisms(str(mechanisms))
    h.load_file('stdrun.hoc')
    h.cvode_active(0)
    h.secondorder = 0
    h.celsius = 34
    sec = h.Section(name='reference')
    sec.L = 20
    sec.diam = 20
    sec.nseg = 1
    sec.insert('Kv1_1')
    seg = sec(0.5)
    mech = seg.Kv1_1
    mech.gateCurrent = 0
    seg.ek = -107
    curves = []
    h.finitialize(-90)
    for v in range(-120, 61):
        mech.rates(v)
        curves.append([v, mech.ninf, mech.taun])
    protocols = []
    for hold, voltage in [(-90, -40), (-40, -100), (-107, -107)]:
        for dt in [0.1, 0.05, 0.025]:
            h.dt = dt
            mech.gbar = 0
            h.finitialize(hold)
            seg.v = voltage
            rows = []
            for it in range(round(20 / dt) + 1):
                # The state kinetics do not depend on gbar. With zero membrane
                # current and no other mechanisms, V is held constant exactly.
                mech.gbar = 0.004
                h.fcurrent()
                rows.append([it * dt, mech.n, mech.ik, seg.v])
                mech.gbar = 0
                h.fadvance()
            protocols.append({'hold': hold, 'voltage': voltage, 'dt': dt, 'rows': rows})
    output.write_text(json.dumps({'version': h.nrnversion(), 'rates': curves,
                                       'protocols': protocols}, indent=2) + '\n')


if __name__ == '__main__':
    main()
