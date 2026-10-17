# Local Claude Code tooling for this repo

This file documents the editor/agent tooling installed on 2026-09-21. It is **not** part of
the A2O port. It sits inside `hdl-plugins/`, which `.gitignore` excludes, so none of it
reaches a reviewer cloning the repo.

If you later decide this belongs elsewhere (a `docs/` page, or outside the repo entirely),
move it — nothing references it by path.

---

## 1. Why any of this exists

Three specific problems, each with a specific fix:

| Problem | Fix |
|---|---|
| Claude edited Verilog/VHDL with no compiler feedback. Errors surfaced only when you ran a simulation, minutes or hours later. | Two language servers (LSP), so the editor and the agent both see diagnostics as the file is written. |
| Every "where is this signal driven?" question made Claude read whole files into the main conversation, burning context you then could not use for actual work. | A `researcher` subagent running on Haiku, with read-only tools, that answers in citations instead of file dumps. |
| Nothing checked a file after an edit. A typo could sit unnoticed until the next test run. | A `PostToolUse` hook that lints automatically after every Edit/Write. |

Two more things were installed for code review, and one for cross-session memory. The memory
one does not work on this machine — see §8.

---

## 2. Using this day to day

### 2.1 Do the plugins apply to every conversation?

Yes, in every project, in both the VSCode extension and a terminal. The extension launches
the same `claude` binary that the terminal does, with `--setting-sources=user,project,local`
(read from the running process, 2026-09-21), so both read the same settings files.

| Piece | Scope | Applies where |
|---|---|---|
| All five plugins | User (`~/.claude/settings.json`) | Every project, extension and terminal |
| Lint hook | User | Every project, but only acts on `.v .sv .vhd .vhdl` files |
| `MAX_THINKING_TOKENS`, status line | User | Every project |
| `researcher` agent | Project (`.claude/agents/`) | Microwatt_MMU only |
| `CLAUDE.md` rules | Project | Microwatt_MMU only |

So opening `~/Documents/TESTCASES_AXI/hello_c` gets the LSPs and the hook, but not the
researcher agent and not the CLAUDE.md rules.

You do not switch anything on. After install, a new session picks everything up. The
`claude plugin update` help text says a restart is required to apply an update; it does not
say the same for a fresh install. In the session that built this setup, the new agents and
skills appeared without a restart. If something is missing, restart the session before
debugging.

### 2.2 What is automatic and what you have to ask for

| Feature | How it runs | What you do |
|---|---|---|
| Lint hook | Automatic, after every edit Claude makes to an HDL file | Nothing. Read the output. |
| Language-server diagnostics | Automatic, appear as warnings/errors after an edit | Nothing. |
| Go-to-definition, find-references, symbol search | Claude calls the `LSP` tool | Ask in plain words (§2.3) |
| `researcher` subagent | Only when Claude delegates to it | Ask for it by name (§2.4) |
| Review plugins | Only when invoked | Type a slash command (§2.5) |

The hook and the diagnostics fire on edits **Claude** makes. If you edit a file yourself in the
editor, the hook does not run. The VSCode extension may still show language-server squiggles
for it, but that is the editor's own behaviour and I have not checked it.

### 2.3 Asking code-intelligence questions

Claude has an `LSP` tool with nine operations: `goToDefinition`, `findReferences`, `hover`,
`documentSymbol`, `workspaceSymbol`, `goToImplementation`, `prepareCallHierarchy`,
`incomingCalls`, `outgoingCalls`. You never call it yourself. You ask, and Claude picks the
operation.

Phrasings that map onto it:

- "List the signals and functions in `tb_walk.v`." (`documentSymbol`)
- "Where is `mk_pte` defined?" (`goToDefinition`)
- "What references `ptcr_r`?" (`findReferences`)
- "Find anything named `tlb` across the workspace." (`workspaceSymbol`)

