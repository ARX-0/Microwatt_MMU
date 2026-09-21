# PROBLEMS.md — radix MMU defect list and decision log

## The rule

**No fix is applied to any item until its `Your decision` field is filled in by Athi.**

This file records that every architectural choice in the radix port was made by the owner,
not by the tool that wrote the code.

- An empty decision field means the item is untouched.
- "Recommended" marks Claude's suggestion. It is not a decision.
- A decision marked *(chat, date)* was given by Athi in a Claude Code session and transcribed
  here by Claude, at Athi's request.
- Once an item is fixed, its `Fix applied` line records the change, the test that proves it
  and whether it is committed.

How to use it:

1. Read one item: what is wrong, the basis, the options.
2. Write your choice in `Your decision`. Pick a letter, write your own option, or write
   "reject", "defer" or "investigate first".
3. Tell Claude which items are decided. Only those get touched.

## What this port is, and why the list was rewritten

A2O is an **out-of-order**, multithreaded **ISA 2.07 Book-E** core. This port adds
**ISA 3.x radix translation** to it, as part of migrating A2O from 2.07 to 3.x. The first
version of this list was written by comparing with Microwatt, which is a single-issue,
**in-order** ISA 3.0 core. Several judgements did not survive the move to an out-of-order
core. This revision re-judges every item against:

- **A2O User's Manual** (`a2o/rel/doc/A2O_UM.pdf`, v0.666), the 2.07 source core.
- **Power ISA v3.1C** (`docs/doc_copare/OPF_PowerISA_v3.1C.pdf`). There is no 3.0 PDF in the
  repo; v3.1C keeps 3.0's radix and synchronization rules. Every ISA citation below says
  "v3.1C".
- The **A2O RTL** for the out-of-order behaviour, the load queue and the completion unit.

### Out-of-order facts that every item below relies on

| # | Fact | Source |
|---|---|---|
| O1 | A D-ERAT miss is sent as **non-speculative** only when its instruction is the **next to complete** on its thread. | `lq_derat.v:4611-4632` (`ex3_itag == cp_next_itag`) |
| O2 | An I-ERAT miss is non-speculative only for the first fetch after a `cp_flush`, when the thread has nothing in flight. | `iuq_ic_select.v:903-906` (`cp_flush_nonspec`) |
| O3 | Only non-speculative misses are walked. | `mmq_tlb_cmp.v:5097`; UM p. 457, note 2 |
| O4 | `cp_flush` is raised by the **completion** unit, in order: on a flushing completion, an exception vector, rfi, reset or a RAM flush. | `iuq_cpl_ctrl.v:2138` |
| O5 | `cp_flush` is the walker's `xu_ex5_flush`. | `c.v:4313` |
| O6 | The load queue kills its own outstanding ERAT-miss entry on any `cp_flush` of that thread. | `lq_derat.v:4553` |
| O7 | The ISA allows **speculative** radix translation for the context that is executing. The A2O non-speculative-only rule is a design choice, not an ISA requirement. | ISA v3.1C Book III p. 1157 |

**Consequences.**
- From O1–O4: while a walk is in flight, the only thing that can flush its thread is
  something that flushes the walk's own instruction: an interrupt, rfi, reset, or that
  instruction's own exception. A younger instruction, such as a mispredicted branch, cannot
  complete first.
- From O7: installing a *valid* translation for an instruction that was flushed is
  architecturally allowed.

## How the list was made

- **2026-09-21, first pass.** Made at commit `7ad773a` plus the uncommitted cocotb bench.
  Three `researcher` agents traced the wiring, the Verible LSP gave symbol outlines, and
  Claude read `mmq_rtw.v` against Microwatt `mmu.vhdl`.
- **2026-09-21, simulation.** The mmq-level cocotb bench (`a2o/rel/src/verilog/sim/cocotb/`)
  found items 22–24. Logs: `before_fix.log` (`TESTS=10 PASS=2 FAIL=8`), then
  `after_fix.log` (`PASS=3 FAIL=7` with items 1–5 and 22 applied).
- **2026-09-21, this revision.** Every item was re-judged against the A2O UM, ISA v3.1C and
  the out-of-order RTL facts above. Items 25 and 26 are new; 7, 13, 14, 15 and 16 were
  re-graded.
- **2026-09-21, Phase B.** Items 4 and 23 were fixed; item 24 turned out to be a bench error.
  Items 27 and 28 are new. `after_phaseB.log`: `TESTS=10 PASS=10`.
- **Commits (branch `radix-integration-fixes`, from `main` at `7ad773a`):**
  - `82edd6b`: RTL fixes for items 1, 2, 3, 4, 5, 22 and 23.
  - `56701fa`: the cocotb bench.
  - The simulation logs and the `sim_build*/` output are **not** committed. They are local
    evidence in `a2o/rel/src/verilog/sim/cocotb/`.

**Status labels.**
- **Confirmed:** follows from the code and the cited spec.
- **Confirmed in simulation:** seen in a cocotb run.
- **Probable:** reads as wrong, but depends on behaviour not yet simulated.
- **Refuted:** the concern does not hold once the out-of-order behaviour or the spec is taken
  into account.
