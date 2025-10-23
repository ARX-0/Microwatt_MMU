# This readme file goes over the interfaces of the MMU of the a2o core 

- IERAT (communicate with the I cache and  ERAT)
- DERAT (communicate with the D-cache and ERAT)
- Load Store (SLB->TLB->PTE)
- SPR access (Read and write)

  ## starting with the outputs (Using Vivado schematics)

  <img width="918" height="796" alt="image" src="https://github.com/user-attachments/assets/684811ef-ff6b-44ad-987d-664d64f80efd" />

## with c_wrapper (being the top file) 

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
- mm_xu_t1_derat_pic[0:13]
- 
  
