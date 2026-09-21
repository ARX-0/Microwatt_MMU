// Behavioural simulation model of the Xilinx RAMB16_S36_S36 block RAM.
//
// FOR SIMULATION ONLY.  A2O's TLB and LRU arrays (trilib/tri_128x168_1w_0.v:222,
// trilib/tri_128x16_1r1w_1.v:294) instantiate this Xilinx unisim primitive, which
// is not in the source tree, so without a model the mmq hierarchy cannot elaborate.
//
// Modelled: 512 x (32 data + 4 parity) bits, two independent synchronous ports,
// Xilinx default WRITE_MODE = WRITE_FIRST (a write also drives DO with DI), and
// SSR as a synchronous output reset to 0 (default SRVAL).
// Not modelled: INIT_xx / SRVAL / WRITE_MODE parameters, and collision checking
// (both call sites pass SIM_COLLISION_CHECK("NONE")).  A same-edge read on one
// port of an address written on the other returns the OLD contents.
// The memory initialises to 0 so an unwritten TLB way reads V=0, never X.

`timescale 1 ns / 1 ns

module RAMB16_S36_S36(
   DOA, DOB, DOPA, DOPB,
   ADDRA, ADDRB, CLKA, CLKB,
   DIA, DIB, DIPA, DIPB,
   ENA, ENB, SSRA, SSRB, WEA, WEB
);
   parameter SIM_COLLISION_CHECK = "ALL";   // accepted for port compatibility, ignored

   output reg [31:0] DOA;
   output reg [31:0] DOB;
   output reg [3:0]  DOPA;
   output reg [3:0]  DOPB;
   input      [8:0]  ADDRA;
   input      [8:0]  ADDRB;
   input             CLKA;
   input             CLKB;
   input      [31:0] DIA;
   input      [31:0] DIB;
   input      [3:0]  DIPA;
   input      [3:0]  DIPB;
   input             ENA;
   input             ENB;
   input             SSRA;
   input             SSRB;
   input             WEA;
   input             WEB;

   reg [35:0] mem [0:511];

   integer i;
   initial begin
      for (i = 0; i < 512; i = i + 1) mem[i] = 36'b0;
      DOA = 32'b0; DOPA = 4'b0;
      DOB = 32'b0; DOPB = 4'b0;
   end

   always @(posedge CLKA)
      if (ENA) begin
         if (WEA) mem[ADDRA] <= {DIPA, DIA};
         if (SSRA)     begin DOA <= 32'b0; DOPA <= 4'b0; end
         else if (WEA) begin DOA <= DIA;   DOPA <= DIPA; end
         else          begin DOA <= mem[ADDRA][31:0]; DOPA <= mem[ADDRA][35:32]; end
      end

   always @(posedge CLKB)
      if (ENB) begin
         if (WEB) mem[ADDRB] <= {DIPB, DIB};
         if (SSRB)     begin DOB <= 32'b0; DOPB <= 4'b0; end
         else if (WEB) begin DOB <= DIB;   DOPB <= DIPB; end
         else          begin DOB <= mem[ADDRB][31:0]; DOPB <= mem[ADDRB][35:32]; end
      end

endmodule
