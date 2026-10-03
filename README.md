# Branch `radix-integration-fixes` — making the radix walker work inside the A2O MMU

> This is the branch README. It describes **this branch**, cut from `main` at `7ad773a`.
> The repo-wide material is further down, unchanged. The defect list and decision log is
> [PROBLEMS.md](PROBLEMS.md).

## The problem this branch addresses

The radix tablewalker `mmq_rtw.v` was written and unit-tested against a direct model of
Microwatt's `mmu.vhdl`, and that unit bench passed: 400 random bit-math vectors and eleven
end-to-end walk scenarios. On that evidence the walker looked finished.

It had never been exercised **inside `mmq`**, the MMU top level. When it was, it did not run
at all, and then — once it ran — it could not install a translation. Seven defects stood
between "the walker is correct" and "the MMU translates". None of them were in the walker's
algorithm; all were in how it joins the existing Book-E machinery.

The gap was a verification gap. `sim/tb_walk.v` instantiates `mmq_rtw` **directly** and
drives its request port by hand, so no part of the `mmq.v` wiring is in its path. The lint
comparison described in [docs/MMU_a2o_new/04-integration.md](docs/MMU_a2o_new/04-integration.md)
§4.8 counts only `%Error` lines, and an undriven implicit net or a truncated port connection
is a Verilog **warning**. Both checks passed throughout.

## What was broken

Items 1–5 were found by reading the RTL; 22 and 23 by simulating it. All are now fixed, in
commit `82edd6b`.

| # | Defect | Where | Effect |
|---|---|---|---|
| 1 | The `mmq_tlb_cmp` instance had no `.mmucr1_rxe` and no `.tlb_rtw_req_valid` connection, though both ports exist (`mmq_tlb_cmp.v:264-265`) | `mmq.v:3236` | The walker was never asked to walk. Both nets read `z`; `tlb_miss_d`, gated by the floating enable, went X. |
| 2 | `.inv_seq_inprogress` and `.inv_all` were tied to `tlb_seq_snoop_inprogress`, a `reg` inside `mmq_tlb_ctl.v:640` that is not a port, so in `mmq.v` it was an undeclared, undriven net | `mmq.v:3925, 3930` | The walker could never see a `tlbivax`/`tlbilx`. Its P0-4 reservation was never cleared, so a walk could install a translation that software had just invalidated. |
| 3 | Four more ports (`tlb_ctl_tag2/3/4_flush`, `tlb_tag2`) connected to undeclared names instead of the `_sig` wires | `mmq.v:3913-3916` | No functional effect; the walker only sinks them. Same class of error as item 2. |
| 4 | `xu_mm_ccr2_notlb_b` and `tlb_delayed_act` connected to whole buses, silently truncated to the wrong bits; `mmucr2_act_override` took bit 0 rather than bit 4 | `mmq.v` `mmq_rtw` instance | Clock-enable and MMU-mode gating came from the wrong bits. `tlb_delayed_act` resolved to `[29:33]`, whose top bit is the LRU write enable. |
| 5 | The walker's request tag was `tlb_htw_req_tag`, which takes PID, LPID, GS, AS from the **matched TLB way** (`mmq_tlb_cmp.v:5103-5110`) and the new entry's thread mask from that way (`:5112-5113`) | `mmq.v:3911` | Correct for a Book-E indirect-entry *hit*; wrong for a radix *miss*, where no way matched. The walker indexed the wrong process table, chose the guest path on a garbage GS, and installed entries with a wrong PID, LPID and thread mask. A thread mask of `0000` matches no thread (`mmq_tlb_matchline.v:560`), so such an entry could never be hit. |
| 22 | The page size written into the PTE used the **TLB's** log₄ codes (4K = `0001`) | `mmq_rtw.v:840-843` | The PTE `PS` field is log₂(size/1 KB): 4K = `0010`, 64K = `0110`, 1M = `1010`, 16M = `1110` (**A2O UM §6.17.3**). The TLB forms its size as `0b0 \|\| PS[52:54]` (same section; `mmq_tlb_ctl.v:2597`), so `0001` became `0000`, an unsupported size, and every install was rejected as ineligible (`mmq_tlb_cmp.v:4403`). `tb_walk.v` expected the wrong value too, so the unit bench agreed with the bug. |
| 23 | The ptereload tag carried `wq = 00` | `mmq_rtw.v:631` | `mmq_tlb_ctl` writes a TLB way only when `wq == 2'b10` (`mmq_tlb_ctl.v:2983`). Book-E's own walker repurposes those two bits as a reservation flag, set at handoff and cleared if another `tlbwe`, ptereload or invalidate gets there first (`mmq_htw.v:785-793`). The radix walker never set it, so **no radix walk ever wrote the TLB**. The ERAT was still reloaded, so a first access would appear to work while every later access walked again. |

