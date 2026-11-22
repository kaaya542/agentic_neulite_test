// SPDX-License-Identifier: GPL-2.0-only
// Copyright (C) 2024,2025,2026 Neulite Core Team <neulite-core@numericalbrain.org>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include "conn.h"
#include "neuron.h"
#include "config.h"

extern int strip_comment_destructive ( char * );
extern int remove_blank_destructive_for_csv ( char * );
extern int get_lines ( const char * );

typedef struct {
  int pre, post_i, post_c;
  double weight, decay, rise, erev, delay;
} conn_line_t;

static FILE *open_csv ( const char *filename )
{
  FILE *file = fopen ( filename, "r" );
  if ( ! file ) { fprintf ( stderr, "Error: no such file %s\n", filename ); exit ( 1 ); }
  return file;
}

// Returns 0 at the end of file. Comment and blank lines are skipped.
static int read_conn_line ( FILE *file, conn_line_t *l )
{
  char buf [ 1024 ];
  while ( fgets ( buf, 1024, file ) ) {
    if ( strip_comment_destructive ( buf ) == 0 ) { continue; }
    if ( remove_blank_destructive_for_csv ( buf ) == 0 ) { continue; }
    char c_type;
    const int nf = sscanf ( buf, "%d,%d,%d,%lf,%lf,%lf,%lf,%lf,%c", &l -> pre, &l -> post_i, &l -> post_c, &l -> weight, &l -> decay, &l -> rise, &l -> erev, &l -> delay, &c_type );
    assert ( nf == 9 );
    return 1;
  }
  return 0;
}

// Fills the decay and rise solver slots of one connection and returns the first slot.
static int set_solver_pair ( conn_t *c, const population_t *u, const neuron_t *n, int *local_idx, const conn_line_t *l )
{
  assert ( 0 <= l -> post_i && l -> post_i < n -> n_neuron );
  assert ( l -> post_c < u -> n_comp [ n -> pid [ l -> post_i ] ] );
  assert ( l -> delay >= 1.0 );

  const double tau_prime = l -> decay * l -> rise / ( l -> decay - l -> rise );
  const double tau_diff  = l -> rise / l -> decay;
  const double norm_coef = 1.0 / ( pow ( tau_diff, ( tau_prime / l -> decay ) ) - pow ( tau_diff, ( tau_prime / l -> rise ) ) );
  const int solver_id1 = c -> ptr_post [ l -> post_i ] + local_idx [ l -> post_i ];
  c -> post_c [ solver_id1 ] = l -> post_c;
  c -> weight [ solver_id1 ] = norm_coef * l -> weight;
  c -> erev   [ solver_id1 ] = l -> erev;
  c -> decay  [ solver_id1 ] = exp ( - DT / l -> decay );
  const int solver_id2 = solver_id1 + 1;
  c -> post_c [ solver_id2 ] = l -> post_c;
  c -> weight [ solver_id2 ] = - norm_coef * l -> weight;
  c -> erev   [ solver_id2 ] = l -> erev;
  c -> decay  [ solver_id2 ] = exp ( - DT / l -> rise );
  local_idx [ l -> post_i ] += 2;
  return solver_id1;
}

