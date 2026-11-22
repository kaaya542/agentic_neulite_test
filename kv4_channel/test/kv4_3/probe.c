/* Test adapter: call the actual flavor initialization, update and current code. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ion.c"

int main ( int argc, char **argv )
{
  if ( argc == 2 && strcmp ( argv[1], "rates" ) == 0 ) {
    for ( int v = -120; v <= 60; v++ ) {
      printf ( "%d,%.17g,%.17g,%.17g,%.17g\n", v, inf_a_Kv4_3 ( v ), tau_a_Kv4_3 ( v ), inf_b_Kv4_3 ( v ), tau_b_Kv4_3 ( v ) );
    }
    return 0;
  }
  if ( argc != 6 ) { fprintf ( stderr, "usage: probe hold voltage dt area duration\n" ); return 2; }
  double v[] = { atof ( argv[1] ) }, ca[] = { 1e-4 };
  const double step = atof ( argv[2] ), dt = atof ( argv[3] ), area = atof ( argv[4] );
  const int count = (int) llround ( atof ( argv[5] ) / dt );
  int zero[] = { 0 };
  neuron_t cell = { .n_neuron = 1, .sid = zero, .pid = zero, .v = v, .ca = ca };
  ion_t *ion = initialize_ion ( &cell );
  double gbar[N_GBAR] = { 0 };
  gbar[G_KV43] = 0.0032 * area * 1000; /* S/cm² * cm² -> mS */
  population_t pop = { .gbar = gbar };
  v[0] = step;
  for ( int it = 0; it <= count; it++ ) {
    double lhs = 0, rhs = 0;
    calc_lhs_and_rhs ( &pop, &cell, ion, 0, 0, &lhs, &rhs );
    printf ( "%.17g,%.17g,%.17g,%.17g,%.17g\n", it * dt, ion->gate[A_KV43], ion->gate[B_KV43], lhs, lhs * v[0] - rhs );
    update_ion ( 0, &cell, v, ion, dt );
  }
  finalize_ion ( ion );
  return 0;
}