Verified 2026-09-21: `documentSymbol` on `a2o/rel/src/verilog/sim/tb_walk.v` returned the
module, its signals, functions and named blocks with line numbers, and `documentSymbol` on
`microwatt/dmi_dtm_dummy.vhdl` returned the entity, its generics and ports. The other seven
operations were not exercised.

Two things to know about the answers:

1. It is a parser's answer, not a text search. It is exact where grep is approximate, but
   it is only as good as the server's parse. Verible understands Verilog syntax, not A2O's
   `tri_*` macro conventions or generate-heavy elaboration, so a signal created inside a
   deep `generate` block may not be found. I have not tested that.
2. For VHDL it is limited by the library problem in §4: without a `vhdl_ls.toml`, references
   into other Microwatt files come back unresolved. Seen live on `dmi_dtm_dummy.vhdl`:
   `No primary unit 'wishbone_types' within library 'work'`.

### 2.4 Using the researcher agent

Ask for it by name and describe the question. It is read-only (`Read`, `Grep`, `Glob`) and
runs on Haiku.

> Use the researcher agent to find every place `ex5_flush` is driven under `a2o/rel/src/verilog/`.

> Use the researcher agent: where is the `tlb` module instantiated, and with what parameters?

When to use it: the answer is short but the search is long. The files it opens are read in a
separate context, so they never enter your main conversation.

When not to use it:

- You need Claude to change something. It cannot edit.
- The question is about one known file. Ask Claude to read the file.
- The answer needs judgement about design. Haiku is fast and cheap, not a reviewer.

It returns `file:line` citations. Open the cited lines before you rely on them. It is a
smaller model, and CLAUDE.md §2 says to verify before asserting.

Note that "find every place X is driven" through a text search cannot see through macros or
generate blocks, for the same reason as in §2.3.

### 2.5 Running the review plugins

Plugin skills are called as `/plugin-name:skill-name`.

| Command | What it does | Cost note |
|---|---|---|
| `/code-review:code-review` | The plugin's review of a pull request | ~2.5k tokens per invocation |
| `/pr-review-toolkit:review-pr` | Runs its six review agents over a PR | ~1.6k for the skill, plus each agent it launches |
| `/code-review` | **Built-in** review of your local diff. Not the plugin. | Separate command with a similar name |

The plugin's `code-review` is described as reviewing "a pull request". Your work sits on a
local branch with no PR yet, so for uncommitted work the built-in `/code-review` is the one
that fits. The `pr-review-toolkit` skills are also PR-oriented. I have run none of these three
on this repo, so I do not know how they behave on Verilog.

You can also name one agent directly:

> Run the pr-review-toolkit code-reviewer agent on my uncommitted diff.

Fit to this repo: `silent-failure-hunter` looks for swallowed exceptions and bad fallbacks,
and `type-design-analyzer` reviews class and type design. Neither concept maps well onto
Verilog. `code-reviewer` and `comment-analyzer` are the two most likely to be useful. That is
my reading of their descriptions, not a test result.

Two separate boundaries when reviewing:

- Anything under `a2o/golden/` or `microwatt/` is pristine or vendored. Do not ask for
  review-and-fix there (CLAUDE.md §1). Reading and reviewing is fine.
- `--fix` style options apply edits to the working tree. That is a file change you should
  decide on per CLAUDE.md §0, not something to run unattended.

### 2.6 A typical session

1. Open the repo. Everything above loads.
2. Ask a navigation question. For a wide one, name the `researcher` agent. For one file,
   ask the `LSP` question directly.
3. Ask for an edit. After the edit, the hook prints lint output and the language server
   posts diagnostics.
4. Read that output. Expect the style noise described in §9 until you decide on a
   `.rules.verible_lint`. Real errors are the ones that are not
   `packed-dimensions-range-ordering`, `line-length`, `explicit-*-lifetime` or
   `explicit-parameter-storage-type`.
5. Run the actual tests yourself or ask Claude to. Lint is not a test. Nothing here runs
   `a2o/rel/src/verilog/sim/run_rtw_tests.sh`.
