# PLAN.md — Porting the Microwatt Radix Page-Table Walk into the A2O MMU

> Reference sources
> - **A2O** (this repo): `rel/src/verilog/work/mmq*.v`, header `rel/src/verilog/work/mmu_a2o.vh`
> - **Microwatt**: `~/Documents/GitHub/microwatt/mmu.vhdl` @ HEAD `5e4c61f`, ISA 3.1C-current
> - Relative paths in this document are given as `rel/src/verilog/work/...` per convention.

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

A case-insensitive grep across all of `rel/src/` for
`radix|ptcr|prtbl|rpds|rts|partition table|process table|htaborg|sdr1|pate|patb`
returns **zero hits**. There is no radix anywhere in A2O.

Microwatt implements the full ISA 3.0B/3.1 radix tree: PTCR → partition table → process
table → up to 4 levels of PDE descent → leaf PTE, with RTS/RPDS/NLS-driven variable index
widths.

### Terminology correction

The task was framed as porting into A2O's "one-hot walk". Two clarifications:

- A2O's TLB sequencer `tlb_seq_q` is **not one-hot**. It is a **6-bit Gray-coded** encoding,
  33 states used of 64 (`rel/src/verilog/work/mmq_tlb_ctl.v:343-375`). The one-hot fields in
  A2O are `tagpos_type` (8 bits, `mmu_a2o.vh:173-180`) and `tagpos_thdid` (4 bits).
- What *is* "one-shot" is the **walk**, not the encoding — one memory access, one level.

This is good news: **31 free 6-bit encodings** (`6'b100001`–`6'b111111`) are available for
new radix states **without widening the state register or perturbing the scan chain**.

---

## 1. Repo unification (first step)

Target layout:

```
Microwatt_MMU/
├── a2o/                     <- everything currently A2O
│   ├── rel/                 (git mv rel a2o/rel)
│   ├── CONTRIBUTING.md
│   └── LICENSE
├── microwatt/               <- copy of ~/Documents/GitHub/microwatt, .git excluded
├── docs/                    <- existing analysis, content unchanged
│   ├── README_MMU.md, Inteface_README.md, MMU_tlb_comparisons.md
│   ├── *.drawio, images/, doc_copare/
│   └── mmu.vhdl.snapshot    (the stale root mmu.vhdl)
├── PLAN.md                  <- this file
└── README.md                <- updated to describe the new layout
```

Commands:

```bash
cd /home/arx-0/Documents/GitHub/Microwatt_MMU
mkdir -p a2o docs
git mv rel a2o/rel
git mv CONTRIBUTING.md LICENSE a2o/
rsync -a --exclude '.git' /home/arx-0/Documents/GitHub/microwatt/ microwatt/
```

**Import method:** plain copy with `.git` excluded (~75 MB of tracked files). Self-contained
and freely editable, which suits a port where both trees are hacked side by side.

### Cleanups to fold into the same pass

| Item | Finding | Action |
|---|---|---|
| `a2o_MMU/` | **Byte-identical duplicate** of the 14 MMU files in `rel/src/verilog/work/` (verified by `diff -q`; only delta is one blank line in `mmq_inval.v`). `a2o_MMU/tri_a20.vh` is an identical copy of `rel/src/verilog/trilib/tri_a2o.vh` with a typo'd name. | **Delete.** 2.3 MB of redundancy that will silently diverge from `rel/` once the port starts. Leave a pointer in `docs/`. |
| Root `mmu.vhdl` | 504-line **stale upstream snapshot**, older than `microwatt/mmu.vhdl` (1878 lines). Not a work product. | Move to `docs/mmu.vhdl.snapshot`. Do not mistake it for the porting source. |
| `.$*.drawio.bkp` (×2) | draw.io lock files, committed to git | Delete; add `.gitignore` with `.$*.bkp` (there is currently **no** `.gitignore`) |
| `MMU vhdl cofe explaination.drawio` | 577-byte empty stub, typo'd filename | Delete |
| `doc_copare/` (49 MB) | Contains exact duplicates of `rel/doc/A2O_UM.pdf` and `rel/doc/PowerISA_V2.07B.pdf`, plus unrelated personal files (`CMRL.pdf`, `rental things.pdf`, `lol.jpeg`) | Deduplicate; reconsider whether the PDFs belong in git |
| `README.md` image links | Absolute `github.com/ARX-0/...` URLs | Switch to relative paths so the repo renders offline |