- **Investigate:** not enough evidence either way.

Paths below are relative to `a2o/rel/src/verilog/work/` unless stated.

---

## Summary

| # | Problem | Severity | Status | Decided | Fixed |
|---|---|---|---|---|---|
| 1 | Radix handoff not connected to `mmq_tlb_cmp` | Blocker | Confirmed in simulation | ☑ | ☑ `82edd6b` |
| 2 | Invalidates never reach the walker (undriven net) | Blocker | Confirmed | ☑ | ☑ `82edd6b` |
| 3 | Four other undeclared implicit nets on `mmq_rtw` | Lint | Confirmed | ☑ | ☑ `82edd6b` |
| 4 | Wrong bit slices on the `mmq_rtw` instance | Low | Confirmed | ☑ | ☑ `82edd6b` |
| 5 | Request PID/LPID/GS/AS/thread mask taken from the TLB way | Blocker | Confirmed | ☑ | ☑ `82edd6b` |
| 6 | Quadrant-0 root cache shared across threads | High | Confirmed | ☑ | ☐ |
| 7 | Root cache refilled with stale data after a PTCR/PID write | — | Reduced to item 6 | ☑ | ☐ (test only) |
| 8 | Process-table index ignores PID[0:1] | Low | Confirmed | ☑ | ☐ |
| 9 | Leaf RPN and table bases above RA 42 silently truncated | Medium | Confirmed | ☑ | ☐ |
| 10 | C bit required for loads and instruction fetch | High | Confirmed (ISA) | ☑ | ☐ |
| 11 | Page with RW=1, R=0 is not readable | Medium | Confirmed (ISA) | ☑ | ☐ |
| 12 | ESR reports the wrong access type | Medium | Confirmed | ☑ | ☐ |
| 13G | ATT decoded as one bit: tolerant I/O is guarded and not executable | Medium | Confirmed (ISA) | ☑ | ☐ |
| 13E | No MSR[LE]: radix pages are always big-endian | Migration gap | Confirmed (UM) | ☐ | ☐ |
| 14 | Flush or invalidate in the accept cycle is ignored | Low | Benign (OoO + ISA) | ☑ | ☐ (comment only) |
| 15 | A miss arriving while the thread's walker is draining is dropped | High | Probable | ☑ investigate | ☐ |
| 16 | Any flush kills the walk: livelock risk | — | Refuted (OoO) | ☑ | — |
| 17 | Load left in flight after a timeout can pollute the next walk | Low | Probable | ☑ investigate | ☐ |
| 18 | LRAT handshake is circular | Latent | Confirmed | ☑ defer | — |
| 19 | No walk-time permission check; `rtw_perm_err` is dead | Medium | Confirmed | ☑ | ☐ |
| 20 | Test and lint flow let items 1–5 through | Process | Confirmed | ☑ | ☐ |
| 21 | `NEXT.md` and docs claims that are now false | Docs | Confirmed | ☑ | ☐ |
| 22 | PTE page-size field uses TLB codes, not PTE PS codes | Blocker | Confirmed in simulation | ☑ | ☑ `82edd6b` |
| 23 | Radix ptereload never carries the reservation: TLB never written | Blocker | Confirmed in simulation | ☑ | ☑ `82edd6b` |
| 24 | ERAT reload after a radix walk decodes as EPN=0, RPN=0 | — | Refuted (harness error) | ☑ | — |
| 25 | Cached PATE/PRTE cannot be invalidated by software | Migration gap | Confirmed (ISA) | ☑ log only | ☐ |
| 26 | A killed walk's late reload may reach a reallocated EMQ slot | Unknown | Investigate | ☐ | ☐ |
| 27 | Every V=0 walker reload (killed, timeout) is reported as a page fault | Medium | Confirmed in simulation | ☐ | ☐ |
| 28 | Book-E TID=0 / TLPID=0 wildcards clash with ISA 3.x PID 0 / LPID 0 | High | Confirmed | ☐ | ☐ |

---

## A. Integration: the walker cannot run inside `mmq`

### 1. Radix handoff not connected

**Status:** Confirmed in simulation. **Severity:** Blocker.

**What is wrong.**
- The `mmq_tlb_cmp` instance (`mmq.v:3236`) had no `.mmucr1_rxe(...)` and no
  `.tlb_rtw_req_valid(...)`, although both ports exist (`mmq_tlb_cmp.v:264-265`).
- So `mmq_rtw` never received a request.
- `tlb_miss_d`, gated by the floating RXE (`mmq_tlb_cmp.v:4378-4381`), went X.

**Evidence.** `before_fix.log`: `rtw_req:xz` for 20 000 cycles; `mm_xu_tlb_miss` = x at
cycle 64.

**OoO relevance.** None.

**Options.**
- **(a) Connect both ports.** *Recommended.*
- **(b) As (a), and rename `mmucr1_rxe`.** It is really `TLB0CFG[44]` (`mmq.v:3758`).

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**
- Change: `mmq.v`, the `mmq_tlb_cmp` instance now connects `.mmucr1_rxe`,
  `.tlb_rtw_req_valid` and the new `.tlb_rtw_req_tag` (item 5).