conn_t *initialize_connection ( const population_t *u, const neuron_t *n, const char *filename, const char *input_filename )
{
  conn_t *c = calloc (1, sizeof ( conn_t ) );

  if ( n -> n_neuron == 0 ) { c -> n_conn = 0; return c; }

  int *pre_ary  = calloc ( n -> n_neuron, sizeof ( int ) );
  int *post_ary = calloc ( n -> n_neuron, sizeof ( int ) );
  int n_conn = 0, n_pre = 0, n_input = 0;
  {
    conn_line_t l;
    FILE *file = open_csv ( filename );
    while ( read_conn_line ( file, &l ) ) {
      n_conn += 2;
      pre_ary  [ l.pre    ] += 2;
      post_ary [ l.post_i ] += 2;
    }
    fclose ( file );
    for ( int i = 0; i < n -> n_neuron; i++ ) { if ( pre_ary [ i ] > 0 ) { n_pre++; } }

    // Input connections share the per-post solver slots; their sources are not Neulite neurons.
    file = open_csv ( input_filename );
    while ( read_conn_line ( file, &l ) ) {
      assert ( l.pre >= 0 );
      assert ( 0 <= l.post_i && l.post_i < n -> n_neuron );
      n_conn += 2;
      post_ary [ l.post_i ] += 2;
      n_input++;
    }
    fclose ( file );
  }

  c -> n_conn = n_conn;
  c -> n_pre = n_pre;
  c -> n_post = n -> n_neuron; // Note: RHS is X n_post, O n -> n_neuron
  c -> n_input = n_input;

  c -> pre_table  = calloc ( c -> n_pre,  sizeof ( int ) ); // list of ids of presynaptic neurons
  {
    int j = 0;
    for ( int i = 0; i < n -> n_neuron; i++ ) {
      if ( pre_ary [ i ] > 0 ) { c -> pre_table [ j ] = i; j++; }
    }
    assert ( j == c -> n_pre );
  }
  c -> ptr_pre = calloc ( c -> n_pre + 1, sizeof ( int ) );
  {
    int j = 0;
    c -> ptr_pre [ 0 ] = 0;
    for ( int i = 0; i < n -> n_neuron; i++ ) {
      if ( pre_ary [ i ] > 0 ) { c -> ptr_pre [ j + 1 ] = c -> ptr_pre [ j ] + pre_ary [ i ]; j++; }
    }
    assert ( j == c -> n_pre );
  }
  c -> ptr_post = calloc ( c -> n_post + 1, sizeof ( int ) );
  {
    c -> ptr_post [ 0 ] = 0;
    for ( int i = 0; i < c -> n_post; i++ ) {
      c -> ptr_post [ i + 1 ] = c -> ptr_post [ i ] + post_ary [ i ];
    }
  }
  free (pre_ary);
  free (post_ary);

  c -> post_c = calloc ( c -> n_conn, sizeof ( int ) );
  c -> weight = calloc ( c -> n_conn, sizeof ( double ) );
  c -> erev   = calloc ( c -> n_conn, sizeof ( double ) );
  c -> decay  = calloc ( c -> n_conn, sizeof ( double ) );
  c -> delay = calloc ( c -> n_conn, sizeof ( int ) );
  c -> id    = calloc ( c -> n_conn, sizeof ( int ) );
  c -> input_pre   = calloc ( c -> n_input, sizeof ( int ) );
  c -> input_post  = calloc ( c -> n_input, sizeof ( int ) );
  c -> input_id    = calloc ( c -> n_input, sizeof ( int ) );
  c -> input_delay = calloc ( c -> n_input, sizeof ( double ) );

  {
    int *local_idx = calloc ( c -> n_post, sizeof ( int ) );
    conn_line_t l;
    FILE *file = open_csv ( filename );
    int idx = 0;
    while ( read_conn_line ( file, &l ) ) {
      const int solver_id1 = set_solver_pair ( c, u, n, local_idx, &l );
      c -> delay [ idx ] = (int)(l.delay / DT);
      c -> id    [ idx ] = solver_id1;
      idx++;
      c -> delay [ idx ] = (int)(l.delay / DT);
      c -> id    [ idx ] = solver_id1 + 1;
      idx++;
    }
    fclose ( file );

    file = open_csv ( input_filename );
    int k = 0;
    while ( read_conn_line ( file, &l ) ) {
      c -> input_pre   [ k ] = l.pre;
      c -> input_post  [ k ] = l.post_i;
      c -> input_id    [ k ] = set_solver_pair ( c, u, n, local_idx, &l );
      c -> input_delay [ k ] = l.delay;
      k++;
    }
    fclose ( file );
    assert ( k == c -> n_input );
    free ( local_idx );
  }

  return c;
}

void finalize_connection ( conn_t *c )
{
  if ( c -> pre_table != NULL ) { free ( c -> pre_table ); }
  if ( c -> ptr_pre   != NULL ) { free ( c -> ptr_pre   ); }
  if ( c -> ptr_post  != NULL ) { free ( c -> ptr_post  ); }
  if ( c -> post_c != NULL ) { free ( c -> post_c ); }
  if ( c -> weight != NULL ) { free ( c -> weight ); }
  if ( c -> erev   != NULL ) { free ( c -> erev   ); }
  if ( c -> decay  != NULL ) { free ( c -> decay  ); }
  if ( c -> delay != NULL ) { free ( c -> delay ); }
  if ( c -> id    != NULL ) { free ( c -> id    ); }
  if ( c -> input_pre   != NULL ) { free ( c -> input_pre   ); }
  if ( c -> input_post  != NULL ) { free ( c -> input_post  ); }
  if ( c -> input_id    != NULL ) { free ( c -> input_id    ); }
  if ( c -> input_delay != NULL ) { free ( c -> input_delay ); }
  free ( c );
}
