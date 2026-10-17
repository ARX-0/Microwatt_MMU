# Retiring the ISA 2.07 Book-E MMU interface from A2O

Survey only. No RTL has been changed. The table in §2 is the TODO list for the next step.
No row is to be acted on until its `Your decision` cell is filled in.

## 1. Problem

A2O implements the ISA 2.07 Book III-E MMU. Software manages the translation lookaside
buffer (TLB) directly, through the MAS registers (MMU Assist Registers) and the `tlbwe`
instruction. The radix port adds ISA 3.1C radix translation, where hardware walks a page
table and software never writes the TLB. ISA 3.1C has no Book III-E MMU: the string `MAS0`
does not occur in `OPF_PowerISA_v3.1C.pdf`.

The 2.07 SPRs (special-purpose registers) and instructions are all still legal in `a2o/rel`,
so any privileged or hypervisor program can bypass radix. Concretely:

- An entry written by `tlbwe` shadows the radix tree. A walk starts only on a TLB miss
  (`mmq_tlb_cmp.v:5093-5099`), so a hit on that entry means no walk happens.
- Three Book-E SPR numbers are different registers in 3.1C. 3.1C software that accesses
  them would reach the Book-E register instead:

  | SPR | Book-E (2.07B Fig. 17, PDF 1082) | 3.1C (Table 5.1, PDF 1137-1140) |
  |---|---|---|
  | 338 | LPIDR | PCR |
  | 339 | MAS5 | HEIR |
  | 1023 | MMUCR3 (A2O-specific) | PIR |

- The opcode of `tlbsrx.` (31/850) is `slbiag` in 3.1C.

The job is to make the 2.07 MMU interface unreachable from software, hypervisor included,
while keeping the 3.x registers the radix path needs.

The hard part is that the radix walker in this port runs *behind* the Book-E TLB. It still
reads several Book-E registers, and the Book-E invalidate instructions are its only
invalidation path. Those items cannot be hidden yet; §2 marks them **blocked**.

## 2. TODO table

Scope (owner, chat 2026-10-17): MMU-related SPRs, TLB instructions and A2O ERAT
instructions. Hiding means illegal in the decode, at every privilege level.

Each row is one of three kinds:
- *Candidate*: nothing in the radix path depends on it.
- *Blocked*: a prerequisite from §2.4 must land first.
- *Keep*: it is a 3.1C register or instruction.

The `Recommended` column is Claude's suggestion and is not a decision.

**RTL sites:**
- **SPR legality:** the `ill_spr_11` lists, legal at `xu_spr_cspr.v:2514-2589` and
  hypervisor at `:2591-2640`.
- **Instruction legality:** `ex1_tlb_illeg_sel`/`ex1_illegal_op` at `xu0_dec.v:1148/1258`.

### 2.1 SPRs with no radix dependency

| # | SPR | Number | 3.1C meaning of the number | Kind | Recommended | Your decision |
|---|---|---|---|---|---|---|
| S1 | MAS0, MAS1, MAS2, MAS3, MAS4, MAS6, MAS2U | 624-628, 630, 631 | undefined | Candidate | hide | |
| S2 | MAS7 | 944 | undefined | Candidate | hide | |
| S3 | MAS5 | 339 | **HEIR** | Candidate | hide | |
| S4 | MAS8 | 341 | undefined | Candidate | hide | |
| S5 | MAS5_6, MAS8_1, MAS7_3, MAS0_1 (64-bit pairs) | 348, 349, 372, 373 | undefined; 349 is AMOR | Candidate | hide | |
| S6 | LRATCFG, LRATPS, TLB0PS, EPTCFG | 342, 343, 344, 350 | undefined | Candidate | hide | |
| S7 | MMUCSR0, MMUCFG | 1012, 1015 | implementation-specific range | Candidate | hide | |
| S8 | MMUCR0 | 1020 | implementation-specific range | Candidate | hide; it only steers ERAT ops (`xu0_dec.v:1317`) | |
| S9 | MMUCR3 | 1023 | **PIR** | Candidate | hide | |
| S10 | LPER, LPERU | 56, 57 | undefined | Candidate | hide | |
| S11 | EPLC, EPSC (external PID; held in LQ) | 947, 948 | undefined | Candidate | hide; site `lq_spr_tspr.v:278-279` as well | |
| S12 | MESR1, MESR2 | 916, 917 | implementation-specific | Candidate | hide; also needs a carve-out from the 912-927 blanket range (`xu_spr_cspr.v:2055`) | |

### 2.2 SPRs the radix path depends on

