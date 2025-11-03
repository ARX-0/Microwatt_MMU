# This readme file goes over the interfaces of the MMU of the a2o core 

- IERAT (communicate with the I cache and  ERAT)
- DERAT (communicate with the D-cache and ERAT)
- Load Store (SLB->TLB->PTE)
- SPR access (Read and write)

  ## starting with the outputs (Using Vivado schematics)

  <img width="918" height="796" alt="image" src="https://github.com/user-attachments/assets/684811ef-ff6b-44ad-987d-664d64f80efd" />

## Note:- Set the c_wrapper (as the top file)  
<!--
### from top to bottom this will be the exact order of ports 
## (o/p)
- abst_scan_out[1:0]
- ac_an_lpar_id[0:7]
- bcfg_scan_out
- ccfg_scan_out
- mm_iu_ierat_snoop_attr[25:0]
- mm_iu_ierat_snoop_vpn[51:0]
- mm_iu_ierat_rel_data[131:0]
- concrete_ctrls_out[3:0]
- dcfg_scan_out
- debug_bus_out[0:31]
- func_scan_out[0:9]
- gptr_scan_out
- mm_pc_bo_fail[0:4]
- mm_pc_bo_diagout[0:4]
- mm_event_bus_out[0:3]
- mm_iu_ierat_mmucr[8:0]
- mmu_iu_tlbwe_binv
- mm_pc_htw_quiesce[0:0]
- mm_pc_inval_quiesce[0:0]
- mm_pc_tlb_ctl_quiesce[0:0]
- mm_pc_tlb_req_quiesce[0:0]
- mm_iu_ierat_snoop_comming
- mm_xu_derat_snoop_comming
- mm_iu_ierat_snoop_val
- mm_xu_derat_snoop_vpn[51:0]
- mm_xu_itag[0:6]
- mm_su_lsu_addr[22:63]
- mm_xu_lsu_lpid[0:7]
- mm_xu_lsu_wimge[0:4]
- mm_xu_lsu_ttype[0:1]
- mm_xu_lsu_u[3:0]
- mm_iu_t0_ierat_mmuc[0:19]
- mm_xu_lsu_lpdir[0:7]
- mm_iu_t0_ierat_pid[0:13]
- mm_xu_t0_derat_pid[0:13]
- mm_xu_ex3_flush_req[0:0]
- mm_xu_ord_n_flush_req_ored
- mm_xu__ord_tlb_multihit
- mm_xu_ord_tlb_par_er
- mm_xu_ord_write_done[0:0]
- mm_xu_ord_write_done_ored
- mm_xu_t0_derat_mmucr[0:19]
- repr_scan_out
- time_scan_out
- mm_iu_t1_ierat_pid[0:13]
- mm_xu_t1_derat_mmucr0[0:19]
- mm_iu_t1_ierat_mmucr0[0:19]
- mm_xu_t1_derat_pid[0:13]
- slowspr_etid_out[0:1]
- slowspr_addr_out[0:9]
- mm_xu_lsu_req[0:0]
- slow_spr_data_out[63:0]
- slowspr_done_out
- slowspr_rw_out
- slowspr_val_out
- ac_an_back_inv_reject
- mm_xu_derat_mmucr1[0:9]
- mm_xu_ord_read_done[0:0]
- mm_iu_bus_snoop_hold_done[0:0]
- mm_iu_bus_snoop_hold_req[0:0]
- mm_iu_flush_req[0:0]
- mm_iu_hold_done[0:0]
- mm_iu_hold_req[0:0]
- mm_pc_local_snoop_reject_ored
- mm_xu_illeg_instr[0:0]
- mm_xu_illeg_instr_ored
- mm_xu_local_snoop_reject[0:0]
- mm_xu_lsu_gs
- mm_xu_lsu_lbit
- mm_xu_quiesce[0:0]
- mm_xu_od_read_done_ored
- mm_xu_Derat_rel_data[0:131]
- mm_iu_tlbi_complete[0:0]
- mm_xu_c0_eq[0:0]
- mm_xu_cr0_eq_valid
- mm_xu_derat_rel_emq[3:0]
- mm_xu_hv_priv
- mm_xuderat_rel_itag[0:6]
- mm_xu_lrat_miss[0:0]
- mm_xu_lru_aprr_err[0:0]
- mm_xu_pt_fault[0:0]
- mm_xu_tlb_multihit_err[0:0]
- mm_xu_tlb_par_err[0:0]
- mm_xu_tlb_miss[0:0]
- mm_iu_ierat_rel_val[0:4]
- mm_xu_derat_rel_val[0:4]
- mm_xu_derat_snoop_attr[0:25]
- mm_pc_lru_par_err_ored
- mm_pc_tlb_multihit_err_ored
- mm_xu_cr0_eq_ored
- mm_xu_c0_eq_valid_ored
- mm_xu_eratmiss_done[0:0]
- mm_xu_esr_epid[0:0]
- mm_xu_esr_pt[0:0]
- mm_xu_esr_st[0:0]
- mm_xu_hv_priv_ored
- mm_xu_lrat_miss_ored
- mm_xu_pt_fault_ored
- mm_xu_tlb_inelig_ored
- mm_xu_tlb_miss_ored