### The fixes

- **1, 3, 4:** connect the ports, using the same signals and bit slices `mmq_htw` uses.
- **2:** a new `mmq_tlb_ctl` output, `tlb_ctl_snoop_inprogress`, carrying the existing
  register. Any invalidation snoop now kills in-flight walks. This is the blunt option;
  a precise LPID/PID/GS/AS match from `mmq_inval` is recorded as the later refinement.
- **5:** a new `tlb_rtw_req_tag` output on `mmq_tlb_cmp`, built from the request
  (`tlb_tag4_q`) rather than from a TLB way, with `{atsel,esel}` carrying the requesting
  thread's mask, so the installed entry is private to the thread that missed.
- **22:** PTE `PS` codes in the walker, and the `tb_walk` expectation corrected.
- **23:** the walker's own reservation is returned in the tag's `wq` bits, exactly as
  Book-E does. A walk whose reservation was cleared still returns its reload, which frees
  the queue entry, but installs nothing.

## Verification

### New: an `mmq`-level test bench

`a2o/rel/src/verilog/sim/cocotb/` drives the **whole `mmq` hierarchy** — request queues,
TLB sequencer, compare logic, both walkers, the invalidation arbiter and the real TLB
arrays — under Icarus with cocotb. Each test asserts three events:

1. an ERAT miss reaches the TLB, misses, and is handed to the walker;
2. the walk returns a ptereload, a TLB way is written, and the ERAT is told to retry
   (the reload on that pass carries no entry: `wren = 0`, `mmq_tlb_cmp.v:4046`, and the
   load queue writes the ERAT only on `wren = 1`, `lq_derat.v:2473`);
3. the replayed request **hits the TLB** and returns the walked real page number, with no
   second walk and no further L2 load.

A failure appears as an assertion, as a watchdog expiry, or as the simulator being killed.
A self-test deliberately stalls the L2 to confirm a hang is reported as a failure rather
than a pass.

| Run | Result |
|---|---|
| Before the fixes (`before_fix.log`) | `TESTS=10 PASS=2 FAIL=8`. The walker never started: `tlb_rtw_req_valid` read `z` for 20 000 cycles in every test. Neither "pass" was meaningful — one asserts that nothing happens, and nothing could happen. |
| After the fixes (`after_phaseB.log`) | `TESTS=10 PASS=10` |

What the ten tests cover: cold miss on the D-ERAT and on the I-ERAT; a miss caused by a
different effective page, by a different PID, by a different LPID, and by a different
address space; a 64 KB page, where a second 4 KB sub-page then hits without walking; a
speculative miss, which must not leave the core; an invalid leaf, which must fault and
install nothing; and the self-test.

### Unchanged checks

- `sim/run_rtw_tests.sh`: 400 random bit-math vectors against a direct model of Microwatt's
  generators, and 11 of 11 walk scenarios.
- Verilator `--lint-only`, the command in doc 04 §4.8: **3 errors, the same as the pristine
  upstream tree** in `a2o/golden`. All three are pre-existing references to Xilinx `RAMB16`
  primitives absent from the source tree.
- Verilator `-Wall`, filtered to `IMPLICIT`, `PINMISSING` and `WIDTH` on the radix-touched
  files: **none remain**. Before the fixes there were 26 in the `mmq.v` instance region.
  (Thirteen `PINCONNECTEMPTY` notices remain, all deliberately unconnected debug outputs.)

### What this evidence does not cover

- **`mmq` only, not the core.** No full-core or boot test was run. The load queue, the
  completion unit and the ERATs are modelled by the bench, not instantiated.
- **One thread at that level.** `THREADS=1` in this configuration, so cross-thread effects
  can only be shown in the unit bench, not in the `mmq` bench.
- **No Book-E regression test.** Nothing proves that the Book-E path with radix disabled
  still behaves exactly as before. The lint comparison and the untouched `mmq_htw` are the
  only evidence, and they are weak evidence.
- **Invalidation is wired but not yet proven.** Item 2's fix has no functional test yet; a
  `tlbilx` case is queued.
- **Nothing is synthesised or timed.**
- **The logs are not committed.** The numbers above are reproduced by rerunning; see
  [PAUSE.md](PAUSE.md) for the commands.

