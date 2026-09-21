# cocotb flow for the mmq-level radix tests (TLB miss -> radix reload -> TLB hit).
#
#   source ~/.venvs/cocotb/bin/activate
#   make                      # radix on, IND off  (BCFG_TLB0CFG_VALUE = 4'b1101)
#   make TLB0CFG=15           # radix on, IND on   (the upstream default IND setting)
#
# TLB0CFG[44:47] = {radix, pt, ind, gtwe}, set through the mmq boot-config parameter
# (work/mmq.v:366, work/mmq_spr.v:2218-2221).  Upstream default is 7 (radix off).

SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
TOPLEVEL       := mmq
MODULE         := test_tlbmiss
TLB0CFG        ?= 13

SRC := $(abspath ../..)

# Order matters: the sim-only copies here must be defined before -y searches trilib/.
VERILOG_SOURCES := $(abspath tri_event_mux1t.v) \
                   $(abspath RAMB16_S36_S36.v) \
                   $(abspath mmq_kw.v)

COMPILE_ARGS += -I$(SRC)/work -I$(SRC)/trilib -y$(SRC)/work -y$(SRC)/trilib
COMPILE_ARGS += -Pmmq.BCFG_TLB0CFG_VALUE=$(TLB0CFG)

# A changed TLB0CFG must force a rebuild; cocotb does not track -P values itself.
SIM_BUILD := sim_build_cfg$(TLB0CFG)
export TLB0CFG

include $(shell cocotb-config --makefiles)/Makefile.sim
