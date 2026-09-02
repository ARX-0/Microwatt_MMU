# Microwatt_MMU — porting the Microwatt radix page-table walk into the A2O MMU

This repo holds both cores side by side so the MMU work can reference them together.
The goal: give the **A2O** core a Power ISA 3.1C **radix multi-level page-table walk**,
taken from **Microwatt**'s `mmu.vhdl`.

See **[PLAN.md](PLAN.md)** for the structural comparison of the two MMUs, the full SPR
present/absent/port analysis, and the `mmq_rtw.v` design.

## Repo structure

```
Microwatt_MMU/
├── PLAN.md                     the port plan: MMU comparison, SPR map, mmq_rtw.v design
├── tools/a2o-diff.sh           diff the editable A2O tree against pristine upstream
├── a2o/                        IBM A2O core (Verilog) — the port target
│   ├── rel/                        EDITABLE — all porting work happens here
│   │   ├── src/verilog/work/       the core; MMU is mmq*.v, header mmu_a2o.vh
│   │   ├── src/verilog/trilib/     tri_* latch/primitive library
│   │   ├── src/vhdl/               AXI wrappers, debug, scom
│   │   ├── build/                  Vivado IP + block-design TCL
│   │   ├── fpga/                   FPGA build scripts
│   │   └── doc/                    A2O_UM.pdf, PowerISA_V2.07B.pdf
│   ├── golden/                     PRISTINE upstream snapshot of rel/src/ — never edited
│   │   └── src/                        308 files, byte-identical to the release
│   ├── GOLDEN.md                   the golden-tree rule and how to diff
│   ├── CONTRIBUTING.md
│   └── LICENSE
├── microwatt/                  Microwatt core (VHDL) — the reference implementation
│   ├── mmu.vhdl                    the radix walker being ported
│   ├── common.vhdl                 SPR numbers, MMU/loadstore record types
│   ├── dcache.vhdl fetch1.vhdl     dTLB / iTLB + ERAT
│   ├── loadstore1.vhdl             MMU request path, DSISR/DAR
│   ├── ... 75 core .vhdl files, Makefile, microwatt.core
│   └── reference/mmu_test/         radix tree setup reference (mmu.c)
└── docs/                       analysis notes and diagrams
    ├── README_MMU.md               Book-E (ISA 2.07) TLB semantics study
    ├── Inteface_README.md          full mmq.v port list, grouped by interface
    ├── MMU_tlb_comparisons.md      ISA 2.07 vs 3.1C tlbie/RIC/PRS gap analysis
    ├── MMU_a2o_peripherals.drawio
    ├── MMU_vhdl_code_explaination.drawio
    ├── mmu.vhdl.snapshot           stale older copy of Microwatt mmu.vhdl, kept for diffing
    ├── images/                     FSM and address-shifter diagrams
    └── doc_copare/                 Power ISA and A2O reference PDFs
```

### Golden / editable split

`a2o/rel/` is the working tree; `a2o/golden/src/` is a byte-identical snapshot of it as
released upstream. `tools/a2o-diff.sh` answers *"what has changed since upstream"* no matter
how many commits have landed — the question that matters when a port touches a few places
inside several 4000-line Verilog files. See [a2o/GOLDEN.md](a2o/GOLDEN.md).

```bash
tools/a2o-diff.sh                  # summary of changed files
tools/a2o-diff.sh --stat           # per-file line counts
tools/a2o-diff.sh mmq_tlb_ctl.v    # unified diff of one file
tools/a2o-diff.sh --patch          # whole-tree unified diff
```

### Provenance