- Evidence: `after_fix.log`, where EVENT 1 is reached in all M tests.
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

### 2. Invalidates never reach the walker

**Status:** Confirmed. **Severity:** Blocker for correctness.

**What is wrong.**
- `.inv_seq_inprogress` and `.inv_all` connected to `tlb_seq_snoop_inprogress`
  (`mmq.v:3925, 3930`). That name is a `reg` inside `mmq_tlb_ctl.v:640`, not a port, so in
  `mmq.v` it was an undriven implicit net.
- So the P0-4 reservation (`mmq_rtw.v:895-900, 1309-1311`) could never be cleared by a
  `tlbivax`/`tlbilx`.

**Basis.**
- ISA v3.1C Book III ch. 13, table on p. 1278: after a `tlbie`/`tlbiel` and a CSI, "storage
  accesses … will not use the … TLB entry(s) … being invalidated" (note 4).
- The A2O equivalent is `tlbivax`/`tlbilx` plus `isync`. A walk that installs after the
  invalidate has been performed breaks that guarantee.

**OoO relevance.** Real. An invalidate from another thread can arrive at any point in a walk.

**Options.**
- **(a) Export `tlb_seq_snoop_inprogress` from `mmq_tlb_ctl`.** Any snoop kills every
  in-flight walk. Blunt but correct. *Recommended.*
- **(b) Route `mmq_inval`'s decoded invalidate** for a precise match.
- **(c) (a) now, (b) later.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**
- Change: new `mmq_tlb_ctl` output `tlb_ctl_snoop_inprogress`, which is the existing reg,
  declared as a wire in `mmq.v` and connected. The claim in doc 04 §4.7 that `mmq_tlb_ctl` is
  unmodified must be corrected (item 21).
- Evidence: lint is clean of IMPLICIT. Functional test: M9 `tlbilx`, pending.
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

### 3. Four other undeclared implicit nets

**Status:** Confirmed. **Severity:** Lint.

**What is wrong.**
- `.tlb_ctl_tag2/3/4_flush` and `.tlb_tag2` connected to undeclared names; the real wires
  carry `_sig` (`mmq.v:488, 519-521`).
- No functional effect: `mmq_rtw` only sinks them into `unused_dc`.

**Options.**
- **(a) Use the `_sig` names.** *Recommended.*
- **(b) Remove the ports.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**
- Change: `mmq.v`, the `mmq_rtw` instance.
- Evidence: Verilator `-Wall` reports no IMPLICIT/PINMISSING/WIDTH on the radix files.
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

### 4. Wrong bit slices on the `mmq_rtw` instance

**Status:** Confirmed. **Severity:** Low.

| Port | `mmq_rtw` got | `mmq_htw` gets |
|---|---|---|
| `xu_mm_ccr2_notlb_b` | whole `[1:12]`, truncated to bit 12 | `[7]` |
| `tlb_delayed_act` (`[24:28]`) | whole `[9:33]`, truncated to `[29:33]` | `[24:28]` |
| `mmucr2_act_override` | `mmucr2_sig[0]` | `mmucr2_sig[4]` |

**Options.**
- **(a) Copy `mmq_htw`'s slices.** *Recommended.*
- **(b) A separate act-override bit.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**
- Change: `mmq.v`, the `mmq_rtw` instance now takes `xu_mm_ccr2_notlb_b[7]`,
  `tlb_delayed_act[24:28]` and `mmucr2_sig[4]`.
- Evidence: `after_phaseB.log`.
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

### 5. Request PID/LPID/GS/AS and thread mask taken from the TLB way

**Status:** Confirmed. **Severity:** Blocker.

**What is wrong.**
- The walker was fed `tlb_htw_req_tag` (`mmq.v:3911`). That tag takes PID, GS, AS and LPID
  from the matched way (`mmq_tlb_cmp.v:5103-5110`), and `{atsel,esel}` from the way's thread
  mask (`:5112-5113`). This is correct for a Book-E IND *hit*.
- On a radix *miss* the way is unrelated, which causes four failures:
  - The walker indexes the wrong process table (`mmq_rtw.v:727-732`).
  - It takes the LRAT branch from a garbage GS.
  - The installed entry gets a wrong PID or LPID (0 matches everything,
    `mmq_tlb_matchline.v:563,566`).
  - The installed entry gets a wrong thread mask (`mmq_tlb_cmp.v:3491`; `0000` never
    matches, `matchline.v:560`).

**OoO relevance.** None.

**Options.**
- **(a) A new `tlb_rtw_req_tag` output built from `tlb_tag4_q`.** *Recommended.*
- **(b) Build it in `mmq.v`.**

**Your decision:** (a), with `{atsel,esel}` set to the requesting thread's mask *(chat,
2026-09-21)*.

**Fix applied:**
- Change: `mmq_tlb_cmp.v`, new port and assigns.
- Evidence: the walk now indexes PRTE0 at `PROC_BASE + 16·PID` (cocotb probe).
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

## B. Root cache and process table

### 6. Quadrant-0 root cache shared across threads

