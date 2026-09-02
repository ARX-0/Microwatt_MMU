# NEXT.md — resume here

Last session ended with **`mmq_rtw.v` written, linting clean, and passing its unit tests**.
The walker module is done; **integrating it into the surrounding files is not**.

Read [PLAN.md](PLAN.md) §4 (design), §5 (out-of-order constraints — the five P0 items are
mandatory) and §6 (verification) before touching anything.

## State of play

```bash
tools/a2o-diff.sh                        # what has changed vs pristine upstream
a2o/rel/src/verilog/sim/run_rtw_tests.sh # lint + both testbenches, ~5 seconds
```

Both should be green. Current diff vs upstream:

| File | State |
|---|---|
| `a2o/rel/src/verilog/work/mmq_rtw.v` | **NEW** — the radix walker, 1900 lines, done |
| `a2o/rel/src/verilog/work/mmu_a2o.vh` | modified — added the `radixpos_*` field defines |
| `a2o/rel/src/verilog/sim/` | **NEW** — `tb_math.v`, `tb_walk.v`, `run_rtw_tests.sh` |

Nothing is committed yet. Untracked: `a2o/GOLDEN.md`, `a2o/golden/`, `tools/`,
`a2o/rel/src/verilog/sim/`, `mmq_rtw.v`. Modified: `PLAN.md`, `README.md`, `mmu_a2o.vh`.

## What `mmq_rtw.v` already does

- Full Microwatt radix walk: PTCR → PATE1 → PRTE0 → up to 4 levels → leaf.
- Caches the partition entry and both quadrant roots with valid bits, dropped on
  `ptcr_wr`/`pid_wr` — a warm walk is 4 loads instead of 6.
- Two walk contexts, **statically bound to threads** (ctx N ↔ thread N ↔ core tag `0110N`),
  which is the structural form of the P2-10 per-thread reservation.
- P0-1 `killed` bit from `xu_ex5_flush`, tested at every level boundary **and on the way out
  of every wait state**.
- P0-2 R/C checked, never written back.
- P0-3 `ptereload` driven on **every** termination path (success / fault / killed / timeout)
  so the LSU EMQ entry is always freed.
- P0-4 reservation cleared on any matching invalidate, EPN deliberately not compared.
- P0-5 one load in flight per context, re-arbitrated per level.
- P1-7 per-slot watchdog, P1-8 bounded ECC retry then escalate, P2-11 guest-mode LRAT gate
  and 42-bit RA bounds check.

## TODO — integration (PLAN.md §4.7)

1. **`mmq.v`** — instantiate `mmq_rtw` in the `generate if (EXPAND_TLB_TYPE > 0)` block
   (opens `:2685`, `mmq_htw` is at `:3681`). Mux `htw_lsu_*` vs `rtw_lsu_*` and
   `ptereload_req_*` on `MMUCR1[RXE]`; route `an_ac_reld_*` (`:3745-3752`) to both.
   Wire `rtw_quiesce` into the `mm_xu_quiesce` AND-tree alongside `htw_quiesce`.
2. **`mmq_tlb_cmp.v`** — add the `tlb_rtw_req_valid` handoff beside `:5071-5089`, gated on
   `MMUCR1[RXE]` (and *not* on `tagpos_ind`, since radix has no indirect entry).
3. **`mmq_tlb_ctl.v`** — the ptereload path already exists and `mmq_rtw` emits a standard
   A2O `ptepos_*` PTE, so this may need **nothing**. Verify first; only add
   `TlbSeq_Radix*` states if a real gap shows up. Free encodings: `6'b100001`–`6'b111111`.
4. **`mmq_spr.v`** — `Spr_Addr_PTCR = 10'b0111010000` (464) near `:333-366`, add to the
   `spr_match_any_mmu` OR-tree (`:1198-1214`) or `done` never asserts, register update
   (`:1281-1420`), read mux (`:2053-2073`). Drive `ptcr`/`ptcr_wr`/`pid_wr` into `mmq_rtw`.
5. **`xu_spr_cspr.v`** — `ex2_ptcr_rdec`/`_wdec`/`_re`/`_we` in the `:1767-1842` /
   `:1885-2060` tables + hypervisor privilege qualification at `:2213-2650`.
6. **`mmq_inval.v`** — P0-5. The six deadlock detours (`:1015, 1030, 1100, 1130, 1321, 1332`)
   get exercised 4-5× harder; re-verify. Consider raising the token count (`:1598-1616`
   already supports 3) and `MMQ_ENTRIES` (`trilib/tri_a2o.vh:126`).
7. Route `rtw_pt_fault`/`badtree`/`segerror`/`perm_err`/`rc_err`/`lrat_miss`/`mchk` onto the
   existing `mm_xu_*` exception outputs (`mmq.v:219-236`) and the ESR bits.

## Known gaps / decisions already made

- **Leaf sizes are demoted** (2M→1M, 1G→16M). Not a shortcut: A2O's size code is
  log4(size/1KB) so 2M has no encoding, and `mmq_tlb_cmp.v:3486` keeps only 3 size bits so
  nothing above 16M survives the ptereload path. See PLAN.md §2.3 item 5.
- **Watchdog is untested in simulation** — it needs a 4096-cycle stall. Either shrink
  `` `RTW_WD_WIDTH `` for a test build or add a force-based test.
- **Two contexts, not four.** `mmq_htw` has 4 slots because a slot parks between its single
  load; a radix context is continuously active and there are only 2 core tags, so 2 is the
  real concurrency limit.
- `tlb_ctl_tag{2,3,4}_flush`, `tlb_tag2`, `tlb_tag5_except` are carried on the port list for
  mux parity with `mmq_htw` but deliberately unused — they are zero for erat/ptereload types,
  which is the P0-1 hazard itself.

## Two bugs the tests caught (do not reintroduce)

1. Barrel shifter: input is `addr(61:12)`, so EA63:62 must be masked off. Padding with 32
   zeros instead of 34 diverged from Microwatt for every shift ≥ 35.
2. Kill/reservation must gate the exit from **wait** states too, not just the request states,
   or a flush landing during the final `ReadWait` completes the walk anyway.