| # | SPR | Number | Why it can't simply be hidden | Kind | Recommended | Your decision |
|---|---|---|---|---|---|---|
| S13 | PID | 48 | Same number as 3.1C PIDR. The walker indexes the process table with it (`mmq_rtw.v:743`). | Keep | keep as PIDR; note it is 14 bits, not 32 | |
| S14 | PTCR | 464 | 3.1C register, added by this port (`xu_spr_cspr.v:1830`) | Keep | keep | |
| S15 | LPIDR | 338 | The walker's `inv_lpid` and TLB tag LPID (`mmq.v:3928`). In 3.1C, 338 is PCR and LPIDR is 319, which A2O already uses for DVC2 (`xu_spr_cspr.v:1783`). | Blocked by P2 | move to 319, then hide 338 | |
| S16 | TLB0CFG | 688 | The radix enable is `tlb0cfg_q[44]` (`mmq_spr.v:2218`, `mmq.v:3764`). | Blocked by P3 | move the enable, then hide | |
| S17 | MMUCR1, MMUCR2 | 1021, 1022 | MMUCR2 sets the TLB probe order before a walk (`mmq_tlb_ctl.v:1284-1301`); `MMUCR2[4]` feeds the walker (`mmq.v:3915`). | Blocked by P4 | fix as internal constants, then hide | |

### 2.3 Instructions (all primary opcode 31)

| # | Instruction | XO | 3.1C meaning of the opcode | Kind | Recommended | Your decision |
|---|---|---|---|---|---|---|
| I1 | `tlbwe` | 978 | none | Candidate | hide | |
| I2 | `tlbre` | 946 | none | Candidate | hide | |
| I3 | `tlbsx`, `tlbsx.` | 914 | none | Candidate | hide | |
| I4 | `tlbsrx.` | 850 | **`slbiag`** | Candidate | hide | |
| I5 | `eratwe`, `eratre`, `eratsx[.]` (A2O-specific) | 211, 179, 147 | none in 3.1C | Candidate | hide | |
| I6 | `tlbilx`, `tlbivax` | 18, 786 | none | Blocked by P1 | hide after `tlbie` exists | |
| I7 | `eratilx`, `erativax` (A2O-specific) | 51, 819 | none in 3.1C | Blocked by P1 | hide after `tlbie` exists | |
| I8 | `tlbsync` | 566 | `tlbsync`, the same instruction | Keep | keep (`lq_dec.v:2118`) | |

### 2.4 Prerequisites

| # | Work | Why | Your decision |
|---|---|---|---|
| P1 | Decode 3.1C `tlbie` (31/306) and `tlbiel` (31/274), with RIC/PRS/R/IS (v3.1C §6.9.3.3, PDF 1208) | Neither is decoded anywhere in `a2o/rel`. Today the walker's invalidation arrives only through the Book-E snoop sequencer (`mmq.v:3927-3932`). | |
| P2 | LPIDR at 319: displace or renumber DVC2 | 3.1C §2.4 (PDF 1094) | |
| P3 | Move the radix enable out of TLB0CFG[44] | Hiding TLB0CFG would otherwise hide the enable | |
| P4 | Make MMUCR1/MMUCR2 values internal (constant or strap) | The walker and the TLB probe read them | |

## 3. Options for *how* to hide

These apply to every *Candidate* row.

| Option | What it is | For | Against |
|---|---|---|---|
| **A. Compile-time parameter** | One parameter (precedent: `hvmode`, `xu.v:1551`) gates the §2 SPRs out of the `ill_spr_11` legal lists and adds the §2 opcodes to `ex1_tlb_illeg_sel` (`xu0_dec.v:1148`) | Software cannot undo it; a Book-E build stays possible; one reviewable switch | A new parameter has to be threaded to `xu_spr_cspr` and `xu0_dec` |
| **B. Delete from the legal lists** | Remove the `_rdec`/`_wdec` terms and add the opcodes to the illegal term unconditionally | Smallest diff | No way back to a Book-E build |
| **C. Runtime SPR bit** | Like CCR2[NOTLB] (`xu0_dec.v:1148`, UM p.322) | No new parameter | A hypervisor can clear it, so it does not meet "not accessible in any way" |
| **D. Edit the `iuq_idec.v` decode table** | Clear the rows at `iuq_idec.v:1458-1465, 1217-1222` | It is the architected decode table | The table generator is not in the repo. The product terms at `:1482-5225` would need hand-editing, which is hard to review. |

Whatever option is chosen, an SPR marked illegal is already blocked from the MMU: the flush
at `xu_spr_cspr.v:994` kills the slow-ring access. `mmq_spr.v` therefore needs no legality
change.

## 4. Conclusion

- **Recommended:** option A, applied in this order:
  1. P1 to P4.
  2. Hide S15-S17 and I6-I7.
  3. Hide S1-S12 and I1-I5. This group has no dependency and could also go first.
- **Keep:** S13, S14 and I8.
- Every row above waits for its decision cell.

## 5. Limitations

