"""mmq-level radix test: TLB miss -> radix walk reloads the TLB -> same EA hits.

Every test follows the same three events on the real mmq hierarchy
(mmq_tlb_req -> mmq_tlb_ctl -> mmq_tlb_cmp -> mmq_rtw -> ptereload -> TLB array):

  EVENT 1  an ERAT miss reaches the TLB and misses; mmq_tlb_cmp raises
           tlb_rtw_req_valid (work/mmq_tlb_cmp.v:5092).
  EVENT 2  mmq_rtw walks the radix tree through the behavioural L2 below, returns a
           ptereload, mmq_tlb_ctl writes a TLB way, and the ERAT receives a
           "miss done" reload with wren=0 -- no entry, by A2O design
           (mmq_tlb_cmp.v:4046-4049; the LQ writes only on wren=1, lq_derat.v:2473).
  EVENT 3  the instruction's replay, modelled by re-issuing the same request.  PASS
           only if it is answered from the TLB: an ERAT reload with wren=1, the walked
           RPN and page size, no tlb_rtw_req_valid, no L2 load.

A failure is one of: an assertion below, a WATCHDOG (a wait exceeded its cycle
budget -- SimTimeoutError), or the simulator being killed by the `timeout` wrapper in
run_rtw_tests.sh.

The radix tree mirrors sim/tb_walk.v:185-212 (RTS=17, 9-9-9-9 levels, 4 KB leaves).

Notes that matter for reading the results:
  * RESET DOES NOT CLEAR THE TLB.  The TLB is a block RAM (RAMB16_S36_S36); sreset
    only resets its output register, as in hardware, where boot software invalidates
    the TLB.  Every test therefore uses its own EAs, so no test depends on another.
  * THREADS=1 (trilib/tri_a2o.vh:47): the ERAT ports carry one thread, so a
    thread-ID mismatch (M7) cannot be produced at mmq level.
  * pid_match / lpid_match wildcard an entry whose PID / LPID is 0
    (work/mmq_tlb_matchline.v:563,566), so mismatch tests use non-zero values.
"""

import os
import re

import cocotb
from cocotb.result import SimTimeoutError
from cocotb.triggers import Event, Timer, with_timeout

# ----------------------------------------------------------------------------
# constants (sources cited)
# ----------------------------------------------------------------------------
SPR_PTCR = 0b0111010000          # work/mmq_spr.v:344
SPR_LPIDR = 0b0101010010         # work/mmq_spr.v:339 (LPIDR, SPR 338)
ERAT_SIZE = {0: 0b001, 4: 0b011, 8: 0b101, 12: 0b111}   # mmq_tlb_cmp.v:401-404, keyed by shift
CORE_TAG0 = 0b01100              # work/mmq_rtw.v:185  (context 0, lsu ttype Rd0)
CORE_TAG1 = 0b01101              # work/mmq_rtw.v:186  (context 1, lsu ttype Rd1)
ERAT_REL_W = 132                 # work/mmu_a2o.vh:80
ERATPOS = {                      # work/mmu_a2o.vh:208-229, big-endian positions
    "epn": (0, 52), "size": (53, 3), "v": (56, 1), "wren": (65, 1), "rpn": (70, 30),
    "usxwr": (116, 6), "gs": (122, 1), "ts": (123, 1),
}
PTEPOS_SIZE = 52                 # work/mmu_a2o.vh ptepos_size (see 03-datapath §3.5)
PTE_W = 64

BUDGET_WALK = 20000              # cycles allowed for EVENT 1 -> EVENT 2
BUDGET_HIT = 2000                # cycles allowed for EVENT 3
QUIET = 500                      # cycles a negative test watches for activity

# radix tree layout, as tb_walk.v:25-31
PTCR_BASE = 0x0010_0000
PROC_BASE = 0x0020_0000
L1_BASE = 0x0030_0000
L2_BASE = 0x0040_0000
L3_BASE = 0x0050_0000
L4_BASE = 0x0060_0000            # 4 KB leaves, NLS=9
L4B_BASE = 0x0068_0000           # 64 KB leaves, NLS=5 (reached from L3 index 4)
TARGET_4K = 0x0080_0000
TARGET_64K = 0x00A0_0000