6. Before you commit, review the diff (`/code-review`, or read it yourself).

### 2.7 If something does not seem to work

| Symptom | Check |
|---|---|
| No lint output after an edit | Was it an HDL file? Was it an edit Claude made? `command -v verible-verilog-lint` (must resolve; `~/.local/bin` must be on `PATH`). |
| "command not found" for a server | `~/.local/bin` is missing from `PATH` in that shell. |
| `claude` not found in a terminal | It is bundled in the extension, not on `PATH`. The binary is at `~/.vscode/extensions/anthropic.claude-code-<version>/resources/native-binary/claude`. To run a plugin command, use that full path. A symlink into `~/.local/bin` makes plain `claude` work, but the version number in the path changes when the extension updates, so the link goes stale. |
| VHDL "unresolved" errors | Expected until `vhdl_ls.toml` exists (§4). Not a defect in your code. |
| A `claude-mem` error or an MCP failure notice at startup | Expected. Node is missing (§8). |
| Status line shows `ctx % \|` with a blank model | `jq` missing or the JSON field differs in your version. `jq` was installed 2026-09-21. |

---

## 3. What is actually installed

Verified by running each binary and `claude plugin list` on 2026-09-21.

### Binaries

| Tool | Version | Location | Purpose |
|---|---|---|---|
| `verible-verilog-ls` | v0.0-4294 | `~/.local/bin/` | Verilog/SystemVerilog language server |
| `verible-verilog-lint` | v0.0-4294 | `~/.local/bin/` | Verilog style/lint checker (used by the hook) |
| `verible-verilog-format` | v0.0-4294 | `~/.local/bin/` | Verilog formatter (installed, not wired to anything) |
| `verible-verilog-syntax` | v0.0-4294 | `~/.local/bin/` | Parser/AST dump (installed, not wired to anything) |
| `vhdl_ls` | 0.88.0 | `~/.local/opt/vhdl_ls/`, symlinked into `~/.local/bin/` | VHDL language server |
| `ghdl` | pre-existing | `/usr/bin/ghdl` | VHDL analyser (used by the hook) |
| `jq` | 1.6 | `/usr/bin/jq` | JSON parsing for the status line |

None of this required root. `~/.local/bin` is first on your `PATH`, so a user-local install
behaves identically to `/usr/local/bin` and is trivially reversible.

`vhdl_ls` was installed as a whole directory rather than a lone binary because it ships its
own compiled `std`, `ieee2008`, `synopsys` and `vital2000` libraries and resolves them
relative to the executable. Copying just the binary would give you a server that cannot
resolve `ieee.std_logic_1164`.

### Plugins

| Plugin | Marketplace | Always-on token cost | Working? |
|---|---|---|---|
| `verilog-lsp` | `hdl-plugins` (local) | ~0 | Yes |
| `vhdl-lsp` | `hdl-plugins` (local) | ~0 | Yes |
| `code-review` | `claude-plugins-official` | ~20 | Yes |
| `pr-review-toolkit` | `claude-plugins-official` | ~2,033 | Yes |
| `claude-mem` | `thedotmack` | ~2,000 | **No — see §8** |

---

## 4. The language servers

### What an LSP gives you

A language server is a separate process that parses your code and answers structured
questions about it: where is this symbol defined, what are its references, what errors does
this file have. It is the same machinery VS Code uses for Go-to-Definition.

The value here is that the agent gets the *parser's* answer rather than a text-search guess.
Asking "where is `ex1_valid` driven" via grep gives you every textual occurrence including
comments; asking the LSP gives you the actual driver.

### Checking they work

```bash
verible-verilog-ls --version
vhdl_ls --version
```

Both should print a version. If either says "command not found", `~/.local/bin` has fallen
off your `PATH`.

### File associations

Set in `verilog-lsp/.lsp.json` and `vhdl-lsp/.lsp.json`:

- Verilog server: `.v`, `.sv`, `.svh`
- VHDL server: `.vhd`, `.vhdl`