**Status:** Confirmed. **Severity:** High (one process's translations used by another).

**What is wrong.**
- One `pgtbl0_q`/`pt0_valid_q` serves both walker contexts (`mmq_rtw.v:470-481`).
- Thread 0 (PID A) caches its root; thread 1 (PID B) then hits `req_root_cached` and walks
  PID A's tree.

**Basis.** ISA v3.1C p. 1157: hardware may "cache … a PRTE when PIDR is loaded". PIDR is
per thread, so a cached PRTE belongs to one thread's PID.

**OoO relevance.** Real, and made worse by SMT: both threads walk concurrently.

**Options.**
- **(a) One quadrant-0 root per thread,** cleared by that thread's PID write. *Recommended.*
- **(b) Tag the root with the PID.**
- **(c) Do not cache quadrant 0.**

**Your decision:** (a); new `mmq_spr` output `pid_wr_thd[0:MM_THREADS-1]` next to the
unchanged `pid_wr` *(chat, 2026-09-21)*.

**Fix applied:**

---

### 7. Root cache refilled with stale data after a PTCR or PID write

**Status:** Reduced to item 6. **Severity:** None left once 6(a) is in.

**What was claimed.** A walk in `PartWait`/`ProcWait` when `ptcr_wr`/`pid_wr` fires refills
the cache with the old entry (`mmq_rtw.v:1038, 1095`).

**Re-analysis for an out-of-order core.**
- **PTCR:** ISA v3.1C ch. 13 note 3 (p. 1280) requires that no translated access be in
  flight on any thread while PTCR changes. So no walk exists at that moment.
- **PID, same thread:** ISA v3.1C ch. 13 requires a CSI *before* `mtspr PIDR` (p. 1278; A2O
  UM Table 1 p. 525 lists PID After Write (Instr) = CSI). A CSI does not start until all
  earlier instructions have completed (A2O UM §2.14.1). The walk serves the next-to-complete
  instruction (O1, O3). So a walk and its own thread's `mtspr PID` cannot overlap.
- **PID, other thread:** this *is* reachable, through the shared cache. It is item 6, and
  6(a) removes it.

**Options.**
- **(a) Resolved by 6(a),** plus a tb_walk test in which thread 1's PID write lands during
  thread 0's `ProcWait`. *Recommended.*
- **(b) Also add a per-context stale bit** as defence against non-conforming software.

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**

---

### 8. Process-table index ignores PID[0:1]

**Status:** Confirmed. **Severity:** Low.

**What is wrong.**
- `effpid` is the low 12 of 14 PID bits (`mmq_rtw.v:732`; `PID_WIDTH=14` at
  `mmu_a2o.vh:69`).
- Two PIDs that differ only in PID[0:1] share a process-table entry.

**Basis.**
- ISA v3.1C §5.3.3 defines PIDR as bits 32:63, and "the number of PIDR bits supported is
  implementation-dependent". So supporting 14 bits is legal. Silently aliasing the upper
  two is not, because it gives two processes one translation.
- The A2O ERAT holds only 8 PID bits, so it relies on context-synchronizing invalidation on
  `mtpid` (A2O UM §6.7.1).

**Options.**
- **(a) Fault (badtree) when PID[0:1] ≠ 0.**
- **(b) Widen `effpid`/`fm4`.**
- **(c) Document it.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**

---

## C. Walk-result correctness against ISA v3.1C

### 9. Addresses above RA 42 silently truncated

**Status:** Confirmed. **Severity:** Medium (aliased real address).

**What is wrong.**
- `ra_overflow` checks only the base of the next PDE (`mmq_rtw.v:829`).
- The leaf RPN, PTCR and the PATE1 base are truncated without any check.

**Basis.** The ISA v3.1C Fig. 6.17 engineering note says the implemented RA width is the
system's physical address size. The ISA does not *require* a machine check for higher bits,
so a machine check is a defensive choice that A2O is free to make.

**Options.**
- **(a) Machine check on non-zero bits 8:21 of the leaf RPN, PTCR or PATE1.** *Recommended.*
- **(b) Check the leaf only.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**

---

### 10. C bit required for loads and instruction fetch

**Status:** Confirmed against the ISA. **Severity:** High (every read of a clean page faults).

**What is wrong.**
- `rc_ok = R & C` (`mmq_rtw.v:871`).
- `tagpos_class` does carry the D-ERAT ttype (`mmq_tlb_ctl.v:2508-2517`): 1 = store,
  3 = epid store.

**Basis.**
- ISA v3.1C §6.7.12 (p. 1142): "the Reference bit must contain 1 in order to access the
  corresponding page and the Change bit must contain 1 in order to store to the
  corresponding page."
- The same section: hardware "unable to set the bit(s) atomically" raises DSI/ISI. So
  faulting instead of writing back is legal. Requiring C for loads is not.

**OoO relevance.** None.

**Options.**
- **(a) Require C only for a D-side store at walk time, and pass the real C to
  `ptepos_c`.** `mmq_tlb_cmp.v:3584-3585` then removes UW/SW on a clean page, so a later store
  hitting an entry installed by a load still faults. That matches the rule quoted above and
  Microwatt's hit-time check (`mmu.vhdl:1600`). *Recommended.*
- **(b) No C check at walk time; real C only.**
- **(c) Keep it and document it.**

**Your decision:** (a) including the real-C pass-through *(chat, 2026-09-21)*

**Fix applied:**

---

### 11. A page with RW=1, R=0 is not readable

**Status:** Confirmed against the ISA. **Severity:** Medium.

**What is wrong.** UR/SR come from the PTE Read bit alone (`mmq_rtw.v:861-862`).

**Basis.** ISA v3.1C Fig. 6.17, EAA bit 1 (Read): "0 – loads permitted only if EAA2 = 1".
Bit 2 is **Read/Write**, not Write. A Read/Write page is readable by definition.

**Options.**
- **(a) UR/SR = R | RW.** *Recommended.*
- **(b) Keep it.** This contradicts the ISA.

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**

---

### 12. ESR reports the wrong access type

**Status:** Confirmed. **Severity:** Medium.

**What is wrong.**
- `ESR[DATA]` is set for every radix storage fault, including instruction fetch
  (`mmq.v:3226-3231`).
- `ESR[ST]` is never set.

**Basis and migration note.** A2O reports storage faults Book-E style (ESR, A2O UM §7.5.17;
DEAR). An ISA 3.x OS expects DSISR/DAR/SRR1 with radix-specific cause bits. That is an
interrupt-model migration outside the MMU; this item only makes the Book-E report accurate.

**Options.**
- **(a) New `mmq_rtw` outputs `rtw_fault_iside` and `rtw_fault_store`,** used to gate
  ESR[DATA] and ESR[ST]. *Recommended.*
- **(b) Document it.**

**Your decision:** (a); ports named `rtw_fault_iside` and `rtw_fault_store` *(chat,
2026-09-21)*.

**Fix applied:**

---

### 13G. ATT decoded as a single bit

**Status:** Confirmed against the ISA. **Severity:** Medium.

**What is wrong.**
- `wimge_out = {0, I, 1, I, 0}` with I = ATT[0] (`mmq_rtw.v:873`), so G = I.
- Execute is denied whenever I = 1 (`mmq_rtw.v:857-858`).

**Basis.** ISA v3.1C Fig. 6.17, ATT:

| ATT | Meaning | WIMG |
|---|---|---|
| 00 | normal | 0010 |
| 10 | non-idempotent I/O | 0111, G = 1 |
| 11 | tolerant I/O | 0110, G = 0 |

Fig. 6.26 rule 1: instruction fetch is not permitted when G = 1. So tolerant I/O is wrongly
marked guarded and wrongly made non-executable. Microwatt has the same simplification
(`mmu.vhdl:367`).

**Options.**
- **(a) Decode ATT into WIMG per Fig. 6.17, and deny execute on G.** *Recommended.*
- **(b) Keep the Microwatt behaviour and document it.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**

---

### 13E. No MSR[LE]: radix pages are always big-endian

**Status:** Confirmed (A2O UM). **Severity:** Migration gap.

**What is wrong.**
- The walker installs E = 0 (`mmq_rtw.v:873`).
- A2O's byte order is set **only** by the page E bit (A2O UM §6.5.5). ISA 3.x sets it
  with MSR[LE], which Book-E A2O does not have.
- So a little-endian ISA 3.x OS cannot run under radix as built.

**Options.**
- **(a) Add a per-thread "radix LE" mode bit** (config or SPR) and install E from it.
  - The ERAT/TLB entries are thread-private (item 5), so this is consistent.
  - Changing the mode needs a TLB/ERAT invalidate.
- **(b) Big-endian only,** documented as a limitation.
- **(c) Implement MSR[LE].** This is a core-wide migration task, not an MMU one.

**Your decision:**

**Fix applied:**

---

## D. Races and forward progress on an out-of-order core

### 14. Flush or invalidate in the accept cycle is ignored

**Status:** Benign after re-analysis. **Severity:** Low.

**What is wrong.** `seq_valid_set` has priority over the kill and reservation updates
(`mmq_rtw.v:1303-1311`).

**Re-analysis.**
- By O1–O5, a `cp_flush` in the accept cycle can only mean the walk's own instruction was
  flushed.
- Its translation is still valid, and ISA v3.1C p. 1157 allows speculative translation for the
  executing context (O7). The walker writes no R/C bits. So finishing the walk is legal.
- The LQ has already dropped its entry (O6).
- An invalidate in the accept cycle is covered by the reservation check at every level
  boundary and at the final `wq` gate (item 23).

**Options.**
- **(a) Honour the kill and reservation in the accept cycle.**
- **(b) Leave it, and add a comment with this reasoning.** *Recommended.*

**Your decision:** (b), changed from (a) after the out-of-order re-analysis *(chat,
2026-09-21)*.

**Fix applied:**

---

### 15. A miss arriving while the thread's walker is draining is dropped

**Status:** Probable (re-scoped). **Severity:** High if reachable (the thread hangs; no
watchdog sees it).

**Old claim, refuted.** "An I-miss and a D-miss on one thread at once." By O1 and O2, both
cannot be non-speculative together.

**New claim.**
- `accept` needs the thread's one context to be idle (`mmq_rtw.v:907`).
- `tlb_rtw_req_valid` has no back-pressure.
- A context stays busy after its instruction is flushed: `Killed` waits for its L2 load to
  return, and `Timeout` waits for the ptereload handshake.

Reachable sequence:
1. An interrupt flushes a walking load (O4). The walk is killed but still draining.
2. The interrupt's vector fetch is the next non-speculative request on that thread (O2).
   It misses the I-ERAT.
3. The miss reaches a busy context and disappears. No reload ever arrives.

**Options.**
- **(a) Investigate first:** a cocotb test that flushes mid-walk and then issues a new
  non-speculative miss on the same thread immediately. *Recommended.*
- **(b) One-deep per-thread request buffer** in `mmq_rtw`.
- **(c) Back-pressure into `mmq_tlb_ctl`,** so the request is replayed.

**Your decision:** investigate first *(chat, 2026-09-21)*

**Fix applied:**

---

### 16. Any flush kills the walk: livelock risk

**Status:** Refuted. **Severity:** None.

**Old claim.** Flushes of younger, unrelated instructions kill the walk repeatedly.

**Re-analysis.**
- `cp_flush` is raised at completion, in order (O4), and the walk serves the next-to-complete
  instruction (O1). A younger instruction cannot complete, and therefore cannot flush,
  before it.
- What remains (interrupt storms) affects every instruction equally. It is not
  radix-specific.
- The LQ uses the same kill-on-`cp_flush` rule for its own miss entries (O6).

**Your decision:** refuted; no action *(chat, 2026-09-21)*

**Fix applied:** —

---

### 17. A load left in flight after a timeout can pollute the next walk

**Status:** Probable. **Severity:** Low (a machine check has already fired).

**What is wrong.**
- `Timeout` frees the context while its L2 load may still be in flight.
- The core tag is fixed per context (`mmq_rtw.v:1295`), so a late critical beat could be
  taken as the next walk's data.

**Options.**
- **(a) Investigate:** a cocotb test that stalls past the watchdog, starts a new walk, then
  delivers the stale beat. *Recommended.*
- **(b) Block the context after a timeout** until drained.
- **(c) Document it.**

**Your decision:** investigate first *(chat, 2026-09-21)*

**Fix applied:**

---

### 18. The LRAT handshake is circular

**Status:** Confirmed. **Severity:** Latent (`rtw_lrat_hit` is tied to 0, so guest walks are
refused).

**What is wrong.**
- `rtw_lrat_req_valid` requires `ctx_seq_load_req` (`mmq_rtw.v:592`), and `load_req` requires
  `rtw_lrat_hit` first (`:1149`).
- The hit is one shared bit.
- The table reads are never LRAT-checked.

**Options.**
- **(a) Defer to the LRAT second-port work.** *Recommended.*
- **(b) Fix the handshake shape now.**

**Your decision:** (a) defer *(chat, 2026-09-21)*

**Fix applied:** —

---

### 19. No walk-time permission check; `rtw_perm_err` is dead

**Status:** Confirmed. **Severity:** Medium.

**What is wrong.**
- `Flt_PermErr` is never assigned.
- The ERAT enforces the installed `usxwr` later, but a first access that is not permitted
  should fault at walk time with a permission cause, not install an entry.

**Basis.** ISA v3.1C Fig. 6.26 and 6.27:
- An instruction fetch is not permitted when G = 1.
- In problem state, no access is permitted to EAA0 = 1 pages.
- Loads need Read or Read/Write; stores need Read/Write; execute needs Execute.
- Privileged access to an EAA0 = 0 page is governed by AMR/IAMR key 0. A2O has neither
  register, so that access is permitted.
- A permission failure takes priority over R/C (Microwatt `mmu.vhdl:1698-1716` orders them
  the same way).

**Options.**
- **(a) Remove the port.**
- **(b) Implement the check.**
  - Microwatt rule set: execute is denied on I (`mmu.vhdl:351-371`).
  - ISA v3.1C rule set: execute is denied on G.
- **(c) Keep it and comment it.**

**Your decision:** (b), following **ISA v3.1C Fig. 6.26/6.27**, not Microwatt *(chat,
2026-09-21)*.

**Fix applied:**

---

## E. Process and documentation

### 20. The test and lint flow let items 1–5 through

**Status:** Confirmed. **Severity:** Process.

**What is wrong.**
- `tb_walk.v` bypasses `mmq.v`.
- The doc 04 §4.8 lint suppresses warnings.
- cocotb 1.9 `make` exits 0 on failure.
- The older `run_rtw_tests.sh` stages never check pass/fail.

**Options.**
- **(a) cocotb stage.**
- **(b) Lint gate.**
- **(c) Both.**

**Your decision:** (c) *(chat, 2026-09-21)*

**Fix applied:**

---

### 21. `NEXT.md` and docs claims that are now false

**Status:** Confirmed. **Severity:** Docs.

**What is wrong.**
- `NEXT.md` says "integration and exception routing are done". Items 1, 2 and 5 contradict
  it.
- Doc 03 §3.5/§3.6: the R/C rule and the PS codes.
- Doc 04:
  - §4.1/§4.3: the shared htw tag
  - §4.7: "`mmq_tlb_ctl` unmodified" (now one output port)
  - §4.8: the lint claim
- Doc 06 needs the new tests.

**Options.**
- **(a) Now.**
- **(b) After the fixes land.**

**Your decision:** (b) *(chat, 2026-09-21)*

**Fix applied:**

---

## F. Found by the mmq-level cocotb run

The logs are in `a2o/rel/src/verilog/sim/cocotb/`.

### 22. PTE page-size field uses TLB codes, not PTE PS codes

**Status:** Confirmed in simulation. **Severity:** Blocker.

**What is wrong.**
- The walker wrote the TLB's log4 size codes (4K = `0001` …) into `ptepos_size`.
- The PTE PS field is log2(size/1KB): 4K = `0010`, 64K = `0110`, 1M = `1010`, 16M = `1110`
  (**A2O UM §6.17.3**, PS field). The TLB takes `0b0 || PS[52:54]` (`mmq_tlb_ctl.v:2597`).
- `0001` therefore became `0000`, which is unsupported, and `tlb_inelig` fired
  (`mmq_tlb_cmp.v:4403`).
- `tb_walk.v:227` expected the wrong value.

**Options.**
- **(a) PTE PS codes in the walker, fix `tb_walk`, correct doc 03 §3.6.** *Recommended.*
- **(b) Walker only.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**
- Change: `mmq_rtw.v` gets the `PTE_PS_*` parameters, and `tb_walk.v:227` now expects
  `0010`.
- Evidence: `tlb_inelig` is gone from `after_fix.log`, and `run_rtw_tests.sh` passes
  (11 of 11 walk scenarios).
- Doc 03 is still pending (item 21).
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

### 23. Radix ptereload never carries the reservation: TLB never written

**Status:** Confirmed in simulation. **Severity:** Blocker.

**What is wrong.**
- `mmq_tlb_ctl` writes a ptereload only when `wq == 2'b10` (`mmq_tlb_ctl.v:2981-2999`).
- `mmq_htw` uses `wq[0]` as its reservation flag (`mmq_htw.v:785-793`).
- `mmq_rtw` passes `wq = 00` (`mmq_rtw.v:631`), so nothing is ever written.

**OoO relevance.** The reservation is what makes item 2 effective. An invalidate from any
thread during the walk clears it, and the final write is then suppressed.

**Options.**
- **(a) `wq = {ctx_resv_q[sel], 0}` on the ptereload tag.** *Recommended.*
- **(b) Set `wq = 10` unconditionally.**
- **(c) Change `mmq_tlb_ctl`'s gate.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Fix applied:**
- Change: `mmq_rtw.v`, `ptereload_req_tag` now returns
  `wq = {ctx_resv_q[sel], 1'b0}`, with every other tag bit unchanged.
- Evidence, `after_phaseB.log`: `TESTS=10 PASS=10`. M1–M6 and M8 each show
  miss → walk → TLB way written → the retry hits the TLB with the walked RPN, with no
  second walk and no extra L2 load. `run_rtw_tests.sh` still passes.
- Committed in `82edd6b` (branch `radix-integration-fixes`).

---

### 24. ERAT reload after a radix walk decodes as EPN=0, RPN=0

**Status:** Refuted: a testbench error, not an RTL bug (see Resolution below).

**What was seen.** On M1, cycle 143: `mm_xu_derat_rel_val = 0b10001`; the data decoded as
EPN = 0, V = 1, RPN = 0.

**Why it is open.** The ptereload reload takes its RPN from `tlb_tag4_way_or`
(`mmq_tlb_cmp.v:4052`), so it may follow from item 23. `ERATPOS` in the bench has not been
checked against a Book-E reload.

**Options.**
- **(a) Re-check after item 23.** *Recommended.*
- **(b) Check the decode now.**

**Your decision:** (a) *(chat, 2026-09-21)*

**Resolution: refuted. It was a testbench error, not an RTL bug.**
- The reload sent on the ptereload pass has `eratpos_wren = 0` (`mmq_tlb_cmp.v:4046-4049`:
  wren needs `type_ptereload == 0` and a way hit). It is a "miss done, retry" notice, and
  its RPN field is whatever `tlb_tag4_way_or` holds.
- The LQ writes the ERAT only on `wren = 1` (`lq_derat.v:2473-2475, 3527`). The
  instruction replays, hits the TLB, and receives a `wren = 1` reload with the translation.
  This is the same flow Book-E uses after an `mmq_htw` ptereload.
- The bench now checks `wren = 0` at EVENT 2 and models the replay at EVENT 3.

**Fix applied:** — (bench only, `sim/cocotb/test_tlbmiss.py`, committed in `56701fa`)

---

## G. Migration gaps and new investigations

### 25. Cached PATE/PRTE cannot be invalidated by software

**Status:** Confirmed against the ISA. **Severity:** Migration gap.

**What is wrong.**
- ISA 3.x invalidates cached Partition/Process Table Entries with `tlbie`/`tlbiel`
  RIC = 2 for a given LPID/PID (ISA v3.1C §6.9.3.3).
- A2O is Book-E: it has `tlbivax`/`tlbilx` and no RIC field.
- The walker's cached roots are cleared only by `ptcr_wr`/`pid_wr`. Software that edits
  the PRTE of the *current* PID has no way to invalidate it.

**Options.**
- **(a) Clear the cached roots on any invalidation snoop** (reusing item 2's signal).
- **(b) Implement `tlbie` with RIC = 2.** This is an ISA 3.x migration task.
- **(c) Document the rule:** rewrite PID (or PTCR) after editing a PRTE.

**Your decision:** log only, decide later *(chat, 2026-09-21)*

**Fix applied:**

---

### 26. A killed walk's late reload may reach a reallocated EMQ slot

**Status:** Investigate (new, from the out-of-order re-analysis). **Severity:** Unknown.

**What is wrong, if it is reachable.**
- On `cp_flush`, the LQ kills its ERAT-miss entry at once (O6; `lq_derat.v:4553-4557`).
- The walker, by design (P0-3), still returns a reload later, tagged with the old EMQ id
  (`tagpos_emq`, carried in the request tag).
- If the LQ has reused that EMQ slot for a new miss in the meantime, the stale reload
  (V = 0, or V = 1 for a different EPN) could be matched to the new miss.
- Not yet traced: whether the LQ holds a killed slot until its reload returns
  (`eratm_entry_mkill_q` behaviour).

**Options.**
- **(a) Investigate first:** read the LQ EMQ reuse rules, and if the case is reachable, add a
  cocotb test. *Recommended.*
- **(b) Drop the reload of a flushed walk** instead of returning it. This changes the P0-3
  design.

**Your decision:**

**Fix applied:**

---

### 27. Every V=0 walker reload is reported as a page fault

**Status:** Confirmed in simulation. **Severity:** Medium.

**What is wrong.**
- Each walker terminal state returns a ptereload with PTE V=0 (P0-3 design,
  `mmq_rtw.v:1245-1279`): Fault, Killed and Timeout.
- `mmq_tlb_cmp` treats any ptereload with V=0 as a Book-E page-table fault and raises
  `pt_fault` (the table at `mmq_tlb_cmp.v:4384-4400`: "ptereload | DSI pt_fault=1").
- So a **Timeout** reports both `rtw_mchk` and `pt_fault`, and a **Killed** walk (a flushed
  instruction, or a cleared reservation) reports a `pt_fault` that has no architectural
  cause.

**Evidence.** `after_phaseB.log`, self-test: after the stalled L2, `pt_fault` at cycle 4169,
alongside the walker watchdog's machine check.

**OoO relevance.**
- Killed walks follow a completion-time flush (O4), and the LQ has already dropped that
  EMQ entry (O6). Whether the XU then ignores the `pt_fault` is not traced.
- A Killed walk whose reservation was cleared by another thread's `tlbivax` belongs to a
  live instruction. That instruction would take a spurious DSI instead of replaying.

**Options.**
- **(a) Mark non-fault terminations** so that cmp does not raise `pt_fault` for them: for
  example, a spare tag bit, or the existing `tagpos_is` encoding
  (`mmq_tlb_cmp.v:4401`, "pte.valid & 0"). The LQ then just replays.
- **(b) Investigate first** what the LQ and XU do with a `pt_fault` for a flushed EMQ entry,
  and for a live one.
- **(c) Document it.**

**Your decision:**

**Fix applied:**

---

### 28. Book-E TID=0 / TLPID=0 wildcards clash with ISA 3.x PID 0 / LPID 0

**Status:** Confirmed by reading. **Severity:** High once PID 0 or LPID 0 is used for
ordinary translations.

**What is wrong.**
- In the A2O TLB, an entry with TID = 0 matches **every** PID, and TLPID = 0 matches
  **every** LPID (`mmq_tlb_matchline.v:563, 566`). These are Book-E "global" entries.
- The walker installs the request's PID and LPID (item 5).
- In ISA 3.x, PID 0 is an ordinary process ID (by convention the kernel process, ISA v3.1C
  §5.3.3 programming note), and LPID 0 is the hypervisor's partition.
- So a quadrant-0 walk made while PIDR = 0 installs an entry that **every** process then
  matches, and entries made while LPIDR = 0 match every partition.
- Seen while writing test M5: with LPIDR = 0, an entry matched LPID 2. The test now uses
  LPIDR 1 and 2.

**Options.**
- **(a) Never install a wildcard.**
  - Quadrant 3 (kernel) entries are process-independent in ISA 3.x, so TID = 0 is actually
    correct for them and could be used deliberately.
  - For quadrant 0 with PID = 0, return the reload without installing (the walk result
    stands, but the entry is not cached).
- **(b) Reserve PID 0 and LPID 0** in the radix OS ABI and document it.
- **(c) Change the matchline wildcard for radix entries.** This touches upstream Book-E
  logic.

**Your decision:**

**Fix applied:**
