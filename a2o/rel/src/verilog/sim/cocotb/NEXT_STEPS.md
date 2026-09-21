# mmq radix TLB test (cocotb): state and next steps

> **Superseded.** This is a snapshot from early on 2026-09-21. The live defect list,
> decisions and fix status are in `PROBLEMS.md` at the repo root.

Status as of 2026-09-21. The plan is at
`~/.claude/plans/in-the-a2o-rel-src-verilog-sim-run-rtw-t-jiggly-swan.md`.

## What exists (uncommitted)

| File | Purpose | State |
|---|---|---|
| `RAMB16_S36_S36.v` | Behavioural Xilinx block RAM, so the TLB and LRU arrays elaborate | Written. Only exercised through `mmq`, with no unit check of its own. |
| `tri_event_mux1t.v` | Sim-only copy of the trilib file with one attribute line removed. Icarus 11 rejects that attribute at `trilib/tri_event_mux1t.v:76`. | Written |
| `mmq_kw.v` | Reads `mmq.v` and `tri_128x16_1r1w_1.v` under Verilog-2005 keywords, because `do` is a port name there | Written |
| `Makefile` | `make` builds with radix on and IND off (`TLB0CFG=13`). `make TLB0CFG=15` builds with IND on. | Written, builds |
| `test_tlbmiss.py` | Harness plus M1–M6, M8, N1, N3 and the watchdog self-test | Written. Only M1 has been run. |

Environment: `source ~/.venvs/cocotb/bin/activate` (cocotb 1.9.2, Icarus 11).

## RTL bugs found (not fixed; test first, then fix, as you decided)

All three are in `work/mmq.v`, in both `a2o/rel` and `../a2o-radix-mmu` (`a2o_MMU`).

1. **The radix handoff is not connected.** The `mmq_tlb_cmp` instance (`mmq.v:3236`) has no
   `.mmucr1_rxe(...)` and no `.tlb_rtw_req_valid(...)`, although both ports exist
   (`mmq_tlb_cmp.v:264-265`).
   - Observed in simulation: `mmucr1_rxe` inside `mmq_tlb_cmp` is `z`, and `tlb_rtw_req_valid`
     is `z`.
   - `mmq_rtw` never receives a request.
   - `tlb_miss_d` goes X, and at cycle 64 `mm_xu_tlb_miss` read `x`.
   - **As connected today, the radix walker cannot run inside `mmq`.**
2. **`mmq_rtw` port wiring** (`mmq.v:3884`).
   - `tlb_ctl_tag2/3/4_flush` and `tlb_tag2` connect to undeclared names, which become
     implicit, undriven 1-bit wires.
   - `tlb_delayed_act` and `xu_mm_ccr2_notlb_b` connect to the whole bus instead of the bit
     slice. `mmq_htw` uses `[24:28]` and `[7]`.
3. **The request tag comes from the TLB way, not from the request (suspected, not yet run).**
   `tlb_rtw_req_tag` is connected to `tlb_htw_req_tag` (`mmq.v:3911`). That tag takes its
   PID, LPID, GS and AS from `tlb_tag4_way_or` (`mmq_tlb_cmp.v:5103-5110`), which is correct for
   the Book-E IND-hit case. On a radix *miss* the way holds no matching entry, so these fields
   are garbage, or 0 in an empty set.
   - An entry installed with PID=0 and LPID=0 matches every PID and every LPID
     (`mmq_tlb_matchline.v:563,566`).
   - Expected symptom: M4 and M5 give a false hit instead of a second walk.
   - The fix is an interface change: a separate `tlb_rtw_req_tag` output built from
     `tlb_tag4_q`. **That is your decision.**

Why the checks so far missed these:

- `tb_walk.v` instantiates `mmq_rtw` directly, so none of this wiring is in its path.
- The doc 04 §4.8 lint comparison suppresses warnings, and implicit nets and unconnected ports
  are warnings.

## Next steps, in order

1. **Before evidence: done.** The log is `before_fix.log`.
   - Result: `TESTS=10 PASS=2 FAIL=8`, 319 s.
   - All M tests and N3 fail by WATCHDOG at EVENT 1. `tlb_rtw_req_valid` reads `z` for all 20 000
     cycles, and `mm_xu_tlb_miss` reads `x` at cycle 64.
   - The two passes are not meaningful here:
     - N1 passes only because nothing can walk.
     - The self-test trips at EVENT 1, not at EVENT 2 as intended.
   - **`make` exits 0 even when tests fail** (cocotb 1.9), so the runner stage must read
     `results.xml`.
2. **Decide** (your call):
   - (a) Fix bugs 1 and 2: connect `.mmucr1_rxe(mmucr1_rxe)` and
     `.tlb_rtw_req_valid(tlb_rtw_req_valid)` on `mmq_tlb_cmp`, and copy `mmq_htw`'s `_sig`
     names and bit slices onto `mmq_rtw`.
   - (b) Choose how to fix bug 3.
   - (c) Choose whether the same fixes go to `../a2o-radix-mmu`, and when.
3. **After evidence.** Rerun `make`. Then debug the remaining harness assumptions, which have
   not been checked yet:
   - L2 reload beat and token timing
   - the ERAT reload `rel_val[4]` meaning
   - the `eratpos_rpn` extraction
   - the 64 KB size-code check in M8
4. **Add the missing rows:**
   - M9 `tlbilx` (`xu_mm_rf1_val`, `xu_mm_rf1_is_tlbilx`, `xu_mm_rf1_t`, `xu_mm_ex1_rs_is`,
     `xu_mm_ex2_eff_addr`; `mmq_inval.v:129-174`)
   - N2 RXE forced to 0 (try a cocotb `Force` on `mmucr1_rxe`; if Icarus refuses, record it as
     skipped)
   - N4 `make TLB0CFG=15 TESTCASE=test_m1_derat_cold`
5. **Runner.** Add a stage to `run_rtw_tests.sh`: `timeout 600 make -C sim/cocotb`. The stage
   fails on exit 124/137 and on any `<failure` in `results.xml`.
6. **Lint** the new `.v` files with `verible-verilog-lint`. `RAMB16_S36_S36.v` currently has two
   style notes (an untyped `parameter`, and `[0:511]` ordering).
7. **Docs.** Correct doc 04 §4.8 once the fixes land, and add the mmq-level test to doc 06.

## Still open from the plan

- M7 (thread mismatch) cannot be produced at `mmq` level because `THREADS=1`.
- M10 (IND mismatch) and parity-error misses are not covered.
- M3 does not guarantee that EA B falls in the same congruence class as EA A.
- The old stages in `run_rtw_tests.sh` still do not check pass/fail.
