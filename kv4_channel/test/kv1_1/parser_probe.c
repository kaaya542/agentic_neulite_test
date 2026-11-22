/* Verify the real parser's density-to-total conductance conversion. */
#include <stdio.h>
#include "ion.h"
#include "popl.h"

int main ( int argc, char **argv )
{
  if ( argc != 2 ) { return 2; }
  population_t *p = initialize_population ( argv[1] );
  printf ( "%.17g,%.17g\n", p->area[p->cid[0]], p->gbar[G_KV11] );
  finalize_population ( p );
  return 0;
}
