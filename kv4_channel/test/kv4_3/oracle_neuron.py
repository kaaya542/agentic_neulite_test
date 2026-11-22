#!/usr/bin/env python3
"""Evaluate the unchanged Kv43.mod in a separate NEURON process."""
import argparse
import json
import os
from pathlib import Path
import re

PROTOCOLS = [(-90, -40), (-40, -100), (-107, -107), (-100, 20)]
DURATION_MS = 50


def mod_parameters(path):
    """Full-precision PARAMETER values from the MOD text; nocmodl stores defaults with 6 digits."""
    block = re.search(r'PARAMETER\s*\{(.*?)\}', path.read_text(), re.S).group(1)
    values = dict(re.findall(r'^\s*(\w+)\s*=\s*([-+0-9.eE]+)', block, re.M))
    del values['celsius']  # NEURON uses the global celsius instead
    return {name: float(value) for name, value in values.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mechanisms', type=Path, required=True)
    parser.add_argument('--mod', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parameters = mod_parameters(args.mod)
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
    sec.insert('Kv4_3')
    seg = sec(0.5)
    mech = seg.Kv4_3
    seg.ek = -107
    defaults = {name: getattr(mech, name) for name in parameters}
    result = {'version': h.nrnversion(), 'mod_parameters': parameters, 'neuron_default_parameters': defaults}
    # exact: MOD text parameters without TABLE (the comparison target).
    # neuron_default: nocmodl-rounded defaults and TABLE (-100..30 mV), reported for information.
    for variant, usetable, values in [('exact', 0, parameters), ('neuron_default', 1, defaults)]:
        h.usetable_Kv4_3 = usetable
        for name, value in values.items():
            setattr(mech, name, value)
        curves = []
        h.finitialize(-90)
        for v in range(-120, 61):
            mech.rate(v)
            curves.append([v, mech.a_inf, mech.tau_a, mech.b_inf, mech.tau_b])
        protocols = []
        for hold, voltage in PROTOCOLS:
            for dt in [0.1, 0.05, 0.025]:
                h.dt = dt
                gkbar = values['gkbar']
                mech.gkbar = 0
                h.finitialize(hold)
                seg.v = voltage
                rows = []
                for it in range(round(DURATION_MS / dt) + 1):
                    # The gate kinetics do not depend on gkbar. With zero membrane
                    # current and no other mechanisms, V is held constant exactly.
                    mech.gkbar = gkbar
                    h.fcurrent()
                    rows.append([it * dt, mech.a, mech.b, mech.ik, seg.v])
                    mech.gkbar = 0
                    h.fadvance()
                protocols.append({'hold': hold, 'voltage': voltage, 'dt': dt, 'rows': rows})
        result[variant] = {'rates': curves, 'protocols': protocols}
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
