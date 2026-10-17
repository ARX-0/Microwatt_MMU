# PAUSE.md — resume here

Written 2026-10-03, end of session. Uncommitted and not meant to be committed; delete it
when the work resumes. For a fresh session (any model): read this file, then `PROBLEMS.md`.

## Where the work is

- **Branch:** `radix-integration-fixes`, cut from `main` at `7ad773a`. Nothing pushed. The
  PR repo `../a2o-radix-mmu` (branch `a2o_MMU`) has **not** been touched and still contains
  the same bugs that were fixed here.
- **Commits on the branch:**
  - `82edd6b` — RTL fixes: `PROBLEMS.md` items 1, 2, 3, 4, 5, 22, 23
  - `56701fa` — the mmq-level cocotb bench, `a2o/rel/src/verilog/sim/cocotb/`
  - `b1cd807` — `PROBLEMS.md`
- **Uncommitted and deliberately so:** `sim_build_cfg13/`, `results.xml`, `__pycache__/`,
  the three `*.log` files in `sim/cocotb/`, and the owner's own `CLAUDE.md`, `.claude/`,
  `.gitignore`.

## State: what works now

The radix walker could not run inside `mmq` at all before this branch. It now does:

- cocotb, mmq level: `TESTS=10 PASS=10` (`sim/cocotb/after_phaseB.log`). Each test proves
  miss → walk → TLB way written → the replayed request hits the TLB with the walked
  translation, with no second walk and no extra L2 load.
- `sim/run_rtw_tests.sh`: 400 bit-math vectors, 11 of 11 walk scenarios.
- Verilator error count 3, the same as `a2o/golden` (upstream), and `-Wall` free of
  IMPLICIT/PINMISSING/WIDTH on the radix-touched files.

## The rule that governs this work

`PROBLEMS.md` at the repo root is the defect list **and the decision log**. **No fix is
applied to an item until its `Your decision` field is filled in by the owner (Athi).** A new
defect gets added there with options and an **empty** decision field; it is not fixed. This
also exists as a memory note (`problems-md-decision-gate`).

Decisions already recorded carry "(chat, 2026-09-21)" and were transcribed from the owner's
answers at his request.

## Next, in order (plan approved 2026-10-03)

The approved plan is at
`~/.claude/plans/in-the-a2o-rel-src-verilog-sim-run-rtw-t-jiggly-swan.md`.

1. **Rewrite the root `README.md` on this branch** so it briefs the repo manager on this
   branch specifically: what was broken, what was fixed, the verification numbers, what is
   still open. Owner's decisions: replace `README.md` (not a new file), full detail with ISA
   v3.1C / A2O UM citations, keep the repo-structure section from the current README so
   nothing is lost. Audience and voice: CLAUDE.md §3.
2. **The ISA-semantics batch** in `mmq_rtw.v`, in this order, each with its `tb_walk.v`
   case before moving on: items **11, 13G, 9, 8, 10, 19**. The exact change and citation per
   item is in the plan file and in `PROBLEMS.md`.
3. Then: items 6 and 7 (per-thread root cache), 12 (ESR attribution), 20 (make the test and
   lint flow fail properly), 21 (docs).
4. Investigations, which produce evidence and then need a decision: items 15, 17, 26.

## Awaiting the owner's decision (do not touch)

- **13E** — no MSR[LE] on A2O, so radix pages are always big-endian (A2O UM §6.5.5).
- **26** — a killed walk's late reload may reach a reallocated EMQ slot.
- **27** — every V=0 walker reload (killed, timeout) is also reported as a page fault.
- **28** — Book-E TID=0 / TLPID=0 are wildcards, but ISA 3.x PID 0 and LPID 0 are ordinary
  IDs.

## Not MMU work, listed as migration gaps

MSR[LE] (13E), `tlbie` with RIC=2 for invalidating cached table entries (25), the ISA 3.x
interrupt model with DSISR/DAR/SRR1 (beyond item 12), and the LRAT second port (18,
deferred).

## How to run the tests

```bash
# unit benches: bit-math and the mmq_rtw walk bench
cd a2o/rel/src/verilog && bash sim/run_rtw_tests.sh

# mmq-level cocotb bench (needs the venv)
source ~/.venvs/cocotb/bin/activate          # cocotb 1.9.2
cd a2o/rel/src/verilog/sim/cocotb
timeout 900 make                              # radix on, IND off
timeout 900 make TLB0CFG=15                   # radix on, IND on (the upstream default)
```

`make` **exits 0 even when tests fail** (cocotb 1.9). Read the `TESTS=` line, or
`results.xml`. Gating that is item 20, still open.

Verilator check, the same command doc 04 §4.8 uses:

```bash
cd a2o/rel/src/verilog && verilator --lint-only --language 1364-2005 \
  -Wno-fatal -Wno-LITENDIAN -Wno-DECLFILENAME -Wno-TIMESCALEMOD \
  -Itrilib -Iwork work/mmq.v --top-module mmq 2>&1 | grep -c '^%Error'   # expect 3
```

## Environment facts that cost time to rediscover

- Python venv `~/.venvs/cocotb` with **cocotb 1.9.2**; Icarus Verilog **11**; Verilator
  4.038 is too old for cocotb, so Icarus is the simulator.
- Three simulation-only files in `sim/cocotb/` exist for Icarus, not for the design:
  - `RAMB16_S36_S36.v` — the TLB and LRU arrays instantiate this Xilinx primitive, which is
    not in the tree.
  - `mmq_kw.v` — reads `mmq.v` and `tri_128x16_1r1w_1.v` under Verilog-2005 keywords,
    because `do` is a port name there and cocotb compiles with `-g2012`.
  - `tri_event_mux1t.v` — a copy of the trilib file with one attribute removed; Icarus 11
    rejects it at `trilib/tri_event_mux1t.v:76`.
- `mmq` has roughly 130 inputs. The bench ties them all low by parsing the port list, then
  sets the functional-mode exceptions. An undriven input floats and poisons the simulation.
- Radix is enabled by a **parameter override**, not a force: `-Pmmq.BCFG_TLB0CFG_VALUE=13`
  (bits are `{radix, pt, ind, gtwe}`; upstream default 7 = radix off, IND on).
- The TLB is a block RAM: **reset does not clear it**. Each test uses its own EAs.
- Sampling rule: read DUT outputs after `await ReadOnly()` or on the falling edge. Reading
  on the rising edge returns stale values.

## Things that look like bugs and are not

- The ERAT reload sent during a walk has `wren = 0` (`mmq_tlb_cmp.v:4046`). It means "miss
  finished, retry", not "here is the entry". The instruction replays and then hits the TLB.
  This cost an afternoon (item 24).
- An ordinary load's LPID comes from **LPIDR**, not from the request's LPID field; the
  request field is only for external-PID ops (`mmq_tlb_req.v:895-899`).
- For a page larger than 4 KB the ERAT entry holds the page-base RPN plus a size code; the
  low bits come from the EA at access time.

## Working agreements

- `CLAUDE.md` §0: the owner makes every architectural and file-handling call. Ask, with
  options and trade-offs; recommend, do not decide.
- Use the project tooling for exploration: the HDL language server (Verible), the
  `researcher` agent in `.claude/agents/`, claude-mem skills. Not the generic Explore agent.
  (Memory note: `use-project-tooling-for-exploration`.)
- Cite ISA v3.1C or the A2O UM for architectural claims. There is no ISA 3.0 PDF in the
  repo; v3.1C keeps 3.0's radix rules.
