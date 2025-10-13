# // LOG 1
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
tlbsync (Ordering fn for TLBIE instrs)

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

For Context

<img width="1287" height="694" alt="image" src="https://github.com/user-attachments/assets/442d383f-a876-4bb5-b6e7-5c780ab56685" />


<img width="1312" height="1170" alt="image" src="https://github.com/user-attachments/assets/9990eca1-188e-4403-9719-c4841bf9d62b" />


[WE NEED THIS SIMPLIFIED ENOUGH]
<<

# Address Space and Translation Details

- **Host real address space size**: `2^m` bytes, where `m ≤ 60`  
  - *See Note 1*  

- **Guest real address space size**: `2^m` bytes, where `m ≤ 60`  
  - *See Notes 1 and 2*  

- **Real page size**: `2^12` bytes (4 KB)  

- **Effective address space size**: `2^64` bytes  

---

## HPT Translation

- An **effective address** is translated to a **virtual address** via a segment descriptor that was either:  
  - Bolted into the **Segment Lookaside Buffer (SLB)** by software, or  
  - Found and installed into the SLB via a hardware walk of the **Segment Table**.  

- After that, the virtual address is translated to a **host real address** via a hardware walk of the **Page Table**.  

- **Virtual address space size**: `2^n` bytes, where `65 ≤ n ≤ 78`  
  - *See Note 3*  

- **Segment size**: `2^s` bytes, where `s = 28` or `40`  

- **Number of virtual segments**:  
  - `2^(n-40) ≤ #segments ≤ 2^(n-28)`  
  - *See Note 3*  

- **Virtual page size**: `2^p` bytes  
  - `p ≥ 12`  
  - `2^p` ≤ min( size of biggest segment, real address space )  
  - Supported sizes: `4 KB`, `64 KB`, plus implementation-dependent sizes  
  - *See Note 4*  

- **Page Table**: specifies the **virtual page size**  
- **SLB**: specifies the **base virtual page size** (`2^b` bytes)  
  - Smallest virtual page size a segment can contain  

- **Segments** may contain:  
  - Pages of a single size  
  - A mixture of 4 KB and 64 KB pages  
  - A mixture of page sizes (including implementation-dependent sizes)  

---

## Radix Tree Translation

- An **effective address** is translated to a **(guest or host) real address** via a hardware walk of the **Page Table**.  

- **Virtual page size**: `2^p` bytes  
  - `p ≥ 12`  
  - `2^p ≤` real address space size  
  - Supported sizes: `4 KB`, `64 KB`, `2 MB`, plus implementation-dependent sizes  
  - *See Note 4*  

- The virtual page size is determined by the **Page Table Entry (PTE)** location in the **Radix Tree**.  

---

## Notes

> **Note 1**:  
> The value of `m` is implementation-dependent (subject to `m ≤ 60`).  
> When used to address storage or to represent a guest real address, the high-order `(60 - m)` bits of the *“60-bit”* real address must be zeros.  

> **Note 2**:  
> The hypervisor may assign a guest real address space size for each partition that uses Radix Tree translation.  
> - Accesses to guest real storage **outside this range but still mappable** by the second-level Radix Tree will cause an **HISI** or **HDSI**.  
> - Accesses to storage **outside the mappable range** will have boundedly undefined results.  

> **Note 3**:  
> The value of `n` is implementation-dependent (subject to `65 ≤ n ≤ 78`).  
> In references to *78-bit virtual addresses* elsewhere in this Book, the high-order `(78 - n)` bits of the *“78-bit”* virtual address are assumed to be zeros.  

> **Note 4**:  
> The supported values of `p` for larger virtual page sizes are implementation-dependent (subject to the above limitations).  

TLBIE,TLBIEL,TLBSYNC TLBALL(2.07)
SLBIE, SLBIA, SLBMTE, SLBMFEV, SLBMFEE, SLVFREE, 

# // LOG 2

# 6.7.3  TLB Address Translation. (2.07 Public) 

## Reffer the page numbers { 1111(1081) to 1116(1086) } To get the original materials.

<img width="1118" height="701" alt="image" src="https://github.com/user-attachments/assets/60714762-430a-40d1-aa54-1f39ae8bb754" />

<img width="1121" height="878" alt="image" src="https://github.com/user-attachments/assets/69e1c881-2efe-4377-9206-9f149b5e4917" />


- The Valid bit of the TLB entry is 1.
- MSR(IS);MSR(DS) = TS bit of the TLB
- PID (reg contents) = TID (reg contents)
- EA{n-1 : 0} = EPN {n-1:0} (effective page number of TLB) {n=64-log2(page size in bytes) }

-  One of the following conditions is true.
- The TLB array supports the IND bit
(TLBnCFGIND = 1) and the IND bit of the TLB
entry is equal to 0.
- The TLB array does not support the IND bit
(TLBnCFGIND = 0).

- LPIDR = TLPID (or) the TLPID = 0
- MSR(GS) = TGS(TLB entry)

### Bonus (TLB Entry Invalidation)

<img width="592" height="550" alt="image" src="https://github.com/user-attachments/assets/b5253560-8f4c-4ad8-912b-6de05e8b9bba" />