M55_12 = ((1 << 56) - 1) & ~((1 << 12) - 1)
M55_8 = ((1 << 56) - 1) & ~((1 << 8) - 1)


# radix field builders, Microwatt little-endian numbering (tb_walk.v:34-49)
def mk_pde(nlb, nls):
    return (1 << 63) | (nlb & M55_8) | (nls & 0x1F)


def mk_pte(ra, r=1, c=1, x=1, w=1, rd=1, priv=0, v=1):
    return ((v << 63) | (1 << 62) | (ra & M55_12) | (r << 8) | (c << 7) |
            (priv << 3) | (rd << 2) | (w << 1) | x)


def mk_prte(base, rts, rpds):
    return (((rts >> 3) & 3) << 61) | (base & M55_12) | ((rts & 7) << 5) | (rpds & 0x1F)


def ea_4k(i):
    """L1=1 L2=2 L3=3 L4=i  ->  leaf at L4_BASE + 8*i, RA = TARGET_4K + i*4K."""
    return (1 << 39) | (2 << 30) | (3 << 21) | (i << 12)


def ea_64k(j, k):
    """L1=1 L2=2 L3=4 L4B=j, 4K sub-page k  ->  RA = TARGET_64K + j*64K + k*4K."""
    return (1 << 39) | (2 << 30) | (4 << 21) | (j << 16) | (k << 12)


def field(vec, width, pos, w):
    """Extract a big-endian [pos : pos+w-1] field from a width-bit vector value."""
    return (vec >> (width - pos - w)) & ((1 << w) - 1)


