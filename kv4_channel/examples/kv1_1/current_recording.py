"""Install current observation in a disposable perisomatic kernel copy.

Keep the original expressions and summation order. This adapter deliberately
fails on unfamiliar source layouts; extend it explicitly for a new mechanism.
"""
from pathlib import Path
import re

CHANNELS = [('G_NAV', 'NaV'), ('G_NATS', 'NaTs'), ('G_NATA', 'NaTa'),
            ('G_NAP', 'Nap'), ('G_KV2', 'Kv2like'), ('G_KV3', 'Kv3_1'),
            ('G_KP', 'K_P'), ('G_KT', 'K_T'), ('G_KD', 'Kd'),
            ('G_IM', 'Im'), ('G_IMV2', 'Im_v2'), ('G_IH', 'Ih'),
            ('G_SK', 'SK'), ('G_CAHVA', 'Ca_HVA'), ('G_CALVA', 'Ca_LVA'),
            ('G_KV11', 'Kv1_1')]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Unsupported recording adapter layout: {old[:100]}')
    return text.replace(old, new)


def instrument(kernel):
    kernel = Path(kernel)
    header = (kernel / 'ion.h').read_text()
    enum = re.search(r'typedef enum \{([^}]+)\} ion_gbar_t;', header).group(1)
    if [s.strip() for s in enum.split(',')] != [k for k, _ in CHANNELS] + ['N_GBAR']:
        raise ValueError('Update the recording schema for this channel list')
    source = (kernel / 'ion.c').read_text()
    signature = source[source.index('void calc_lhs_and_rhs ('):].split('\n', 1)[0]
    internal = signature.replace('void calc_lhs_and_rhs', 'static void evaluate_ion')
    internal = internal[:-1] + ', double *currents )'
    source = replace_once(source, signature, internal)
    found = set()
    lines = []
    for line in source.splitlines(keepends=True):
        lines.append(line)
        if '_r += _c *' in line:
            mechanism = re.search(r'gbar\s*\[\s*(G_\w+)\s*\]', line).group(1)
            reversal = re.search(r'_r \+= _c \* (.*?);', line).group(1)
            if mechanism in found:
                raise ValueError(f'Duplicate current expression: {mechanism}')
            found.add(mechanism)
            lines.append(f'  if ( currents ) currents [ {mechanism} ] = _c * ( _v - {reversal} );\n')
        if re.search(r'const double I0 =', line):
            if 'G_NAP' not in line:
                raise ValueError('Unexpected nonlinear current')
            found.add('G_NAP')
            # Record the original nonlinear current, not its matrix slope.
            lines.append('    if ( currents ) currents [ G_NAP ] = I0;\n')
    if found != {k for k, _ in CHANNELS}:
        raise ValueError(f'Incomplete current observation: {found}')
    source = ''.join(lines)
    source += '\n' + signature + '''
{
  evaluate_ion ( u, n, i, pid, id, lhs, rhs, NULL );
}

void sample_ion_currents ( const population_t *u, const neuron_t *n,
    const ion_t *i, const int pid, const int id, double *currents )
{
  double lhs, rhs;
  evaluate_ion ( u, n, i, pid, id, &lhs, &rhs, currents );
}
'''
    (kernel / 'ion.c').write_text(source)
    header += '\nextern void sample_ion_currents ( const population_t *, const neuron_t *, const ion_t *, const int, const int, double * );\n'
    (kernel / 'ion.h').write_text(header)
    path = kernel / 'network.h'
    path.write_text(replace_once(path.read_text(), 'FILE *v_dat, *s_dat;',
                                 'FILE *v_dat, *s_dat, *current_dat;'))
    path = kernel / 'network.c'
    source = path.read_text()
    source = replace_once(source, '#include <stdint.h>', '#include <stdint.h>\n#include "record_currents.h"')
    source = replace_once(source, '  net -> spike = calloc',
                           '  open_current_recording ( net );\n\n  net -> spike = calloc')
    source = replace_once(source, '  free ( net -> spike  );',
                           '  if ( net -> current_dat ) { const int status = fclose ( net -> current_dat ); assert ( status == 0 ); }\n  free ( net -> spike  );')
    source = replace_once(source, '      solve ( i, net -> u,',
                           '      if ( net -> current_dat ) record_currents ( t_ms + DT * iter, net, i );\n      solve ( i, net -> u,')
    path.write_text(source)
    columns = ['time_ms', 'cell_id', 'v_mV', 'ca_mM', 'n_Kv1_1', 'area_cm2']
    columns += [f'I_{name}_uA' for _, name in CHANNELS]
    columns += ['I_leak_uA', 'I_inject_nA']
    (kernel / 'record_currents.h').write_text('''/* Generated observation support: pre-step instantaneous somatic currents. */
static void open_current_recording ( network_t *net )
{
  const char *enabled = getenv ( "NEULITE_RECORD_CURRENTS" );
  if ( !enabled || strcmp ( enabled, "1" ) != 0 ) return;
  net -> current_dat = fopen ( "currents.csv", "w" );
  assert ( net -> current_dat );
  fputs ( "''' + ','.join(columns) + '''\\n", net -> current_dat );
}

static void record_currents ( const double time, network_t *net, const int id )
{
  const int sid = net -> n -> sid [ id ], pid = net -> n -> pid [ id ];
  const int cid = net -> u -> cid [ pid ];
  const double v = net -> n -> v [ sid ];
  double currents [ N_GBAR ];
  sample_ion_currents ( net -> u, net -> n, net -> i, pid, id, currents );
  FILE *out = net -> current_dat;
  fprintf ( out, "%.17g,%d,%.17g,%.17g,%.17g,%.17g", time, id, v,
      net -> n -> ca [ sid ], net -> i -> gate [ N_GATEVAL * id + N_KV11 ], net -> u -> area [ cid ] );
  for ( int k = 0; k < N_GBAR; k++ ) fprintf ( out, ",%.17g", currents [ k ] );
  /* Conductance mS * voltage mV = uA; injected current retains its input unit nA. */
  const double leak = net -> u -> gl [ cid ] * ( v - net -> u -> vl [ cid ] );
  const int written = fprintf ( out, ",%.17g,%.17g\\n", leak, net -> n -> i_ext [ sid ] );
  assert ( written > 0 );
}
''')
