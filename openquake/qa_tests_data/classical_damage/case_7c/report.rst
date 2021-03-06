Classical PSHA-Based Hazard
===========================

============== ===================
checksum32     949,605,442        
date           2018-02-25T06:42:03
engine_version 2.10.0-git1f7c0c0  
============== ===================

num_sites = 7, num_levels = 25

Parameters
----------
=============================== ==================
calculation_mode                'classical_damage'
number_of_logic_tree_samples    0                 
maximum_distance                {'default': 200.0}
investigation_time              50.0              
ses_per_logic_tree_path         1                 
truncation_level                3.0               
rupture_mesh_spacing            1.0               
complex_fault_mesh_spacing      1.0               
width_of_mfd_bin                0.1               
area_source_discretization      20.0              
ground_motion_correlation_model None              
minimum_intensity               {}                
random_seed                     42                
master_seed                     0                 
ses_seed                        42                
=============================== ==================

Input files
-----------
======================= ============================================================
Name                    File                                                        
======================= ============================================================
exposure                `exposure_model.xml <exposure_model.xml>`_                  
gsim_logic_tree         `gmpe_logic_tree.xml <gmpe_logic_tree.xml>`_                
job_ini                 `job_haz.ini <job_haz.ini>`_                                
source                  `source_model.xml <source_model.xml>`_                      
source_model_logic_tree `source_model_logic_tree.xml <source_model_logic_tree.xml>`_
structural_fragility    `fragility_model.xml <fragility_model.xml>`_                
======================= ============================================================

Composite source model
----------------------
========= ====== =============== ================
smlt_path weight gsim_logic_tree num_realizations
========= ====== =============== ================
b1        1.000  trivial(1)      1/1             
========= ====== =============== ================

Required parameters per tectonic region type
--------------------------------------------
====== ================ ========= ========== ==========
grp_id gsims            distances siteparams ruptparams
====== ================ ========= ========== ==========
0      SadighEtAl1997() rrup      vs30       mag rake  
====== ================ ========= ========== ==========

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(size=1, rlzs=1)
  0,SadighEtAl1997(): [0]>

Number of ruptures per tectonic region type
-------------------------------------------
================ ====== ==================== ============ ============
source_model     grp_id trt                  eff_ruptures tot_ruptures
================ ====== ==================== ============ ============
source_model.xml 0      Active Shallow Crust 1,694        1,694       
================ ====== ==================== ============ ============

Informational data
------------------
======================= ===================================================================================
count_ruptures.received tot 10.44 KB, max_per_task 825 B                                                   
count_ruptures.sent     sources 13.88 KB, srcfilter 13.32 KB, param 9.33 KB, monitor 4.19 KB, gsims 1.52 KB
hazard.input_weight     1694.0                                                                             
hazard.n_imts           3                                                                                  
hazard.n_levels         25                                                                                 
hazard.n_realizations   1                                                                                  
hazard.n_sites          7                                                                                  
hazard.n_sources        1                                                                                  
hazard.output_weight    175.0                                                                              
hostname                tstation.gem.lan                                                                   
require_epsilons        False                                                                              
======================= ===================================================================================

Exposure model
--------------
=============== ========
#assets         7       
#taxonomies     3       
deductibile     absolute
insurance_limit absolute
=============== ========

======== ===== ====== === === ========= ==========
taxonomy mean  stddev min max num_sites num_assets
Wood     1.000 0.0    1   1   3         3         
Concrete 1.000 0.0    1   1   2         2         
Steel    1.000 0.0    1   1   2         2         
*ALL*    1.000 0.0    1   1   7         7         
======== ===== ====== === === ========= ==========

Slowest sources
---------------
========= ================= ============ ========= ========= =========
source_id source_class      num_ruptures calc_time num_sites num_split
========= ================= ============ ========= ========= =========
1         SimpleFaultSource 1,694        0.061     106       15       
========= ================= ============ ========= ========= =========

Computation times by source typology
------------------------------------
================= ========= ======
source_class      calc_time counts
================= ========= ======
SimpleFaultSource 0.061     1     
================= ========= ======

Duplicated sources
------------------
There are no duplicated sources

Information about the tasks
---------------------------
================== ===== ====== ===== ===== =========
operation-duration mean  stddev min   max   num_tasks
count_ruptures     0.009 0.004  0.003 0.014 13       
================== ===== ====== ===== ===== =========

Slowest operations
------------------
============================== ========= ========= ======
operation                      time_sec  memory_mb counts
============================== ========= ========= ======
total count_ruptures           0.116     0.238     13    
managing sources               0.084     0.0       1     
reading composite source model 0.010     0.0       1     
store source_info              0.003     0.0       1     
reading exposure               0.001     0.0       1     
aggregate curves               1.814E-04 0.0       13    
saving probability maps        2.575E-05 0.0       1     
reading site collection        5.960E-06 0.0       1     
============================== ========= ========= ======