# ----------------------------------------------------------------------------
# harness
# ----------------------------------------------------------------------------
class Tb:
    def __init__(self, dut):
        self.dut = dut
        self.log = dut._log
        self.cycle = 0
        self._fall = Event()
        self.rst = 1
        self.mem = {}
        self.l2_stall = False
        self.nloads = 0
        self.loads = []
        self.ev = []                      # (cycle, name, value) activity record

    # ---- clocks: nclk[0]=clk, nclk[1]=sreset, nclk[2]=clk2x (work/c_wrapper.v:373-375)
    # nclk is [0:5] big-endian, so nclk[0] is the MSB of the integer value.
    def _nclk(self, clk, clk2x):
        self.dut.nclk.value = (clk << 5) | (self.rst << 4) | (clk2x << 3)

    async def _clockgen(self):
        while True:
            self._nclk(1, 1)
            await Timer(2500, "ps")
            self._nclk(1, 0)
            await Timer(2500, "ps")
            self._nclk(0, 1)              # falling edge of clk: drive & sample point
            self.cycle += 1
            ev, self._fall = self._fall, Event()
            ev.set()
            await Timer(2500, "ps")
            self._nclk(0, 0)
            await Timer(2500, "ps")

    async def tick(self, n=1):
        for _ in range(n):
            await self._fall.wait()

    # ---- tie every input low, then set the functional-mode exceptions
    def _tie_inputs(self):
        src = os.path.join(os.path.dirname(__file__), "..", "..", "work", "mmq.v")
        with open(src) as f:
            text = f.read()
        head = text[:text.index(");")]           # the port list
        for name in re.findall(r"^\s*input\s*(?:\[[^\]]*\])?\s*(\w+)", head, re.M):
            # ports inside `ifdef blocks (e.g. *_t1 when THREADS=1) are not elaborated
            if name != "nclk" and hasattr(self.dut, name):
                getattr(self.dut, name).value = 0
        d = self.dut
        d.tc_ac_scan_dis_dc_b.value = 1
        d.xu_mm_hid_mmu_mode.value = 0           # 0 = MMU mode (work/mmq_inval.v:256)
        d.xu_mm_lmq_stq_empty.value = 1
        d.iu_mm_lmq_empty.value = 1

    # ---- behavioural partner logic, sampled/driven on the falling edge
    async def _partners(self):
        d = self.dut
        pend = []                                 # [due_cycle, addr, ttype]
        token_due = []
        while True:
            await self.tick()
            # handshake acks, one cycle behind their requests
            d.iu_mm_hold_ack.value = d.mm_iu_hold_req.value
            d.iu_mm_bus_snoop_hold_ack.value = d.mm_iu_bus_snoop_hold_req.value
            d.iu_mm_ierat_snoop_ack.value = d.mm_iu_ierat_snoop_val.value
            d.xu_mm_derat_snoop_ack.value = d.mm_xu_derat_snoop_val.value

            # L2: accept a load request, return its doubleword 3 cycles later
            d.an_ac_reld_data_vld.value = 0
            d.an_ac_reld_crit_qw.value = 0
            d.xu_mm_lsu_token.value = 0
            if int(d.mm_xu_lsu_req.value) != 0 and not self.l2_stall:
                addr = int(d.mm_xu_lsu_addr.value)
                ttype = int(d.mm_xu_lsu_ttype.value)
                self.nloads += 1
                self.loads.append(addr)
                self.log.info("    [L2] load %d addr=%011x data=%016x",
                              self.nloads, addr, self.mem.get(addr & ~7, 0))
                pend.append([self.cycle + 3, addr, ttype])
            if pend and pend[0][0] <= self.cycle:
                _, addr, ttype = pend.pop(0)
                dw = self.mem.get(addr & ~7, 0)
                d.an_ac_reld_core_tag.value = CORE_TAG1 if ttype == 3 else CORE_TAG0
                d.an_ac_reld_qw.value = (addr >> 4) & 3
                d.an_ac_reld_data.value = (dw << 64) if (addr & 8) == 0 else dw
                d.an_ac_reld_data_vld.value = 1
                d.an_ac_reld_crit_qw.value = 1
                token_due.append(self.cycle + 2)  # LSU credit back after the reload
            if token_due and token_due[0] <= self.cycle:
                token_due.pop(0)
                d.xu_mm_lsu_token.value = 1

    # ---- activity monitor: everything the checks look at
    async def _monitor(self):
        d = self.dut
        cmp = d.tlb_gen_logic.mmq_tlb_cmp
        probes = [
            ("rtw_req", d.tlb_rtw_req_valid),
            ("ptereload", d.ptereload_req_valid),
            ("tlb_write", d.tlb_write),
            ("derat_rel", d.mm_xu_derat_rel_val),
            ("ierat_rel", d.mm_iu_ierat_rel_val),
            ("tlb_miss", d.mm_xu_tlb_miss),
            ("pt_fault", d.mm_xu_pt_fault),
            ("lrat_miss", d.mm_xu_lrat_miss),
            ("tlb_inelig", d.mm_xu_tlb_inelig),
            ("rtw_mchk", d.rtw_mchk_sig),
            ("wayhit", cmp.tlb_tag4_wayhit_q),
        ]
        while True:
            await self.tick()
            for name, h in probes:
                v = h.value
                if not v.is_resolvable:
                    # an x/z is never counted as the event itself; it is recorded
                    # under its own name so a floating net cannot fake a pass
                    self.ev.append((self.cycle, name + ":xz", str(v)))
                elif int(v) != 0:
                    self.ev.append((self.cycle, name, int(v)))
            if int(d.ptereload_req_valid.value):
                self.ev.append((self.cycle, "pte", int(d.ptereload_req_pte.value)))
            for side, val, dat in (("derat", d.mm_xu_derat_rel_val, d.mm_xu_derat_rel_data),
                                   ("ierat", d.mm_iu_ierat_rel_val, d.mm_iu_ierat_rel_data)):
                if val.value.is_resolvable and (int(val.value) & 1):
                    self.ev.append((self.cycle, side + "_data", int(dat.value)))

    def seen(self, name, since):
        return [(c, v) for (c, n, v) in self.ev if n == name and c > since]

    # ---- bring-up
    async def start(self):
        self._tie_inputs()
        self.rst = 1
        cocotb.start_soon(self._clockgen())
        await self.tick(8)
        self.rst = 0
        await self.tick(4)
        cocotb.start_soon(self._partners())
        cocotb.start_soon(self._monitor())
        await self.tick(20)
        self.build_tree()
        await self.spr_write(SPR_PTCR, PTCR_BASE)
        got = await self.spr_read(SPR_PTCR)
        assert got == PTCR_BASE, f"PTCR readback {got:#x} != {PTCR_BASE:#x}"
        self.log.info("PTCR written and read back over slowspr: %#x", got)

    def build_tree(self):
        m = self.mem
        m[PTCR_BASE + 8] = PROC_BASE | 9                     # PATE1: PRTB, PRTS=9
        for pid in (0, 5, 6):                                # PRTE0 per PID, 16-byte stride
            m[PROC_BASE + 16 * pid] = mk_prte(L1_BASE, 17, 9)
        m[L1_BASE + 8 * 1] = mk_pde(L2_BASE, 9)
        m[L2_BASE + 8 * 2] = mk_pde(L3_BASE, 9)
        m[L3_BASE + 8 * 3] = mk_pde(L4_BASE, 9)
        m[L3_BASE + 8 * 4] = mk_pde(L4B_BASE, 5)            # NLS=5 -> 64 KB leaves
        for i in range(64):
            m[L4_BASE + 8 * i] = mk_pte(TARGET_4K + i * 0x1000)
        for j in range(32):
            m[L4B_BASE + 8 * j] = mk_pte(TARGET_64K + j * 0x10000)

    # ---- slowspr ring (work/mmq_spr.v:1203-1212, 1424)
    async def spr_write(self, addr, data):
        d = self.dut
        d.slowspr_rw_in.value = 0
        d.slowspr_etid_in.value = 0
        d.slowspr_addr_in.value = addr
        d.slowspr_data_in.value = data
        d.slowspr_done_in.value = 0
        d.slowspr_val_in.value = 1
        await self.tick()
        d.slowspr_val_in.value = 0
        await self.tick(8)

    async def spr_read(self, addr):
        d = self.dut
        d.slowspr_rw_in.value = 1
        d.slowspr_etid_in.value = 0
        d.slowspr_addr_in.value = addr
        d.slowspr_data_in.value = 0
        d.slowspr_done_in.value = 0
        d.slowspr_val_in.value = 1
        await self.tick()
        d.slowspr_val_in.value = 0
        for _ in range(20):
            await self.tick()
            if int(d.slowspr_val_out.value) and int(d.slowspr_done_out.value):
                return int(d.slowspr_data_out.value)
        raise AssertionError("slowspr read of PTCR never returned done")

    # ---- miss injection (work/mmq_tlb_req.v:691-722, 853-878)
    async def request(self, side, ea, pid=0, lpid=0, pr=0, gs=0, as_=0, nonspec=1):
        d = self.dut
        state = (pr << 3) | (gs << 2) | (as_ << 1) | 1       # {pr, gs, as, cm}
        epn = ea >> 12
        if side == "derat":
            d.xu_mm_derat_epn.value = epn
            d.xu_mm_derat_thdid.value = 1
            d.xu_mm_derat_ttype.value = 0
            d.xu_mm_derat_state.value = state
            d.xu_mm_derat_tid.value = pid
            d.xu_mm_derat_lpid.value = lpid
            d.lq_mm_derat_req_nonspec.value = nonspec
            d.lq_mm_derat_req_emq.value = 0b1000
            d.xu_mm_derat_req.value = 1
            await self.tick()
            d.xu_mm_derat_req.value = 0
        else:
            d.iu_mm_ierat_epn.value = epn
            d.iu_mm_ierat_thdid.value = 1
            d.iu_mm_ierat_state.value = state
            d.iu_mm_ierat_tid.value = pid
            d.iu_mm_ierat_req_nonspec.value = nonspec
            d.iu_mm_ierat_req.value = 1
            await self.tick()
            d.iu_mm_ierat_req.value = 0

    async def wait_for(self, pred, budget, what):
        """Watchdog: fail with WATCHDOG if pred() is not true within budget cycles."""
        async def _poll():
            while True:
                await self.tick()
                r = pred()
                if r:
                    return r
        try:
            return await with_timeout(_poll(), budget * 10, "ns")
        except SimTimeoutError:
            self.dump_since(self.cycle - budget)
            raise AssertionError(f"WATCHDOG: {what} not seen within {budget} cycles")

    def dump_since(self, c0):
        names = {}
        for (c, n, v) in self.ev:
            if c > c0 and n not in ("pte", "derat_data", "ierat_data"):
                names.setdefault(n, []).append(c)
        for n, cs in names.items():
            self.log.info("    activity %-10s x%d first@%d last@%d", n, len(cs), cs[0], cs[-1])
        if not names:
            self.log.info("    no activity at all since cycle %d", c0)

    # ---- the three events
    async def miss_walk_hit(self, side, ea, expect_ra, label, shift=0, **kw):
        """EVENT 1 -> EVENT 2 -> EVENT 3 for one request.  Returns the walked reload."""
        # EVENT 1
        c0 = self.cycle
        loads0 = self.nloads
        await self.request(side, ea, **kw)
        await self.wait_for(lambda: self.seen("rtw_req", c0), BUDGET_WALK,
                            f"{label}: EVENT 1 (tlb_rtw_req_valid)")
        self.log.info("  EVENT 1 %s: TLB miss handed to mmq_rtw (cycle %d)", label,
                      self.seen("rtw_req", c0)[0][0])

        # EVENT 2: the ptereload pass writes a TLB way and sends the ERAT a
        # "miss done" reload with wren=0 -- it carries no entry to write
        # (mmq_tlb_cmp.v:4046-4049; the LQ writes the ERAT only on wren=1,
        # lq_derat.v:2473-2475). The instruction then replays, which EVENT 3 models.
        rel = await self.wait_for(lambda: self.seen(side + "_data", c0), BUDGET_WALK,
                                  f"{label}: EVENT 2 (ptereload-pass ERAT reload)")
        await self.tick(4)                   # tag5 array write follows the tag4 reload
        self.check_no_fault(c0, label)
        assert self.seen("tlb_write", c0), f"{label}: EVENT 2 no TLB way written"
        wren = field(rel[0][1], ERAT_REL_W, *ERATPOS["wren"])
        assert wren == 0, f"{label}: EVENT 2 ptereload-pass reload has wren=1"
        self.log.info("  EVENT 2 %s: walked in %d L2 loads, TLB way written, ERAT told to retry",
                      label, self.nloads - loads0)
        await self.tick(20)

        # EVENT 3: the replay -- must hit the TLB and reload the ERAT with data
        return await self.expect_hit(side, ea, expect_ra, label, shift=shift, **kw)

    async def expect_hit(self, side, ea, expect_ra, label, shift=0, **kw):
        c1 = self.cycle
        loads1 = self.nloads
        await self.request(side, ea, **kw)
        rel = await self.wait_for(lambda: self.seen(side + "_data", c1), BUDGET_HIT,
                                  f"{label}: EVENT 3 (ERAT reload from a TLB hit)")
        assert not self.seen("rtw_req", c1), f"{label}: EVENT 3 re-lookup started another walk"
        assert self.nloads == loads1, f"{label}: EVENT 3 re-lookup issued {self.nloads - loads1} L2 loads"
        assert self.seen("wayhit", c1), f"{label}: EVENT 3 no TLB way hit recorded"
        self.check_reload(rel[0][1], ea, expect_ra, label, "EVENT 3", shift)
        self.log.info("  EVENT 3 %s: TLB hit, no walk, RPN=%#x", label,
                      field(rel[0][1], ERAT_REL_W, *ERATPOS["rpn"]))
        await self.tick(20)
        return rel[0][1]

    def check_no_fault(self, c0, label):
        for n in ("pt_fault", "lrat_miss", "tlb_inelig", "rtw_mchk", "tlb_miss"):
            hits = self.seen(n, c0)
            assert not hits, f"{label}: unexpected {n} at cycle {hits[0][0]}"

    def check_reload(self, rel, ea, expect_ra, label, ev, shift=0):
        """shift = log2(page size / 4 KB). For a large page the ERAT entry carries
        the page-base RPN/EPN; the low bits come from the EA at access time."""
        low = (1 << shift) - 1
        v = field(rel, ERAT_REL_W, *ERATPOS["v"])
        rpn = field(rel, ERAT_REL_W, *ERATPOS["rpn"])
        epn = field(rel, ERAT_REL_W, *ERATPOS["epn"])
        size = field(rel, ERAT_REL_W, *ERATPOS["size"])
        assert v == 1, f"{label}: {ev} ERAT reload has V=0"
        assert field(rel, ERAT_REL_W, *ERATPOS["wren"]) == 1, f"{label}: {ev} ERAT reload has wren=0"
        assert size == ERAT_SIZE[shift], f"{label}: {ev} ERAT size {size:03b} != {ERAT_SIZE[shift]:03b}"
        assert (rpn & ~low) == ((expect_ra >> 12) & ~low), \
            f"{label}: {ev} RPN {rpn:#x} != expected {expect_ra >> 12:#x} (page mask {low:#x})"
        assert (epn & ~low) == ((ea >> 12) & ~low), f"{label}: {ev} EPN {epn:#x} != {ea >> 12:#x}"


