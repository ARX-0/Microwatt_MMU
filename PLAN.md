# PLAN.md — Porting the Microwatt Radix Page-Table Walk into the A2O MMU

> Reference sources
> - **A2O**: `a2o/rel/src/verilog/work/mmq*.v`, header `a2o/rel/src/verilog/work/mmu_a2o.vh`
> - **Microwatt**: `microwatt/mmu.vhdl` @ upstream HEAD `5e4c61f`, ISA 3.1C-current
> - **Path convention:** a bare `file.v:NNN` citation means
>   `a2o/rel/src/verilog/work/file.v` for Verilog and `microwatt/file.vhdl` for VHDL.
>   Full paths are given where the file lives anywhere else.
> - `a2o/golden/src/` holds the pristine upstream A2O tree, so **every line number in this
>   document stays valid as editing begins**. Use `tools/a2o-diff.sh` to see what has
>   drifted.

---

## 0. Context and goal

This repo holds the OpenPOWER **A2O** core release plus loose MMU analysis artifacts. The
project goal is to give A2O a **Power ISA 3.1C radix multi-level page-table walk**, taken
from Microwatt's `mmu.vhdl`.

A2O today is a pure **Book-E / ISA 2.06 embedded MMU**. Its hardware tablewalker
`mmq_htw.v` performs a **single-level** "E.PT indirect TLB entry" walk: software installs an
IND=1 TLB entry whose RPN field is the real base of a flat page-table array, and the walker
issues **exactly one 8-byte load** to fetch the PTE. There is no root-pointer SPR, no level
counter, no address accumulator, no multi-level descent.

A case-insensitive grep across all of `a2o/rel/src/` for
`radix|ptcr|prtbl|rpds|rts|partition table|process table|htaborg|sdr1|pate|patb`
returns **zero hits**. There is no radix anywhere in A2O.

Microwatt implements the full ISA 3.0B/3.1 radix tree: PTCR → partition table → process
table → up to 4 levels of PDE descent → leaf PTE, with RTS/RPDS/NLS-driven variable index
widths.

### Terminology correction

The task was framed as porting into A2O's "one-hot walk". Two clarifications:

- A2O's TLB sequencer `tlb_seq_q` is **not one-hot**. It is a **6-bit Gray-coded** encoding,
  33 states used of 64 (`mmq_tlb_ctl.v:343-375`). The one-hot fields in
  A2O are `tagpos_type` (8 bits, `mmu_a2o.vh:173-180`) and `tagpos_thdid` (4 bits).
- What *is* "one-shot" is the **walk**, not the encoding — one memory access, one level.

This is good news: **31 free 6-bit encodings** (`6'b100001`–`6'b111111`) are available for
new radix states **without widening the state register or perturbing the scan chain**.

---

## 1. Repo structure — DONE

Phase 1 (repo unification) is complete. The layout below is what exists now; it is not a
proposal.

```
Microwatt_MMU/
├── PLAN.md                     this document
├── README.md                   project overview + repo map
├── tools/a2o-diff.sh           diff the editable A2O tree against pristine upstream
├── a2o/                        IBM A2O core (Verilog) — the port target
│   ├── rel/                        EDITABLE. All porting work happens here.
│   │   ├── src/verilog/work/           the core; MMU is mmq*.v, header mmu_a2o.vh
│   │   ├── src/verilog/trilib/         tri_* latch/primitive library
│   │   ├── src/vhdl/                   AXI wrappers, debug, SCOM
│   │   ├── build/ fpga/                Vivado IP + block-design TCL
│   │   └── doc/                        A2O_UM.pdf, PowerISA_V2.07B.pdf
│   ├── golden/                     PRISTINE snapshot of rel/src/. Never edited.
│   │   └── src/                        308 files, 18 MB, byte-identical to release
│   ├── GOLDEN.md                   the golden-tree rule and how to diff
│   ├── CONTRIBUTING.md
│   └── LICENSE
├── microwatt/                  Microwatt core (VHDL) — the reference implementation
│   ├── mmu.vhdl                    the radix walker being ported
│   ├── common.vhdl                 SPR numbers, MMU/loadstore record types
│   ├── loadstore1.vhdl             MMU request path, DSISR/DAR
│   ├── dcache.vhdl fetch1.vhdl     dTLB / iTLB + ERAT
│   ├── ... 75 core .vhdl files, Makefile, microwatt.core
│   └── reference/mmu_test/         radix tree setup reference (mmu.c)
└── docs/                       analysis notes and diagrams
    ├── README_MMU.md               Book-E (ISA 2.07) TLB semantics study
    ├── Inteface_README.md          full mmq.v port list, grouped by interface
    ├── MMU_tlb_comparisons.md      ISA 2.07 vs 3.1C tlbie/RIC/PRS gap analysis
    ├── mmu.vhdl.snapshot           stale older Microwatt mmu.vhdl, kept for diffing
    ├── images/  doc_copare/        diagrams; Power ISA and A2O reference PDFs
    └── *.drawio
```

### Provenance

- **`a2o/`** — OpenPOWER A2O core release, <https://git.openpower.foundation/cores/a2o>.
  Power ISA 2.07, Book III-E.
- **`microwatt/`** — <https://github.com/antonblanchard/microwatt> at commit `5e4c61f`,
  `.git` excluded, **pruned to CPU sources only** (96 files, 1.5 MB). Removed: `tests/`,
  `litedram/`, `liteeth/`, `litesdcard/`, `openocd/`, `micropython/`, `fpga/`,
  `hello_world/`, `rust_lib_demo/`, `uart16550/`, `scripts/`, `constraints/`, `media/`,
  `verilator/`, `esim/`, `sim-unisim/`. `tests/mmu/`'s text sources were kept as
  `microwatt/reference/mmu_test/` because §2.1 and §6 cite them as the radix-tree setup
  reference.

### Golden / editable split

`a2o/golden/src/` is a byte-identical snapshot of `a2o/rel/src/` as released.
`tools/a2o-diff.sh` answers *"what has changed since upstream"* regardless of how many
commits have landed — which is the question that matters when the port touches a handful of
places inside several 4000-line files. See [a2o/GOLDEN.md](a2o/GOLDEN.md).

```bash
tools/a2o-diff.sh                  # summary of changed files
tools/a2o-diff.sh --stat           # per-file line counts
tools/a2o-diff.sh mmq_tlb_ctl.v    # unified diff of one file
```

### Cleanups performed

| Item | Finding | Action taken |
|---|---|---|
| `a2o_MMU/` | Duplicate of the 14 MMU files in `a2o/rel/src/verilog/work/`; verified 14/15 byte-identical, `mmq_inval.v` differing only by a blank line. `tri_a20.vh` was an identical copy of `trilib/tri_a2o.vh` with a typo'd name. | **Deleted** (2.3 MB) |
| Root `mmu.vhdl` | 504-line stale upstream snapshot, older than `microwatt/mmu.vhdl` (1878 lines) | Moved to `docs/mmu.vhdl.snapshot` |
| `.$*.drawio.bkp` ×2 | draw.io lock files, committed | **Deleted** |
| `MMU vhdl cofe explaination.drawio` | 577-byte empty stub, typo'd filename | **Deleted** |
| Microwatt `tests/` etc. | 131 MB of tracked test binaries + vendored peripherals | **Pruned**, 149 MB → 1.5 MB |
| `README.md` image links | Absolute `github.com/ARX-0/...` URLs | Switched to relative paths |

**Not done, deliberately:** `docs/doc_copare/` still contains `A2O_UM.pdf` (an exact
duplicate of `rel/doc/A2O_UM.pdf`) and three unrelated personal files (`CMRL.pdf`,
`rental things.pdf`, `lol.jpeg`). Left alone — deleting a user's documents is their call.
Note `PowerISA_V2.07B.pdf` in the two locations is **not** a duplicate (different md5).

### Trace array note

The Microwatt copy carries a **local fork feature**: an MMU walk-trace array (SPR 704/705,
four 2048×64 BRAMs, `mmu_event_t`, `mmu.vhdl:43-49, 106-123, 1185-1198, 1311-1372,
1764-1816`) plus the widening of `sprnf`/`sprnt` from 1 to 2 bits in `common.vhdl:734-735`.
It is kept verbatim but is **not** part of the A2O port. The pure radix machinery to port is
`mmu.vhdl:29-41` (states), `351-371` (`check_perm_c`), `1378-1448` (shifter/mask
generators), `1450-1877` minus `1764-1816`.

---

## 2. Structural comparison of the two MMUs

