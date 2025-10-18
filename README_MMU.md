# The instructions that i observed in 2.07 MMU TLB

### PG 1077
<img width="735" height="768" alt="image" src="https://github.com/user-attachments/assets/d5a5ba05-a6a5-46fc-b14f-f361c61c9007" />
<img width="1280" height="1250" alt="image" src="https://github.com/user-attachments/assets/90d80dd5-a581-4eb5-aae9-77adce93c9ce" />

The effective address space is divided into pages. The
page represents the granularity of effective address
translation, access control, and storage control
attributes. In MMU Architecture Version 1.0, up to sixteen page sizes (1KB, 4KB, 16KB, 64KB, 256KB, 1MB,
4MB, 16MB, 64MB, 256MB, 1GB, 4GB, 16GB, 64GB,
256GB, 1TB) may be simultaneously supported. 


# 6.7.3  TLB Address Translation. (2.07 Public) 

## Reffer the page numbers { 1111(1081) to 1116(1086) } To get the original materials.

<img width="1118" height="701" alt="image" src="https://github.com/user-attachments/assets/60714762-430a-40d1-aa54-1f39ae8bb754" />

<img width="1121" height="878" alt="image" src="https://github.com/user-attachments/assets/69e1c881-2efe-4377-9206-9f149b5e4917" />

#### The pages for you to KNOW the context in the 2.07 ISA doc (1078-1081)

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

## new instructions (referencing the figure 22)

- tlbsrx <E.TWC> ? ( MAS1(TS) == TS )
- tlbilx ? ( MAS6(SAS) == TS )
- tlbilx with T = 3  ? (MAS6(SAS) == TS )
- tliibax with EA[61] = 0 ? (MAS6(SAS) == TS