async def setup(dut):
    tb = Tb(dut)
    await tb.start()
    return tb


# ----------------------------------------------------------------------------
# M: every reachable miss cause, each followed by reload and hit
# ----------------------------------------------------------------------------
@cocotb.test()
async def test_m1_derat_cold(dut):
    """M1: empty TLB, D-ERAT miss."""
    tb = await setup(dut)
    await tb.miss_walk_hit("derat", ea_4k(4), TARGET_4K + 4 * 0x1000, "M1")


@cocotb.test()
async def test_m2_ierat_cold(dut):
    """M2: empty TLB, I-ERAT miss."""
    tb = await setup(dut)
    await tb.miss_walk_hit("ierat", ea_4k(5), TARGET_4K + 5 * 0x1000, "M2")


@cocotb.test()
async def test_m3_epn_mismatch(dut):
    """M3: TLB holds EA A; EA B misses on the address compare."""
    tb = await setup(dut)
    await tb.miss_walk_hit("derat", ea_4k(6), TARGET_4K + 6 * 0x1000, "M3/A")
    await tb.miss_walk_hit("derat", ea_4k(7), TARGET_4K + 7 * 0x1000, "M3/B")


@cocotb.test()
async def test_m4_pid_mismatch(dut):
    """M4: entry installed for PID 5; the same EA under PID 6 misses."""
    tb = await setup(dut)
    await tb.miss_walk_hit("derat", ea_4k(8), TARGET_4K + 8 * 0x1000, "M4/pid5", pid=5)
    await tb.miss_walk_hit("derat", ea_4k(8), TARGET_4K + 8 * 0x1000, "M4/pid6", pid=6)