- **`a2o/`** — the OpenPOWER A2O core release. Upstream:
  <https://git.openpower.foundation/cores/a2o>
  (mirror: <https://github.com/OpenPOWERFoundation/a2o>).
  Compliant to Power ISA 2.07, Book III-E. Its MMU is a Book-E embedded MMU with a
  single-level E.PT hardware tablewalker — no radix.
- **`microwatt/`** — copy of <https://github.com/antonblanchard/microwatt> at commit
  `5e4c61f`, `.git` excluded, **pruned to CPU sources only**. Removed: `tests/`,
  `litedram/`, `liteeth/`, `litesdcard/`, `openocd/`, `micropython/`, `fpga/`,
  `hello_world/`, `rust_lib_demo/`, `uart16550/`, `scripts/`, `constraints/`, `media/`,
  `verilator/`, `esim/`, `sim-unisim/`. Implements the full ISA 3.0B/3.1 radix tree.
  This copy carries a local fork feature — an MMU walk-trace array on SPR 704/705 — which
  is **not** part of the A2O port.

## The MMU FSM in Microwatt

The numbers are code line references; the comments inside each state are the control
signals, and the edge labels give the transition conditions.

![The FSM of the Microwatt MMU](docs/images/FSM%20done.png)

![Address shifting and bit masking](docs/images/Screenshot%202025-07-30%20113719.png)

## Power ISA 3.1 reading references

Radix
- 6.7.10 Radix Tree Translation — p. 1198, through Radix on Radix — p. 1203

Hash
- Radix using Partitions — pp. 1184-1190
- Page table search — p. 1196

## A2O core notes (from the upstream release)

A2O optimizes single-thread performance, targeting 3+ GHz in 45 nm. It is a 27 FO4
implementation with an out-of-order pipeline supporting 1 or 2 threads, fully supporting
Power ISA 2.07 using Book III-E. It supports pluggable MMU and AXU logic macros, including
eliminating the MMU entirely and using ERAT-only mode for translation/protection.

See [a2o/rel/readme.md](a2o/rel/readme.md) for build details and
[a2o/rel/doc/A2O_UM.pdf](a2o/rel/doc/A2O_UM.pdf) for the user manual.

### Compliancy — why this project exists

> The A2O core is compliant to Power ISA 2.07 and will need updates to be compliant with
> either version 3.0c or 3.1. Changes will include:
> * **radix translation**
> * op updates, to eliminate noncompliant ones and add missing ones required for a given
>   compliancy level
> * various 'mode' and other changes to meet the open specification targeted compliancy
>   level (III-E needs to be changed to III)

This repo addresses the first item.

### Technology scaling

A comparison of the design in original technology and scaled to 7 nm (SMT2, fixed-point,
no MMU):

|      |Freq     |Pwr    |Freq Sort|Pwr Sort|Area     |Vdd    |
|-----:|---------|-------|---------|--------|---------|-------|
|45nm  |2.30 GHz |1.49 W |         |        |4.90 mm<sup>2</sup> |0.97 V |
| 7nm  |3.90 GHz |0.79 W |4.17 GHz |0.85 W  |0.31 mm<sup>2</sup> |1.1  V |
| 7nm  |3.75 GHz |0.63 W |4.03 GHz |0.67 W  |0.31 mm<sup>2</sup> |1.0  V |
| 7nm  |3.55 GHz |0.49 W |3.87 GHz |0.52 W  |0.31 mm<sup>2</sup> |0.9  V |
| 7nm  |3.07 GHz |0.32 W |3.60 GHz |0.38 W  |0.31 mm<sup>2</sup> |0.8  V |
| 7nm  |2.40 GHz |0.20 W |3.00 GHz |0.25 W  |0.31 mm<sup>2</sup> |0.7  V |

Estimates based on a semicustom design in representative foundry processes
(IBM 45 nm / Samsung 7 nm).

### Errata (upstream, unresolved)

1. A problem circumvented by setting `LSUCR0.DFWD=1` **and** limiting the store queue size
   (currently 4). It appears directly related to forwarding (L1 DC hit returns 0's instead
   of data), but the store queue size also had to be limited. Not debugged; could be a bad
   generation parm, a bad edit for Vivado compilation, or something else.
2. A2O was not released as a product. Its documentation was derived from A2I and is much
   less complete; errors vis-a-vis the RTL remain likely, especially in
   implementation-specific SPRs.
