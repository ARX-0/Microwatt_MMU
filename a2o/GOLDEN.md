# `a2o/golden/` — pristine upstream snapshot

## The rule

**Never edit anything under `a2o/golden/`.**

All porting work happens in `a2o/rel/`. `a2o/golden/src/` is a byte-identical copy of
`a2o/rel/src/` as it was released upstream, kept so that any file can be diffed against
pristine at any point in the project.

## Why this exists alongside git

`git diff` answers *"what changed since the last commit"*. `golden/` answers a different
question: *"what has this file accumulated since upstream"* — which stays meaningful no
matter how many commits have landed. It also lets you point `vimdiff`, `meld`, or plain
`diff -r` at two real directories, which is the practical way to review a port that touches
a handful of places in several 4000-line Verilog files.

## Usage

```bash
tools/a2o-diff.sh                  # summary of every changed/added/removed file
tools/a2o-diff.sh --stat           # per-file added/removed line counts
tools/a2o-diff.sh mmq_tlb_ctl.v    # full unified diff of one file (found by name)
tools/a2o-diff.sh --patch          # one unified diff of the whole tree
```

Or directly:

```bash
meld    a2o/golden/src/verilog/work a2o/rel/src/verilog/work
vimdiff a2o/golden/src/verilog/work/mmq_tlb_ctl.v a2o/rel/src/verilog/work/mmq_tlb_ctl.v
```

## Scope

`golden/` mirrors `rel/src/` only — 308 files, 18 MB:

| Path | Contents |
|---|---|
| `src/verilog/work/` | the core; MMU is `mmq*.v` + header `mmu_a2o.vh` |
| `src/verilog/trilib/` | `tri_*` latch / primitive library |
| `src/vhdl/` | AXI wrappers, debug, SCOM |

`rel/doc/`, `rel/build/` and `rel/fpga/` are **not** mirrored — they are documentation and
Vivado TCL, and the port does not edit them.

## Re-baselining

Only if a newer upstream A2O release is merged into `a2o/rel/`. Then, and only then:

```bash
rsync -a --delete a2o/rel/src/ a2o/golden/src/
```

Doing this at any other time destroys the record of the port's own changes.