| Aspect | Microwatt (`microwatt/mmu.vhdl`) | A2O (`mmq*.v`) |
|---|---|---|
| Architecture | ISA 3.0B/3.1 **Radix** | Book-E / ISA 2.06 **Embedded** (E, E.MF, E.LRAT, E.PT — `mmu_a2o.vh:42-52`) |
| Walk depth | Up to **4 levels**, RTS/RPDS/NLS driven | **1 level** (E.PT indirect entry) |
| Walk terminates on | `r.shift` exhaustion + leaf bit `data(62)` (`mmu.vhdl:1719-1736`) | N/A — single fetch |
| Root pointer | `PTCR` SPR → partition table → `PRTBL` (memory-resident) | **None.** Page-table base is the IND=1 TLB entry's `waypos_rpn` (PTRPN), installed by software via `tlbwe` |
| Main FSM | 12 states, `state_t` (`mmu.vhdl:29-41`) | 33 states, 6-bit Gray `tlb_seq_q` (`mmq_tlb_ctl.v:343-375`) |
| Walker FSM | Same FSM (`RADIX_LOOKUP`/`RADIX_READ_WAIT`) | Separate: `HtwSeq` 2-bit + 2× `PteSeq` 3-bit (`mmq_htw.v:164-175`) |
| Main TLB | 256 entries, 4-way, 64 sets, hashed, **4 kB only** | **512 entries, 4-way, 128 rows** (`mmu_a2o.vh:87-90`), hashed per page size, 8 sizes |
| TLB entry | 64-bit PTE + 16-bit valid/PID word | **168-bit way** (`waypos_*`, `mmu_a2o.vh:187-206`), 2× 84-bit words (74 data + 10 parity) |
| TLB tag | EA[51:20] + 12-bit PID | **122-bit tag** (`tagpos_*`, `mmu_a2o.vh:148-185`): 52b EPN, 14b PID, 8b LPID, GS/TS/PR/CM, thdid, size, 8b one-hot type |
| Match mechanism | RAM read + comparator, 4 sequential probe states | **4× matchline CAM** per row (`mmq_tlb_matchline.v:163-166`), 86-bit compare with per-field enables, pre-decoded 5-bit `cmpmask` for variable page size |
| Page-walk cache | **Yes** — 256-entry PWC caching 2M/1G/512G PDEs + 2M leaf PTEs (`mmu.vhdl:198-302`) | **None** |
| L1 translation | dTLB in `dcache.vhdl` (128e, 2-way); iTLB + 2-entry ERAT in `fetch1.vhdl` (64e, direct-mapped) | **I-ERAT** 16e (`iuq_ic_ierat.v:236-237`), **D-ERAT** 32e (`lq_derat.v:482-483`), both CAM |
| Hypervisor level | PATB **vestigial** — hardwired to partition entry 0 dword 1 (`mmu.vhdl:1846`), LPID ignored, PATS ignored, **no gRA→hRA** | **LRAT**: 8-entry fully-associative, LPID-keyed, real `mm_xu_lrat_miss` exception + `LPER` capture (`mmq_tlb_lrat.v`) |
| Memory port | Direct to dcache, **1 outstanding**, `d_out.valid` / `d_in.done` (`common.vhdl:751-765`) | `mmq_htw` → `mmq_inval` arbiter → `mm_xu_lsu_*` → `lq_imq.v` → L2. **2 core tags** (`01100`/`01101`), **1 credit token** |
| Data return | 64-bit `d_in.data`, byte-swapped in the MMU (`mmu.vhdl:1490-1494`) | 4× 128-bit quadword beats on `an_ac_reld_*`; 8 bytes selected by `pteN_score_cl_offset_q[58:60]` (`mmq_htw.v:1389-1394`) |
| R/C bits | **Checked only** (`mmu.vhdl:1700`); no writeback; software sets them | **Folded into permissions at reload** (`mmq_tlb_cmp.v:3576-3581`); no writeback path exists at all |
| Real address width | 56 bits used | **42 bits** (`` `REAL_ADDR_WIDTH 42 ``, `mmu_a2o.vh:108`) — a hard constraint |
| Page sizes | 4 K / 64 K / 2 M / 1 G | 4 K / 64 K / 1 M / 16 M / 1 G advertised (`TLB0PS = 0x00104444`); **2 M absent** |
| Faults | `invalid/badtree/segerr/perm_error/rc_error` → DSISR 33/36/44/45 (`loadstore1.vhdl:1267-1271`) | Book-E: TLB miss, PT fault, LRAT miss, permission, parity → ESR/DEAR |

### 2.1 Microwatt's radix walk — the algorithm to port

| Step | Source | Detail |
|---|---|---|
| Partition-table read | `mmu.vhdl:1846` | `addr = (PTCR & ~0xFFF) + 8` — **hardwired to partition entry 0, dword 1**. LPID/PATS unused. |
| Process-table read | `mmu.vhdl:1823-1826` | 16-byte entries; only PRTE0 read. PRTS controls how many PID bits override the base. |
| RTS extraction | `mmu.vhdl:1655-1657` | `six := '0' & data(62 downto 61) & data(7 downto 5)`; address space = `rts + 31` bits |
| RPDS / NLS | `mmu.vhdl:1668-1669`, `1720` | 5 bits; valid range **5..16** |
| Table base (NLB) | `mmu.vhdl:1670` | `pgbase = pgtbl(55 downto 8) & x"00"` — tables 256-byte aligned |
| Segment check | `mmu.vhdl:1667-1685` | `mbits=0` → invalid; `addr(63) /= addr(62)` or EA bits above `31+RTS` nonzero → segerror; `RPDS<5 or >16 or > RTS+19` → badtree |
| Index extraction | `addrshifter`, `mmu.vhdl:1380-1414` | 3-stage barrel shifter: `(addr(61:12) >> shift)(15:0)`. Stage 1 on `shift(5:4)`, stage 2 on `shift(3:2)`, stage 3 on `shift(1:0)` |
| Index mask | `addrmaskgen`, `mmu.vhdl:1417-1432` | 16-bit, seeded `0x001f`, bit *i* set for `5 <= i < mask_size` |
| PDE address | `mmu.vhdl:1828-1830` | `pgbase \| (((EA >> (shift+12)) & (2^mbits - 1)) << 3)` — 8-byte entries, index **OR'd** into base, not added |
| PDE decode | `mmu.vhdl:1692-1742` | `data(63)`=V, `data(62)`=L (1=leaf PTE, 0=directory PDE) |
| Level descent | `mmu.vhdl:1719-1736` | `shift -= NLS`; `pgbase = data(55:8) & x"00"`. **No explicit level counter** — guard is `NLS > shift` → badtree |
| Final RPN | `mmu.vhdl:1831-1833` | `pte = (pde(55:12) & ~finalmask) \| (addr(55:12) & finalmask)`, with `pde(11:0)` attributes; `finalmask` from `finalmaskgen` (`:1436-1448`), 44-bit, bit *i* set iff `i < shift` |
| Permission check | `check_perm_c`, `mmu.vhdl:351-371` | PTE bit map: `(0)=X, (1)=W, (2)=R, (3)=PRIV, (5)=CI, (7)=C, (8)=Rref`. Load: `R or W`. Store: `W and C`. Exec: `X and not CI` |
| RC check | `mmu.vhdl:1700` | `rc_ok = data(8) and (data(7) or not store)` |
| Quadrants | `mmu.vhdl:1496-1502, 1818-1822` | `addr(63)=1` → quadrant 3, `effpid=0`, uses `pgtbl3`. `addr(63)=0` → quadrant 0, uses `r.pid`/`pgtbl0`. Quadrants 1/2 rejected as segerror |
| Byte swap | `mmu.vhdl:1490-1494` | Radix structures are big-endian |

Software setup reference — `microwatt/tests/mmu/mmu.c:125-138`:
`store_pte(&part_tbl[1], proc_tbl); mtspr(PTCR, part_tbl); mtspr(PID,1);
store_pte(&proc_tbl[2*1], pgdir | 0xa000000000000009ul);` → RTS=8 (512 GB), RPDS=9.

### 2.2 A2O's existing walk — what it is replacing

`mmq_htw.v` (2864 lines) — Book-E category E.PT, **exactly one memory access**.

Field overloading on IND=1 entries (`mmq_htw.v:763-769`):

```
 tlb_way   IND=0    IND=1
  134       UX      SPSIZE0
  135       SX      SPSIZE1
  136       UW      SPSIZE2
  137       SW      SPSIZE3
  138       UR      PTRPN
  139       SR      PA52
```

Address formation (`mmq_htw.v:804-808`), 4 KB sub-pages:
`pte_ra = {30b PTRPN, PA52, EPN[44:51], 3'b000}` — 42 bits, 8-byte aligned.

Three small state machines:
- `Htw_Sequencer` 2-bit (`:572-601`): `Idle → Stg1 (load pteaddr) → Stg2 (spin on req_taken) → Idle`
- `Pte0_Sequencer` / `Pte1_Sequencer` 3-bit (`:607-681`, `:686-760`): one per outstanding load

Capacity: **4 parked walk requests** (one per thread) but only **2 in-flight loads**, because
only 2 L2 core tags exist.

### 2.3 The five real porting problems

These are the substance of the work, not the FSM transcription:

1. **No root register.** A2O has nowhere to hold PTCR or the cached PRTBL. New SPR + new
   latches required. See §3.
2. **42-bit real addresses.** Microwatt forms 56-bit PDE addresses. Either constrain the
   radix tree to the low 42 bits of RA (**recommended** — the FPGA build cannot address more
   anyway) and raise a machine check on RA ≥ 2^42, or widen `htw_lsu_addr`/`mm_xu_lsu_addr`
   through `mmq_inval.v` → `mmq.v` → `c.v` → `lq.v` → `lq_imq.v`.
3. **Dependent-load serialisation.** Only **1 LSU credit token**
   (`mmq_inval.v:1601-1608`) and **2 core tags** (`lq_imq.v:614-616`). A 4-level walk is 4
   serial L2 round-trips: `HtwSeq` 3 cycles + LQ queue + L2 latency + 4-stage reload pipe
   (~8 local cycles) **per level**. Expect 200+ cycles per cold walk. This is precisely why
   Microwatt has a page-walk cache; A2O will want one, but it is out of scope for v1.
4. **PTE → 168-bit way conversion.** Radix packs perms into PTE bits 0-8; A2O's way uses
   `waypos_usxwr[134:139]` = UX,SX,UW,SW,UR,SR. A translation function is needed. Model it on
   the existing `ptereload_req_derived_usxwr` at `mmq_tlb_cmp.v:3576-3581`, which already
   folds R/C into the permission bits.
5. **Radix leaf sizes must be demoted; 2 MB cannot be added.** *(Corrected during
   implementation — the earlier plan to "add PS21 to TLB0PS" is not achievable.)*
   Two independent limits:
   - A2O's 4-bit size code is **log4(size/1KB)** (4K=0001, 64K=0011, 1M=0101, 16M=0111,
     256M=1001, 1G=1010), so it can only express **power-of-4** sizes. 2 MB has no encoding.
   - `mmq_tlb_cmp.v:3486` builds the way's size field as
     `{1'b0, pte[ptepos_size+0 : +2]}` — only three bits survive the ptereload path, so
     **everything above 16 MB is unreachable too**, 1 GB included.

   `mmq_rtw.v` therefore installs each radix leaf at the **largest representable sub-page
   size**: 4K→4K, 64K→64K, 2M→1M, 1G→16M. Demotion is always architecturally safe — a
   smaller page maps a subset of the same translation with identical permissions — and the
   final-mask shift is taken from the *installed* size so the extra EA bits merge into the
   RPN correctly. The cost is extra TLB misses on large pages, not incorrectness. Lifting
   this needs the way-size field widened through `mmq_tlb_cmp.v:3486`/`:3527` and new
   cmpmask entries (`mmq_tlb_matchline.v:194-224`).

---

## 3. SPR map — both cores, in Microwatt conventions

### 3.0 Conventions adopted from Microwatt

All Microwatt SPR state lives in one file, `microwatt/common.vhdl`, in four constant
families:

| Family | Type | Value form | Purpose |
|---|---|---|---|
| `SPR_<MNEMONIC>` | `spr_num_t` = integer 0..1023 (`common.vhdl:30`) | **decimal** | architected SPR number |
| `<REG>_<FIELD>` | integer | **`63 - <IBM bit>`** | bit position inside an SPR |
| `RAMSPR_<NAME>` | `unsigned(2 downto 0)` | `to_unsigned(N,3)` | slot in the paired RAM file |
| `SPRSEL_<NAME>` | `std_ulogic_vector(3 downto 0)` | `4x"h"` | port on execute1's slow read mux |

Casing is `UPPER_SNAKE` for constants, `lower_snake` for the signals and record fields that
hold the same registers (`ctrl.lpcr_ld`, `r.ptcr`, `r3.dsisr`), and `lower_snake` verbs for
functions (`map_spr`, `decode_spr_num`, `assemble_lpcr`, `check_perm_c`).

**The one rule worth carrying into A2O Verilog is the `63 - N` idiom.** Bit positions are
written as an arithmetic expression against IBM big-endian numbering, never pre-computed, so
the source stays readable against the ISA text while the hardware indexes little-endian.
A2O's `mmu_a2o.vh` already uses MSB-first `[0:N]` ranges and bare positional defines
(`` `define ptepos_r 45 ``), which is the same spirit. Concretely: **new radix field defines
go in `mmu_a2o.vh` beside `ptepos_*` (`:231-240`), named `radixpos_<field>`, each carrying a
comment giving the ISA bit number.**

Two structural facts about Microwatt's convention that cannot be copied wholesale, because
all three namespaces are exactly full:

- `SPRSEL_*` is **16/16** (`common.vhdl:196-211`)
- `RAMSPR_*` is **8/8 in both halves** (`common.vhdl:159-175`)
- loadstore1's 3-bit `sprsel` is **8/8** (`loadstore1.vhdl:634-644`)

Adding an SPR on the Microwatt side needs a width increase, not just an entry. Worth knowing
if the reference implementation is ever extended.

### 3.1 How each core decodes SPRs

**Microwatt** — `decode_spr_num` (`common.vhdl:32, 967-970`) reassembles the split XFX field
as `insn(15 downto 11) & insn(20 downto 16)`, MSB-first. Two decode tables run
combinationally on *every* instruction at `decode1.vhdl:605-607`: `decode_ram_spr`
(`:403-453`) for the 8-entry paired RAM file, and `map_spr` (`:455-527`) for the slow/ctrl
SPRs. Privilege needs no table at all — `decode2.vhdl:619-621` tests SPR bit 5 directly.
Eight SPRs are re-routed to `unit := LDST` (`decode2.vhdl:444-446` read, `:465-470` write)
because they physically live outside execute1: DAR, DSISR, DAWR0/1, DAWRX0/1 in
`loadstore1.vhdl`, and **PID + PTCR in `mmu.vhdl`**. MTSPR to those also sets
`sgl_pipe := '1'` — a write to PID or PTCR must drain the pipe before it perturbs
translation.

**A2O** — two encodings coexist. The raw *swizzled* `instr[11:20]` is used in
`xu_spr_cspr.v`, `xu_spr_tspr.v`, `lq_spr_cspr.v`, `lq_spr_tspr.v`, `xu0_dec.v`,
`iuq_idec.v`, `iuq_cpl.v`, with the decimal number in a trailing comment on every line. The
*unswizzled* `slowspr_addr[0:9]`, produced at `xu_spr_cspr.v:1355`
(`{ex3_instr_q[16:20], ex3_instr_q[11:15]}`), is used in `iuq_spr.v`, `pcq_spr.v` and
`mmq_spr.v`. There is **no `SPRN_` macro set and no `case(spr…)` table** anywhere — the union
of the decode lines *is* the master list.

| File | Lines | Content |
|---|---|---|
| `a2o/rel/src/verilog/work/xu_spr_cspr.v` | 1700-1843 (`_rdec`), 1885-1955 (`_re`), 1958-2020 (`_wdec`), 2023-2060 (`_we`), 2213-2650 (priv qual) | **master core-scope table**, ~90 SPRs |
| `xu_spr_tspr.v` | 1573-1607, 1649-1665, 1716-1752 | thread-scope (SRR/CSRR/MCSRR/DBCR/G*) |
| `lq_spr_cspr.v` | 619-632 | LQ core-scope (DAC/DVC/LESR/LSUCR0/PESR/XUCR2/XUDBG) |
| `lq_spr_tspr.v` | 274-280, 295 | LQ thread-scope (ACOP/DBCR2/3/DSCR/EPLC/EPSC/HACOP) |
| **`mmq_spr.v`** | **333-380** (`parameter [0:9] Spr_Addr_*`), matches 1199-1214, updates 1281-1420, read mux 2053-2119 | **the MMU's own SPR list** |
| `iuq_spr.v` | 1395-1433 | IU slow-SPR selects |
| `pcq_spr.v` | 535-538 | pervasive (CESR1/RESR1/RESR2/SRAMD) |

Counts: Microwatt declares **92 `SPR_*` constants** (`common.vhdl:34-123`) plus two unnamed
literals, 724 LOG_ADDR and 725 LOG_DATA (`decode1.vhdl:482, 484`). A2O decodes **138
numbers**. Reproduce the A2O set with:

```bash
cd a2o/rel/src/verilog/work
grep -hoE "instr\[11:20\] == 10'b[01]{10}\);[[:space:]]*//[[:space:]]*[0-9]+" \
  xu_spr_cspr.v xu_spr_tspr.v lq_spr_cspr.v lq_spr_tspr.v \
  | grep -oE "[0-9]+$" | sort -n -u        # 138 numbers
```

### 3.2 Numbering policy

**Keep A2O's Book-E numbers. Add new registers only at verified-free slots.**

A2O's numbering is deeply wired into `xu_spr_cspr.v` privilege qualification and the debug
path. Chasing ISA 3.1 numbering would mean relocating DVC1/DVC2, IAC2-4, DBSR, TSR, MAS5 and
MMUCR3 — see §3.4 — for no functional gain in an MMU port. The consequence is that
**software needs an A2O-specific SPR map**; that is already true of A2O today (LPIDR at 338,
the MAS registers, no DSISR) so the port does not make it worse.

### 3.3 Band 1 — same number, same register in both cores

No work required. Microwatt and A2O agree:

| SPR | # | SPR | # | SPR | # |
|---|---|---|---|---|---|
| DSCR | 17 | SPRG3U | 259 | TBUW | 285 |
| DEC | 22 | TB | 268 | PVR | 287 |
| SRR0 | 26 | TBU | 269 | SIAR | 796 |
| SRR1 | 27 | SPRG0-3 | 272-275 | TAR | 815 |
| **PID** | **48** | TBLW | 284 | | |
| VRSAVE | 256 | | | | |

The MMU-relevant one is **PID = 48**. Microwatt: 12 bits (`mmu.vhdl:61`), read back
zero-extended (`:1205`). A2O: **14 bits**, per-thread `pid0_q`/`pid1_q`
(`mmq_spr.v:333, 1281-1285`), and it is the field actually compared in the TLB matchline
(`mmq_tlb_matchline.v:163`). ISA 3.1's PIDR is 32-bit. Either widen A2O's field — which
touches `` `PID_WIDTH ``, the 122-bit tag, the 168-bit way, the matchline and
`` `PID_WIDTH_ERAT 8 `` — or accept 14 bits and document the limit. **Recommend accepting 14
bits for v1**; it is not on the critical path for a working radix walker.

### 3.4 Band 2 — HARD COLLISIONS

Microwatt's number is occupied by a *different* A2O register. This is where A2O's Book-E
heritage and ISA 3.x diverge, and it extends well beyond the MMU:

| Microwatt / ISA 3.x | # | A2O occupant | A2O decode site |
|---|---|---|---|
| HSPRG0 | 304 | **DBSR** | `xu_spr_tspr.v:1579` |
| HRMOR | 313 | **IAC2** | `xu_spr_cspr.v:1791` |
| HSRR0 | 314 | **IAC3** | `xu_spr_cspr.v:1792` |
| HSRR1 | 315 | **IAC4** | `xu_spr_cspr.v:1793` |
| **LPCR** | **318** | **DVC1** | `lq_spr_cspr.v:623` |
| **LPIDR** *(ISA 3.1; absent in Microwatt)* | **319** | **DVC2** | `lq_spr_cspr.v:624` |
| HMER | 336 | **TSR** | `xu_spr_tspr.v:1604` |
| HEIR | 339 | **MAS5** | `xu_spr_cspr.v:1820` |
| PIR | 1023 | **MMUCR3** | `xu_spr_cspr.v:1831` |

The pattern: **A2O's Book-E debug block (304-319), timer block (336-343) and MMU control
block (1012-1023) sit exactly where ISA 3.x puts its hypervisor registers, HEIR, and PIR.**
A2O's own PIR is at 286 and its LPIDR at 338. The full 304-319 range is Book-E debug —

```
304 DBSR   306 DBSRWR  307 EPCR   308 DBCR0  309 DBCR1  310 DBCR2  311 MSRP
312-315 IAC1-4        316 DAC1   317 DAC2   318 DVC1   319 DVC2
```

— leaving **305 as the only free slot in the whole block**. The ISA 3.1 hypervisor set has
nowhere to land there.

**None of these collisions block the radix port**, because none of the colliding registers
is needed by it (see §3.5). They are recorded because any future ISA 3.1 compliance work
will hit them, and because assuming ISA numbering in test software would silently alias onto
data-value-compare debug registers.

### 3.5 Band 3 — in Microwatt, free in A2O

Portable at the ISA number if ever wanted:

DSISR 18, DAR 19, CFAR 28, CTRL 136, CTRLW 152, FSCR 153, DAWR0/1 180/181, CIABR 187,
DAWRX0/1 188/189, HFSCR 190, HSPRG1 305, HMEER 337, HDEXCU 455, **PTCR 464**,
HASHKEYR 468, HASHPKEYR 469, HDEXCR 471, the PMU block 768-798 *except* SIAR 796,
DEXCRU 812, DEXCR 828.

Verified-free ranges in A2O, checked against the 138-number occupied set:

```
25, 29, 305, 352-436, 448-511 (incl. 464 = PTCR), 512-543 (entire block),
604-623, 629, 632-687, 689-696, 704, 705, 706-795, 1017, 1018, 1019
```

### 3.6 Band 4 — in A2O, absent from Microwatt

Book-E machinery with no ISA 3.x counterpart. **All untouched by the port**, except where
noted:

| SPR | # | Role | Port relevance |
|---|---|---|---|
| **MMUCR0** | 1020 | ExtClass, TID_NZ, GS/TS, TLBSel, TID; HW-written by both ERATs | per-thread walk context; walker must maintain |
| **MMUCR1** | 1021 | 32 bits: IRRE/DRRE/REE/CEE, parity inject, ICTID/DCTID, TLBWE_BINV, error status. Boot `0x0C000000` | **radix-mode enable `MMUCR1[RXE]` goes here** — see §3.7 |
| **MMUCR2** | 1022 | page-size probe order, 5× 4-bit fields at `[12:31]`. Boot `0x000A7531` = {1G,16M,1M,64K,4K} | **must change if 2 M is added** (§2.3 item 5) |
| **MMUCR3** | 1023 | X-bit, R, C, ECL, Class, WLC, ResvAttr, ThdID. Boot `0x000F` | **radix reload must supply R/C here** |
| **MMUCFG** | 1015 | RO `0x08558341`: LPIDSIZE=8, RASIZE=42, PIDSIZE=13 (→14 bits) | update PIDSIZE only if PID is widened |
| **MMUCSR0** | 1012 | bit 61 `TLB0_FI`, self-clearing after the 128-row flush sweep | reuse for radix TLB flush |
| **TLB0CFG** | 688 | RO `0x0400A200`: ASSOC=4, NENTRY=512; bits 45/46/47 = PT/IND/GTWE boot latches | `tlb0cfg_ind` gates `TlbSeq_Stg11`; **add a parallel `tlb0cfg_radix`** |
| **TLB0PS** | 344 | RO `0x00104444` = 1G/16M/1M/64K/4K | **change to `0x00304444`** to advertise 2 M |
| **LRATCFG / LRATPS** | 342 / 343 | 8-entry LRAT config; 1T…1M page sizes | the A2O analogue of the partition table; **and see §5 P2-11** |
| **LPER / LPERU** | 56 / 57 | LRAT-miss capture, HW-written (`mmq_tlb_ctl.v:3218-3226`) | reuse for partition-scoped radix faults |
| **MESR1 / MESR2** | 916 / 917 | MMU error status | add radix fault status bits |
| **EPTCFG** | 350 | E.PT sub-page config (256M/64K, 1M/4K) | Book-E walker only; unchanged |
| **MAS0-MAS8** | 624-628, 630, 631, 339, 341, 944 | Book-E TLB access registers | **untouched**; `tlbwe`/`tlbre`/`tlbsx` keep working. Note **MAS5 is at 339, not 629** |
| **MAS pairs** | 348, 349, 372, 373 | 64-bit paired accesses | untouched |
| ESR / DEAR | 62 / 61 | Book-E fault status + address | **radix faults map here**, not to DSISR/DAR |
| EPCR, GSPRG0-3, GSRR0/1, GDEAR, GESR, GPIR | 307, 368-371, 378-383 | guest/hypervisor set | untouched |

### 3.7 What the port actually needs

Microwatt implements **exactly two** MMU configuration SPRs:

- **`SPR_PID` = 48** — 12 bits (`mmu.vhdl:61`)
- **`SPR_PTCR` = 464** — 64 bits stored, **only `[55:12]` used** (`mmu.vhdl:1846`:
  `addr := x"00" & r.ptcr(55 downto 12) & x"008"`). PATS and LPID are ignored; the
  partition table is read at entry 0, doubleword 1, unconditionally.

plus `LPCR` = 318 with 8 defined bits. Everything else radix needs is memory-resident:
`PRTBL`/`PGTBL` are cached copies of memory in `r.prtbl`/`r.pgtbl0`/`r.pgtbl3` with
`ptb_valid`/`pt0_valid`/`pt3_valid`, not SPRs.

**Two facts that determine the A2O design:**

1. **`LPCR[UPRT]` and `LPCR[HR]` are hardwired to `'1'`** (`execute1.vhdl:429-430`).
   Microwatt is *permanently* in radix mode with a process table — there is no way to turn
   radix off, and the MMU never consults either bit. A2O must keep Book-E working, so a mode
   bit is **not optional**. This is the one place the port cannot follow Microwatt, and it is
   why the radix enable is `MMUCR1[RXE]` rather than a ported LPCR. Since 318 is DVC1
   anyway (§3.4), the collision and the design need point the same way.
2. Microwatt has **no LPIDR, no AMR/IAMR/UAMOR/AMOR, no HDSISR/HDAR, no PSSCR, no SDR1,
   no ASDR, no TIDR, no HDEC**. `dcache.vhdl:1103` (*"we don't yet implement AMR, thus no
   KUAP"*) and `mmu.vhdl:365` (*"no IAMR, so no KUEP support for now"*) say so explicitly.
   **Key-based protection is therefore out of scope by construction** — there is nothing to
   port.

Also note two live gaps in the Microwatt fork itself, in case they confuse a reader of the
reference: `SPR_HFSCR` (190) is declared at `common.vhdl:64` but absent from `map_spr`, and
`SPR_704`/`SPR_705` have full loadstore1 + mmu plumbing but are missing from both `map_spr`
and the `unit := LDST` lists, so they are unreachable from software.

### 3.8 Consolidated verdict

| SPR | Microwatt | A2O | Verdict |
|---|---|---|---|
| **PID** | 48 (12b) | 48 (14b, per-thread) | **both, same number** — keep 48, accept 14 bits for v1 |
| **PTCR** | 464 (64b, `[55:12]` used) | — | **ABSENT → PORT to 464 (verified free)** |
| **PRTBL / PGTBL** | memory-resident, cached in MMU regs | — | **port as latches, not an SPR** |
| **PARTTBL / PATB** | derived from PTCR, vestigial | — | **not needed** — A2O's LRAT covers partition scope |
| **LPCR** | 318, 8 bits, HR/UPRT hardwired 1 | — (318 = DVC1) | **DO NOT PORT** — use `MMUCR1[RXE]` |
| **LPIDR** | absent | 338 | **A2O only** — keep 338; 319 = DVC2 |
| **DSISR / DAR** | 18 / 19 | — (ESR 62 / DEAR 61) | **map radix faults onto ESR/DEAR** |
| **AMR / IAMR / UAMOR** | absent | absent | **nothing to port** — no KUAP/KUEP in either core |
| **SDR1** | absent (25 free in A2O) | absent | not needed — radix only |
| **MAS0-8, MMUCR0-3, MMUCFG, TLB0CFG/PS, LRAT*, LPER, MESR1/2, MMUCSR0** | — | see §3.6 | **A2O only** — extend MMUCR1/2/3, TLB0CFG, TLB0PS; rest untouched |

**Net: exactly one new SPR number is claimed — PTCR at 464 — and it collides with nothing.
The nine Band-2 collisions are all outside the port's footprint.**

---

## 4. The radix walker: `mmq_rtw.v`

### 4.1 Approach

A new module `a2o/rel/src/verilog/work/mmq_rtw.v`, instantiated in `mmq.v` inside the same
`generate if (EXPAND_TLB_TYPE > 0)` block as `mmq_htw` (block opens at `mmq.v:2685`;
`mmq_htw` instantiated at `mmq.v:3681`). Mode-selected by `MMUCR1[RXE]`.

**`mmq_htw.v` is left untouched and functional.** This is the lowest-risk integration: the
Book-E path keeps working, and the new walker mirrors `mmq_htw`'s external contract exactly,
so `mmq_inval` and `mmq_tlb_ctl` need only a 2:1 mux on the mode bit.

Interface (identical shape to `mmq_htw`):

- **In:** `tlb_rtw_req_valid`, `_tag[0:121]`, `_way[84:167]` — same handoff as
  `mmq_tlb_cmp.v:5071-5089`
- **Out:** `rtw_lsu_req_valid/_ttype/_thdid/_wimge/_u/_addr`; **In:** `rtw_lsu_req_taken`
- **Out:** `ptereload_req_valid/_tag/_pte` back to `mmq_tlb_ctl` — same interface as
  `mmq_htw.v:1401-1409`
- **Out:** `rtw_quiesce` — per-thread walk-in-progress, holds the ERAT-miss stall. **Must be
  driven** or the core resumes before the reload lands (cf. `mmq_htw.v:85, 555-560`).
- **In:** `xu_ex5_flush` (`mmq.v:199`) — drives the per-slot `killed` bit (§5 P0-1).
- **Out:** `mm_xu_derat_rel_val` + the saved `itag`/`emq` — **must be driven on every
  termination path without exception**, or the LSU leaks an EMQ entry and the thread hangs
  (§5 P0-3). This is the single most important interface obligation in the module.
- **Internal:** per-slot watchdog counter (§5 P1-7) and retry counter (§5 P1-8). A2O has no
  timeout anywhere today, and a 4-5 level walk has 4-5x the opportunities to hang.

### 4.2 State mapping

| Microwatt (`mmu.vhdl:29-41`) | `mmq_rtw` | Purpose |
|---|---|---|
| `PART_TBL_READ` / `PART_TBL_WAIT` | `RtwSeq_PartRd` / `_PartWait` | Fetch PATE1 at `(PTCR & ~0xFFF) + 8` (`mmu.vhdl:1846`) |
| `PROC_TBL_READ` / `PROC_TBL_WAIT` | `RtwSeq_ProcRd` / `_ProcWait` | Fetch PRTE0 at `prtable_addr` (`mmu.vhdl:1823-1826`) |
| `SEGMENT_CHECK` | `RtwSeq_SegChk` | RPDS decode, quadrant check, tree sanity (`mmu.vhdl:1667-1685`) |
| `RADIX_LOOKUP` | `RtwSeq_Lookup` | Issue PDE load at `pgtable_addr` (`mmu.vhdl:1828-1830`) |
| `RADIX_READ_WAIT` | `RtwSeq_ReadWait` | Decode PDE: V/L/perm/RC, or descend a level (`mmu.vhdl:1691-1747`) |
| `RADIX_LOAD_TLB` | `RtwSeq_Reload` | Drive `ptereload_req_*` |
| `RADIX_FINISH` | `RtwSeq_Fault` | Raise the fault back to `mmq_tlb_ctl` |
| *(no counterpart)* | `RtwSeq_Killed` | **New, §5 P0-1.** Flushed mid-walk: retire the slot, no TLB write, no exception, but still return `mm_xu_derat_rel_*` |
| *(no counterpart)* | `RtwSeq_Timeout` | **New, §5 P1-7.** Watchdog expiry: terminal state returning `derat_rel` with a machine-check indication |
| `IDLE` / `DO_TLBIE` / `TLBWAIT` | *(not ported)* | A2O's `TlbSeq_Idle` and `mmq_inval` already cover arbitration and invalidation |

**Every entry into `RtwSeq_Lookup` must re-test the `killed` bit and the reservation** before
issuing level N+1 (§5 P0-1, P0-4, P1-6). `nonspec` is sampled once at handoff and is never
re-evaluated by the hardware, so the walker has to do it itself.

Microwatt's `TLBWAIT` arbitration (`mmu.vhdl:1588-1639`) and the whole PWC are **not ported
in v1** — A2O has no page-walk cache. Note for future work: this is where Microwatt's
`r.rereadpte` mechanism lives (`mmu.vhdl:87, 1604, 1613`), which forces a full memory walk
past the caches on a permission fault, because permissions can be *raised* without a `tlbie`.

### 4.3 Coding conventions — non-negotiable in this codebase

Use A2O's idiom throughout, or the module will not behave the same in sim and synth:

1. **State constants** as `parameter [0:N] RtwSeq_* = N'b...;` — see `mmq_tlb_ctl.v:343-375`.
2. **State register is a scan latch**, not `always @(posedge)`. Model on
   `mmq_tlb_ctl.v:4165-4181` (`tri_rlmreg_p #(.WIDTH(6), .INIT(0), .NEEDS_SRESET(1))` with
   `nclk`, `thold_b`, `sg`, `force_t`, `delay_lclkr`, `mpw1_b`, `mpw2_b`, `d_mode`, `scin`/`scout`).
3. **Scan-chain offsets** follow the `parameter … _offset = previous + WIDTH` chain
   (`mmq_tlb_ctl.v:378-500`). Add new latches at the end of the chain.
4. **Next-state logic** is one combinational `always` with an **explicit Verilog-1995
   sensitivity list** (`mmq_tlb_ctl.v:1382-1392`) and a **full default-assignment prologue**
   (`:1394-1426`). A missing sensitivity-list entry causes a silent sim/synth mismatch; a
   missing default infers a latch. These are the two failure modes to lint for.
5. **Preserve `TlbSeq_Idle == 6'b000000`.** `tlb_seq_abort` AND-masks the state vector to zero
   as its "return to Idle" mechanism (`mmq_tlb_ctl.v:1376-1378`). Any new encoding must not
   break this.

### 4.4 Datapath to transcribe from `mmu.vhdl`

| What | Source | Notes |
|---|---|---|
| RTS extraction | `mmu.vhdl:1655-1657` | `'0' & data(62:61) & data(7:5)` |
| RPDS / NLS | `mmu.vhdl:1668-1669`, `1720` | 5-bit, valid 5..16 |
| Barrel shifter | `addrshifter`, `mmu.vhdl:1380-1414` | 3-stage, `(addr(61:12) >> shift)(15:0)` |
| Index mask gen | `addrmaskgen`, `mmu.vhdl:1417-1432` | seeded `0x001f`, widened to `mask_size` |
| Final RPN mask | `finalmaskgen`, `mmu.vhdl:1436-1448` | 44-bit, bit *i* set iff `i < shift` |
| PDE address | `mmu.vhdl:1828-1830` | index **OR'd** into base, 8-byte entries |
| Level descent | `mmu.vhdl:1719-1736` | `shift -= NLS`; termination = shift exhaustion, guard = `NLS > shift` |
| Final PTE assembly | `mmu.vhdl:1831-1833` | `(pde & ~finalmask) \| (addr & finalmask)` |
| Permission check | `check_perm_c`, `mmu.vhdl:351-371` | See §2.1 bit map. Note: **no IAMR/KUEP** in Microwatt (explicit comment at `:364`) |
| Byte swap | `mmu.vhdl:1490-1494` | Radix structures are big-endian |
| Fault conditions | `mmu.vhdl:1676, 1679, 1682, 1715, 1717, 1723, 1741, 1746` | invalid / segerror / badtree / perm / rc; `perm_err` takes precedence over `rc_error` (`v.rc_error := perm_ok`) |

### 4.5 A2O-specific glue with no Microwatt counterpart

1. **Radix PTE → 168-bit way conversion.** New function alongside
   `mmq_tlb_cmp.v:3486` (lo word) / `:3527` (32-bit variant). Map radix `{X,W,R,PRIV}` and
   `{Rref,C}` onto `waypos_usxwr[134:139]`, following the R/C-folding pattern at
   `mmq_tlb_cmp.v:3576-3581`. Set `waypos_size` from the leaf `shift` value
   (0→4K, 4→64K, 9→2M, 18→1G) and `waypos_rpn[88:117]` from the assembled RPN.
2. **Address formation within 42 bits.** `rtw_lsu_addr[22:63]`. Assert / machine-check on
   RA ≥ 2^42.
3. **Cache-line beat selection.** Reuse `mmq_htw.v:1358-1400` verbatim — the 4-stage
   `tm1→t→tp1→tp2→tp3` reload pipe, `cl_offset_q[58:60]` quadword/half selection,
   `qwbeat_q[0:3]` beat tracking for ECC replay, and `score_error_q[0]=ECC / [1]=UE / [2]=retry`.
4. **Two core tags only.** Keep `mmq_htw`'s `pte0`/`pte1` machine split and the
   `pte_load_ptr_q` / `ptereload_ptr_q` pointers. Core tags are `5'b01100` / `5'b01101`
   (`mmq_htw.v:149-150`, `lq_imq.v:614-616`) and are the **only** way returning data is
   identified. A radix walk is inherently serial per request, so 2 tags = 2 concurrent walks.
5. **PTCR / PRTBL cache invalidation.** On `mtspr PTCR` clear `pt0_valid`, `pt3_valid`,
   `ptb_valid` and force TLB invalidate-all; on `mtspr PID` clear `pt0_valid` and invalidate.
   Mirrors `mmu.vhdl:1544-1555`. Note A2O's ERATs, like Microwatt's L1 TLBs, store a
   truncated PID (`` `PID_WIDTH_ERAT 8 ``) so a PID change needs a full ERAT flush.
6. **No R/C writeback path exists — and must not be added. See §5 P0-2.** `imq_arb_mmq_st_req_avail` exists but is used only for
   TLBIVAX/TLBI-COMPLETE broadcast, carrying `{lpid, 5'b0, ind, gs, lbit}` as store data
   (`lq_imq.v:610-618`). There is **no read-modify-write or atomic primitive available to the
   MMU**. Adopt A2O's existing answer: fold R/C into the permission bits at reload and take a
   permission fault, letting software set R/C — which is exactly what Microwatt does too
   (`mmu.vhdl` has no write path at all; `loadstore1.vhdl:1237-1253` re-issues the walk on a
   perm/RC error in case the PTE was updated).
   **This is a P0 constraint, not a preference:** a hardware R/C store would be an
   architecturally-visible memory write issued on behalf of a non-committed instruction, and
   A2O's `WAIT_UPDATES` machinery (`mmu_a2o.vh:52`, `mmq_spr.v:1420-1497`) covers SPR latches
   only — there is no pending-memory-write path anywhere in `mmq_*`.
7. **Per-level LRAT translation in guest mode. See §5 P2-11.** In guest mode (`gs==1`) every
   level's real address is derived from guest-writable memory and must go through
   `mmq_tlb_lrat.v` *before* the load is issued, raising `lrat_miss` on failure — reuse the
   `lrat_tag4_hit_status == 4'b1100` gate (`mmq_tlb_ctl.v:2980`). Bounds-check every derived
   address against `` `REAL_ADDR_WIDTH ``. A2O never needed this because its single walk
   address came from a hypervisor-installed indirect entry. **Security requirement, not an
   optimisation.**

### 4.6 Free state encodings

`` `TLB_SEQ_WIDTH = 6 `` (`mmu_a2o.vh:93`). `TlbSeq_Stg32 = 6'b100000` is the highest used.
**`6'b100001`–`6'b111111` — 31 encodings — are free.** No width change is needed, which
matters because widening would require bumping the two literal `6`s at
`mmq_tlb_ctl.v:4165, 4177-4178`, shifting every downstream scan offset, and widening
`tlb_ctl_dbg_seq_q` (`mmq_tlb_ctl.v:252, 3272`) and its consumer in `mmq_dbg.v`.

`mmq_inval.v:267-297` uses the same 6-bit Gray-parameter idiom for its 30 `InvSeq_*` states
if a second reference is wanted.

### 4.7 Files to modify

| File | Change |
|---|---|
| **`a2o/rel/src/verilog/work/mmq_rtw.v`** *(new)* | The radix walker |
| `a2o/rel/src/verilog/work/mmu_a2o.vh` | Add radix PDE/PTE field defines; add the 2 M page-size code; bump `` `PID_WIDTH `` if widening PID |
| `a2o/rel/src/verilog/work/mmq.v` | Instantiate `mmq_rtw` in the `generate` block at `:2685`; mux `htw_lsu_*` vs `rtw_lsu_*` and `ptereload_req_*` on `MMUCR1[RXE]`; route `an_ac_reld_*` (`:3745-3752`) to both walkers |
| `a2o/rel/src/verilog/work/mmq_tlb_ctl.v` | New `TlbSeq_Radix*` params (`:343-375`); new case arms (`:1427-2243`); sensitivity list (`:1382-1392`); default prologue (`:1394-1426`); branch in from `Stg15-Stg18` where the IND=1 path currently goes to `Stg29` (`:2174`) |
| `a2o/rel/src/verilog/work/mmq_tlb_cmp.v` | Radix-PTE→way conversion beside `:3486`/`:3527`; `tlb_rtw_req_valid` handoff beside `:5071-5089`; 2 M cmpmask |
| `a2o/rel/src/verilog/work/mmq_spr.v` | `Spr_Addr_PTCR = 10'b0111010000` (464) near `:333-366`; add to `spr_match_any_mmu` OR-tree (`:1198-1214`); register update logic (`:1281-1420`); read mux (`:2053-2073`); `TLB0PS` → `0x00304444`; `MMUCFG` PIDSIZE if widened; radix status bits in MESR1/2 |
| `a2o/rel/src/verilog/work/xu_spr_cspr.v` | `ex2_ptcr_rdec` / `_wdec` / `_re` / `_we` in the `:1767-1842` / `:1885-2060` tables; hypervisor-privilege qualification at `:2213-2650` |
| `a2o/rel/src/verilog/work/mmq_tlb_matchline.v` | 2 M `cmpmask` / `xbitmask` entries (`:194-224`) |
| `a2o/rel/src/verilog/work/mmq_inval.v` | **Must be revisited** (§5 P0-5). Mux the two walkers upstream in `mmq.v` where possible, but the six deadlock detours (`:1015, 1030, 1100, 1130, 1321, 1332`) and the token counter (`:1598-1616`) are directly implicated by 4-5x more request events. Widen the reservation-clear match (§5 P0-4). FSM `:919-1400`, mux `:1609-1712` |
| `a2o/rel/src/verilog/work/mmq_htw.v` | Reservation-clear widening (§5 P0-4), if the radix walker reuses the HTW slot/reservation scheme rather than duplicating it |

---

## 5. Out-of-order ordering constraints — READ BEFORE WRITING THE FSM

A2O is an **out-of-order, 2-threaded** core: register renaming, reservation stations, a
completion buffer, a store queue. Microwatt is **in-order and single-threaded**, and its
`mmu.vhdl` gets all of its ordering for free.

The clearest illustration: Microwatt dispatches `tlbie` **through the same FSM** as a walk
(`mmu.vhdl:1524-1525`, `1571-1574`). Because the MMU is in `DO_TLBIE`, it structurally
cannot simultaneously be in `RADIX_READ_WAIT`. A `tlbie` and a walk are mutually exclusive
by construction. One core, one FSM, one outstanding request, no races.

**That serialisation assumption evaporates in A2O.** Everything below is a consequence.
Section 4's walker design as written would produce a walker that hangs the core; the P0
items are mandatory changes, not refinements.

### 5.1 The A2O contract that must be preserved

**Rule 1 — never leave the core on behalf of a speculative request.**
`nonspec` gates the walk handoff absolutely (`mmq_tlb_cmp.v:5071-5072`) and gates even
*searching* for the indirect entry (`mmq_tlb_ctl.v:1603, 1641, 1679, 1717, 1750`).
`nonspec` does **not** mean "committed" — it means *"this request belongs to the instruction
currently next-to-complete in its thread"*, i.e. the oldest un-completed instruction
(`lq_derat.v:4628-4632`, `ex3_cp_next_tid` compared against `cp_next_itag_q`). A speculative
ERAT miss probes the TLB and is then **silently dropped**; the load recirculates and
re-requests once it becomes oldest.

What a speculative walk would cost, and why the gate exists: TLB/ERAT pollution and LRU
corruption; spurious `mm_xu_lrat_miss` / `mm_xu_pt_fault` (`mmq.v:224, 226`); machine checks
from walking a garbage PDE into a nonexistent real address; a Spectre-class timing footprint;
and — new to radix — **R/C bit writes, which are architecturally visible and cannot be
undone**.

**Rule 2 — walks are not abortable; they are made *harmless*.**
Three interlocking legs:

1. the per-slot **reservation bit** (`tagpos_wq` repurposed, `mmq_htw.v:786-793`, 11 clear
   conditions documented at `:933-957`),
2. the **`wq == 2'b10` gate** on the TLB write (`mmq_tlb_ctl.v:2980, 2985, 2990, 2995`),
3. the **never-recycled EMQ entry** (`lq_derat.v:4503-4512`).

A stale reload still returns; it just writes nothing. A multi-level walker that lengthens
the vulnerable window by ~100× must either strengthen all three legs or add real abort
capability.

### 5.2 P0 — blockers that change the `mmq_rtw.v` design

**P0-1 — The flush window is ~5 cycles; a radix walk is ~100× longer.**

`tlb_ctl_tag{1,2,3,4}_flush_sig` are **hard-wired to zero for the `derat`, `ierat`, `snoop`
and `ptereload` tag types** (`mmq_tlb_ctl.v:2332-2342`); only `tlbre`/`tlbwe`/`tlbsx`/
`tlbsrx` are flushable. The RTL states it outright at `mmq_tlb_ctl.v:2057`:
*"tag0 (ex2) tlbre,tlbwe (flushable), or ptereload (not flushable)"*. Consequently
`tlb_seq_abort` (`:1376-1378`) **can never fire for a walk**. The flush accumulation chain is
only 5 latches deep (`:926-971`), so the window closes ~5 cycles after the op enters the MMU
— a single-load walk is over before the chain even fills.

→ **Mitigation.** Add a per-slot `killed` bit in `mmq_rtw`, set from `xu_ex5_flush`
(`mmq.v:199`) matched against the slot's `thdid`. Test it **at every level boundary**: if
set, retire the slot without issuing level N+1, without writing the TLB, and without raising
an exception — but still return `mm_xu_derat_rel_*` (P0-3). **Never kill mid-load**: the L2
reload still arrives tagged `01100`/`01101` and must be drained.

**P0-2 — R/C writeback would be an uncommitted, architecturally-visible memory write.**

`WAIT_UPDATES` (`mmu_a2o.vh:52`, logic `mmq_spr.v:1420-1497`) states the design intent
plainly: *no architected state may be updated until `cp_mm_except_taken` confirms the
interrupt was actually taken*. Six per-thread pending flags hold MAS1/MAS2, LPER/LPERU and
MMUCR1 updates, released only by a **type-matched** exception-taken code
(`cp_mm_except_taken_t0[0:5]`, `mmq.v:268-277`) and cleared on `cp_flush_p1`
(`mmq_spr.v:1439, 1444, 1449, 1454, 1459, 1464`).

That machinery covers **SPR latches only**. There is no "pending memory write" path anywhere
in `mmq_*`, and the MMU→LSU port is load-only — `lq_imq.v:107` decodes ttype as
{TLBIVAX, TLBI_COMPLETE, LOAD, LOAD}.

→ **Mitigation: do not set R/C in hardware.** Take a fault and let software set them. This
is what Microwatt does too (`mmu.vhdl` has no write path at all; `loadstore1.vhdl:1237-1253`
re-issues the walk on a perm/RC error in case the PTE was updated), and it matches A2O's
existing answer of folding R/C into the permission bits at reload
(`mmq_tlb_cmp.v:3576-3581`). **This is a P0 constraint, not a preference:** "oldest in
thread" is not "committed", so even a `nonspec` request can be flushed by an older machine
check or asynchronous interrupt.

**P0-3 — The EMQ entry is held for the entire walk; there are 4, one reserved.**

An LSU ERAT-Miss-Queue entry leaves `EMQ_RPEN` only on reload, block, or POR
(`lq_derat.v:4503-4512`). A `cp_flush` sets `kill`/`mkill` but does **not** deallocate
(`:4550-4554`) — which is precisely what makes the stale-reload case safe. Entry 0 is
reserved for the oldest itag (`:4536-4541`); that is the **only** anti-starvation guarantee
anywhere in the stack.

→ **Mitigation — a hard requirement on `mmq_rtw.v`:** return `mm_xu_derat_rel_val` plus the
saved `itag` and `emq` on **every** termination path — success, page fault, badtree,
segerror, permission fault, flush-kill, ECC UE, invalidate-kill, watchdog timeout. Any path
that silently drops a request permanently leaks an EMQ entry and hangs that thread. The
existing HTW has this property on its UE path (`mmq_htw.v:645-660`) and its invalidate-kill
path (`mmq_tlb_cmp.v:4139-4141`) — preserve it.

**P0-4 — The invalidate reservation tracks only the *leaf* VA; a radix walk touches 4-5
different memory locations.**

A2O's reservation compare is a single `(lpid, pid, gs, as, sized-EPN)` match
(`htw_resvN_tag3_*_match`, `mmq_htw.v:1096-1160`). A `tlbie`/`tlbivax` arriving mid-walk may
invalidate a **directory** level whose contents were already consumed — the leaf-VA compare
will never see it. Note also that snoops beat ptereload in `TlbSeq_Idle` priority
(`mmq_tlb_ctl.v:1429-1436`), so the ordering is right but the *coverage* is not.

→ **Mitigation.** Keep A2O's scheme and widen it conservatively: clear the reservation on
**any** matching invalidate for the slot's `(lpid, pid, gs, as)` **regardless of EPN**,
because you cannot know which level was hit. This is exactly the semantics `term4`
(tlbilx T=0) already implements at `mmq_htw.v:963`. Additionally clear on RIC=2/3-style
process-table / partition-table invalidates, which have no A2O equivalent and must be added
(see `docs/MMU_tlb_comparisons.md` for the RIC/PRS decode). Preserve the ptereload holdoff
(`mmq_htw.v:1401-1403`) and the `wq==2'b10` write gate as the last line of defence. Redoing
a walk after an invalidate is correct and rare — **do not optimise it**.

**P0-5 — One LSU credit token and a 2-deep queue serialise 4-5 dependent loads.**

`lsu_tokens_q` is initialised to 1 (`mmq_inval.v:1598-1616`), and that single port is shared
by **three** consumers: page-table loads, `tlbivax` broadcasts, and `tlbsync` completes.
`MMQ_ENTRIES` is 2 (`a2o/rel/src/verilog/trilib/tri_a2o.vh:126`), matching the two PTE score
machines. The token is returned at **L2-send**, not data-return (`lq_imq.v:483-484`).

→ **Mitigation.** Each level must re-enter the `inv_seq` arbiter (`InvSeq_Stg31`,
`mmq_inval.v:1395-1403`). **Critically:** `mmq_inval` contains six deliberate *"service the
HTW load or we deadlock"* detours — `:1015, 1030, 1100, 1130, 1321, 1332` — each carrying an
explicit "could hang waiting on empty, so service it" comment. These are the only intentional
deadlock breakers in the whole MMU. With 4-5× more request events they will be exercised far
harder and **must be re-verified, not assumed**. The token counter already supports up to 3
(*"this logic provides for expansion >1"*, `:1598`); raising it and `MMQ_ENTRIES` is the
obvious relief valve.

### 5.3 P1 / P2 — design for these, lower blast radius

| # | Hazard | Evidence | Mitigation |
|---|---|---|---|
| **P1-6** | `nonspec` is sampled **once**, at handoff. "Was oldest 300 cycles ago" ≠ "is oldest now". | `mmq_tlb_cmp.v:5071-5072` | Re-evaluate at each level boundary; fold into P0-1's `killed` bit. **Never widen** the gate to hide latency. |
| **P1-7** | **No timeout anywhere in `mmq_*`.** Slot valid clears only on `pteN_reload_req_taken`. If L2 never responds: `htw_quiesce` never asserts, the EMQ entry never frees, the thread hangs forever. Every wait loop is unbounded. | `mmq_htw.v:555-560, 770-773`; `mmq_inval.v:690-694`; `mmq.v:262-266` | Per-slot watchdog forcing a terminal state (return `derat_rel` + machine-check) after N cycles. 4-5× more round trips = 4-5× more hang opportunities. |
| **P1-8** | ECC-UE livelock, amplified. The retry is one-shot and *passive* — it waits for L2 to re-send the line, does not re-issue. A persistent UE loops forever: UE → reservation cleared → ptereload discarded → load restarts → same UE. No counter, no escalation. | `mmq_htw.v:607-684, 798`; `mmq_tlb_ctl.v:2980` | Count retries per slot; escalate to `mm_xu_tlb_par_err` (`mmq.v:234`) on the 2nd or 3rd failure. |
| **P1-9** | **No store-queue coherence.** The walk bypasses the D-cache, LSQ and store queue entirely (`lq_imq.v` → `lq_arb.v:681`) and sees only L2 state. `xu_mm_lmq_stq_empty` is used **only** by the invalidate sequencer, never by the walk path. | `mmq.v:192-193`; `mmq_inval.v:1032, 1113-1122` | Document the architected requirement: store PTE → `msync` → walk. **Do not** gate `rtw_lsu_req_valid` on `stq_empty` without extending the P0-5 deadlock detours — it will deadlock against the invalidate sequencer. |
| **P2-10** | Thread starvation. 4 HTW slots are allocated round-robin **thread-agnostically** (`htw_inptr_q`); 2 PTE machines, 1 `TlbSeq`, 1 token, all shared. One thread can hold everything for thousands of cycles. | `mmq_htw.v:1288-1302, 562-569`; `mmq_tlb_ctl.v:1427`; `mmq_tlb_req.v:1079-1122` | Reserve one slot and one PTE machine per thread, mirroring the LSU's "entry 0 for the oldest itag" rule. |
| **P2-11** | **Walk addresses derived from guest-writable memory are never validated.** In A2O every walk address comes from a hypervisor-installed indirect entry — trusted by construction. In radix, levels 2..N addresses come *out of memory*. There is no LRAT check on the walk address and no bounds check against 42 bits. | `mmq_htw.v:826-832`; `mmq.v:285`; `mmq_tlb_cmp.v:4399-4407` (LRAT checked on the **result** only) | In guest mode (`gs==1`), each level's real address must go through `mmq_tlb_lrat.v` **before** the load is issued, raising `lrat_miss` on failure; reuse the `lrat_tag4_hit_status == 4'b1100` gate. Bounds-check against `` `REAL_ADDR_WIDTH ``. **This is a security requirement, not an optimisation.** |
| **P2-12** | Infinite walk-relaunch risk. `tagpos_ind` is forced to 0 on the ptereload pass, with the comment *"prevents htw re-request, ptereload is always ind=0 entry"*. | `mmq_tlb_ctl.v:2628-2646` | If a page-walk cache is added later and the walker can return a *directory* entry, this guard must be extended or `tlb_htw_req_valid` (`mmq_tlb_cmp.v:5071`) relaunches forever. |
| **P2-13** | Load-bearing invariant with no assertion: the ptereload ERAT-reload arm ignores `tag4_flush`, unlike the two arms above it. Safe today **only** because the LSU never recycles an EMQ entry while `EMQ_RPEN`. | `mmq_tlb_cmp.v:4133, 4141, 4540`; `lq_derat.v:4503` | Assert `eratm_entry_state_q[emq] == EMQ_RPEN` whenever `eratm_tlb_rel_val[emq]`. Keep the contract explicit rather than emergent. |

### 5.4 Summary — the two sentences to keep in mind

1. **Never leave the core on behalf of a speculative request, and never update architected
   state until the completion unit says the exception was taken.**
2. **Walks are not abortable — they are made harmless.** The reservation bit, the
   `wq==2'b10` TLB-write gate, and the never-recycled EMQ entry are the three legs of that
   stool. Lengthening the walk by 100× means strengthening all three.

---

## 6. Verification

No simulation flow exists in this repo today — `a2o/rel/build/` is Vivado synthesis TCL only.
This has to be built as part of the work.

1. **Lint first.**
   `verilator --lint-only -Ia2o/rel/src/verilog/trilib -Ia2o/rel/src/verilog/work a2o/rel/src/verilog/work/mmq.v`
   This catches the two classic A2O hazards from §4.3: missing sensitivity-list entries and
   missing default assignments, both of which produce silent sim/synth divergence.
2. **Unit bench for `mmq_rtw.v`.** Drive `tlb_rtw_req_*` directly; model the L2 with a
   behavioural memory returning `an_ac_reld_*` quadword beats. Port the tree layout from
   `microwatt/reference/mmu_test/mmu.c:125-138` (RTS=8 → 512 GB, RPDS=9). Cases:
   - 1 / 2 / 3 / 4-level hits
   - V=0 → page fault
   - NLS < 5, NLS > 16, NLS > shift → badtree
   - `addr(63) /= addr(62)` (quadrants 1 and 2) → segerror
   - EA bits above `31+RTS` nonzero → segerror
   - permission fail (each of load / store / exec)
   - R/C fail, and confirm perm takes precedence over rc
   - 4 K / 64 K / 2 M / 1 G leaf page sizes
   - bus error on the process-table read and on a PDE read → badtree
3. **Cross-check against Microwatt.** There is **no `mmu_tb`** in Microwatt — the MMU test
   is *software*: `microwatt/reference/mmu_test/mmu.c` built and run on the core via
   `core_tb`. Build the same page table in both benches and compare the final RPN and fault
   code. This is the highest-value check available: the reference implementation is in this
   repo, and the two walkers should agree bit-for-bit on every case in item 2.
4. **Integration in `mmq`.** With `MMUCR1[RXE]=0`, `tlbwe` an IND=1 entry and confirm
   `mmq_htw` still walks correctly (Book-E regression). Then set `RXE=1` and confirm radix.
   Confirm `rtw_quiesce` holds the ERAT stall for the full walk duration.
5. **SPR regression.** Read/write PTCR at 464 and confirm the value round-trips and that
   `done` asserts (i.e. the `spr_match_any_mmu` OR-tree was updated). Confirm DVC1/DVC2 at
   318/319, LPIDR at 338, PID at 48, and all MAS registers read back unchanged.
6. **Out-of-order cases — these are the ones that will actually break** (all from §5):
   - **Flush mid-walk at every level.** Assert `xu_ex5_flush` for the walking thread while
     level 1, 2, 3 and 4 are outstanding. Expect: no TLB write, no exception, the L2 reload
     still drained, and exactly one `mm_xu_derat_rel_val` returned (P0-1, P0-3).
   - **EMQ-entry leak check.** Instrument the bench to assert that **every** accepted
     request produces exactly one `derat_rel` — across success, every fault type,
     flush-kill, ECC UE, invalidate-kill and watchdog. A leak here hangs the thread and is
     the highest-severity failure mode in the design (P0-3).
   - **`tlbivax` mid-walk hitting a directory level**, not the leaf VA. Expect the
     reservation to clear and the ptereload to be discarded by the `wq==2'b10` gate; the
     load then restarts and re-walks against post-invalidate state (P0-4).
   - **Watchdog fires** when the modelled L2 never responds; expect a terminal state and a
     returned `derat_rel`, not a hang (P1-7).
   - **ECC UE escalation** — repeat a UE on the same line and confirm it escalates to
     `mm_xu_tlb_par_err` rather than livelocking (P1-8).
   - **Two-thread fairness.** Both threads walking concurrently; confirm neither starves on
     HTW slots, PTE machines, or the LSU token (P0-5, P2-10).
   - **Guest-mode LRAT check per level.** A corrupted PDE pointing outside the LRAT mapping
     must raise `lrat_miss`, not issue an L2 request to an arbitrary real address (P2-11).
   - **Invalidate-vs-walk deadlock.** Drive `tlbivax`/`tlbsync` concurrently with a 4-level
     walk and confirm the `mmq_inval` detour states still break the deadlock (P0-5).
7. **`mmq_rtw.v` unit tests — written and passing.** `a2o/rel/src/verilog/sim/`:
   - `run_rtw_tests.sh` — lint + both benches.
   - `tb_math.v` — the ported bit manipulation (barrel shifter, index mask, final mask,
     segment mask) against a direct little-endian model of the `mmu.vhdl` source it was
     transcribed from. 400 random vectors, all four generators match bit-for-bit.
     **This caught a real bug:** the shifter input is `addr(61:12)`, so EA63:62 must not be
     visible; the first version padded with 32 zeros instead of masking them off and
     diverged from Microwatt for every shift ≥ 35.
   - `tb_walk.v` — end-to-end walks against a behavioural L2 and a real radix tree in
     memory (RTS=17, RPDS=9 → a genuine 4-level tree). Covers: cold walk (6 loads: PATE1 +
     PRTE0 + 4 levels, correct RPN/usxwr/size), warm walk (4 loads, proving the root cache
     works), V=0 → page fault, R=0 → rc_error, NLS=2 → badtree, quadrant 1 → segerror,
     **flush mid-walk** (P0-1/P0-3: reload still returned with V=0, EMQ freed), and
     **invalidate mid-walk** (P0-4: walk discarded, reload still returned).
     **This caught a second real bug:** the kill/reservation test initially gated only the
     *request* states, so a flush or invalidate arriving during the final `ReadWait`
     completed the walk anyway. It now gates the exit from every wait state.
8. **Synthesis check.** `a2o/rel/build/tcl/create_ip_a2o_core.tcl`. Confirm the new module adds
   no unintended latches and does not create a critical path through `tlb_seq_q`.

---

## 7. Deliverables and order

1. ~~Unified repo — `a2o/`, `microwatt/`, `docs/`, plus the §1 cleanups.~~ **DONE** (§1),
   including the `a2o/golden/` snapshot and `tools/a2o-diff.sh`.
2. ~~This `PLAN.md`.~~ **DONE.**
3. SPR additions (§3.5) — small and independently testable; do these before the walker so
   PTCR is readable/writable while the walker is being brought up.
4. ~~`mmq_rtw.v`~~ **DONE** — the walker module is written, lints clean and passes its unit
   tests (see §6.7). The §4.7 modifications to the *surrounding* files (`mmq.v` instantiation
   and mux, `mmq_tlb_ctl.v` states, `mmq_tlb_cmp.v` handoff, `mmq_spr.v` PTCR) are still to do.
5. Verification infrastructure (§5).

**Order:** ~~Phase 1 (repo)~~ **done** → ~~PLAN.md~~ **done** → SPR additions → walker →
verification. Read **§5 before writing any FSM code**: the five P0 items are mandatory
changes to §4, not refinements.

### Known deferred items

- **No page-walk cache.** Microwatt's 256-entry PWC (`mmu.vhdl:198-302`) is not ported.
  Cold-walk latency will be 4 serial L2 round-trips. This is the first optimisation to
  revisit.
- **PID limited to 14 bits** unless the tag/way/matchline/ERAT widening is done.
- **Real addresses limited to 42 bits.**
- **Partition-scoped (gRA→hRA) radix-on-radix not implemented** — neither core has it.
  Microwatt's partition table is vestigial; A2O's LRAT provides the equivalent one-level
  relocation and can be left in place.
- **Trace array not ported** — remains a Microwatt-side debug aid.
- **No store-queue interlock** (§5 P1-9). The walk bypasses the D-cache, LSQ and store
  queue and sees only L2. Software must use the architected sequence: store PTE → `msync` →
  walk. Adding a hardware interlock means extending the P0-5 deadlock detours.
- **No per-thread resource reservation** (§5 P2-10). Slots, PTE machines, the `TlbSeq` and
  the LSU token are all shared thread-agnostically.
- **PWC deferred** — and if one is added later, §5 P2-12 applies: the `tagpos_ind` forcing
  at `mmq_tlb_ctl.v:2628-2646` must be extended, or a returned directory entry relaunches
  the walk forever.
- **No IAMR/AMR key protection** — absent from both cores by design (§3.7), so nothing to
  port.