Commit the reorg on its own branch first, so it is a clean reviewable diff separate from RTL
work.

### Trace array note

The Microwatt clone carries a **local fork feature**: a walk-trace array (SPR 704/705, four
2048×64 BRAMs, `mmu_event_t`, `mmu.vhdl:43-49, 106-123, 1185-1198, 1311-1372, 1764-1816`)
plus the widening of `sprnf`/`sprnt` from 1 to 2 bits in `common.vhdl:734-735`. It is copied
into `microwatt/` verbatim but is **not** part of the A2O port. The pure radix machinery to
port is: `mmu.vhdl:29-41` (states), `351-371` (`check_perm_c`), `1378-1448` (shifter/mask
generators), `1450-1877` minus `1764-1816`.

---

## 2. Structural comparison of the two MMUs

| Aspect | Microwatt (`microwatt/mmu.vhdl`) | A2O (`rel/src/verilog/work/mmq*.v`) |
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
5. **2 MB page size is not supported by A2O's TLB.** `TLB0PS = 0x00104444` advertises
   4 K / 64 K / 1 M / 16 M / 1 G. Radix produces 4 K / 64 K / 2 M / 1 G. Either add PS21
   (2 M) to `TLB0PS`, the hash tables (`mmq_tlb_ctl.v:1217-1274`) and the cmpmask tables
   (`mmq_tlb_matchline.v:194-224`), or shatter 2 M radix leaves into 4 K entries on reload.
   **Recommend adding 2 M** — the cmpmask scheme is already generic over power-of-2 sizes,
   and shattering discards the entire benefit of large pages.

---

## 3. SPR comparison — present vs absent vs needs porting

### 3.1 Method

A2O decodes SPRs in **two different encodings**, and both appear in the RTL:

1. **Raw swizzled instruction field** `instr[11:20]`, i.e. SPR# = `instr[16:20] || instr[11:15]`.
   Used in `xu_spr_cspr.v`, `xu_spr_tspr.v`, `lq_spr_cspr.v`, `lq_spr_tspr.v`, `xu0_dec.v`,
   `iuq_idec.v`, `iuq_cpl.v`. Every decode line carries the decimal number in a trailing
   comment.
2. **Unswizzled `slowspr_addr[0:9]`**, produced at `xu_spr_cspr.v:1355`:
   `assign xu_slowspr_addr_out = {ex3_instr_q[16:20], ex3_instr_q[11:15]};`
   Used in `iuq_spr.v`, `pcq_spr.v`, and **`mmq_spr.v`**.

There is **no `SPRN_` macro set and no `case(spr…)` table** anywhere in A2O. The union of the
decode lines below *is* the master list. Primary tables:

| File | Lines | Content |
|---|---|---|
| `rel/src/verilog/work/xu_spr_cspr.v` | 1700-1843 (`_rdec`), 1885-1955 (`_re`), 1958-2020 (`_wdec`), 2023-2060 (`_we`), 2213-2650 (priv qual) | **Master core-scope table**, ~90 SPRs |
| `rel/src/verilog/work/xu_spr_tspr.v` | 1573-1607, 1649-1665, 1716-1752 | Thread-scope (SRR/CSRR/MCSRR/DBCR/G*) |
| `rel/src/verilog/work/lq_spr_cspr.v` | 619-632 | LQ core-scope (DAC/DVC/LESR/LSUCR0/PESR/XUCR2/XUDBG) |
| `rel/src/verilog/work/lq_spr_tspr.v` | 274-280, 295 | LQ thread-scope (ACOP/DBCR2/DBCR3/DSCR/EPLC/EPSC/HACOP) |
| **`rel/src/verilog/work/mmq_spr.v`** | **333-380** (`parameter [0:9] Spr_Addr_*`), matches 1199-1214, updates 1281-1420, read mux 2053-2119 | **The MMU's own SPR list** |
| `rel/src/verilog/work/iuq_spr.v` | 1395-1433 | IU slow-SPR selects |
| `rel/src/verilog/work/pcq_spr.v` | 535-538 | Pervasive (CESR1/RESR1/RESR2/SRAMD) |