# (i/p)
### Input peripherals 
- iu_mm_ierat_epn[51:0]
- an_ac_reld_core_tag[4:0]
- iu_mm_ierat_tid[13:0]
- lq_mm_derat_req_emq[0:3]
- an_ac_reld_data[1:127]
- slowspr_data_in[0:63]
- an_ac_back_inv_addr[22:63]
- iu_mm_ierat_mmucr0[0:17]
- an_ac_back_inv_lpar_id[0:7]
- iu_mm_ierat__mmucr[0:3]
- iu_mm_ierat_state[0:3]
- debug_bus_in[0:31]
- pc_mm_func_sl_thold_3[0:1]
- pc_mm_func_spl_nsl_thold_3
- pc_mm_func_slp_sl_thold[0:1]
- slowspr_addr_in[0:9]
- lq_mm_derat_req_itag[0:6]
- an_ac_reld_qw[58:59]
- coretracew_Ctrls_in[0:3]
- mm_event_bus_in[0:3]
- xu_mm_ex2_eff_addr[0:63]
- xu_mm_derat_epn[0:51]
- xu_mm_ex1_rs_is[0:8]
- xu_ex2_flush[0:0]
- xu_ex5_flush[0:0]
- xu_ex3_flush[0:0]
- xu_mm_derat_lpid[0:7]
- xu_mm_derat_state[0:3]
- xu_mm_derat_tid[0:13]
- xu_mm_derat_ttype[0:1]
- pc_mm_debug_mux1_ctrls[0:10]
-->
-->
# (i/p)
### the IERAT instructions (instr Eff to Real address translation)

- iu_mm_ierat_epn[51:0]
- iu_mm_ierat_tid[13:0]
- iu_mm_ierat_mmucr0[0:17]
- iu_mm_ierat_state[0:3]
- iu_mm_ierat__mmucr[0:3]

### DERAT (Data Effective-to-Real Address Translation)

- xu_mm_derat_epn[0:51]
- xu_mm_derat_lpid[0:7]
- xu_mm_derat_state[0:3]
- xu_mm_derat_tid[0:13]
- xu_mm_derat_ttype[0:1]
- lq_mm_derat_req_emq[0:3]
- lq_mm_derat_req_itag[0:6]

### Load/store and memory operations 
- an_ac_reld_core_tag[4:0]
- an_ac_reld_data[1:127]
- an_ac_reld_qw[58:59]
- an_ac_back_inv_addr[22:63]
- an_ac_back_inv_lpar_id[0:7]
- xu_mm_ex2_eff_addr[0:63]
- xu_mm_ex1_rs_is[0:8]
- xu_ex2_flush[0:0]
- xu_ex3_flush[0:0]
- xu_ex5_flush[0:0]

### SPR Access/ Debug/ Control
- slowspr_data_in[0:63]
- slowspr_addr_in[0:9]
- pc_mm_func_sl_thold_3[0:1]
- pc_mm_func_spl_nsl_thold_3
- pc_mm_func_slp_sl_thold[0:1]
- debug_bus_in[0:31]
- coretracew_Ctrls_in[0:3]
- mm_event_bus_in[0:3]
- pc_mm_debug_mux1_ctrls[0:10]



# (o/p)
### The DERAT Related signals 

- mm_xu_derat_snoop_comming  
- mm_xu_derat_snoop_vpn[51:0]  
- mm_xu_derat_snoop_attr[0:25]  
- mm_xu_derat_rel_val[0:4]  
- mm_xu_derat_rel_emq[3:0]  
- mm_xuderat_rel_itag[0:6]  
- mm_xu_Derat_rel_data[0:131]  
- mm_xu_t0_derat_mmucr[0:19]  
- mm_xu_t1_derat_mmucr0[0:19]  
- mm_xu_derat_mmucr1[0:9]  
- mm_xu_t0_derat_pid[0:13]  
- mm_xu_t1_derat_pid[0:13]  