Note `.svh` is mapped but A2O does not use SystemVerilog headers; it is there because the
Verible server accepts them.

### VHDL needs a project file to be useful

`vhdl_ls` analyses one file at a time unless you tell it which files form a library. Without
that, opening `microwatt/execute1.vhdl` produces errors about `wishbone_types` not being
found — not real defects, just the server having no idea the rest of Microwatt exists.

To fix it for the Microwatt tree, create `vhdl_ls.toml` at the repo root:

```toml
[libraries]
work.files = [
  "microwatt/*.vhdl",
]
```

This has **not** been done. It is a real decision about which files constitute the `work`
library, and it is yours to make.

---

## 5. The post-edit lint hook

### How it fires

`~/.claude/settings.json` registers a `PostToolUse` hook matching `Edit|Write`. After Claude
edits any file, Claude Code runs `~/.claude/hooks/hdl-lint.sh` and feeds it a JSON payload on
stdin describing the tool call.

The script pulls `tool_input.file_path` out of that JSON and dispatches on extension:

| Extension | Command run |
|---|---|
| `.v`, `.sv` | `verible-verilog-lint <file>` |
| `.vhd`, `.vhdl` | `ghdl -a --std=08 <file>` |
| anything else | nothing |

Output is capped at 50 lines. The script always exits 0, so a lint failure **never blocks an
edit** — it is advisory only. It also checks the tool exists first, so removing Verible
degrades to silence rather than an error on every edit.

### A note on how hooks receive input

The obvious way to write this script is `FILE="$1"`. That does not work. Hooks get a JSON
object on stdin and no positional arguments; `$1` is always empty, the `case` matches
nothing, and the hook silently does nothing forever while appearing to be installed. If you
write another hook later, read stdin.

### Testing it by hand

```bash
echo '{"tool_input":{"file_path":"/path/to/file.v"}}' | ~/.claude/hooks/hdl-lint.sh
```

### Turning it off

Delete the `hooks` block from `~/.claude/settings.json`, or for a single session set the
file extension outside the matched set. There is no per-invocation toggle.

---

## 6. The `researcher` subagent

Defined at `.claude/agents/researcher.md` (this one **is** tracked by git — decide whether
you want that before your next commit).

It runs on Haiku with only `Read`, `Grep` and `Glob`. It cannot edit anything.

Use it for questions whose answer is short but whose search is long:

- "Find every place `ex1_flush` is driven in `a2o/rel/src/verilog/`."
- "Where is `tri_rlmreg_p` instantiated in the MMU?"
- "Which files reference SPR 0x30?"

The point is that the *searching* happens in a throwaway context. Only the answer comes back
into your main conversation. Asking Claude directly to do the same search pulls every file it
opens into your context permanently.

It is instructed to return `file:line` citations and to say so when a symbol does not exist,
rather than guessing at a similarly-named one.

---

## 7. The review plugins

### `code-review` (~20 tokens always-on)

Cheap. Provides the `code-review` skill. Reviews the current diff or a named target for
correctness bugs.

```
/code-review
/code-review high
```

Effort levels run low → medium → high → max. Low and medium give few, high-confidence
findings; high and above cast wider and will include uncertain ones.

### `pr-review-toolkit` (~2,033 tokens always-on)

Six specialist agents — `code-reviewer`, `code-simplifier`, `comment-analyzer`,
`silent-failure-hunter`, `pr-test-analyzer`, `type-design-analyzer` — plus a `review-pr`
skill.

Be aware this is the single most expensive thing installed: about 2,000 tokens are added to
**every session you ever start**, whether you use it or not, because the agent descriptions
must be loaded for the agents to be selectable. Given that your stated goal was minimum token
waste, this one deserves a conscious decision. If you review PRs rarely:

```bash
claude plugin disable pr-review-toolkit
claude plugin enable pr-review-toolkit    # when you actually need it
```

Note also that these agents are tuned for general software review. `silent-failure-hunter`
and `type-design-analyzer` have limited meaning for Verilog.