### Deliberately refused (proposed; needs the owner's ruling)
- **Exception type deviates from 3.1C.** A hidden SPR gives Program/Illegal Instruction
  (PIL), because A2O has no Hypervisor Emulation Assistance (HEA) interrupt. 3.1C specifies
  something different for an undefined SPR at MSR.PR=0:
  - a no-op when LPCR.EVIRT=0;
  - an HEA interrupt when LPCR.EVIRT=1.

  Source: v3.1C §5.4.4 mtspr, PDF 1142 / p.1106. Book-E 2.07B allows the Illegal
  interrupt (§5.4.1, PDF 1084), so the chosen behaviour is Book-E-legal but not 3.1C-exact.
- **Missing 3.1C registers are not added.** LPIDR 319, LPCR 318, DSISR 18, DAR 19,
  HDSISR 306, HDAR 307 and ASDR 816 are absent from A2O. This work hides registers; it does
  not add them. Radix faults are still reported through Book-E ESR/DEAR (PROBLEMS.md item 12).

### Not yet done
- **Conflict with `PLAN.md`.** `PLAN.md:413,430,469-480` says the Book-E MMU registers are
  "kept and extended", and marks nothing for retirement. This document contradicts it.
  `PLAN.md` needs updating, or this document needs rejecting.
- **Stale comments.** `mmq_rtw.v:36,87` still say the radix enable is "MMUCR1[RXE]". It is
  `TLB0CFG[44]`.
- **Hard-coded SPR numbers elsewhere.** These become dead once the SPRs are hidden:
  `iuq_idec.v:800,5252` (mfspr MMUCR1), `xu0_dec.v:1275` and `xu_spr_cspr.v:2650`.

### Not verified
- **Not every RTL path was traced.** The ERAT-op paths through `xu0_dec` beyond the illegal
  terms were not traced. The guest-state interaction of EPCR[DGTMI] was not checked.
- **No simulation was run, and the existing tests do not cover this.**
  `run_rtw_tests.sh` exercises only `mmq_rtw.v` standalone.
- **The 2.07B privilege columns are unchecked.** They were extracted with `pdftotext` and
  not checked against the rendered PDF for TLBnPS, LRATCFG, MMUCFG and TLBnCFG.
- **The opcode conflict check is partial.** It used 3.1C Table E.1 only, not the D.14
  opcode map.

---

## Appendix: evidence

Sources:
- 2.07B: `docs/doc_copare/PowerISA_V2.07B.pdf`. PDF page = printed page + 31.
- 3.1C: `docs/doc_copare/OPF_PowerISA_v3.1C.pdf`. PDF page = printed page + 36.
- Microwatt: `microwatt/` (the local fork).

### A1. Undefined-SPR rules side by side

| State | 2.07B Book III-E (§5.4.1, §7.6.8) | 3.1C Book III (§5.4.4) | A2O today | Microwatt |
|---|---|---|---|---|
| Problem, privileged-encoded number | Privileged Program interrupt | Privileged Program interrupt | Program/PPR (`xu_spr_cspr.v:2662`) | Program (`execute1.vhdl:1644`) |
| Problem, user-encoded number | Illegal | HEA | Program/PIL | HEA (`execute1.vhdl:1654`) |
| Supervisor / hypervisor | Illegal or boundedly undefined | No-op (EVIRT=0) / HEA (EVIRT=1) | Program/PIL (`xu_spr_cspr.v:2660`) | No-op (`execute1.vhdl:1455-1466`) |

### A2. A2O decode mechanism
- **SPR legality** is one central table in `xu_spr_cspr.v`. It is not built from claims made
  by each unit. The per-SPR decodes are at `:1766-1844`. Only `ill_spr_11` is built, because
  `xu.v:1551` sets `hvmode=1, a2mode=1`.
- **Exception codes** (`xu0_dec.v:1504-1508`):
  - illegal SPR: 6
  - privileged SPR: 8
  - hypervisor SPR: 9

  Illegal has the highest priority of the three.
- **Opcode legality:**
  - Mechanism: a comment-encoded table (`iuq_idec.v:1058-1478`) with generated product
    terms (`:1482-5225`). The generator is not in the repo.
  - Path to the interrupt: `valop`, then `iuq_cpl_ctrl.v:3081-3085`, then Program, vector
    0x0E0.
- **Existing knobs:** A2O has no hide knob of any kind, compile-time or runtime.
  `hvmode=0` (`ill_spr_10`, `xu_spr_cspr.v:2405-2433`) already drops most MAS/CFG SPRs, but
  it also removes guest state, so it is too broad to use as is.

### A3. Microwatt (ISA 3.0) reference set
- **SPRs:** PID 48, PTCR 464, DSISR 18, DAR 19 and LPCR 318 (`common.vhdl:38-59`).
- **Instructions:** `tlbie`, `tlbiel`, `slbia`, `tlbsync` (`decode1.vhdl:334,390-392`).
- **Not implemented:** LPIDR, ASDR, HDAR, HDSISR and AMR/IAMR.
- **Fields not read:** PRS and R, so every `tlbie` is treated as radix and process-scoped
  (`mmu.vhdl:477-490`).
