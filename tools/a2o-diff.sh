#!/usr/bin/env bash
# Diff the editable A2O tree (a2o/rel/src) against the pristine upstream
# snapshot (a2o/golden/src).
#
#   tools/a2o-diff.sh                  summary of every changed/added/removed file
#   tools/a2o-diff.sh --stat           per-file added/removed line counts
#   tools/a2o-diff.sh mmq_tlb_ctl.v    full unified diff of one file
#   tools/a2o-diff.sh --patch          one unified diff of the whole tree
#
# Unlike `git diff`, this answers "what has changed since UPSTREAM", no matter
# how many commits have landed since, and it works with vimdiff/meld because
# both sides are real directories.
set -euo pipefail

R="$(git rev-parse --show-toplevel)"
G="$R/a2o/golden/src"
E="$R/a2o/rel/src"

[ -d "$G" ] || { echo "missing golden tree: $G" >&2; exit 1; }
[ -d "$E" ] || { echo "missing editable tree: $E" >&2; exit 1; }

case "${1:-}" in
  "")
      if diff -rq "$G" "$E" > /dev/null 2>&1; then
          echo "a2o/rel/src is identical to upstream (a2o/golden/src)"
      else
          diff -rq "$G" "$E" || true
      fi
      ;;
  --patch)
      diff -ruN "$G" "$E" || true
      ;;
  --stat)
      diff -ruN "$G" "$E" 2>/dev/null | awk '
          /^--- /                 { f=$2; sub(".*/golden/src/","",f) }
          /^\+\+\+ /              { g=$2; sub(".*/rel/src/","",g); if (f=="/dev/null") f=g }
          /^\+/ && !/^\+\+\+ /    { add[f]++ }
          /^-/  && !/^--- /       { del[f]++ }
          END { for (k in add) printf "%6d +  %6d -   %s\n", add[k], del[k]+0, k
                for (k in del) if (!(k in add)) printf "%6d +  %6d -   %s\n", 0, del[k], k }
      ' | sort -k7
      ;;
  -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      ;;
  *)
      f=$(cd "$E" && find . -name "$1" | head -1)
      [ -n "$f" ] || { echo "no such file under a2o/rel/src: $1" >&2; exit 1; }
      f="${f#./}"
      diff -u "$G/$f" "$E/$f" || true
      ;;
esac
