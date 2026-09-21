// SIMULATION-ONLY wrapper for sim/cocotb.
//
// cocotb's Icarus flow compiles with -g2012, where `do` is a keyword.  A2O uses
// `do` as a port name (trilib/tri_128x16_1r1w_1.v:174, connected at work/mmq.v:4249),
// so those two files are read here under the Verilog-2005 keyword set.  The rest of
// the hierarchy still needs -g2012 (trilib/tri_event_mux1t.v has a multi-statement
// function).  No RTL is modified.
`begin_keywords "1364-2005"
`include "mmq.v"
`include "tri_128x16_1r1w_1.v"
`end_keywords