---

## 8. `claude-mem` does not work on this machine

It is installed and enabled, and it is **entirely non-functional**.

`claude-mem` is a Node application. Its `package.json` declares `engines: node >=20.12.0`.
All seven of its hooks (`Setup`, `SessionStart`, `UserPromptSubmit`, `PostToolUse`,
`PreToolUse`, `Stop`, `SessionEnd`) shell out to `node`, and its MCP server spawns `node`.

There is no `node`, `npm`, `bun`, or `nvm` anywhere on this system. Verified:

```
$ node "$D/scripts/version-check.js"
bash: node: command not found
```

Every hook fails this way, silently, on every session. Meanwhile it still costs ~2,000
always-on tokens for twenty skill descriptions that cannot run.

**You have two options.** Both are your call:

```bash
# Option A — make it work: install Node 20+
sudo apt install nodejs npm          # Ubuntu 22.04 ships Node 12; likely too old
# or use nodesource / nvm for a current version

# Option B — stop paying for it
claude plugin uninstall claude-mem@thedotmack
```

Until one of those happens, you are paying ~2,000 tokens per session for nothing. My
recommendation is Option B now, Option A later if you decide you want the feature — but it is
your decision, not mine.

One caution for Option A: `claude-mem` registers its own `PostToolUse` hook. Plugin hooks and
your `settings.json` hooks both run independently, so it will not clobber the HDL lint hook.

---

## 9. Verible fights A2O's house style

This is the most important thing in this file.

Running the linter on one real file from the tree:

```
$ verible-verilog-lint a2o/rel/src/verilog/sim/tb_walk.v | wc -l
41

   18  packed-dimensions-range-ordering
    8  line-length
    7  explicit-parameter-storage-type
    4  explicit-function-lifetime
    3  explicit-task-lifetime
    1  unpacked-dimensions-range-ordering
```

`packed-dimensions-range-ordering` flags descending bit ranges — `[0:63]` rather than
`[63:0]`. But big-endian bit ranges are A2O's documented convention, recorded in this repo's
own `CLAUDE.md` §2 as a rule to follow. Verible's default ruleset therefore contradicts your
house style on essentially every file, permanently.

Left alone, the hook will emit dozens of lines of style noise after every Verilog edit, and
the genuine findings will be buried in it.

I did not silence these rules, because which lint rules govern the port is an architectural
decision that belongs to you. When you want it done:

```bash
cat > /home/arx-0/Documents/GitHub/Microwatt_MMU/.rules.verible_lint <<'EOF'
-packed-dimensions-range-ordering
-unpacked-dimensions-range-ordering
-line-length
EOF
```

Verible discovers `.rules.verible_lint` by walking up from the linted file's directory, so one
file at the repo root covers the whole tree. A leading `-` disables a rule. Full rule list:

```bash
verible-verilog-lint --help_rules | less
```

Consider whether you want that file tracked by git. Tracked, it documents the port's lint
policy to a reviewer; untracked, it is invisible local preference.

---

## 10. Status line

`~/.claude/settings.json` sets a status line showing remaining context and model:

```
ctx 87% | Opus 5
```

It reads the status JSON from stdin and parses it with `jq`. Two notes:

- `$CLAUDE_STATUS_INPUT` does not exist. Status line commands receive JSON on **stdin**,
  same as hooks.
- `context_window.remaining_percentage` may not exist in every Claude Code version. The
  `// 100` fallback in the `jq` filter means it degrades to showing `100%` rather than
  breaking.

---

## 11. Limitations and things not done

Stated plainly, because finding these yourself is cheaper than finding them mid-review.

**Not done, deliberately:**
- No `.rules.verible_lint` — §9, your decision.
- No `vhdl_ls.toml` — §4, your decision about library membership.
- `claude-mem` neither fixed nor removed — §8, your decision.
- `verible-verilog-format` installed but not wired to anything. Auto-formatting A2O source
  would produce enormous diffs against `a2o/golden/` and destroy `tools/a2o-diff.sh`'s
  usefulness. It is there if you want it on a single new file.