@cocotb.test()
async def test_m5_lpid_mismatch(dut):
    """M5: entry installed for LPID 1; the same EA under LPID 2 misses."""
    # A D-ERAT request's own LPID is used only for external-PID ops; ordinary
    # loads/stores take LPIDR (mmq_tlb_req.v:895-899), so LPIDR is what changes.
    # LPID 0 is avoided: Book-E TLPID=0 is a wildcard (PROBLEMS.md item 28).
    tb = await setup(dut)
    await tb.spr_write(SPR_LPIDR, 1)
    await tb.miss_walk_hit("derat", ea_4k(9), TARGET_4K + 9 * 0x1000, "M5/lpid1")
    await tb.spr_write(SPR_LPIDR, 2)
    await tb.miss_walk_hit("derat", ea_4k(9), TARGET_4K + 9 * 0x1000, "M5/lpid2")


@cocotb.test()
async def test_m6_as_mismatch(dut):
    """M6: entry installed with AS=0; the same EA with AS=1 misses on the state compare."""
    tb = await setup(dut)
    await tb.miss_walk_hit("derat", ea_4k(10), TARGET_4K + 10 * 0x1000, "M6/as0", as_=0)
    await tb.miss_walk_hit("derat", ea_4k(10), TARGET_4K + 10 * 0x1000, "M6/as1", as_=1)