Extracting all decoded numbers from those tables yields **138 occupied SPR numbers** in A2O.

Microwatt's constants are all in `microwatt/common.vhdl:34-123`; `decode_spr_num`
(`common.vhdl:967-970`) is the standard split-field `insn(15:11) & insn(20:16)`.

### 3.2 Decision: SPR numbering policy

**Keep A2O's Book-E numbers. Add radix SPRs only at verified-free slots.**

Rationale: A2O's existing numbering is deeply wired into `xu_spr_cspr.v` privilege
qualification and the debug logic. Moving DVC1/DVC2 to free 318/319 for ISA 3.1 compliance
would touch `lq_spr_cspr.v`, `xu_spr_cspr.v` and the data-value-compare debug path for no
functional gain in the port. Consequence: **software needs an A2O-specific SPR map** — it is
not drop-in Linux-compatible. This is already true of A2O today (LPIDR at 338, MAS registers,
no DSISR) so the port does not make it worse.

### 3.3 Present in both — same number, same architectural role

| SPR | # | Microwatt | A2O | Verdict |
|---|---|---|---|---|
| **PID** | **48** | `mmu.vhdl:61`, **12 bits** (`52x"0" & r.pid`, read at `:1205`) | `mmq_spr.v:333`, **14 bits** (`spr_data[50:63]`, `:1281-1285`), **per-thread** (`pid0_q`/`pid1_q`) | **Keep 48.** Numerically identical, semantically compatible. But ISA 3.1 PIDR is 32-bit and A2O's 14-bit PID is the field actually compared in `mmq_tlb_matchline.v:163`. Either **widen to ≥20 bits** (touches `` `PID_WIDTH ``, the 122-bit tag, the 168-bit way, the matchline, and `` `PID_WIDTH_ERAT 8 ``) or accept the 14-bit limit and document it. Recommend accepting 14 bits for v1. |

### 3.4 Present in both — **different number** (hard numeric collisions)

| Register | ISA 3.1 / Microwatt # | A2O # | A2O occupant of the ISA-3.1 number | Resolution |
|---|---|---|---|---|
| **LPIDR** | **319** | **338** (`mmq_spr.v:335`, 8 bits, core-wide) | **DVC2** (`lq_spr_cspr.v:624`) | **Keep A2O's 338.** Do not decode 319. |
| **LPCR** | **318** | *(absent)* | **DVC1** (`lq_spr_cspr.v:623`) | **Do not add LPCR at 318.** Put the radix-mode control bit in `MMUCR1` instead (see §3.6). |

Microwatt note: `LPCR` (SPR 318) exists there with only 6 writable bits
(`execute1.vhdl:2198-2205`), and `LPCR[UPRT]`/`LPCR[HR]` are **hardwired to `'1'`**
(`execute1.vhdl:429-430`) and never consulted by the MMU. So there is nothing of substance to
port from LPCR.

Also note the **entire 304-319 block is Book-E debug** in A2O:

```
304 DBSR   306 DBSRWR  307 EPCR   308 DBCR0  309 DBCR1  310 DBCR2  311 MSRP
312-315 IAC1-4        316 DAC1   317 DAC2   318 DVC1   319 DVC2
```

**305 is the only free slot in 304-319.** The ISA 3.1 hypervisor block
(HSPRG0/1, HDSISR, HDAR, HSRR0/1) has nowhere to land there — a further reason not to chase
ISA 3.1 numbering.

### 3.5 Present in Microwatt, **ABSENT in A2O** — must be ported