**Known weaknesses of what was built:**
- The VHDL half of the lint hook uses `ghdl -a` on one file in isolation. For any file that
  depends on another (most of Microwatt), it reports missing-unit errors that are artifacts
  of single-file analysis, not real defects. It is only trustworthy on self-contained files.
  Replacing it with a `vhdl_ls`-driven check would fix this.
- The hook lints the file that was edited, not the design. It cannot catch an error you
  introduced in file A that only manifests in file B.
- Nothing runs `a2o/rel/src/verilog/sim/run_rtw_tests.sh`. Lint is not test.

**Not verified:**
- Both language servers were confirmed serving live requests in a Claude Code session on
  2026-09-21, but only through `documentSymbol`, on two files (`tb_walk.v`,
  `dmi_dtm_dummy.vhdl`). The other eight `LSP` operations (go-to-definition, find-references,
  hover, call hierarchy and so on) were not exercised. Behaviour across A2O's `tri_*` macros
  and `generate` blocks is untested.
- The Verible and vhdl_ls versions installed are the current releases as of 2026-09-21. I did
  not test them against the full A2O tree, only the sample files quoted above.
- The three review commands in §2.5 were not run on this repo.
- Whether the VSCode chat panel displays the status line is unconfirmed. Whether
  `MAX_THINKING_TOKENS=8000` overrides the extension's `--max-thinking-tokens 31999` launch
  flag is unconfirmed.

---

## 12. Undoing everything

```bash
# plugins
claude plugin uninstall verilog-lsp@hdl-plugins
claude plugin uninstall vhdl-lsp@hdl-plugins
claude plugin uninstall code-review@claude-plugins-official
claude plugin uninstall pr-review-toolkit@claude-plugins-official
claude plugin uninstall claude-mem@thedotmack
claude plugin marketplace remove hdl-plugins
claude plugin marketplace remove thedotmack

# binaries
rm ~/.local/bin/verible-verilog-{ls,lint,format,syntax}
rm ~/.local/bin/vhdl_ls
rm -rf ~/.local/opt/vhdl_ls

# hook
rm ~/.claude/hooks/hdl-lint.sh
# then delete the "hooks" and "statusLine" blocks from ~/.claude/settings.json

# repo changes
rm -rf hdl-plugins/ .claude/ .gitignore
git checkout CLAUDE.md
```

A timestamped backup of your original `~/.claude/settings.json`, taken before any of this,
is at `~/.claude/backups/settings.json.20260921T100228.bak`.

---

## 13. Where everything lives

```
~/.local/bin/verible-verilog-*        Verible binaries
~/.local/bin/vhdl_ls                  symlink
~/.local/opt/vhdl_ls/                 vhdl_ls + its bundled std/ieee libraries
~/.claude/hooks/hdl-lint.sh           the post-edit lint hook
~/.claude/settings.json               env, statusLine, hooks, enabled plugins
~/.claude/backups/                    pre-change settings backup
~/.claude/plugins/                    installed plugin cache

<repo>/hdl-plugins/                   local marketplace (gitignored)
  .claude-plugin/marketplace.json     marketplace manifest
  verilog-lsp/                        Verible LSP plugin
  vhdl-lsp/                           vhdl_ls LSP plugin
  README.md                           this file
<repo>/.claude/agents/researcher.md   the Haiku search subagent (tracked by git)
<repo>/.gitignore                     excludes hdl-plugins/
<repo>/CLAUDE.md                      §5 appended; §0-4 untouched
```

## 14. One security note

During the session that produced this setup, a sudo password was sent in chat. It was not
used — the installs went to `~/.local/` and never needed root — but it was written to the
session transcript under `~/.claude/projects/`. Change that password and delete the
transcript. As a general rule, nothing installed here ever needs your password; if something
appears to, stop and check why.
