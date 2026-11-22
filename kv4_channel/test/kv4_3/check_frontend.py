#!/usr/bin/env python3
"""Exercise real CSV conversion on valid, invalid and mismatched flavor inputs for Kv4_3."""
import copy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.modules['mpi4py'] = None  # documented single-process BMTK fallback
sys.path.insert(0, str(ROOT / 'bionetlite'))
from bionetlite import NeuliteNetwork


def convert(model, flavor, output, v_init=-92.49911499023438):
    source = output / 'models'
    source.mkdir()
    (source / 'example_fit.json').write_text(json.dumps(model))
    # Isolate the converter for negative inputs; build.py exercises normal construction.
    network = object.__new__(NeuliteNetwork)
    network.kernel_flavor = flavor
    network._simulation_config = {'conditions': {'v_init': v_init}}
    network._v_init = network._resolve_initial_voltage()
    network.neulite_dir = str(output)
    network.convert_ion_channels(str(source), 'csv')
    return [[float(v) for v in line.split(',')] for line in
            (output / 'csv/example_fit.csv').read_text().splitlines()]


def main():
    original = json.loads((ROOT / 'examples/kv1_1/reference/472363762_fit.json').read_text())
    model = copy.deepcopy(original)
    model['genome'].append({'section': 'soma', 'mechanism': 'Kv4_3',
                            'name': 'gkbar_Kv4_3', 'value': 0.0032})
    cases = []
    for value in [-0.1, float('nan'), float('inf'), True, '0.0032']:
        bad = copy.deepcopy(model)
        bad['genome'][-1]['value'] = value
        cases.append((f'invalid density {value!r}', bad, 'kv4_3'))
    for field, value in [('section', 'dend'), ('mechanism', 'unknown'), ('name', 'gbar_Kv4_3')]:
        bad = copy.deepcopy(model)
        bad['genome'][-1][field] = value
        cases.append((f'invalid {field}', bad, 'kv4_3'))
    bad = copy.deepcopy(model)
    bad['genome'].append(copy.deepcopy(bad['genome'][-1]))
    cases.append(('duplicate', bad, 'kv4_3'))
    bad = copy.deepcopy(model)
    bad['conditions'][0]['celsius'] = 30
    cases.append(('inconsistent celsius', bad, 'kv4_3'))
    bad = copy.deepcopy(model)
    bad['conditions'][0]['erev'][0]['ek'] = -88
    cases.append(('inconsistent ek', bad, 'kv4_3'))
    cases.append(('Kv4_3 with vanilla', model, 'vanilla'))
    cases.append(('Kv4_3 with kv1_1', model, 'kv1_1'))
    kv11 = copy.deepcopy(original)
    kv11['genome'].append({'section': 'soma', 'mechanism': 'Kv1_1', 'name': 'gbar_Kv1_1', 'value': 0.004})
    cases.append(('Kv1_1 with kv4_3', kv11, 'kv4_3'))
    with tempfile.TemporaryDirectory(prefix='neulite-input-check-') as td:
        base = Path(td)
        for i, (name, data, flavor) in enumerate(cases):
            directory = base / str(i)
            directory.mkdir()
            try:
                convert(data, flavor, directory)
            except ValueError:
                pass
            else:
                raise AssertionError(f'{name} was silently accepted')
        for name, data, flavor, columns, value in [
            ('present', model, 'kv4_3', 24, 0.0032),
            ('absent', original, 'kv4_3', 24, 0),
            ('vanilla', original, 'vanilla', 23, None),
        ]:
            directory = base / name
            directory.mkdir()
            rows = convert(data, flavor, directory)
            assert len(rows) == 4 and all(len(row) == columns for row in rows)
            if value is not None:
                assert rows[0][-1] == value and all(row[-1] == 0 for row in rows[1:])
        directory = base / 'kv4_3-v-init'
        directory.mkdir()
        rows = convert(original, 'kv4_3', directory, v_init=-65.0)
        assert all(row[5] == -65.0 for row in rows)
        assert rows[0][4] != -65.0, 'V_INIT must be independent of e_pas'
    print(json.dumps({'rejected_invalid_cases': len(cases), 'valid_cases': 4}))


if __name__ == '__main__':
    main()