| Register | Microwatt | A2O status | Proposed A2O # | Notes |
|---|---|---|---|---|
| **PTCR** | **464** (`common.vhdl:58`), full 64-bit reg `r.ptcr` (`mmu.vhdl:60`), written on `sprnt="01"` (`:1549-1555`), read at `:1204` | **ABSENT** | **464 — verified FREE** | Nothing in 352-436 or 448-511 is decoded anywhere in A2O. Clean adoption of the ISA number. Only `ptcr(55:12)` is used, as the PATB base. |
| **PRTBL / PGTBL** | **Not an SPR.** Memory-resident, cached in `r.prtbl` (`mmu.vhdl:1583`), `r.pgtbl0`, `r.pgtbl3` with `ptb_valid`/`pt0_valid`/`pt3_valid` | ABSENT | **none — keep memory-resident** | Mirror Microwatt: cache the fetched PRTE0 in `mmq_rtw` latches with a valid bit, invalidated on PTCR/PID write. |
| **PARTTBL / PATB** | Not an SPR — derived from PTCR | ABSENT | none | Microwatt's partition table is **vestigial**: hardwired to entry 0, dword 1 (`mmu.vhdl:1846`); LPID and PATS ignored; no gRA→hRA translation (header comment `mmu.vhdl:8-10`). |
| **DSISR** | **18** (`common.vhdl:38`), `r3.dsisr` 32-bit in `loadstore1.vhdl:164` | ABSENT (A2O uses **ESR**=62 and **DEAR**=61) | none | **Map radix fault codes onto A2O's ESR/DEAR**, not DSISR. Microwatt's DSISR bits: 33=invalid, 36=perm, 44=badtree, 45=rc_error. |
| **DAR** | **19** (`common.vhdl:39`) | ABSENT (A2O uses DEAR=61) | none | Same. |
| **SDR1** | 25 (hash MMU legacy) | ABSENT (**25 free**) | none | Radix-only port; not needed. |
| **LPIDR** | ABSENT in Microwatt entirely (`grep -rn LPID --include=*.vhdl` → nothing) | present at 338 | — | Nothing to port. |

### 3.6 Present in A2O, absent in Microwatt — relevant to the port

