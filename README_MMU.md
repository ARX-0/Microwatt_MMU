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

- tlbsrx (Translation Address Space: <E.TWC> ? ( MAS1(TS) == TS ))
- tlbsx (Translation Address Space: ? ( MAS6(SAS) == TS )) (Indirect: ? MAS6(SIND) == IND )
- tlbilx (Translation with Address Space: T = 3  ? (MAS6(SAS) == TS )) (Indirect T=3: ? MAS6(SIND) == IND )
- tliivax (Translation Address Space : with EA[61] = 0 ? (MAS6(SAS) == TS) (Indirect EA[61]=0: ? MAS6(SIND) == IND )

<img width="432" height="161" alt="image" src="https://github.com/user-attachments/assets/ceabbd35-2bad-4b97-9592-9edbdd6f8c30" />

-pg1133

The tlbivax instruction is used to invalidate TLB
entries. Additional instructions are used to read and
write, and search TLB entries, and to provide an ordering function for the effects of tlbivax

<img width="419" height="159" alt="image" src="https://github.com/user-attachments/assets/ba0aafb4-0eda-454e-91cf-8dcaa763270f" />

-pg 1134

The tlbilx instruction invalidates TLB entries in the
thread that executes the tlbilx instruction. TLB entries
which are protected by the IPROT attribute (entryIPROT
= 1) are not invalidated.

<img width="428" height="160" alt="image" src="https://github.com/user-attachments/assets/d65a3dbe-2a0a-4611-9224-9abefa0b40cd" />

-pg 1136

If any TLB array contains a valid entry matching the
MAS1IND <E.PT> and virtual address formed by
MAS5SGS <E.HV>, MAS5SLPID <E.HV>, MAS1TS TID,
and EA, the search is considered successful. 

<img width="393" height="159" alt="image" src="https://github.com/user-attachments/assets/72ef6cce-352a-4782-b499-41b882d1c179" />

-pg 1138

Let the effective address (EA) be the sum (RA|0)+
(RB).
If any TLB array contains a valid entry matching the
MAS1IND <E.PT> and virtual address formed by
MAS5SGS <E.HV>, MAS5SLPID <E.HV>, MAS1TS TID,
and EA, the search is considered successful.

<img width="404" height="143" alt="image" src="https://github.com/user-attachments/assets/55900742-3553-4f41-80d7-46f92bbd6d53" />

-pg 1139

READ TLB entry 

<img width="428" height="137" alt="image" src="https://github.com/user-attachments/assets/c99ebdc1-7d98-48e3-b0d5-ba199e1b4030" />

-pg 1141

WRITE TLB ENTRY


<img width="404" height="142" alt="image" src="https://github.com/user-attachments/assets/0344a7be-70b8-492c-ad42-0a1b6e4b800f" />

-pg 1141

The tlbsync instruction provides an ordering function
for the effects of all tlbivax instructions executed by the
thread executing the tlbsync instruction, with respect
to the memory barrier created by a subsequent sync
instruction executed by the same thread.

### w.r.t PAGE size

- tlbwe (write data to the TLB)
- tlbre (read data from the TLB)

- THE TGS (This 1-bit field indicates whether this TLB
entry is valid for the guest space or for the
hypervisor space.)

- 0 Hypervisor space
- 1 Guest space

 ## The PTE (Page Table Entry)

Each Page Table Entry (PTE) maps a VPN to an RPN.
If the corresponding indirect TLB entry has an LPID
<E.HV> or PID value of zero, multiple VPNs are
mapped by a single PTE in a Page Table pointed to by such an indirect TLB entry. Figure 24 shows the layout
of a PTE.

# The Status Control Bits

<img width="813" height="132" alt="image" src="https://github.com/user-attachments/assets/ec260dab-4123-453d-9da3-1fcb693e119c" />
<img width="380" height="555" alt="image" src="https://github.com/user-attachments/assets/239e61fb-72ad-46ee-bb6b-618a1b799e1c" />

## the PID register (Process ID) 

<img width="399" height="248" alt="image" src="https://github.com/user-attachments/assets/2890a523-f12e-4f70-8982-c96aee51e8b0" />

## the MMU config registers

<img width="426" height="275" alt="image" src="https://github.com/user-attachments/assets/13e86a0d-4db9-4f93-8e57-7f1f0ebba259" />

## TLB configuration Registers (TLBnCFG)

<img width="396" height="246" alt="image" src="https://github.com/user-attachments/assets/1daf7e36-520c-4346-b40d-edf4197ebd9b" />

## Things that I have left out 
- the LRAT Configuration register
- The LRAT page size register
- MMU control and status register (MMUCSR0)
- MAS0-MAS8 Registers # I found something interesting on (page 1109) (NV) next victim in the MAS0 register 

## the storage control instructions (Cache management instructions)

<img width="399" height="233" alt="image" src="https://github.com/user-attachments/assets/43776df3-eaa3-48ab-bc3c-9d1d79b8626e" />

<img width="401" height="165" alt="image" src="https://github.com/user-attachments/assets/e85dce7d-29b3-41ff-bdeb-741e3ac71bcb" />
-pg1121
<img width="399" height="188" alt="image" src="https://github.com/user-attachments/assets/9427bfb8-acbb-49cd-bc60-d314012756b3" />
-pg 1121



