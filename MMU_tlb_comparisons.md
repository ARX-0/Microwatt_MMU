
# 6.9.3.3 TLB Management Instructions in v3.1C.

Radix Invalidation Control (RIC) 

0 Just invalidate TLB. // the variants of tlbie and tibel where in (IS != 0, RIC = 2) is same as RIC = 0.

1 Invalidate just Page Walk Cache.// this and IS!=0 -> The page walk entries of the specified LIPD or PID are invalidated.

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


tlbiel (Translation Lookaside Buffer Invalidate Entry Local)
tlbie (TLB invalidate entry)


NOTE :- The ability to target an individual Page Walk
Cache Entry or the set of entries associated with a given
Page Table Entry (i.e. IS=0 for RIC=1 or RIC=2) is NOT
supported by the Power ISA.