@cocotb.test()
async def test_m8_64k_page(dut):
    """M8: a 64 KB leaf is installed at 64 KB; another 4 KB sub-page of it hits
    without a walk, and a different 64 KB page misses."""
    tb = await setup(dut)
    walked = await tb.miss_walk_hit("derat", ea_64k(1, 0), TARGET_64K + 1 * 0x10000, "M8/sub0", shift=4)
    pte = [v for (c, n, v) in tb.ev if n == "pte"][-1]
    size = field(pte, PTE_W, PTEPOS_SIZE, 4)
    # PTE PS is log2(size/1KB): 64 KB = 0110 (A2O UM 6.17.3)
    assert size == 0b0110, f"M8: ptereload PS {size:04b}, expected 0110 (64 KB)"
    await tb.expect_hit("derat", ea_64k(1, 5), TARGET_64K + 1 * 0x10000 + 5 * 0x1000, "M8/sub5", shift=4)
    await tb.miss_walk_hit("derat", ea_64k(2, 0), TARGET_64K + 2 * 0x10000, "M8/next64K", shift=4)


# ----------------------------------------------------------------------------
# N: misses that must NOT walk, and a walk that must NOT install
# ----------------------------------------------------------------------------
@cocotb.test()
async def test_n1_speculative_miss(dut):
    """N1: a speculative (nonspec=0) miss must not leave the core."""
    tb = await setup(dut)
    c0, l0 = tb.cycle, tb.nloads
    await tb.request("derat", ea_4k(12), nonspec=0)
    await tb.tick(QUIET)
    assert not tb.seen("rtw_req", c0), "N1: speculative miss started a walk"
    assert tb.nloads == l0, "N1: speculative miss issued L2 loads"
    assert not tb.seen("tlb_miss", c0), "N1: speculative miss raised a TLB-miss exception"
    tb.log.info("  N1: speculative miss -> no walk, no load, no exception")


