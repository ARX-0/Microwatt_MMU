
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

## read the below for all the possible TLB control instructions.

tlbie (TLB Invalidate Entry X-form)
tlbiel (TLB Invalidate Entry Local X-form)
tlbsync (TLB Synchronize X-form
)

## Storage Control Overview. 

[for context i felt like i need to include this]

<img width="1287" height="694" alt="image" src="https://github.com/user-attachments/assets/442d383f-a876-4bb5-b6e7-5c780ab56685" />

[WE NEED THIS SIMPLIFIED ENOUGH]
<<Host real address space size is 2m bytes, m≤60;
see Note 1.
• Guest real address space size is 2m bytes, m≤60;
see Notes 1 and 2.
• Real page size is 212 bytes (4 KB).
• Effective address space size is 264 bytes.
• For HPT translation, an effective address is translated to a virtual address via a segment descriptor
that was either bolted into the Segment Lookaside
Buffer (SLB) by software or found and installed into
the SLB via a hardware walk of the Segment Table.
After that, the virtual address is translated to a host
real address via a hardware walk of the Page Table.
– Virtual address space size is 2n bytes,
65≤n≤78; see Note 3.
– Segment size is 2s bytes, s=28 or 40.
– 2
n-40 ≤ number of virtual segments ≤ 2
n-28;
see Note 3.
– Virtual page size is 2p bytes, where 12≤p,
and 2p
is no larger than either the size of the
biggest segment or the real address space; a
size of 4 KB, 64 KB, and an implementationdependent number of other sizes are supported; see Note 4. The Page Table specifies
the virtual page size. The SLB specifies the
base virtual page size, which is the smallest
virtual page size that the segment can contain. The base virtual page size is 2b bytes.
– Segments contain pages of a single size, a
mixture of 4 KB and 64 KB pages, or a mixture
of page sizes that include implementationdependent page sizes.
• For Radix Tree translation, an effective address is
translated to a (guest or host) real address via a
hardware walk of the Page Table.
– Virtual page size is 2p bytes, where 12≤p, and
2
p
is no larger than the size of the real address
space; a size of 4 KB, 64 KB, 2MB, and an
implementation-dependent number of other
sizes are supported; see Note 4. The virtual
page size is determined by the location of the
Page Table Entry in the Radix Tree.
Notes:
1. The value of m is implementation-dependent (subject to the maximum given above). When used to
address storage or to represent a guest real address, the high-order 60-m bits of the “60-bit” real
address must be zeros.
2. The hypervisor may assign a guest real address
space size for each partition that uses Radix Tree
translation. Accesses to guest real storage outside
this range but still mappable by the second level
Radix Tree will cause an HISI or HDSI. Accesses
to storage outside the mappable range will have
boundedly undefined results.
3. The value of n is implementation-dependent (subject to the range given above). In references to
78-bit virtual addresses elsewhere in this Book, the
high-order 78-n bits of the “78-bit” virtual address
are assumed to be zeros.
4. The supported values of p for the larger virtual
page sizes are implementation-dependent (subject
to the limitations given above).
>>


