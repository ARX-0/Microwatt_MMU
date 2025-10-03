
# 6.9.3.3 TLB Management Instructions in v3.1C.

Radix Invalidation Control (RIC) 

0 Just invalidate TLB.
1 Invalidate just Page Walk Cache.
2 Invalidate TLB, Page Walk Cache, and any caching
of Partition and Process Table Entries.
3 Invalidate a group of translations (just in the TLB).

Process Scoped (PRS)

0 Invalidate partition-scoped translation(s).
1 Invalidate process-scoped translation(s).
(for RIC=2, whether Process or Partition Table
caching is being invalidated.) WDYM by that? 

Radix (R)

0 Invalidate HPT translation(s).
1 Invalidate Radix Tree translation(s).

Invalidation Selector (IS) (found in RB) specifies the scope
of the context to be invalidated.

0 Invalidate just the target VA.
1 Invalidate matching PID.
2 Invalidate matching LPID.
3 If MSRHV=1, invalidate all entries, otherwise invalidate matching LPID.