## Corrections to earlier claims in the documentation

Two statements in the committed documentation are now wrong, and are queued for correction
(PROBLEMS.md item 21):

- Doc 04 §4.7 says `mmq_tlb_ctl.v` required **no modification at all**. It now has one
  added output port (item 2).
- Doc 04 §4.8 presents the equal lint error count as evidence that the integration did no
  harm. The count is equal, but it was equal while five integration defects were present,
  so it does not support that conclusion on its own.
- Doc 03 §3.6 lists the TLB size codes as the PTE encoding (item 22), and §3.5 states the
  R/C rule that item 10 changes.

## What is still open

[PROBLEMS.md](PROBLEMS.md) carries 28 items, each with its evidence, its basis in the A2O
User's Manual or Power ISA v3.1C, its relevance on an out-of-order core, the options, and
the owner's decision. Summary:

- **Fixed and committed:** 1, 2, 3, 4, 5, 22, 23.
- **Decided, queued:** 6 and 7 (the quadrant-0 root cache is shared between threads),
  8–13G (walk-result semantics against ISA v3.1C: the change bit required for loads, a
  read/write page not readable, the attribute field decoded as one bit, real addresses
  above 42 bits truncated, the process-table index ignoring two PID bits), 12 (exception
  reporting says "data" for instruction fetches), 19 (no permission check at walk time),
  20 (the test and lint flow does not fail on failures), 21 (the documentation above).
- **Withdrawn after re-analysis for an out-of-order core:** item 16 (a flush cannot come
  from an unrelated younger instruction, because flushes are raised at completion, in
  order — `iuq_cpl_ctrl.v:2138` — and a walk only serves the next-to-complete instruction,
  `lq_derat.v:4611-4632`), item 7 (reduced to item 6), item 24 (a test-bench error, not an
  RTL defect).
- **Awaiting a decision:** 13E, 26, 27, 28.
- **Migration gaps beyond the MMU:** no MSR[LE] on A2O, so radix pages are always
  big-endian (A2O UM §6.5.5, versus ISA v3.1C); no `tlbie` with RIC=2, so cached
  partition- and process-table entries cannot be invalidated by software (ISA v3.1C
  §6.9.3.3); the ISA 3.x interrupt model (DSISR/DAR/SRR1) versus Book-E's ESR; and the
  LRAT second port, which guest-mode walks need.

## Commits on this branch

| Commit | Contents |
|---|---|
| `82edd6b` | The RTL fixes above, in `mmq.v`, `mmq_rtw.v`, `mmq_tlb_cmp.v`, `mmq_tlb_ctl.v`, plus the corrected `tb_walk.v` expectation |
| `56701fa` | The `mmq`-level cocotb bench and its simulation-only support files |
| `b1cd807` | `PROBLEMS.md` |

---

# Microwatt_MMU — porting the Microwatt radix page-table walk into the A2O MMU

This repo holds both cores side by side so the MMU work can reference them together.
The goal: give the **A2O** core a Power ISA 3.1C **radix multi-level page-table walk**,
taken from **Microwatt**'s `mmu.vhdl`.

**Start here: [docs/MMU_a2o_new/](docs/MMU_a2o_new/00-README.md)** — a seven-document set
covering the radix walker: background, the state machine, the datapath, integration,
out-of-order safety, and verification. Self-contained, with an executive summary.

See **[PLAN.md](PLAN.md)** for the working plan (SPR analysis, hazard analysis, remaining
work) and **[NEXT.md](NEXT.md)** for the resume-here notes.

## Repo structure

```
Microwatt_MMU/
├── PROBLEMS.md                 defect list and decision log for the radix work
├── PLAN.md                     the port plan: MMU comparison, SPR map, mmq_rtw.v design
├── tools/a2o-diff.sh           diff the editable A2O tree against pristine upstream
├── a2o/                        IBM A2O core (Verilog) — the port target
│   ├── rel/                        EDITABLE — all porting work happens here
│   │   ├── src/verilog/work/       the core; MMU is mmq*.v, header mmu_a2o.vh
│   │   ├── src/verilog/trilib/     tri_* latch/primitive library
│   │   ├── src/verilog/sim/        tb_math.v, tb_walk.v, run_rtw_tests.sh
│   │   ├── src/verilog/sim/cocotb/ mmq-level radix bench (this branch)
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
    ├── MMU_a2o_new/                **the radix walker documentation set (start here)**
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