| SPR | # | `mmq_spr.v` | Role | Port relevance |
|---|---|---|---|---|
| **MMUCR0** | 1020 | `:336`, 20 bits | `0`=ExtClass, `1`=TID_NZ (derived), `2:3`=GS/TS, `4:5`=TLBSel, `6:19`=TID. HW-written by both ERATs | Per-thread walk context. Radix walker must maintain it. |
| **MMUCR1** | 1021 | `:337`, 32 bits | `0`IRRE `1`DRRE `2`REE `3`CEE `4`,`5` ctx-sync/isync inval disable, `6:11` parity inject, `12:15` ICTID/ITTID/DCTID/DTTID, `16`DCCD, `17`TLBWE_BINV, `18`TLBI_MSB, `19`TLBI_REJ, `20:22` err-detect (clear-on-read), `23:31` EEN. Boot `0x0C000000` | **Put the radix-mode enable here** — pick a documented free bit, call it `MMUCR1[RXE]`. This is the substitute for LPCR[HR]/[UPRT]. |
| **MMUCR2** | 1022 | `:338`, 32 bits | `[0]`=act_override; `[12:15]`=pgsize5 … `[28:31]`=pgsize1. Boot `0x000A7531` = {1G,16M,1M,64K,4K} | **Must change if 2 M is added** (§2.3 item 5). |
| **MMUCR3** | 1023 | `:339`, 15 bits | `49`=X-bit, `50:51`=R,C, `52`=ECL, `53`=TID_NZ, `54:55`=Class, `56:57`=WLC, `58:59`=ResvAttr, `60:63`=ThdID. Boot `0x000F`. Has a backdoor test mode (`:1367-1379`) | **Radix reload must supply R/C here.** |
| **MMUCFG** | 1015 | `:358`, RO | `0x08558341`: LPIDSIZE=8, RASIZE=42, LRAT/TWC boot bits, PIDSIZE=13 (→14 bits), NTLBS=0, MAVN=1 | Update PIDSIZE if PID is widened. |
| **MMUCSR0** | 1012 | `:359` | Only bit 61 `TLB0_FI`; set by write, **cleared by HW** when the 128-row flush sweep completes | Reuse for radix TLB flush. |
| **TLB0CFG** | 688 | `:360`, RO except boot bits | `0x0400A200`: ASSOC=4, NENTRY=512, IPROT=1, HES=1; bits 45/46/47 = PT/IND/GTWE from boot latches | `tlb0cfg_ind` gates entry to `TlbSeq_Stg11` (`mmq_tlb_ctl.v:1603,1641,1679,1717,1750`). **Add a parallel `tlb0cfg_radix` bit** to gate the new radix states. |
| **TLB0PS** | 344 | `:361`, RO | `0x00104444` = PS20(1G), PS14(16M), PS10(1M), PS6(64K), PS2(4K) | **Change to `0x00304444`** to advertise 2 M. |
| **LRATCFG** | 342 | `:362`, RO | `0x00542008`: fully-assoc, LASIZE=42, LPID=1, NENTRY=8 | The A2O analogue of the partition table. |
| **LRATPS** | 343 | `:363`, RO | `0x51544400` = 1T/256G/16G/4G/1G/256M/16M/1M | |
| **EPTCFG** | 350 | `:364`, RO | `0x00091942`: PS1=256M/SPS1=64K, PS0=1M/SPS0=4K | Book-E walker only; unchanged. |
| **LPER / LPERU** | 56 / 57 | `:365-366` | LRAT-miss error capture; HW-written on LRAT miss (`mmq_tlb_ctl.v:3218-3226`) | Reusable for radix partition-scoped faults. |
| **MESR1 / MESR2** | 916 / 917 | `:342-343` | MMU error status | **Add radix fault reporting bits here.** |
| **MAS0-MAS8** | 624, 625, 626, 627, 628, 630, 631, 339, 341, 944 | `:344-353` | Book-E TLB access registers | **Untouched.** Radix does not use MAS; `tlbwe`/`tlbre`/`tlbsx` keep working. Note **MAS5 is at 339, not 629** — 629 is free. |
| **MAS pairs (64-bit)** | 348 MAS5_MAS6, 349 MAS8_MAS1, 372 MAS7_MAS3, 373 MAS0_MAS1 | `:354-357` | Paired 64-bit accesses, high half at `:2104-2119` | Untouched. |

MMU SPR hit detection: `spr_match_any_mmu` at `mmq_spr.v:1198-1214` is the OR of all 30
addresses `mmq_spr` owns; when unset, `mmq_spr` forwards the slowspr bus onward
(`:2073`). **A new PTCR must be added to this OR-tree** or its `done` will never assert.

Access path: `xu_mm_slowspr_{val,rw,etid,addr,data,done}` in (`mmq_spr.v:307-313`) →
3-deep latch pipeline `_in_q` → `_int_q` → `_out_q` → `mm_iu_slowspr_*` out
(`:2069-2074, 2121-2126`). `spr_ctl[0]`=val, `[1]`=rw (0=write, 1=read), `[2]`=done.

### 3.7 Verified-free SPR numbers in A2O

Checked against the extracted 138-number occupied set:

```
25, 29, 305,
352-436,  448-511   (includes 464 = PTCR)
512-543              (entire block, nothing decoded)
604-623, 629, 632-687, 689-696
704, 705, 706-795
1017, 1018, 1019
```

Only **PTCR = 464** is strictly required by the port. If a radix walk-trace register is ever
wanted, **704/705 are free in A2O** and happen to match the numbers the Microwatt fork
already uses for its trace array — a convenient convention even though the trace array itself
is not being ported.

### 3.8 Consolidated present / absent / port table

