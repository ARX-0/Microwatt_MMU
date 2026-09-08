# NEXT.md — resume here

**Integration and exception routing are done.** `mmq_rtw.v` is written, instantiated, muxed,
and its faults reach the architected `mm_xu_*` outputs. The whole `mmq` hierarchy lints with
the *same* error count as pristine upstream (3, all pre-existing missing-Xilinx-primitive
errors). 11 walk scenarios + the bit-math bench pass.

What is left is **whole-core simulation** and the LRAT second port — not wiring.

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
| `work/mmq_rtw.v` | **NEW** — the radix walker, ~1950 lines |
| `work/mmu_a2o.vh` | `radixpos_*` field defines |
| `work/mmq.v` | instantiates `mmq_rtw`; muxes LSU + ptereload on the enable; ANDs quiesce |
| `work/mmq_tlb_cmp.v` | `tlb_rtw_req_valid` handoff; suppresses the TLB-miss exception when radix is on |
| `work/mmq_spr.v` | PTCR (464); `ptcr_wr`/`pid_wr` strobes; `tlb0cfg_radix` boot bit |
| `work/xu_spr_cspr.v` | PTCR decode + slowspr/illegal/hypervisor OR-trees |
| `work/mmq.v` | also merges radix faults onto `mm_xu_pt_fault` / `_lrat_miss` / `_tlb_par_err` / ESR |
| `sim/` | **NEW** — `tb_math.v`, `tb_walk.v`, `run_rtw_tests.sh` |

All committed; working tree clean.

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

## Design decisions made during integration

- **Radix enable is `TLB0CFG[44]`**, a boot-config latch, *not* an MMUCR1 bit as PLAN.md §3.6
  suggested. MMUCR1 is fully assigned (23:31 is the hardware-written EEN status field) and
  MMUCR2[0:11] is the act_override distribution — neither has a free bit. TLB0CFG[44] is
  reserved, sits next to the existing PT/IND/GTWE boot bits, and is the exact analogue of
  `tlb0cfg_ind` which already gates the E.PT walker. Reset value 0, so an unmodified A2O
  still boots Book-E.
- **The radix handoff triggers on a TLB *miss*, not a hit.** `tlb_htw_req_valid` requires
  `tagpos_ind==1` (an indirect-entry hit); radix has no indirect entry, so
  `tlb_rtw_req_valid` mirrors `tlb_miss_d` instead — endflag, no way hit, no parity error,
  and `nonspec`. `tlb_miss_d` itself is gated off when radix is enabled, or every walk would
  also raise a spurious TLB-miss interrupt.
- **`mmq_rtw`'s two scan chains are stitched into one** external bit: `func_scan_in_int` is
  `[0:9]` and `mmq_htw` already takes 7:8, leaving only bit 9.
- `htw_quiesce_sig` is the **AND** of both walkers' quiesce — a thread is idle only when
  neither holds a request.

## Exception mapping (done)

A2O's Book-E exception set has no encodings for the radix-specific causes Microwatt reports
via DSISR bits 44/45. They are all storage interrupts, so:

| radix fault | A2O output |
|---|---|
| invalid (V=0), badtree, segerror, perm, rc | `mm_xu_pt_fault` + `ESR[PT]` + `ESR[DATA]` |
| lrat_miss | `mm_xu_lrat_miss` + `ESR[PT]` |
| mchk (watchdog / UE escalation / RA overflow) | `mm_xu_tlb_par_err` |

Collapsing is safe — software re-reads the PTE and re-walks either way. Preserving the
distinct cause would need new MESR1 bits (PLAN.md §3.6).

## TODO — remaining

1. **LRAT second port (P2-11).** `mmq_tlb_lrat` is a *pipelined* lookup driven from
   `tlb_tag0_*`, not a standalone request port, so a per-level walker check needs a second
   compare port rather than a wire. Until then `rtw_lrat_hit` is tied **low** in `mmq.v`, so
   **guest-mode radix walks are refused outright** (`lrat_miss`) instead of proceeding with
   addresses read out of guest-writable memory. Radix in hypervisor state (gs=0) is
   unaffected and fully functional. This is the last real feature gap.
2. **`mmq_inval.v`** — P0-5. The six deadlock detours (`:1015, 1030, 1100, 1130, 1321, 1332`)
   get exercised 4-5× harder; re-verify. Consider raising the token count (`:1598-1616`
   already supports 3) and `MMQ_ENTRIES` (`trilib/tri_a2o.vh:126`).
3. **Invalidate match is conservative.** `inv_seq_inprogress`/`inv_all` are both driven from
   `tlb_seq_snoop_inprogress`, so *any* snoop kills *every* in-flight walk. Correct but
   blunt; narrow it once the interface to `mmq_inval`'s decode is settled.
4. **Whole-core simulation.** Everything so far is `mmq_rtw` in isolation. A full `mmq` or
   core-level bench needs the Xilinx RAMB16 primitives that make `mmq.v` unlintable
   standalone (3 pre-existing errors, same as upstream). PLAN.md §6.4-§6.6.
5. **`mmq_tlb_ctl.v`** — needed **nothing**, as predicted: `mmq_rtw` emits a standard A2O
   `ptepos_*` PTE so the existing ptereload path carries it unchanged.

## Known gaps / decisions already made

- **Leaf sizes are demoted** (2M→1M, 1G→16M). Not a shortcut: A2O's size code is
  log4(size/1KB) so 2M has no encoding, and `mmq_tlb_cmp.v:3486` keeps only 3 size bits so
  nothing above 16M survives the ptereload path. See PLAN.md §2.3 item 5.
- ~~Watchdog untested~~ — now covered: `tb_walk` test 11 stalls the L2 model and the
  watchdog trips at 4097 cycles with a machine check and a freed EMQ entry.
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
3. The watchdog must measure **time since last progress**, not time since the load was
   issued. Counting only while a load was outstanding missed the case where the LSU arbiter
   never grants the request at all — an equally hard hang. It now also trips from the
   request states, not just the waits.
