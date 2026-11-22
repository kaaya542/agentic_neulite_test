// SPDX-License-Identifier: GPL-2.0-only
// Copyright (C) 2024,2025,2026 Neulite Core Team <neulite-core@numericalbrain.org>

#pragma once

typedef struct {
  int step; // index of the time step in which the event takes effect
  int slot; // first of the two solver slots of the input connection
} input_event_t;

typedef struct {
  double *sum0;
  int *delay;
  // Input spike events, grouped by post neuron (CSR) and sorted by step within each neuron
  input_event_t *event;
  int *event_ptr;  // size == # neurons + 1
  int *event_next; // size == # neurons; next undelivered event
  int *step;       // size == # neurons; number of completed time steps
} synapse_t;

extern synapse_t *initialize_synapse ( conn_t *, const char * );
extern void update_synapse ( const int, const conn_t *, synapse_t * );
extern void finalize_synapse ( synapse_t * );
