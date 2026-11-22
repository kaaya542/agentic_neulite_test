/* Observe every channel and compare to isolated actual solver contributions. */
#include <assert.h>
#include <math.h>
#include "ion.c"

int main ( void )
{
  double worst = 0;
  for ( int sample = 0; sample < 6; sample++ ) {
    double v[] = { -100 + 60 * ( sample % 3 ) };
    double ca[] = { sample < 3 ? 1e-4 : 5e-3 };
    int zero[] = { 0 };
    neuron_t cell = { .n_neuron = 1, .sid = zero, .pid = zero, .v = v, .ca = ca };
    ion_t *ion = initialize_ion ( &cell );
    double gbar[N_GBAR], recorded[N_GBAR];
    for ( int k = 0; k < N_GBAR; k++ ) gbar[k] = ( k + 1 ) * 1e-5;
    population_t pop = { .gbar = gbar };
    sample_ion_currents ( &pop, &cell, ion, 0, 0, recorded );
    double total = 0, lhs, rhs;
    for ( int k = 0; k < N_GBAR; k++ ) {
      double isolated[N_GBAR] = { 0 };
      isolated[k] = gbar[k];
      population_t single = { .gbar = isolated };
      calc_lhs_and_rhs ( &single, &cell, ion, 0, 0, &lhs, &rhs );
      const double error = fabs ( recorded[k] - ( lhs * v[0] - rhs ) );
      assert ( isfinite ( recorded[k] ) && error < 1e-12 );
      if ( error > worst ) worst = error;
      total += recorded[k];
    }
    calc_lhs_and_rhs ( &pop, &cell, ion, 0, 0, &lhs, &rhs );
    assert ( fabs ( total - ( lhs * v[0] - rhs ) ) < 1e-12 );
    finalize_ion ( ion );
  }
  printf ( "%.17g\n", worst );
}
