// SPDX-License-Identifier: GPL-2.0-only
// Copyright (C) 2024,2025,2026 Neulite Core Team <neulite-core@numericalbrain.org>

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <assert.h>
#include "conn.h"
#include "synapse.h"
#include "config.h"

extern int strip_comment_destructive ( char * );
extern int remove_blank_destructive_for_csv ( char * );

static int compare_event_step ( const void *a, const void *b )
{
  const input_event_t *x = a, *y = b;
  return ( x -> step > y -> step ) - ( x -> step < y -> step );
}

// Calls deliver ( s, post neuron, event ) for every arrival of a spike in the spike CSV (time_ms,node_id).
static void for_each_input_event ( const conn_t *c, const int *src_ptr, const int *src_conn, const int n_src,
                                   const char *spike_filename, synapse_t *s, void ( *deliver ) ( synapse_t *, const int, const input_event_t ) )
{
  FILE *file = fopen ( spike_filename, "r" );
  if ( ! file ) { fprintf ( stderr, "Error: no such file %s\n", spike_filename ); exit ( 1 ); }
  char buf [ 1024 ];
  while ( fgets ( buf, 1024, file ) ) {
    if ( strip_comment_destructive ( buf ) == 0 ) { continue; }
    if ( remove_blank_destructive_for_csv ( buf ) == 0 ) { continue; }
    double time_ms;
    int node_id;
    const int nf = sscanf ( buf, "%lf,%d", &time_ms, &node_id );
    assert ( nf == 2 );
    assert ( time_ms >= 0.0 && node_id >= 0 );
    if ( node_id >= n_src ) { continue; } // source without input connections
    for ( int j = src_ptr [ node_id ]; j < src_ptr [ node_id + 1 ]; j++ ) {
      const int k = src_conn [ j ];
      // Same as NEURON's fixed step: an event arriving at te is delivered at the step starting nearest to te
      // (te <= t + dt/2). UNIT: ms
      const double te = time_ms + c -> input_delay [ k ];
      const input_event_t e = { .step = ( int ) ceil ( te / DT - 0.5 ), .slot = c -> input_id [ k ] };
      assert ( e.step >= 1 );
      deliver ( s, c -> input_post [ k ], e );
    }
  }
  fclose ( file );
}

static void count_event ( synapse_t *s, const int post, const input_event_t e ) { s -> event_ptr [ post + 1 ]++; }
static void store_event ( synapse_t *s, const int post, const input_event_t e ) { s -> event [ s -> event_next [ post ]++ ] = e; }

synapse_t *initialize_synapse ( conn_t *c, const char *spike_filename )
{
  synapse_t *s = calloc ( 1, sizeof ( synapse_t ) );

  s -> sum0   = calloc ( c -> n_conn, sizeof ( double ) );
  s -> delay  = calloc ( c -> n_conn, sizeof ( int ) );
  s -> event_ptr  = calloc ( c -> n_post + 1, sizeof ( int ) );
  s -> event_next = calloc ( c -> n_post, sizeof ( int ) );
  s -> step       = calloc ( c -> n_post, sizeof ( int ) );

  // Input connections grouped by source node id (CSR)
  int n_src = 0; for ( int k = 0; k < c -> n_input; k++ ) { if ( c -> input_pre [ k ] + 1 > n_src ) { n_src = c -> input_pre [ k ] + 1; } }
  int *src_ptr  = calloc ( n_src + 1, sizeof ( int ) );
  int *src_conn = calloc ( c -> n_input, sizeof ( int ) );
  for ( int k = 0; k < c -> n_input; k++ ) { src_ptr [ c -> input_pre [ k ] + 1 ]++; }
  for ( int i = 0; i < n_src; i++ ) { src_ptr [ i + 1 ] += src_ptr [ i ]; }
  {
    int *fill = calloc ( n_src, sizeof ( int ) );
    for ( int k = 0; k < c -> n_input; k++ ) { const int p = c -> input_pre [ k ]; src_conn [ src_ptr [ p ] + fill [ p ]++ ] = k; }
    free ( fill );
  }

  // Two passes over the spike file: count events per post neuron, then store them.
  for_each_input_event ( c, src_ptr, src_conn, n_src, spike_filename, s, count_event );
  for ( int i = 0; i < c -> n_post; i++ ) { s -> event_ptr [ i + 1 ] += s -> event_ptr [ i ]; }
  s -> event = calloc ( s -> event_ptr [ c -> n_post ], sizeof ( input_event_t ) );
  for ( int i = 0; i < c -> n_post; i++ ) { s -> event_next [ i ] = s -> event_ptr [ i ]; }
  for_each_input_event ( c, src_ptr, src_conn, n_src, spike_filename, s, store_event );
  for ( int i = 0; i < c -> n_post; i++ ) {
    assert ( s -> event_next [ i ] == s -> event_ptr [ i + 1 ] );
    qsort ( &s -> event [ s -> event_ptr [ i ] ], s -> event_ptr [ i + 1 ] - s -> event_ptr [ i ], sizeof ( input_event_t ), compare_event_step );
    s -> event_next [ i ] = s -> event_ptr [ i ];
  }
  free ( src_ptr );
  free ( src_conn );

  return s;
}

void finalize_synapse ( synapse_t *s )
{
  if ( s -> sum0  != NULL ) { free ( s -> sum0  ); }
  if ( s -> delay != NULL ) { free ( s -> delay ); }
  if ( s -> event      != NULL ) { free ( s -> event      ); }
  if ( s -> event_ptr  != NULL ) { free ( s -> event_ptr  ); }
  if ( s -> event_next != NULL ) { free ( s -> event_next ); }
  if ( s -> step       != NULL ) { free ( s -> step       ); }
  free ( s );
}

void update_synapse ( const int id, const conn_t * __restrict__ c, synapse_t * __restrict__ s )
{
  for ( int i = c -> ptr_post [ id ]; i < c -> ptr_post [ id + 1 ]; i++ ) {
    s -> sum0 [ i ] = s -> sum0 [ i ] * c -> decay [ i ] + (( s -> delay [ i ] == 1) ? 1 : 0) ;
    if( s -> delay [ i ] > 0 ) s -> delay [ i ]--;
  }

  // Input events taking effect in the next step: add them to both exponentials, as NET_RECEIVE of Exp2Syn.
  const int next_step = ++s -> step [ id ];
  for ( ; s -> event_next [ id ] < s -> event_ptr [ id + 1 ] && s -> event [ s -> event_next [ id ] ].step == next_step; s -> event_next [ id ]++ ) {
    const int slot = s -> event [ s -> event_next [ id ] ].slot;
    s -> sum0 [ slot     ] += 1.0;
    s -> sum0 [ slot + 1 ] += 1.0;
  }
}