@cocotb.test()
async def test_n3_invalid_leaf(dut):
    """N3: leaf V=0 -> pt_fault, nothing installed, the re-lookup walks again."""
    tb = await setup(dut)
    tb.mem[L4_BASE + 8 * 13] = 0
    c0 = tb.cycle
    await tb.request("derat", ea_4k(13))
    await tb.wait_for(lambda: tb.seen("pt_fault", c0), BUDGET_WALK, "N3: pt_fault")
    await tb.tick(50)
    assert not tb.seen("tlb_write", c0), "N3: a V=0 leaf was written into the TLB"
    c1 = tb.cycle
    await tb.request("derat", ea_4k(13))
    await tb.wait_for(lambda: tb.seen("rtw_req", c1), BUDGET_WALK, "N3: second walk")
    tb.log.info("  N3: pt_fault raised, TLB not written, re-lookup walked again")
    await tb.wait_for(lambda: tb.seen("pt_fault", c1), BUDGET_WALK, "N3: second pt_fault")


@cocotb.test()
async def test_selftest_watchdog(dut):
    """Harness self-test: with the L2 silent, EVENT 2 must fail by WATCHDOG, so a
    hang can never be reported as a pass."""
    tb = await setup(dut)
    tb.l2_stall = True
    try:
        await tb.miss_walk_hit("derat", ea_4k(14), TARGET_4K + 14 * 0x1000, "SELFTEST")
    except AssertionError as e:
        # A stall ends in the walker's own watchdog (mchk); the V=0 reload it then
        # returns is also reported as pt_fault by mmq_tlb_cmp (PROBLEMS.md item 27).
        assert any(k in str(e) for k in ("WATCHDOG", "rtw_mchk", "pt_fault")), f"wrong failure: {e}"
        tb.log.info("  self-test: stalled L2 reported as failure (%s)", e)
    else:
        raise AssertionError("self-test: a stalled L2 was reported as a pass")
    finally:
        tb.l2_stall = False
