// Print every input event delivered by the spike_input flavor's update_synapse as
// "connection line index,step", using the real initialization from the input CSV files.
#include <stdio.h>
#include <stdlib.h>
#include "popl.h"
#include "neuron.h"
#include "conn.h"
#include "synapse.h"
#include "config.h"

int main ( int argc, char *argv [ ] )
{
  if ( argc < 5 ) { fprintf ( stderr, "usage: %s <population_csv> <connection_csv> <input_connection_csv> <input_spike_csv>\n", argv [ 0 ] ); exit ( 1 ); }
  population_t *u = initialize_population ( argv [ 1 ] );
  neuron_t *n = initialize_neuron ( u );
  conn_t *c = initialize_connection ( u, n, argv [ 2 ], argv [ 3 ] );
  synapse_t *s = initialize_synapse ( c, argv [ 4 ] );

  const int n_steps = ( int ) ( TSTOP * INV_DT );
  for ( int step = 0; step < n_steps; step++ ) {
    for ( int id = 0; id < n -> n_neuron; id++ ) {
      const int first = s -> event_next [ id ];
      update_synapse ( id, c, s );
      for ( int e = first; e < s -> event_next [ id ]; e++ ) {
        int line = -1;
        for ( int k = 0; k < c -> n_input; k++ ) { if ( c -> input_id [ k ] == s -> event [ e ].slot ) { line = k; } }
        printf ( "%d,%d\n", line, s -> step [ id ] );
      }
    }
  }
  finalize_synapse ( s );
  finalize_connection ( c );
  finalize_neuron ( n );
  finalize_population ( u );
  return 0;
}