| SPR | Microwatt | A2O | Verdict |
|---|---|---|---|
| **PID** | 48 (12b) | 48 (14b, per-thread) | **Present in both, same number.** Keep 48. Optionally widen the A2O field. |
| **PTCR** | 464 | — | **ABSENT in A2O → PORT to 464 (verified free).** |
| **PRTBL / PGTBL** | memory-resident, cached in MMU regs | — | **ABSENT → port as latches, not an SPR.** |
| **PARTTBL / PATB** | derived from PTCR, vestigial | — | **ABSENT → not needed** (A2O's LRAT covers partition scope). |
| **LPCR** | 318 (6 writable bits, HR/UPRT hardwired) | — | **DO NOT PORT.** 318 = DVC1. Use an `MMUCR1[RXE]` bit instead. |
| **LPIDR** | — | **338** | **A2O only.** Keep 338; 319 = DVC2. |
| **DSISR / DAR** | 18 / 19 | — (ESR 62 / DEAR 61) | **Map radix faults onto A2O ESR/DEAR.** |
| **SDR1** | 25 | — (25 free) | Not needed (radix-only). |
| **MAS0-MAS8 + 4 pairs** | — | 624-628, 630, 631, 339, 341, 944, 348, 349, 372, 373 | **A2O only. Untouched.** |
| **MMUCR0-3** | — | 1020-1023 | **A2O only. Extend MMUCR1 (mode bit), MMUCR2 (page sizes), MMUCR3 (R/C).** |
| **MMUCFG / TLB0CFG / TLB0PS** | — | 1015 / 688 / 344 | **A2O only. Update constants** (PIDSIZE, radix-enable bit, 2 M). |
| **LRATCFG / LRATPS / LPER / LPERU** | — | 342 / 343 / 56 / 57 | **A2O only. Reuse for partition-scoped radix faults.** |
| **MMUCSR0** | — | 1012 | **A2O only. Reuse for radix TLB flush.** |
| **MESR1 / MESR2** | — | 916 / 917 | **A2O only. Add radix fault status bits.** |

**Net result: exactly one new SPR number is claimed — PTCR at 464. There are no numeric
collisions introduced by the port.**

---

## 4. The radix walker: `mmq_rtw.v`

### 4.1 Approach

A new module `rel/src/verilog/work/mmq_rtw.v`, instantiated in `mmq.v` inside the same
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
| `IDLE` / `DO_TLBIE` / `TLBWAIT` | *(not ported)* | A2O's `TlbSeq_Idle` and `mmq_inval` already cover arbitration and invalidation |

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
6. **No R/C writeback path exists.** `imq_arb_mmq_st_req_avail` exists but is used only for
   TLBIVAX/TLBI-COMPLETE broadcast, carrying `{lpid, 5'b0, ind, gs, lbit}` as store data
   (`lq_imq.v:610-618`). There is **no read-modify-write or atomic primitive available to the
   MMU**. Adopt A2O's existing answer: fold R/C into the permission bits at reload and take a
   permission fault, letting software set R/C — which is exactly what Microwatt does too
   (`mmu.vhdl` has no write path at all; `loadstore1.vhdl:1237-1253` re-issues the walk on a
   perm/RC error in case the PTE was updated).

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
| **`rel/src/verilog/work/mmq_rtw.v`** *(new)* | The radix walker |
| `rel/src/verilog/work/mmu_a2o.vh` | Add radix PDE/PTE field defines; add the 2 M page-size code; bump `` `PID_WIDTH `` if widening PID |
| `rel/src/verilog/work/mmq.v` | Instantiate `mmq_rtw` in the `generate` block at `:2685`; mux `htw_lsu_*` vs `rtw_lsu_*` and `ptereload_req_*` on `MMUCR1[RXE]`; route `an_ac_reld_*` (`:3745-3752`) to both walkers |
| `rel/src/verilog/work/mmq_tlb_ctl.v` | New `TlbSeq_Radix*` params (`:343-375`); new case arms (`:1427-2243`); sensitivity list (`:1382-1392`); default prologue (`:1394-1426`); branch in from `Stg15-Stg18` where the IND=1 path currently goes to `Stg29` (`:2174`) |
| `rel/src/verilog/work/mmq_tlb_cmp.v` | Radix-PTE→way conversion beside `:3486`/`:3527`; `tlb_rtw_req_valid` handoff beside `:5071-5089`; 2 M cmpmask |
| `rel/src/verilog/work/mmq_spr.v` | `Spr_Addr_PTCR = 10'b0111010000` (464) near `:333-366`; add to `spr_match_any_mmu` OR-tree (`:1198-1214`); register update logic (`:1281-1420`); read mux (`:2053-2073`); `TLB0PS` → `0x00304444`; `MMUCFG` PIDSIZE if widened; radix status bits in MESR1/2 |
| `rel/src/verilog/work/xu_spr_cspr.v` | `ex2_ptcr_rdec` / `_wdec` / `_re` / `_we` in the `:1767-1842` / `:1885-2060` tables; hypervisor-privilege qualification at `:2213-2650` |
| `rel/src/verilog/work/mmq_tlb_matchline.v` | 2 M `cmpmask` / `xbitmask` entries (`:194-224`) |
| `rel/src/verilog/work/mmq_inval.v` | **Preferably untouched** — mux the two walkers upstream in `mmq.v`. If a fourth arbiter user is added instead: FSM `:919-1400`, mux `:1609-1712`, token counter `:1601-1608` |

---

## 5. Verification

No simulation flow exists in this repo today — `rel/build/` is Vivado synthesis TCL only.
This has to be built as part of the work.

1. **Lint first.**
   `verilator --lint-only -Irel/src/verilog/trilib -Irel/src/verilog/work rel/src/verilog/work/mmq.v`
   This catches the two classic A2O hazards from §4.3: missing sensitivity-list entries and
   missing default assignments, both of which produce silent sim/synth divergence.
2. **Unit bench for `mmq_rtw.v`.** Drive `tlb_rtw_req_*` directly; model the L2 with a
   behavioural memory returning `an_ac_reld_*` quadword beats. Port the tree layout from
   `microwatt/tests/mmu/mmu.c:125-138` (RTS=8 → 512 GB, RPDS=9). Cases:
   - 1 / 2 / 3 / 4-level hits
   - V=0 → page fault
   - NLS < 5, NLS > 16, NLS > shift → badtree
   - `addr(63) /= addr(62)` (quadrants 1 and 2) → segerror
   - EA bits above `31+RTS` nonzero → segerror
   - permission fail (each of load / store / exec)
   - R/C fail, and confirm perm takes precedence over rc
   - 4 K / 64 K / 2 M / 1 G leaf page sizes
   - bus error on the process-table read and on a PDE read → badtree
3. **Cross-check against Microwatt.** Run the identical tree through Microwatt's own
   `mmu_tb` / `make tests` in `microwatt/` and compare the final RPN and fault code. This is
   the highest-value check available — the reference implementation is in the same repo.
4. **Integration in `mmq`.** With `MMUCR1[RXE]=0`, `tlbwe` an IND=1 entry and confirm
   `mmq_htw` still walks correctly (Book-E regression). Then set `RXE=1` and confirm radix.
   Confirm `rtw_quiesce` holds the ERAT stall for the full walk duration.
5. **SPR regression.** Read/write PTCR at 464 and confirm the value round-trips and that
   `done` asserts (i.e. the `spr_match_any_mmu` OR-tree was updated). Confirm DVC1/DVC2 at
   318/319, LPIDR at 338, PID at 48, and all MAS registers read back unchanged.
6. **Synthesis check.** `rel/build/tcl/create_ip_a2o_core.tcl`. Confirm the new module adds
   no unintended latches and does not create a critical path through `tlb_seq_q`.

---

## 6. Deliverables and order

1. Unified repo — `a2o/`, `microwatt/`, `docs/`, plus the §1 cleanups. **One branch, one
   reviewable commit.**
2. This `PLAN.md`.
3. SPR additions (§3.5) — small and independently testable; do these before the walker so
   PTCR is readable/writable while the walker is being brought up.
4. `mmq_rtw.v` and the §4.7 file modifications.
5. Verification infrastructure (§5).

**Order:** Phase 1 (repo) → PLAN.md → SPR additions → walker → verification.

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
