#!/usr/bin/env python3
"""Exercise real CSV conversion on valid, invalid and mismatched flavor inputs."""
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
    model['genome'].append({'section': 'soma', 'mechanism': 'Kv1_1',
                            'name': 'gbar_Kv1_1', 'value': 0.004})
    cases = []
    for value in [-0.1, float('nan'), float('inf'), True, '0.004']:
        bad = copy.deepcopy(model)
        bad['genome'][-1]['value'] = value
        cases.append((f'invalid density {value!r}', bad, 'kv1_1'))
    for field, value in [('section', 'dend'), ('mechanism', 'unknown'), ('name', 'gateCurrent_Kv1_1')]:
        bad = copy.deepcopy(model)
        bad['genome'][-1][field] = value
        cases.append((f'invalid {field}', bad, 'kv1_1'))
    bad = copy.deepcopy(model)
    bad['genome'].append(copy.deepcopy(bad['genome'][-1]))
    cases.append(('duplicate', bad, 'kv1_1'))
    for name, value in [('celsius', 22)]:
        bad = copy.deepcopy(model)
        bad['conditions'][0][name] = value
        cases.append((f'inconsistent {name}', bad, 'kv1_1'))
    bad = copy.deepcopy(model)
    bad['conditions'][0]['erev'][0]['ek'] = -88
    cases.append(('inconsistent ek', bad, 'kv1_1'))
    cases.append(('Kv1_1 with vanilla', model, 'vanilla'))
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
            ('present', model, 'kv1_1', 24, 0.004),
            ('absent', original, 'kv1_1', 24, 0),
            ('vanilla', original, 'vanilla', 23, None),
        ]:
            directory = base / name
            directory.mkdir()
            rows = convert(data, flavor, directory)
            assert len(rows) == 4 and all(len(row) == columns for row in rows)
            if value is not None:
                assert rows[0][-1] == value and all(row[-1] == 0 for row in rows[1:])
        for flavor in ['vanilla', 'kv1_1']:
            directory = base / f'{flavor}-v-init'
            directory.mkdir()
            rows = convert(original, flavor, directory, v_init=-65.0)
            assert all(row[5] == -65.0 for row in rows)
            assert rows[0][4] != -65.0, 'V_INIT must be independent of e_pas'
        for i, value in enumerate([float('nan'), float('inf'), True, '-65']):
            directory = base / f'invalid-v-init-{i}'
            directory.mkdir()
            try:
                convert(model, 'kv1_1', directory, v_init=value)
            except ValueError:
                pass
            else:
                raise AssertionError(f'Invalid V_INIT accepted: {value!r}')
    print(json.dumps({'rejected_invalid_cases': len(cases) + 4, 'valid_cases': 5}))


if __name__ == '__main__':
    main()