### The IERAT related signals

- mm_iu_ierat_snoop_attr[25:0]  
- mm_iu_ierat_snoop_vpn[51:0]  
- mm_iu_ierat_rel_data[131:0]  
- mm_iu_ierat_mmucr[8:0]  
- mm_iu_t0_ierat_mmuc[0:19]  
- mm_iu_t0_ierat_pid[0:13]  
- mm_iu_t1_ierat_pid[0:13]  
- mm_iu_t1_ierat_mmucr0[0:19]  
- mm_iu_ierat_snoop_comming  
- mm_iu_ierat_rel_val[0:4]  

### The LRAT related signals

- mm_xu_lrat_miss[0:0]  
- mm_xu_lrat_miss_ored  

### LSU related datapath control signals 

- mm_su_lsu_addr[22:63]  
- mm_xu_lsu_lpid[0:7]  
- mm_xu_lsu_wimge[0:4]  
- mm_xu_lsu_ttype[0:1]  
- mm_xu_lsu_u[3:0]  
- mm_xu_lsu_lpdir[0:7]  
- mm_xu_lsu_req[0:0]  
- mm_xu_lsu_gs  
- mm_xu_lsu_lbit  

### Slow SPR interface

- slowspr_etid_out[0:1]  
- slowspr_addr_out[0:9]  
- slow_spr_data_out[63:0]  
- slowspr_done_out  
- slowspr_rw_out  
- slowspr_val_out

### Parity, Faults, Errors ,Illegal/Privilige signals 

- mm_xu_tlb_multihit_err[0:0]  
- mm_xu_tlb_par_err[0:0]  
- mm_xu_tlb_miss[0:0]  
- mm_xu_pt_fault[0:0]  
- mm_xu_lru_aprr_err[0:0]  
- mm_pc_lru_par_err_ored  
- mm_pc_tlb_multihit_err_ored  
- mm_xu_tlb_miss_ored  
- mm_xu_tlb_inelig_ored  
- mm_xu_pt_fault_ored  
- mm_xu_lrat_miss_ored  
- mm_xu_cr0_eq_valid  
- mm_xu_c0_eq_valid_ored  
- mm_xu_cr0_eq_ored  
- mm_xu_c0_eq[0:0]  
- mm_xu_illeg_instr[0:0]  
- mm_xu_illeg_instr_ored  
- mm_xu_hv_priv  
- mm_xu_hv_priv_ored  
- mm_xu_esr_epid[0:0]  
- mm_xu_esr_pt[0:0]  
- mm_xu_esr_st[0:0]

### Bus/Quiesce/Flush/Ordering Controls

- mm_pc_bo_fail[0:4]  
- mm_pc_bo_diagout[0:4]  
- mm_pc_htw_quiesce[0:0]  
- mm_pc_inval_quiesce[0:0]  
- mm_pc_tlb_ctl_quiesce[0:0]  
- mm_pc_tlb_req_quiesce[0:0]  
- mm_pc_local_snoop_reject_ored  
- mm_xu_quiesce[0:0]  
- mm_xu_ord_n_flush_req_ored  
- mm_xu__ord_tlb_multihit  
- mm_xu_ord_tlb_par_er  
- mm_xu_ord_write_done[0:0]  
- mm_xu_ord_write_done_ored  
- mm_xu_od_read_done_ored  
- mm_xu_ord_read_done[0:0]  
- mm_xu_ex3_flush_req[0:0]  
- mm_iu_flush_req[0:0]  
- mm_iu_hold_req[0:0]  
- mm_iu_hold_done[0:0]  
- mm_iu_bus_snoop_hold_req[0:0]  
- mm_iu_bus_snoop_hold_done[0:0]  
- mm_pc_tlb_multihit_err_ored  
- mm_iu_tlbi_complete[0:0]

### Scan chain/ debug / misc channels 

- abst_scan_out[1:0]  
- bcfg_scan_out  
- ccfg_scan_out  
- dcfg_scan_out  
- repr_scan_out  
- time_scan_out  
- func_scan_out[0:9]  
- gptr_scan_out  
- concrete_ctrls_out[3:0]  
- debug_bus_out[0:31]

### Cross domain control coherence rejection 

- ac_an_back_inv_reject  
- mm_pc_local_snoop_reject_ored  
- mm_xu_local_snoop_reject[0:0]


  


  
