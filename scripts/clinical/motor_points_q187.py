#!/usr/bin/env python3
"""Q187: muscle motor points / intramuscular innervation zones, placed on all four viewers.

PRIVATE CLINICAL LAYER (see PROJECT_STATE.md licensing rule and clinical/LICENSE_PRIVATE.md).
This script READS the anatomy viewers (their published geometry) and WRITES only
clinical/data/motor_points.json and data/derived/Q187_motor_points_coverage.json. It never
writes into an anatomy bundle.

Method (every point):
  1. Each source rule is a landmark rule from a real published study (citation, DOI, PMID in
     SOURCES; the rule in the source's own terms in RULES).
  2. The landmarks are measured on EACH body's own bones (or, where the source's line runs
     origin->insertion of the muscle itself, on that body's own muscle mesh ends).
  3. Rule types:
       level    -- a % (or mm) along a landmark line, no transverse coordinate: the point is
                   placed in the muscle's cross-section in the plane perpendicular to the line
                   at that level (section centroid, or the named sector of it).
       surface  -- a 2-D surface coordinate (oblique % axes, or % plus a mm offset): the point
                   is placed mid-way through the muscle on the needle line through that surface
                   coordinate along the source's approach direction.
     projection_mm = distance from the rule's plane / needle line to the placed point.
  4. Placed points are tested INSIDE the muscle mesh (generalised winding number). A rule
     whose plane/line misses the muscle by >5 mm is recorded as FAILED, never forced.

    python3 scripts/clinical/motor_points_q187.py [--viewers vhm,vhf,zan_m,zan_f] [--render DIR]
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
OUT_JSON = REPO / "clinical" / "data" / "motor_points.json"
OUT_COVERAGE = REPO / "data" / "derived" / "Q187_motor_points_coverage.json"
FAIL_MM = 5.0
UNC_FLOOR_MM = 5.0  # source SDs below this ignore the error of finding the landmark on a mesh

VIEWERS = {
    "vhm": {"kind": "own", "html": REPO / "build/viewer_m_hr/atlas_viewer_male.html",
            "bin": REPO / "build/viewer_m_hr/bundle.bin", "label": "own male (Visible Human male)"},
    "vhf": {"kind": "own", "html": REPO / "build/viewer_f_hr/atlas_viewer_female.html",
            "bin": REPO / "build/viewer_f_hr/bundle.bin", "label": "own female (Visible Human female)"},
    "zan_m": {"kind": "zan", "html": REPO / "build/viewer_zan_atlas/atlas_viewer_zan_atlas.html",
              "label": "Z-Anatomy (generic male reference)"},
    "zan_f": {"kind": "zan", "html": REPO / "build/viewer_zan_female/atlas_viewer_zan_female.html",
              "label": "Z-Anatomy fitted to the female body"},
}
FRAME = "atlas mm (+X right,+Y superior,+Z anterior)"

# --------------------------------------------------------------------------- sources
SOURCES = {
    "kwon2009": dict(citation="Kwon JY, Kim JS, Lee WI. Anatomic localization of motor points of hip adductors. Am J Phys Med Rehabil 2009;88(4):336-341", doi="10.1097/PHM.0b013e3181619435", pmid="18174845"),
    "an2010": dict(citation="An XC, Lee JH, Im S, Lee MS, Hwang K, Kim HW, Han SH. Anatomic localization of motor entry points and intramuscular nerve endings in the hamstring muscles. Surg Radiol Anat 2010;32(6):529-537", doi="10.1007/s00276-009-0609-5", pmid="20063163"),
    "rha2016": dict(citation="Rha DW, Yi KH, Park ES, Park C, Kim HJ. Intramuscular nerve distribution of the hamstring muscles: application to treating spasticity. Clin Anat 2016;29(6):746-751", doi="10.1002/ca.22735", pmid="27213466"),
    "lee2011pl": dict(citation="Lee JH, Lee BN, An X, Chung RH, Kwon SO, Han SH. Anatomic localization of motor entry point of superficial peroneal nerve to peroneus longus and brevis muscles. Clin Anat 2011;24(2):232-236", doi="10.1002/ca.21076", pmid="21322046"),
    "choi2019fib": dict(citation="Choi YJ, Cho TH, Won SY, Yang HM. Guideline for botulinum toxin injections in the effective treatment of fibular spasticity. Clin Anat 2020;33(3):365-369", doi="10.1002/ca.23487", pmid="31581308"),
    "lee2010scm": dict(citation="Lee JH, Lee BN, Han SH, An XC, Chung RH. The effective zone of botulinum toxin A injections in the sternocleidomastoid muscle. Surg Radiol Anat 2011;33(3):185-190", doi="10.1007/s00276-010-0729-y", pmid="20886338"),
    "yi2019scm": dict(citation="Yi KH, Choi YJ, Cong L, Lee KL, Hu KS, Kim HJ. Effective botulinum toxin injection guide for treatment of cervical dystonia. Clin Anat 2020;33(2):192-198", doi="10.1002/ca.23430", pmid="31301235"),
    "choi2023tfl": dict(citation="Choi S, Yang HM, Cho TH, Yeo IS, Won SY. Intramuscular innervation of the tensor fasciae latae: application to total hip arthroplasty. Clin Anat 2023;36(8):1089-1094", doi="10.1002/ca.24034", pmid="36864670"),
    "yi2024vm": dict(citation="Yi KH, Hu H, Hwang SO, Ahn H, Lee JH, Lee HJ. Intramuscular neural distribution of the vastus medialis for botulinum neurotoxin injection: application to spasticity. Surg Radiol Anat 2024;46(12):2067-2073", doi="10.1007/s00276-024-03482-y", pmid="39400571"),
    "yi2026vl": dict(citation="Yi KH, Hu H, Hwang SO, Lee JH, Lee HJ. Intramuscular neural distribution of the vastus lateralis (Sihler's staining). Sci Rep 2026;16(1):5353", doi="10.1038/s41598-026-37960-7", pmid="41644588"),
    "page2019": dict(citation="Page BJ, Mrowczynski OD, Payne RA, Tilden SE, Lopez H, Rizk E, Harbaugh K. Motor entry points of the femoral nerve branches to the quadriceps. Cureus 2019;11(1):e3882", doi="10.7759/cureus.3882", pmid="30899633"),
    "yi2021sart": dict(citation="Yi KH, Lee JH, Lee DK, Hu HW, Seo KK, Kim HJ. Anatomical locations of the motor endplates of sartorius muscle for botulinum toxin injections in treatment of muscle spasticity. Surg Radiol Anat 2021;43(12):2025-2030", doi="10.1007/s00276-021-02813-7", pmid="34378107"),
    "diaconu3": dict(citation="Diaconu S et al. The Elias University Hospital approach: a visual guide to ultrasound-guided botulinum toxin injection in spasticity. Part III -- proximal lower limb muscles. Toxins (Basel) 2025;17(5):240 (review synthesis of the Sihler/motor-point literature)", doi="10.3390/toxins17050240", pmid="40423325"),
    "diaconu4": dict(citation="Diaconu S et al. The Elias University Hospital approach: a visual guide to ultrasound-guided botulinum toxin injection in spasticity. Part IV -- distal lower limb muscles. Toxins (Basel) 2025;17(10):508 (review synthesis)", doi="10.3390/toxins17100508", pmid="41150208"),
    "diaconu2": dict(citation="Diaconu S et al. The Elias University Hospital approach: a visual guide to ultrasound-guided botulinum toxin injection in spasticity. Part II -- proximal upper limb muscles. Toxins (Basel) 2025;17(6):276 (review synthesis; brachioradialis zones after Yang et al. 2017)", doi="10.3390/toxins17060276", pmid="40559854"),
    "yi2016ta": dict(citation="Yi KH, Cong L, Bae JH, Park ES, Rha DW, Kim HJ. Neuromuscular structure of the tibialis anterior muscle for functional electrical stimulation. Surg Radiol Anat 2017;39(1):77-83", doi="10.1007/s00276-016-1698-6", pmid="27206542"),
    "yi2023gc": dict(citation="Yi KH, Park HJ, Kim JH, Kim SO, Cheon GW, An MH. Intramuscular neural distribution of the gastrocnemius for botulinum neurotoxin injection: application to cosmetic calf shaping. Yonsei Med J 2023;64(8):511-517", doi="10.3349/ymj.2023.0124", pmid="37488703"),
    "yi2025sol": dict(citation="Yi KH, Hu H, Hwang SO, Lee JH, Lee HJ. Intramuscular neural distribution of the soleus for botulinum neurotoxin injection: application to spasticity. Sci Rep 2025;16(1):279", doi="10.1038/s41598-025-07508-2", pmid="41444715"),
    "huang2024": dict(citation="Huang K, Ye X, Zhu S, Liu Y, Sun F, Su X. Anatomical study of the motor branches of the tibial nerve and incision design for hyperselective neurectomy. Surg Radiol Anat 2024;46(7):1121-1129", doi="10.1007/s00276-024-03383-0", pmid="38743143"),
    "lee2010tp": dict(citation="Lee JH, Lee BN, An X, Chung RH, Han SH. Location of the motor entry point and intramuscular motor point of the tibialis posterior muscle: for effective motor point block. Clin Anat 2011;24(1):91-96", doi="10.1002/ca.21062", pmid="21154644"),
    "oddy2006": dict(citation="Oddy MJ, Brown C, Mistry R, Eastwood DM. Botulinum toxin injection site localization for the tibialis posterior muscle. J Pediatr Orthop B 2006;15(6):414-417", doi="10.1097/01.bpb.0000228387.94065.ff", pmid="17001247"),
    "kim2026pop": dict(citation="Kim SJ, Lee JH, Yeo IS. Intramuscular innervation of the popliteus. Diagnostics (Basel) 2026;16(6):834", doi="10.3390/diagnostics16060834", pmid="41897567"),
    "yi2021pir": dict(citation="Yi KH, Lee KL, Lee JH, Hu HW, Lee K, Seo KK, Kim HJ. Guidelines for botulinum neurotoxin injections in piriformis syndrome. Clin Anat 2021;34(7):1028-1034", doi="10.1002/ca.23711", pmid="33347678"),
    "vancampenhout2010": dict(citation="Van Campenhout A, Hubens G, Fagard K, Molenaers G. Localization of motor nerve branches of the human psoas muscle. Muscle Nerve 2010;42(2):202-207", doi="10.1002/mus.21660", pmid="20544927"),
    "yi2023delt": dict(citation="Yi KH, Lee JH, Hu H, Park HJ, Lee HJ, Choi YJ. Botulinum neurotoxin injection in the deltoid muscle: application to cosmetic shoulder contouring. Surg Radiol Anat 2023;45(7):875-880", doi="10.1007/s00276-023-03163-2", pmid="37178218"),
    "lee2009bb": dict(citation="Lee JH, Kim HW, Im S, An X, Lee MS, Lee UY. Localization of motor entry points and terminal intramuscular nerve endings of the musculocutaneous nerve to biceps and brachialis muscles. Surg Radiol Anat 2010;32(3):213-220", doi="10.1007/s00276-009-0561-4", pmid="19779662"),
    "park2007": dict(citation="Park BK, Shin YB, Ko HY, Park JH, Baek SY. Anatomic motor point localization of the biceps brachii and brachialis muscles. J Korean Med Sci 2007;22(3):459-462", doi="10.3346/jkms.2007.22.3.459", pmid="17596654"),
    "amirali2007": dict(citation="Amirali A, Mu L, Gracies JM, Simpson DM. Anatomical localization of motor endplate bands in the human biceps brachii. J Clin Neuromuscul Dis 2007;9(2):306-312", doi="10.1097/CND.0b013e31815c13a7", pmid="18090684"),
    "yi2023tri": dict(citation="Yi KH, Lee JH, Hur HW, Lee HJ, Choi YJ, Kim HJ. Distribution of the intramuscular innervation of the triceps brachii: clinical importance in the treatment of spasticity with botulinum neurotoxin. Clin Anat 2023;36(7):964-970", doi="10.1002/ca.24004", pmid="36606364"),
    "zhou2023": dict(citation="Zhou J, Jia F, Chen P, Zhou G, Wang M, Wu J, Yang S. Localisation of the centre of the highest region of muscle spindle abundance of anterior forearm muscles. J Anat 2024;244(5):803-814", doi="10.1111/joa.14000", pmid="38155435"),
    "caetano2020": dict(citation="Caetano EB, Vieira LA, Sabongi Neto JJ, Caetano MBF, Picin CP, Silva Junior LCN. Anatomical study of the motor branches of the radial nerve to the extensor carpi radialis longus, brevis and supinator. Rev Bras Ortop 2020;55(6):(PMC7748920)", doi="10.1055/s-0040-1713403", pmid="33364657"),
    "xie2012": dict(citation="Xie P, Jiang Y, Zhang X, Yang S. The study of intramuscular nerve distribution patterns and relations of the thenar and hypothenar muscles. PLoS One 2012;7(12):e51538", doi="10.1371/journal.pone.0051538", pmid="23251569"),
    "lee2022ssp": dict(citation="Lee HJ, Lee JH, Yi KH, Kim HJ. Intramuscular innervation of the supraspinatus muscle assessed using Sihler's staining: potential application in myofascial pain syndrome. Toxins (Basel) 2022;14(5):310", doi="10.3390/toxins14050310", pmid="35622557"),
    "lee2023isp": dict(citation="Lee HJ, Lee JH, Yi KH, Kim HJ. Anatomical analysis of the motor endplate zones of the infraspinatus. J Anat 2023;243(1) (PMC10439366)", doi="10.1111/joa.13868", pmid="36988105"),
    "yi2023tm": dict(citation="Yi KH, Lee KW, Hu HW, Lee JH, Lee HJ. A practical guide to botulinum neurotoxin treatment of teres major muscle in shoulder spasticity: intramuscular neural distribution. PM R 2024;16(2):160-164", doi="10.1002/pmrj.13048", pmid="37526565"),
    "yi2020rh": dict(citation="Yi KH, Lee HJ, Choi YJ, Hu KS, Kim HJ. Intramuscular neural distribution of rhomboid muscles: evaluation for botulinum toxin injection using modified Sihler's method. Toxins (Basel) 2020;12(5):289", doi="10.3390/toxins12050289", pmid="32375284"),
    "lee2023ls": dict(citation="Lee JH, Lee KW, Yi KH, Lee HJ. Anatomical analysis of the intramuscular distribution patterns of the levator scapulae and the clinical implications for pain management. Surg Radiol Anat 2023;45(7):859-864", doi="10.1007/s00276-023-03146-3", pmid="37138162"),
    "yi2020trap": dict(citation="Yi KH, Lee HJ, Choi YJ, Lee K, Lee JH, Kim HJ. Anatomical guide for botulinum neurotoxin injection: application to cosmetic shoulder contouring, pain syndromes, and cervical dystonia. Clin Anat 2021;34(6):822-828", doi="10.1002/ca.23690", pmid="32996645"),
    "kwon2020sp": dict(citation="Kwon HJ, Yang HM, Won SY. Intramuscular innervation patterns of the splenius capitis and splenius cervicis and their clinical implications for botulinum toxin injections. Clin Anat 2020;33(8):1138-1143", doi="10.1002/ca.23553", pmid="31894602"),
    "wang2024": dict(citation="Wang D, Chen P, Jia F, Wang M, Wu J, Yang S. Division of neuromuscular compartments and localization of the center of the intramuscular nerve-dense region in deep cervical muscles. Front Neuroanat 2024;18:1340468", doi="10.3389/fnana.2024.1340468", pmid="38840810"),
    "li2021pec": dict(citation="Li Y, Wang M, Tang S, Zhu X, Yang S. Localization of nerve entry points and the center of intramuscular nerve-dense regions in the adult pectoralis major and pectoralis minor and its significance in blocking muscle spasticity. J Anat 2021;239(5):1123-1133", doi="10.1111/joa.13493", pmid="34176122"),
}

# --------------------------------------------------------------------------- rules
# f: percent (single value, (lo,hi) range, or (mean, sd) with sd=True). Lines run A (0 %) -> B (100 %).
# Landmark names are the functions in LANDMARKS; "mend:<hint>" = this body's own muscle-mesh end
# (origin end chosen by the hint direction; the other end is the insertion).
# sel = sector of the cross-section (axis lat|ant|sup, band of the section's extent) used when the
# body has ONE mesh for a muscle the source maps per head/part; parts = per-part structure ids.

def R(muscle, src, kind, typ, rule, **kw):
    d = dict(muscle=muscle, src=src, kind=kind, type=typ, rule=rule)
    d.update(kw)
    return d


RULES = [
    # ---------------- hip adductors / medial thigh (Kwon 2009: motor points, mean +/- SD)
    *[R(m, "kwon2009", "motor_point", "surface", f"Motor point at {fl}% (SD {sl}) of the pubic tubercle -> medial femoral epicondyle line (distal to the pubic tubercle) and {fh}% (SD {sh}) of the pubic tubercle -> greater trochanter line (lateral to it).",
        O="pubic_tubercle", B1="femur_ME", f1=(fl, sl), B2="femur_GT", f2=(fh, sh), approach="ant", nerve="obturator nerve (anterior/posterior divisions)" if m != "adductor_magnus" else None)
      for m, fl, sl, fh, sh in [("adductor_longus", 26.0, 4.8, 24.9, 7.8), ("adductor_brevis", 21.0, 4.8, 24.9, 7.4), ("adductor_magnus", 30.4, 4.1, 33.6, 5.9)]],
    R("gracilis", "kwon2009", "motor_point", "level", "Motor point at 32.1% (SD 2.1) of the pubic tubercle -> medial femoral epicondyle line (no transverse coordinate reported).",
      A="pubic_tubercle", B="femur_ME", f=(32.1, 2.1)),
    # ---------------- hamstrings (An 2010 MEPs: x on IT->ME line, y on IT->GT line)
    *[R(m, "an2010", "motor_point", "surface", f"Motor entry point at {x}% of the superior-medial ischial tuberosity -> proximal medial femoral epicondyle line (x) and {y}% of the ischial tuberosity -> lateral greater trochanter line (y){lbl}.",
        O="ischial_tub", B1="femur_ME", f1=x, B2="femur_GT", f2=y, approach="post", label=lab, sel=sel, nerve=nv)
      for m, lab, x, y, sel, lbl, nv in [
          ("biceps_femoris", "long head", 41.5, 36.3, None, " (long head)", "tibial division of the sciatic nerve"),
          ("biceps_femoris", "short head", 56.2, 59.7, None, " (short head)", "common fibular division of the sciatic nerve"),
          ("semitendinosus", "upper zone", 20.3, 18.9, None, " (upper of two innervation zones)", "tibial division of the sciatic nerve"),
          ("semitendinosus", "lower zone", 59.9, 21.4, None, " (lower of two innervation zones)", "tibial division of the sciatic nerve"),
          ("semimembranosus", None, 62.2, 18.8, None, "", "tibial division of the sciatic nerve")]],
    *[R(m, "rha2016", "innervation_zone", "level", f"Intramuscular arborization at {lo}-{hi}% of the line from the medial/lateral tibial condyles (0%) to the ischial tuberosity (100%).",
        A="tibial_condyles_mid", B="ischial_tub", f=(lo, hi), label=lab)
      for m, lo, hi, lab in [("biceps_femoris", 15, 30, "distal zone"), ("biceps_femoris", 50, 60, "proximal zone"),
                             ("semitendinosus", 25, 40, "distal zone"), ("semitendinosus", 60, 80, "proximal zone"),
                             ("semimembranosus", 20, 40, None)]],
    # ---------------- quadriceps, sartorius, TFL
    R("rectus_femoris", "diaconu3", "innervation_zone", "level", "Motor-point concentration at 40% of the ASIS -> superior patellar edge line (review synthesis).", A="ASIS", B="patella_base", f=40, label="proximal", nerve="femoral nerve"),
    R("rectus_femoris", "diaconu3", "innervation_zone", "level", "Motor-point concentration at 60% of the ASIS -> superior patellar edge line (review synthesis).", A="ASIS", B="patella_base", f=60, label="distal", nerve="femoral nerve"),
    R("vastus_lateralis", "yi2026vl", "innervation_zone", "level", "Highest intramuscular nerve-ending density in zone 3 = 50-75% of the greater trochanter -> base of patella line (modified Sihler).", A="femur_GT", B="patella_base", f=(50, 75)),
    R("vastus_medialis", "yi2024vm", "innervation_zone", "level", "Prominent intramuscular nerve distribution in areas 6-9 of 10 (50-90%) of the ASIS -> base of patella line (modified Sihler).", A="ASIS", B="patella_base", f=(50, 90)),
    R("vastus_intermedius", "page2019", "motor_point", "level", "Motor branch entry at a mean ratio of 0.30 (SD 0.05) of the line from the femoral nerve at the inguinal ligament (taken here as the mid-inguinal point) to the superior patellar margin.", A="mid_inguinal", B="patella_base", f=(30, 5), nerve="femoral nerve"),
    R("sartorius", "yi2021sart", "innervation_zone", "level", "Intramuscular neural distribution densely at 20-40% of the ASIS (0%) -> medial femoral epicondyle (100%) line.", A="ASIS", B="femur_ME", f=(20, 40), label="proximal zone"),
    R("sartorius", "yi2021sart", "innervation_zone", "level", "Intramuscular neural distribution densely at 60-80% of the ASIS (0%) -> medial femoral epicondyle (100%) line.", A="ASIS", B="femur_ME", f=(60, 80), label="distal zone"),
    R("tensor_fasciae_latae", "choi2023tfl", "motor_point", "level", "Superior gluteal nerve entry at 16.71% (SD 2.55) of the ASIS -> patella line (patella taken as its centre).", A="ASIS", B="patella_center", f=(16.71, 2.55), nerve="superior gluteal nerve"),
    # ---------------- leg
    R("tibialis_anterior", "yi2016ta", "motor_point", "level", "Nerve entry points densely between 86.5 and 90.6% of the lateral malleolus (0%) -> fibular head (100%) line.", A="lat_malleolus_tip", B="fibular_head", f=(86.5, 90.6), nerve="deep fibular nerve"),
    R("tibialis_anterior", "yi2016ta", "innervation_zone", "level", "Dense intramuscular arborization at 70-80% of the lateral malleolus (0%) -> fibular head (100%) line.", A="lat_malleolus_tip", B="fibular_head", f=(70, 80), nerve="deep fibular nerve"),
    R("fibularis_longus", "lee2011pl", "motor_point", "level", "Motor entry points gathered at 20-40% of the most proximal fibular head -> most distal lateral malleolus line.", A="fibular_head", B="lat_malleolus_tip", f=(20, 40), nerve="superficial fibular nerve"),
    R("fibularis_brevis", "lee2011pl", "motor_point", "level", "Motor entry points gathered at 40-60% of the most proximal fibular head -> most distal lateral malleolus line.", A="fibular_head", B="lat_malleolus_tip", f=(40, 60), nerve="superficial fibular nerve"),
    R("fibularis_longus", "choi2019fib", "innervation_zone", "level", "Highest nerve-ending density in section 2 of 4 (25-50%) from the fibular head to the lateral malleolus.", A="fibular_head", B="lat_malleolus_tip", f=(25, 50)),
    R("fibularis_brevis", "choi2019fib", "innervation_zone", "level", "Highest nerve-ending density in section 3 of 4 (50-75%) from the fibular head to the lateral malleolus.", A="fibular_head", B="lat_malleolus_tip", f=(50, 75)),
    R("gastrocnemius", "yi2023gc", "innervation_zone", "level", "Greatest arborization in the 7/10-8/10 section of the medial head, measured from the transverse line of the calcaneal tuberosity (0) to that of the fibular head (1).", A="calcaneal_tub", B="fibular_head", f=(70, 80), label="medial head", sel=[("lat", 0.0, 0.5)]),
    R("gastrocnemius", "yi2023gc", "innervation_zone", "level", "Greatest arborization in the 7.5/10-8.5/10 section of the lateral head, measured from the transverse line of the calcaneal tuberosity (0) to that of the fibular head (1).", A="calcaneal_tub", B="fibular_head", f=(75, 85), label="lateral head", sel=[("lat", 0.5, 1.0)]),
    R("gastrocnemius", "huang2024", "motor_point", "level_mm", "Nerve entry into the medial head 14-33 mm distal to the tip of the femoral medial epicondyle (measured down the leg).", A="femur_ME", B="medial_malleolus", mm=(14, 33), label="medial head", sel=[("lat", 0.0, 0.5)], nerve="tibial nerve (medial gastrocnemius branch)"),
    R("gastrocnemius", "huang2024", "motor_point", "level_mm", "Nerve entry into the lateral head 22-45 mm distal to the tip of the femoral medial epicondyle (measured down the leg).", A="femur_ME", B="medial_malleolus", mm=(22, 45), label="lateral head", sel=[("lat", 0.5, 1.0)], nerve="tibial nerve (lateral gastrocnemius branch)"),
    R("soleus", "huang2024", "motor_point", "level_mm", "Proximal soleus branch entry 35-81 mm distal to the tip of the femoral medial epicondyle.", A="femur_ME", B="medial_malleolus", mm=(35, 81), label="proximal branch", nerve="tibial nerve (proximal soleus branch)"),
    R("soleus", "yi2025sol", "innervation_zone", "level", "Most prominent nerve distribution in zone 5 of 10 (40-50%, zones counted from the calcaneal tuberosity line up to the fibular head line) in the lateral third.", A="calcaneal_tub", B="fibular_head", f=(40, 50), label="lateral third", sel=[("lat", 2 / 3, 1.0)]),
    R("soleus", "yi2025sol", "innervation_zone", "level", "Most prominent nerve distribution in zone 3 of 10 (20-30%, from the calcaneal tuberosity line) in the middle third.", A="calcaneal_tub", B="fibular_head", f=(20, 30), label="middle third", sel=[("lat", 1 / 3, 2 / 3)]),
    R("soleus", "yi2025sol", "innervation_zone", "level", "Most prominent nerve distribution in zone 5 of 10 (40-50%, from the calcaneal tuberosity line) in the medial third.", A="calcaneal_tub", B="fibular_head", f=(40, 50), label="medial third", sel=[("lat", 0.0, 1 / 3)]),
    R("tibialis_posterior", "lee2010tp", "motor_point", "level", "82.5% of motor entry points at 10-30% of the line from the most proximal-medial tibial articular margin to the most distal point of the medial malleolus.", A="tibia_medial_plateau", B="medial_malleolus_tip", f=(10, 30), nerve="tibial nerve"),
    R("tibialis_posterior", "lee2010tp", "innervation_zone", "level", "67.9% of intramuscular motor points at 10-40% of the proximal-medial tibial articular margin -> distal medial malleolus line.", A="tibia_medial_plateau", B="medial_malleolus_tip", f=(10, 40), nerve="tibial nerve"),
    R("tibialis_posterior", "oddy2006", "motor_point", "level", "Nerve entered the muscle 22.1% down the posterior midline axis from the level of the fibular head to the intermalleolar axis.", A="fibular_head", B="intermalleolar_mid", f=22.1, nerve="nerve to tibialis posterior (tibial nerve)"),
    R("flexor_digitorum_longus", "diaconu4", "innervation_zone", "level", "Single zone at 40-50% of the line from the most prominent point of the lateral malleolus to the fibular head (review synthesis).", A="lat_malleolus_prom", B="fibular_head", f=(40, 50)),
    R("flexor_hallucis_longus", "diaconu4", "innervation_zone", "level", "Zone at 30-40% of the lateral malleolus (prominent point) -> fibular head line (review synthesis).", A="lat_malleolus_prom", B="fibular_head", f=(30, 40), label="distal zone"),
    R("flexor_hallucis_longus", "diaconu4", "innervation_zone", "level", "Zone at 60-70% of the lateral malleolus (prominent point) -> fibular head line (review synthesis).", A="lat_malleolus_prom", B="fibular_head", f=(60, 70), label="proximal zone"),
    R("popliteus", "kim2026pop", "innervation_zone", "level", "High-density nerve zone at 56-64% of muscle length from the insertion (0%, posterior tibia) to the origin (100%, lateral femoral condyle); ends measured on this body's own popliteus.", A="mend_ins:+sup", B="mend_org:+sup", f=(56, 64), nerve="tibial nerve"),
    # ---------------- hip / pelvis
    R("piriformis", "yi2021pir", "motor_point", "level", "Nerve entry between the lateral border of the sacrum and one-fifth of the distance to the greater trochanter (0-20%).", A="sacrum_lat_border", B="femur_GT", f=(0, 20)),
    R("piriformis", "yi2021pir", "innervation_zone", "level", "Largest arborization between one-fifth and two-fifths (20-40%) of the lateral sacral border -> greater trochanter distance.", A="sacrum_lat_border", B="femur_GT", f=(20, 40)),
    R("iliopsoas", "vancampenhout2010", "innervation_zone", "level", "Motor endplate zone between 30% and 70% of the distance from T12 to where psoas passes under the inguinal ligament (T12 body centre and mid-inguinal point measured here).", A="T12_body", B="mid_inguinal", f=(30, 70), parts={"zan": "zan_psoas_major_{s}"}, nerve="lumbar plexus branches"),
    # ---------------- shoulder girdle / arm
    *[R("deltoid", "yi2023delt", "innervation_zone", "level", f"Greatest arborization of the {b} belly between {lo_t} and {hi_t} of the distance from the marginal line of the muscle origin to the line joining the anterior and posterior upper edges of the axilla (axillary line taken here at the mean lowest level of pectoralis major and latissimus dorsi within 40 mm of the humerus (either alone if the other is absent)).",
        A="deltoid_top", B="axillary_level", f=(lo, hi), label=f"{b} belly", sel=[("ant", *band)], parts={"zan": f"zan_{zp}_part_of_deltoid_muscle_{{s}}"}, nerve="axillary nerve")
      for b, lo, hi, lo_t, hi_t, band, zp in [("anterior", 100 / 3, 200 / 3, "1/3", "2/3", (2 / 3, 1.0), "clavicular"),
                                              ("middle", 200 / 3, 100, "2/3", "the axillary line", (1 / 3, 2 / 3), "acromial"),
                                              ("posterior", 100 / 3, 200 / 3, "1/3", "2/3", (0.0, 1 / 3), "scapular_spinal")]],
    R("biceps_brachii", "lee2009bb", "innervation_zone", "surface", "Intramuscular nerve endings most dense at 64.6-70.3% of the coracoid process (0%) -> medial humeral epicondyle line, 21.6-32.6 mm lateral to it.",
      O="coracoid", B1="humerus_ME", f1=(64.6, 70.3), off=(21.6, 32.6), offdir="lat", approach="ant", nerve="musculocutaneous nerve"),
    R("biceps_brachii", "park2007", "motor_point", "surface", "Motor point at approximately half (50%) of the coracoid process -> lateral humeral epicondyle line.",
      O="coracoid", B1="humerus_LE", f1=50, off=0, offdir="lat", approach="ant", nerve="musculocutaneous nerve"),
    *[R("biceps_brachii", "amirali2007", "innervation_zone", "level", f"Motor endplate band (inverted V) at {r:.2f} of the olecranon -> acromion length at the {e} of the muscle (Sihler/AChE).",
        A="olecranon", B="acromion", f=r * 100, label=e, sel=[("lat", *band)])
      for r, e, band in [(0.39, "midline", (0.4, 0.6)), (0.25, "lateral edge", (0.8, 1.0)), (0.28, "medial edge", (0.0, 0.2))]],
    R("brachialis", "lee2009bb", "innervation_zone", "surface", "Intramuscular nerve endings at 75.4% of the coracoid process -> medial humeral epicondyle line, 27.1-35.4 mm lateral to it.",
      O="coracoid", B1="humerus_ME", f1=75.4, off=(27.1, 35.4), offdir="lat", approach="ant", nerve="musculocutaneous nerve"),
    R("brachialis", "park2007", "motor_point", "surface", "Motor point at 70% of the coracoid process -> lateral humeral epicondyle line and 2 cm medial to it.",
      O="coracoid", B1="humerus_LE", f1=70, off=-20.0, offdir="lat", approach="ant", nerve="musculocutaneous nerve"),
    *[R("triceps_brachii", "yi2023tri", "innervation_zone", "level", f"Intramuscular arborization of the {h} at {lo}-{hi}% of the midpoint of the olecranon (0%) -> anteroinferior acromion (100%) line.",
        A="olecranon", B="acromion", f=(lo, hi), label=lab, sel=sel, parts={"zan": f"zan_{zp}_head_of_triceps_brachii_{{s}}"}, nerve="radial nerve")
      for h, lo, hi, lab, sel, zp in [("long head (medial region)", 30, 50, "long head, proximal zone", [("lat", 0.0, 0.5), ("ant", 0.0, 0.6)], "long"),
                                      ("long head (medial region)", 60, 70, "long head, distal zone", [("lat", 0.0, 0.5), ("ant", 0.0, 0.6)], "long"),
                                      ("medial head", 30, 40, "medial head", [("lat", 0.0, 0.5), ("ant", 0.5, 1.0)], "medial"),
                                      ("lateral head", 30, 60, "lateral head", [("lat", 0.5, 1.0)], "lateral")]],
    R("brachioradialis", "diaconu2", "innervation_zone", "level", "Intramuscular nerve-dense zone at 39.04-61.9% of muscle length, origin (lateral supracondylar ridge) -> insertion (radial styloid); ends measured on this body's own muscle.", A="mend_org:+sup", B="mend_ins:+sup", f=(39.04, 61.9), label="proximal zone", nerve="radial nerve"),
    R("brachioradialis", "diaconu2", "innervation_zone", "level", "Intramuscular nerve-dense zone at 73.8-90.47% of muscle length, origin -> insertion; ends measured on this body's own muscle.", A="mend_org:+sup", B="mend_ins:+sup", f=(73.8, 90.47), label="distal zone", nerve="radial nerve"),
    R("supraspinatus", "lee2022ssp", "innervation_zone", "level", "Injection within the medial 25-75% of the supraspinatus (nerve arborization concentrated in the central section); ends measured on this body's own muscle, medial (origin) end = 0%.", A="mend_org:-lat", B="mend_ins:-lat", f=(25, 75), nerve="suprascapular nerve"),
    R("infraspinatus", "lee2023isp", "innervation_zone", "level", "Endplate zone mainly in section B (20-40%) of the medial scapular border -> greater tubercle of the humerus line.", A="scap_medial_border_isp", B="humerus_GT", f=(20, 40), nerve="suprascapular nerve"),
    R("teres_major", "yi2023tm", "innervation_zone", "level", "Greatest density of intramuscular nerve endings in the middle 20% (40-60%) of the muscle from origin to insertion; ends measured on this body's own muscle.", A="mend_org:-sup", B="mend_ins:-sup", f=(40, 60), nerve="lower subscapular nerve"),
    R("rhomboid_major", "yi2020rh", "innervation_zone", "level", "Densest arborization in the middle third (33-67%) from origin (spinous processes) to insertion (medial scapular border); ends measured on this body's own muscle.", A="mend_org:-lat", B="mend_ins:-lat", f=(33, 67), nerve="dorsal scapular nerve"),
    R("rhomboid_minor", "yi2020rh", "innervation_zone", "level", "Arborization-dense medial third (0-33%) from origin to insertion; ends measured on this body's own muscle.", A="mend_org:-lat", B="mend_ins:-lat", f=(0, 33), label="medial third", nerve="dorsal scapular nerve"),
    R("rhomboid_minor", "yi2020rh", "innervation_zone", "level", "Arborization-dense lateral third (67-100%) from origin to insertion; ends measured on this body's own muscle.", A="mend_org:-lat", B="mend_ins:-lat", f=(67, 100), label="lateral third", nerve="dorsal scapular nerve"),
    R("levator_scapulae", "lee2023ls", "innervation_zone", "level", "Most intramuscular nerve terminals between 30 and 70% with origin = 0% and insertion = 100%; ends measured on this body's own muscle.", A="mend_org:+sup", B="mend_ins:+sup", f=(30, 70), nerve="C3-C5 (dorsal scapular nerve contribution)"),
    *[R("trapezius", "yi2020trap", "innervation_zone", "surface", f"Greatest arborization of the {p} trapezius in vertical sections {v0}-{v1}/10 of the external occipital protuberance -> T12 spinous process line and horizontal sections {h0}-{h1}/5 from the midline toward the acromion.",
        O="EOP", B1="T12_spinous", f1=(v0 * 10, v1 * 10), B2="acromion_x_from_midline", f2=(h0 * 20, h1 * 20), approach="post", label=f"{p} part", nerve="spinal accessory nerve")
      for p, v0, v1, h0, h1 in [("superior", 2, 4, 1, 2), ("middle", 4, 5, 1, 3), ("inferior", 5, 7, 1, 2)]],
    *[R(m, "li2021pec", k, "pec", txt, H=h, L=l, approach="ant", label=lab, parts={"zan": zp} if zp else None, nerve=nv)
      for m, k, h, l, lab, zp, nv, txt in [
          ("pectoralis_major", "motor_point", (47.70, 0.67), (-9.64, 0.25), "lateral pectoral nerve entry", "zan_clavicular_head_of_pectoralis_major_muscle_{s}", "lateral pectoral nerve", "Nerve entry point of the lateral pectoral nerve projected at 47.70% of the acromion -> jugular notch line (H) and -9.64% of the jugular notch -> xiphisternal joint line (L); needle perpendicular to the coronal plane."),
          ("pectoralis_major", "motor_point", (32.03, 0.46), (36.08, 0.32), "medial pectoral nerve entry", "zan_sternocostal_head_of_pectoralis_major_muscle_{s}", "medial pectoral nerve", "Nerve entry point of the medial pectoral nerve at 32.03% of line H and 36.08% of line L."),
          ("pectoralis_major", "innervation_zone", (41.96, 0.72), (-3.89, 0.49), "clavicular nerve-dense centre", "zan_clavicular_head_of_pectoralis_major_muscle_{s}", "lateral pectoral nerve", "Centre of the intramuscular nerve-dense region 1 (clavicular part) at 41.96% of line H and -3.89% of line L."),
          ("pectoralis_major", "innervation_zone", (55.81, 0.53), (25.19, 0.66), "sternocostal nerve-dense centre", "zan_sternocostal_head_of_pectoralis_major_muscle_{s}", "lateral and medial pectoral nerves", "Centre of the intramuscular nerve-dense region 2 (sternal part) at 55.81% of line H and 25.19% of line L."),
          ("pectoralis_minor", "motor_point", (34.43, 0.59), (2.46, 0.23), None, None, "medial pectoral nerve", "Nerve entry point of the medial pectoral nerve branch to pectoralis minor at 34.43% of line H and 2.46% of line L."),
          ("pectoralis_minor", "innervation_zone", (32.37, 0.54), (-6.97, 0.51), None, None, "medial pectoral nerve", "Centre of the intramuscular nerve-dense region at 32.37% of line H and -6.97% of line L.")]],
    # ---------------- forearm (Zhou 2023: oblique surface coordinates from the medial epicondyle)
    *[R(m, "zhou2023", "innervation_zone", "surface", f"Centre of the highest muscle-spindle-abundance region within the intramuscular nerve-dense region{(' (' + lab + ')') if lab else ''}: {fl}% of the medial epicondyle -> ulnar styloid line and {ft}% of the medial -> lateral epicondyle line (spiral-CT projection; source depth {dp}% of limb thickness).",
        O="humerus_ME", B1="ulnar_styloid", f1=fl, B2="humerus_LE", f2=ft, approach="ant", label=lab, parts={"zan": zp} if zp else None, nerve=nv)
      for m, lab, fl, ft, dp, zp, nv in [
          ("flexor_carpi_radialis", None, 28.83, 41.2, 23.76, None, "median nerve"),
          ("flexor_carpi_ulnaris", None, 17.65, 7.77, 15.49, None, "ulnar nerve"),
          ("palmaris_longus", None, 13.43, 19.7, 18.04, "zan_palmaris_longus_muscle_{s}", "median nerve"),
          ("pronator_teres", "humeral head", 12.54, 45.52, 27.25, None, "median nerve"),
          ("pronator_teres", "ulnar head", 18.38, 42.48, 21.92, None, "median nerve"),
          ("flexor_digitorum_superficialis", "proximal target", 32.76, 25.65, 31.36, None, "median nerve"),
          ("flexor_digitorum_superficialis", "distal target", 57.32, 47.42, 26.59, None, "median nerve"),
          ("flexor_digitorum_profundus", "radial half", 45.94, 38.41, 45.14, None, "anterior interosseous nerve"),
          ("flexor_digitorum_profundus", "ulnar half", 20.05, 12.28, 38.72, None, "ulnar nerve"),
          ("flexor_pollicis_longus", None, 64.12, 53.47, 41.28, None, "anterior interosseous nerve"),
          ("pronator_quadratus", None, 88.71, None, None, None, "anterior interosseous nerve")] if ft is not None],
    R("extensor_carpi_radialis_longus", "caetano2020", "motor_point", "level", "Motor branch entered the muscle within its proximal third (0-33% of origin -> insertion) in 30/30 limbs; ends measured on this body's own muscle.", A="mend_org:+sup", B="mend_ins:+sup", f=(0, 33), nerve="radial nerve"),
    R("extensor_carpi_radialis_brevis", "caetano2020", "motor_point", "level", "Motor branch entered within the proximal two-thirds (0-67%; proximal third in 56.5%); ends measured on this body's own muscle.", A="mend_org:+sup", B="mend_ins:+sup", f=(0, 67), nerve="radial nerve (deep branch)"),
    R("supinator", "caetano2020", "motor_point", "level", "Motor branches from the posterior interosseous nerve entered within the proximal two-thirds (0-67%) in most limbs; ends measured on this body's own muscle.", A="mend_org:+sup", B="mend_ins:+sup", f=(0, 67), nerve="posterior interosseous nerve"),
    # ---------------- hand (Xie 2012: dense-branch zones stated in words, read as thirds of muscle length)
    *[R(m, "xie2012", "innervation_zone", "level", f"Nerve branches densely distributed {w} ({lo}-{hi}% of origin -> insertion, the source's words read as thirds); ends measured on this body's own muscle.",
        A="mend_org:+sup", B="mend_ins:+sup", f=(lo, hi), nerve=nv)
      for m, w, lo, hi, nv in [("abductor_pollicis_brevis", "at the junction of the proximal and middle thirds", 30, 40, "recurrent branch of the median nerve"),
                               ("flexor_pollicis_brevis", "in the middle area", 33, 67, "median / ulnar nerve"),
                               ("abductor_digiti_minimi_hand", "in the middle part", 33, 67, "deep branch of the ulnar nerve"),
                               ("flexor_digiti_minimi_brevis_hand", "through the middle part", 33, 67, "deep branch of the ulnar nerve"),
                               ("opponens_digiti_minimi", "in the middle and distal parts", 33, 100, "deep branch of the ulnar nerve")]],
    # ---------------- neck
    R("sternocleidomastoid", "lee2010scm", "motor_point", "level", "97% of motor entry points at 20-40% of the mastoid process -> most medial point of the clavicle line.", A="mastoid", B="clavicle_medial", f=(20, 40), nerve="spinal accessory nerve"),
    R("sternocleidomastoid", "yi2019scm", "innervation_zone", "level", "Most densely innervated 5/10-6/10 along the lateral half of the muscle (mastoid process -> sternoclavicular joint).", A="mastoid", B="clavicle_medial", f=(50, 60), label="lateral half", sel=[("lat", 0.5, 1.0)], nerve="spinal accessory nerve"),
    R("sternocleidomastoid", "yi2019scm", "innervation_zone", "level", "Most densely innervated 6/10-7/10 along the medial half of the muscle (mastoid process -> sternoclavicular joint).", A="mastoid", B="clavicle_medial", f=(60, 70), label="medial half", sel=[("lat", 0.0, 0.5)], nerve="spinal accessory nerve"),
    R("splenius_capitis", "kwon2020sp", "innervation_zone", "level", "Innervation spreads from the central (50%) point of the origin -> insertion length; ends measured on this body's own muscle.", A="mend_org:-sup", B="mend_ins:-sup", f=50),
    R("splenius_cervicis", "kwon2020sp", "innervation_zone", "level", "Motor neurons innervate the muscle from about 30% to 70% of origin -> insertion; ends measured on this body's own muscle.", A="mend_org:-sup", B="mend_ins:-sup", f=(30, 70), parts={"zan": "zan_splenius_colli_muscle_{s}"}),
    *[R(m, "wang2024", "innervation_zone", "level", f"Intramuscular nerve-dense region {lab} at {lo}-{hi}% of muscle length origin -> insertion (the region the source's puncture simulation found unobstructed); ends measured on this body's own muscle.",
        A="mend_org:+sup", B="mend_ins:+sup", f=(lo, hi), label=lab, nerve=nv)
      for m, lab, lo, hi, nv in [("scalenus_anterior", "INDR1", 45.41, 59.66, "C5 ventral ramus branch"),
                                 ("scalenus_medius", "INDR2b", 70.55, 78.3, "cervical ventral rami"),
                                 ("scalenus_posterior", "INDR3", 44.74, 70.79, "C7-C8 ventral rami")]],
]

# muscles the atlas has that were searched and have NO usable landmark rule here
NOT_COVERED_REASON = {
    "latissimus_dorsi": "Yi 2022 (doi:10.3390/toxins14020107) / Diaconu 2025 give zones relative to a T5-spinous-process-to-iliac-crest line; T5 is not separable in the own bodies' merged thoracic vertebra mesh -- not implemented.",
    "gluteus_maximus": "Yi 2024 (doi:10.3390/diagnostics14020140) gives 30-70% ranges per segment but the reference line is not stated in the abstract; full text not reviewed -- not implemented.",
    "gluteus_medius": "Botte 1991 (PMID 1991010) gives a region 3 cm lateral to the greater sciatic notch at the superior piriformis margin (soft-tissue landmark) -- not implemented.",
    "obturator_internus": "Yi 2023 (doi:10.1007/s00276-023-03216-6) uses the medial edge of the obturator foramen (not robustly measurable on the meshes) -- not implemented.",
    "subscapularis": "Sihler studies (Cho 2019 doi:10.1002/ca.23303; Cho 2023) describe territories, not a landmark rule.",
    "extensor_hallucis_longus": "Diaconu 2025 states ~35% of 'lower limb length' / ~12 cm above the bimalleolar line -- line ends not defined well enough.",
    "longus_colli": "Wang 2024 origin/insertion convention for this multi-part muscle is ambiguous on the meshes.",
    "longus_capitis": "Wang 2024 recommends against the reachable zone (submandibular gland) / convention ambiguous.",
    "adductor_pollicis": "Garg 2026 (doi:10.1016/j.aanat.2026.152881) gives distances to the 1st MCP joint and the 3rd-metacarpal axis -- needs per-phalanx joint landmarks not implemented.",
    "flexor_hallucis_brevis": "Diaconu 2025 uses soft-tissue sole landmarks -- not implemented.",
}

# --------------------------------------------------------------------------- geometry loading


def _own(viewer):
    h = Path(viewer["html"]).read_text(encoding="utf-8")
    m = re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S)
    b = json.loads(m.group(1))
    blob = Path(viewer["bin"]).read_bytes()
    need = sum(int(e["nv"]) * 6 + int(e["nf"]) * 6 for e in b["structures"])
    if need != len(blob):
        raise ValueError(f"{viewer['bin']}: {len(blob)} bytes, bundle-json needs {need}")
    q = float(b["quantum_mm"]); off = 0; out = {}
    for e in b["structures"]:
        nv, nf = int(e["nv"]), int(e["nf"])
        v = np.frombuffer(blob, np.int16, nv * 3, off).reshape(-1, 3).astype(np.float64) * q; off += nv * 6
        f = np.frombuffer(blob, np.uint16, nf * 3, off).reshape(-1, 3).astype(np.int64); off += nf * 6
        out.setdefault(e["id"], {"cat": e["cat"], "parts": []})["parts"].append((v, f))
    return _concat(out)


def _zan(viewer):
    html = Path(viewer["html"])
    h = html.read_text(encoding="utf-8")
    i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man = json.JSONDecoder().raw_decode(h[i:])[0]
    j = h.find("window.__ANATOMY_BIN_FILES__=") + len("window.__ANATOMY_BIN_FILES__=")
    files = json.JSONDecoder().raw_decode(h[j:])[0]
    blob = b"".join(base64.b64decode((html.parent / f["path"]).read_text().strip()) for f in files)
    out = {}
    for m in man["meshes"]:
        q = np.frombuffer(blob, "<u2", m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
        v = np.array(m["min"]) + q / 65535.0 * np.array(m["span"])
        f = np.frombuffer(blob, "<u2", m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
        out.setdefault(m["id"], {"cat": m["sys"], "parts": []})["parts"].append((v, f))
    return _concat(out)


def _concat(out):
    for d in out.values():
        vs, fs, o = [], [], 0
        for v, f in d["parts"]:
            vs.append(v); fs.append(f + o); o += len(v)
        d["v"] = np.vstack(vs); d["f"] = np.vstack(fs); del d["parts"]
    return out


def load_viewer(key):
    vw = VIEWERS[key]
    return _own(vw) if vw["kind"] == "own" else _zan(vw)


# --------------------------------------------------------------------------- geometry helpers

def winding(points, V, F, chunk=256):
    """Generalised winding number of each point w.r.t. the triangle mesh (V,F)."""
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    out = np.empty(len(points))
    for s in range(0, len(points), chunk):
        p = points[s:s + chunk, None, :]
        a, b, c = A[None] - p, B[None] - p, C[None] - p
        la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
        det = np.einsum("ijk,ijk->ij", a, np.cross(b, c))
        den = la * lb * lc + np.einsum("ijk,ijk->ij", a, b) * lc + np.einsum("ijk,ijk->ij", a, c) * lb + np.einsum("ijk,ijk->ij", b, c) * la
        out[s:s + chunk] = np.arctan2(det, den).sum(axis=1) / (2 * np.pi)
    return out


def inside(points, V, F):
    return np.abs(winding(np.atleast_2d(points), V, F)) > 0.5


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


class LandmarkMissing(Exception):
    pass


# --------------------------------------------------------------------------- landmarks (own bones)

class Body:
    def __init__(self, key, meshes):
        self.key, self.m = key, meshes
        self.kind = VIEWERS[key]["kind"]
        self.skin = meshes.get("skin") if self.kind == "own" else None
        if self.skin is not None:
            self.skin_tree = cKDTree(self.skin["v"])
        self._cache = {}

    def has(self, sid):
        return sid in self.m

    def V(self, sid):
        if sid not in self.m:
            raise LandmarkMissing(sid)
        return self.m[sid]["v"]

    def bone(self, name, s):
        for c in (f"{name}_{s}", name):
            if c in self.m:
                return self.m[c]["v"]
        raise LandmarkMissing(f"{name}_{s}")

    # ---- generic helpers
    @staticmethod
    def band(V, axis, lo, hi):
        t = V[:, axis]; a, b = t.min(), t.max()
        sel = V[(t >= a + lo * (b - a)) & (t <= a + hi * (b - a))]
        if len(sel) == 0:
            raise LandmarkMissing("empty band")
        return sel

    def lm(self, name, s):
        k = (name, s)
        if k not in self._cache:
            self._cache[k] = np.asarray(getattr(self, "lm_" + name)(s), float)
        return self._cache[k]

    # ---- upper limb
    def lm_acromion(self, s):
        sx = 1 if s == "r" else -1
        top = self.band(self.bone("scapula", s), 1, 0.8, 1.0)
        return top[np.argmax(sx * top[:, 0])]

    def lm_coracoid(self, s):
        top = self.band(self.bone("scapula", s), 1, 0.6, 1.0)
        return top[np.argmax(top[:, 2])]

    def lm_humerus_ME(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("humerus", s), 1, 0.0, 0.12)
        return d[np.argmax(-sx * d[:, 0])]

    def lm_humerus_LE(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("humerus", s), 1, 0.0, 0.12)
        return d[np.argmax(sx * d[:, 0])]

    def lm_humerus_GT(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("humerus", s), 1, 0.9, 1.0)
        return d[np.argmax(sx * d[:, 0])]

    def lm_olecranon(self, s):
        d = self.band(self.bone("ulna", s), 1, 0.9, 1.0)
        return d[np.argmin(d[:, 2])]

    def lm_ulnar_styloid(self, s):
        u = self.bone("ulna", s)
        return u[np.argmin(u[:, 1])]

    def lm_scap_medial_border_isp(self, s):
        sx = 1 if s == "r" else -1
        sc = self.bone("scapula", s)
        y0 = self.V(f"infraspinatus_{s}")[:, 1].mean()
        b = sc[np.abs(sc[:, 1] - y0) < 15]
        if len(b) == 0:
            raise LandmarkMissing("scapula at infraspinatus level")
        return b[np.argmin(sx * b[:, 0])]

    # ---- pelvis / lower limb
    def lm_ASIS(self, s):
        up = self.band(self.bone("hip_bone", s), 1, 0.55, 1.0)
        return up[np.argmax(up[:, 2])]

    def lm_pubic_tubercle(self, s):
        # anterior-most point of the pubis, biased laterally (the tubercle is the lateral end of the crest)
        sx = 1 if s == "r" else -1
        lo = self.band(self.bone("hip_bone", s), 1, 0.0, 0.4)
        lat = sx * lo[:, 0] - (sx * lo[:, 0]).min()
        c = lo[lat < 45]; score = c[:, 2] + 0.3 * lat[lat < 45]
        return c[np.argmax(score)]

    def lm_ischial_tub(self, s):
        h = self.bone("hip_bone", s)
        return h[np.argmin(h[:, 1])]

    def lm_mid_inguinal(self, s):
        return 0.5 * (self.lm("ASIS", s) + self.lm("pubic_tubercle", s))

    def lm_femur_GT(self, s):
        sx = 1 if s == "r" else -1
        p = self.band(self.bone("femur", s), 1, 0.8, 1.0)
        return p[np.argmax(sx * p[:, 0])]

    def lm_femur_ME(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("femur", s), 1, 0.0, 0.12)
        return d[np.argmax(-sx * d[:, 0])]

    def lm_patella_base(self, s):
        p = self.bone("patella", s)
        return p[np.argmax(p[:, 1])]

    def lm_patella_center(self, s):
        return self.bone("patella", s).mean(axis=0)

    def lm_tibial_condyles_mid(self, s):
        d = self.band(self.bone("tibia", s), 1, 0.92, 1.0)
        return 0.5 * (d[np.argmin(d[:, 0])] + d[np.argmax(d[:, 0])])

    def lm_tibia_medial_plateau(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("tibia", s), 1, 0.94, 1.0)
        return d[np.argmax(-sx * d[:, 0])]

    def lm_medial_malleolus(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("tibia", s), 1, 0.0, 0.1)
        return d[np.argmax(-sx * d[:, 0])]

    def lm_medial_malleolus_tip(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("tibia", s), 1, 0.0, 0.1)
        med = d[-sx * d[:, 0] > np.median(-sx * d[:, 0])]
        return med[np.argmin(med[:, 1])]

    def lm_fibular_head(self, s):
        f = self.bone("fibula", s)
        return f[np.argmax(f[:, 1])]

    def lm_lat_malleolus_tip(self, s):
        f = self.bone("fibula", s)
        return f[np.argmin(f[:, 1])]

    def lm_lat_malleolus_prom(self, s):
        sx = 1 if s == "r" else -1
        d = self.band(self.bone("fibula", s), 1, 0.0, 0.1)
        return d[np.argmax(sx * d[:, 0])]

    def lm_intermalleolar_mid(self, s):
        return 0.5 * (self.lm("medial_malleolus", s) + self.lm("lat_malleolus_prom", s))

    def lm_calcaneal_tub(self, s):
        c = self.bone("calcaneus", s)
        return c[np.argmin(c[:, 2])]

    def lm_sacrum_lat_border(self, s):
        sx = 1 if s == "r" else -1
        b = self.band(self.bone("sacrum", s), 1, 0.2, 0.5)  # band measured from the bottom: S3-S4 level
        return b[np.argmax(sx * b[:, 0])]

    # ---- trunk / neck
    def _thoracic_lowest(self):
        if "zan_vertebra_t12" in self.m:
            return self.m["zan_vertebra_t12"]["v"]
        t = self.V("thoracic_vertebrae")
        return t[t[:, 1] < t[:, 1].min() + 35]

    def lm_T12_spinous(self, s):
        t = self._thoracic_lowest()
        return t[np.argmin(t[:, 2])]

    def lm_T12_body(self, s):
        t = self._thoracic_lowest()
        return t[t[:, 2] > np.median(t[:, 2])].mean(axis=0)

    def _skull(self):
        for c in ("cranium", "occipital"):
            if c in self.m:
                return self.m[c]["v"]
        raise LandmarkMissing("cranium/occipital")

    def lm_EOP(self, s):
        k = self._skull()
        xm = 0.5 * (k[:, 0].min() + k[:, 0].max())
        mid = k[np.abs(k[:, 0] - xm) < 8]
        return mid[np.argmin(mid[:, 2])]

    def lm_mastoid(self, s):
        # The mastoid is identified on this body's own skull as the part the sternocleidomastoid inserts
        # on: the skull vertex nearest the muscle's superior end, then the lowest skull vertex within
        # 20 mm of it (the tip). Pure extreme-point searches picked the styloid / condyles instead.
        k = self.m[f"temporal_{s}"]["v"] if f"temporal_{s}" in self.m else self._skull()
        scm = self.V(f"sternocleidomastoid_{s}")
        top = scm[scm[:, 1] >= np.percentile(scm[:, 1], 98)].mean(axis=0)
        d, i = cKDTree(k).query(top)
        if d > 20:
            raise LandmarkMissing(f"skull surface {d:.0f} mm from the SCM insertion (mastoid not in this skull mesh)")
        near = k[np.linalg.norm(k - k[i], axis=1) < 20]
        return near[np.argmin(near[:, 1])]

    def lm_clavicle_medial(self, s):
        sx = 1 if s == "r" else -1
        c = self.bone("clavicle", s)
        return c[np.argmin(sx * c[:, 0])]

    def lm_jugular_notch(self, s):
        st = self.V("sternum")
        xm = np.median(st[:, 0])
        mid = st[np.abs(st[:, 0] - xm) < 6]
        return mid[np.argmax(mid[:, 1])]

    def lm_xiphisternal(self, s):
        st = self.V("sternum")
        xm = np.median(st[:, 0])
        mid = st[np.abs(st[:, 0] - xm) < 10]
        return mid[np.argmin(mid[:, 1])]

    def lm_acromion_x_from_midline(self, s):
        # the 100% end of a horizontal line from the posterior midline (at EOP's X) toward the acromion
        eop = self.lm("EOP", s); ac = self.lm("acromion", s)
        return eop + np.array([ac[0] - eop[0], 0.0, 0.0])

    # ---- muscle-derived
    def deltoid_ids(self, s):
        ids = [i for i in (f"deltoid_{s}",) if i in self.m]
        ids += [i for i in (f"zan_clavicular_part_of_deltoid_muscle_{s}", f"zan_acromial_part_of_deltoid_muscle_{s}",
                            f"zan_scapular_spinal_part_of_deltoid_muscle_{s}") if i in self.m]
        if not ids:
            raise LandmarkMissing(f"deltoid_{s}")
        return ids

    def lm_deltoid_top(self, s):
        v = np.vstack([self.m[i]["v"] for i in self.deltoid_ids(s)])
        return v[np.argmax(v[:, 1])]

    def lm_axillary_level(self, s):
        hum = cKDTree(self.bone("humerus", s))
        levels, why = [], []
        for group in (("pectoralis_major_{s}", "zan_clavicular_head_of_pectoralis_major_muscle_{s}", "zan_sternocostal_head_of_pectoralis_major_muscle_{s}", "zan_abdominal_part_of_pectoralis_major_muscle_{s}"),
                      ("latissimus_dorsi_{s}",)):
            vs = [self.m[g.format(s=s)]["v"] for g in group if g.format(s=s) in self.m]
            if not vs:
                why.append(group[0].format(s=s)); continue
            v = np.vstack(vs)
            d, _ = hum.query(v)
            near = v[d < 40]
            if len(near) == 0:
                why.append(f"{group[0].format(s=s)} within 40 mm of the humerus"); continue
            levels.append(near[:, 1].min())
        if not levels:
            raise LandmarkMissing("axillary fold level: " + "; ".join(why))
        top = self.lm("deltoid_top", s)
        return np.array([top[0], float(np.mean(levels)), top[2]])


def muscle_ends(V, hint):
    c = V.mean(axis=0)
    u = np.linalg.svd(V - c, full_matrices=False)[2][0]
    t = (V - c) @ u
    e1 = V[t >= np.percentile(t, 97)].mean(axis=0)
    e2 = V[t <= np.percentile(t, 3)].mean(axis=0)
    return (e1, e2) if (e1 - c) @ hint >= (e2 - c) @ hint else (e2, e1)


def hint_vec(h, s):
    sx = 1 if s == "r" else -1
    sign = -1.0 if h.startswith("-") else 1.0
    ax = h.lstrip("+-")
    return sign * {"sup": np.array([0, 1.0, 0]), "ant": np.array([0, 0, 1.0]), "lat": np.array([sx, 0, 0.0])}[ax]


# --------------------------------------------------------------------------- placement

def pct_spec(f, sd=False):
    if isinstance(f, (int, float)):
        return float(f), None, "single value (no dispersion reported)"
    a, b = float(f[0]), float(f[1])
    if sd:
        return a, b, f"SD {b:g}%"
    return 0.5 * (a + b), 0.5 * (b - a), f"range {a:g}-{b:g}%"


def is_sd(rule, key):
    # (mean, sd) tuples: Kwon, Page, Choi, Li are given as mean/SD; every other tuple is a range
    return rule["src"] in ("kwon2009", "page2019", "choi2023tfl", "li2021pec") and key in ("f", "f1", "f2", "H", "L")


def section(V, F, p0, n, sel, s, step=1.5):
    """Inside sample points of the mesh cross-section in the plane (p0, n); None if the plane misses."""
    d = (V - p0) @ n
    fd = d[F]
    cross = (fd.min(axis=1) <= 0) & (fd.max(axis=1) >= 0)
    if not cross.any():
        return None, float(np.min(np.abs(d)))
    e1 = _unit(np.cross(n, [0, 0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0, 0]))
    e2 = np.cross(n, e1)
    P = V[np.unique(F[cross])]
    P = P - np.outer((P - p0) @ n, n)
    a, b = (P - p0) @ e1, (P - p0) @ e2
    span = max(np.ptp(a), np.ptp(b))
    step = max(step, span / 45.0)
    ga = np.arange(a.min() - 1, a.max() + 1, step); gb = np.arange(b.min() - 1, b.max() + 1, step)
    G = p0 + ga[:, None, None] * e1 + gb[None, :, None] * e2
    G = G.reshape(-1, 3)
    ins = G[inside(G, V, F)] if len(G) else G
    if len(ins) == 0:
        return None, 0.0
    for ax, lo, hi in (sel or []):
        u = hint_vec("+" + ax, s); u = _unit(u - (u @ n) * n)
        t = ins @ u
        a0, a1 = t.min(), t.max()
        keep = (t >= a0 + lo * (a1 - a0) - 1e-6) & (t <= a0 + hi * (a1 - a0) + 1e-6)
        if keep.any():
            ins = ins[keep]
    c = ins.mean(axis=0)
    return ins[np.argmin(np.linalg.norm(ins - c, axis=1))], 0.0


def along_line(V, F, P, u):
    """Mid-point of the inside segment of the line P + t u nearest P; else nearest inside point near it."""
    lo, hi = V.min(axis=0) - 5, V.max(axis=0) + 5
    ext = np.linalg.norm(hi - lo)
    t = np.arange(-ext, ext, 1.0)
    pts = P + np.outer(t, u)
    box = np.all((pts >= lo) & (pts <= hi), axis=1)
    if box.any():
        ins = np.zeros(len(t), bool)
        ins[box] = inside(pts[box], V, F)
        if ins.any():
            idx = np.flatnonzero(ins)
            segs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
            best = min(segs, key=lambda sg: abs(t[sg].mean()))
            return P + t[best].mean() * u, 0.0
    # line misses: nearest inside point around the closest mesh vertex
    rel = V - P
    dist = np.linalg.norm(rel - np.outer(rel @ u, u), axis=1)
    q = V[np.argmin(dist)]
    g = np.arange(-8, 8.01, 1.6)
    G = (q + np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3))
    G = G[inside(G, V, F)]
    if len(G) == 0:
        return None, float(dist.min())
    rel = G - P
    dg = np.linalg.norm(rel - np.outer(rel @ u, u), axis=1)
    return G[np.argmin(dg)], float(dg.min())


_NB = np.vstack([np.eye(3), -np.eye(3)])


def deepen(p, V, F, margin=1.0, reach=4.0):
    """Keep p if p and its six +/-margin neighbours are all inside; else the nearest such point within
    `reach` mm (a placed point must not sit on the muscle surface). Returns (point, distance moved)."""
    if inside(p + np.vstack([[0, 0, 0], margin * _NB]), V, F).all():
        return p, 0.0
    g = np.arange(-reach, reach + 0.01, 1.0)
    G = p + np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    G = G[np.linalg.norm(G - p, axis=1) <= reach]
    G = G[np.argsort(np.linalg.norm(G - p, axis=1))]
    ins = inside(G, V, F)
    for q in G[ins]:
        if inside(q + margin * _NB, V, F).all():
            return q, float(np.linalg.norm(q - p))
    return None, 0.0


def skin_depth(body, p):
    if body.skin is None:
        return None
    V, F = body.skin["v"], body.skin["f"]
    d, i = body.skin_tree.query(p, k=12)
    faces = np.flatnonzero(np.isin(F, i).any(axis=1))
    if len(faces) == 0:
        return round(float(d[0]), 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ds = [_pt_tri(p, V[F[k, 0]], V[F[k, 1]], V[F[k, 2]]) for k in faces]
    best = np.nanmin(ds + [d[0]])  # degenerate (zero-area) skin triangles give NaN and are ignored
    return round(float(best), 1)


def _pt_tri(p, a, b, c):
    # closest-point distance from p to triangle abc (Ericson)
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = ab @ ap, ac @ ap
    if d1 <= 0 and d2 <= 0:
        return np.linalg.norm(ap)
    bp = p - b; d3, d4 = ab @ bp, ac @ bp
    if d3 >= 0 and d4 <= d3:
        return np.linalg.norm(bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return np.linalg.norm(p - (a + ab * d1 / (d1 - d3)))
    cp = p - c; d5, d6 = ab @ cp, ac @ cp
    if d6 >= 0 and d5 <= d6:
        return np.linalg.norm(cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return np.linalg.norm(p - (a + ac * d2 / (d2 - d6)))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return np.linalg.norm(p - (b + (c - b) * (d4 - d3) / ((d4 - d3) + (d5 - d6))))
    den = 1.0 / (va + vb + vc)
    return np.linalg.norm(p - (a + ab * vb * den + ac * vc * den))


def structure_for(body, rule, s):
    parts = rule.get("parts") or {}
    if body.kind == "zan" and "zan" in parts:
        sid = parts["zan"].format(s=s)
        if sid in body.m:
            return sid, True
    sid = f"{rule['muscle']}_{s}"
    if sid in body.m and body.m[sid]["cat"] == "muscle":
        return sid, False
    return None, False


def point_of(body, name, s, V):
    if name.startswith("mend_"):
        which, h = name[5:].split(":")
        org, ins = muscle_ends(V, hint_vec(h, s))
        return org if which == "org" else ins
    return body.lm(name, s)


def place(body, rule, s):
    sid, is_part = structure_for(body, rule, s)
    if sid is None:
        return None, f"no structure {rule['muscle']}_{s} in this viewer"
    M = body.m[sid]; V, F = M["v"], M["f"]
    sel = None if is_part else rule.get("sel")
    typ = rule["type"]
    try:
        if typ in ("level", "level_mm"):
            A = point_of(body, rule["A"], s, V); B = point_of(body, rule["B"], s, V)
            L = float(np.linalg.norm(B - A)); n = _unit(B - A)
            if typ == "level":
                c, hw, basis = pct_spec(rule["f"], is_sd(rule, "f"))
                p0 = A + c / 100.0 * (B - A)
                unc = (hw if hw is not None else 5.0) / 100.0 * L
                if hw is None:
                    basis += "; +/-5% of the line assumed as reading precision"
            else:
                a, b = rule["mm"]; c_mm = 0.5 * (a + b)
                p0 = A + c_mm * n; unc = 0.5 * (b - a); basis = f"range {a:g}-{b:g} mm"
            pos, miss = section(V, F, p0, n, sel, s)
            proj = miss
            if pos is None and 0 < miss <= FAIL_MM:
                # the plane just misses the muscle's end: take the nearest level that cuts it
                d = (V - p0) @ n
                shift = d[np.argmin(np.abs(d))]
                pos, _ = section(V, F, p0 + (shift + np.sign(shift) * 2.0) * n, n, sel, s)
                proj = abs(shift) + 2.0
            line_len = L
        else:
            if typ == "pec":
                a = body.lm("acromion", s); jn = body.lm("jugular_notch", s); xs = body.lm("xiphisternal", s)
                h, hsd = rule["H"]; l, lsd = rule["L"]
                ph = a + h / 100 * (jn - a); pl = jn + l / 100 * (xs - jn)
                P = np.array([ph[0], pl[1], max(ph[2], pl[2])]); u = np.array([0, 0, -1.0])
                Hn, Ln = np.linalg.norm(jn - a), np.linalg.norm(xs - jn)
                unc = float(np.hypot(hsd / 100 * Hn, lsd / 100 * Ln)); basis = f"SD {hsd:g}% (H) and {lsd:g}% (L)"
                line_len = Hn
            else:
                O = body.lm(rule["O"], s); B1 = body.lm(rule["B1"], s)
                c1, h1, b1 = pct_spec(rule["f1"], is_sd(rule, "f1"))
                P = O + c1 / 100 * (B1 - O)
                L1 = float(np.linalg.norm(B1 - O)); line_len = L1
                comps = [(h1 if h1 is not None else 5.0) / 100 * L1]
                basis = b1 + ("; +/-5% of the line assumed as reading precision" if h1 is None else "")
                axis2 = None
                if "B2" in rule:
                    B2 = body.lm(rule["B2"], s)
                    c2, h2, b2 = pct_spec(rule["f2"], is_sd(rule, "f2"))
                    v2 = B2 - O
                    v2 = v2 - (v2 @ _unit(B1 - O)) * _unit(B1 - O) if rule["src"] == "an2010" else v2
                    P = P + c2 / 100 * v2; axis2 = v2
                    comps.append((h2 if h2 is not None else 5.0) / 100 * np.linalg.norm(v2)); basis += f"; transverse {b2}"
                else:
                    off = rule.get("off", 0)
                    c2 = off if isinstance(off, (int, float)) else 0.5 * (off[0] + off[1])
                    lat = hint_vec("+" + rule.get("offdir", "lat"), s); ln = _unit(B1 - O)
                    axis2 = _unit(lat - (lat @ ln) * ln)
                    P = P + c2 * axis2
                    if not isinstance(off, (int, float)):
                        comps.append(0.5 * (off[1] - off[0])); basis += f"; offset range {off[0]:g}-{off[1]:g} mm"
                unc = float(np.hypot(*comps)) if len(comps) > 1 else comps[0]
                # needle line: normal to the surface-coordinate plane (sampled both ways from P)
                u = _unit(np.cross(B1 - O, axis2))
            pos, proj = along_line(V, F, P, u)
    except LandmarkMissing as e:
        return None, f"landmark not measurable on this body: {e}"
    if pos is None:
        return None, f"FAILED: rule plane/line misses {sid} by {proj:.1f} mm"
    pos, moved = deepen(pos, V, F)
    if pos is None:
        return None, f"FAILED: no point at least 1 mm inside {sid} near the rule plane/line"
    proj += moved
    if proj > FAIL_MM:
        return None, f"FAILED: nearest point inside {sid} is {proj:.1f} mm from the rule plane/line (> {FAIL_MM} mm)"
    if unc < UNC_FLOOR_MM:
        unc = UNC_FLOOR_MM; basis += f"; floored at {UNC_FLOOR_MM:g} mm for landmark identification on the mesh"
    return dict(structure_id=sid, pos=pos, projection_mm=round(float(proj), 1), uncertainty_mm=round(float(unc), 1),
                basis=basis, line_len=round(line_len, 1), is_part=is_part), None


# --------------------------------------------------------------------------- run

def short_cite(src):
    c = SOURCES[src]["citation"]
    yr = re.search(r"\b((?:19|20)\d\d)\s*;", c)
    return f"{c.split(' ')[0]} et al. {yr.group(1) if yr else ''}".strip()


def run_one(key):
    meshes = load_viewer(key)
    body = Body(key, meshes)
    pts, failed, skipped = [], [], []
    counters = {}
    for rule in RULES:
        for s in ("r", "l"):
            res, why = place(body, rule, s)
            aid = f"{rule['muscle']}_{s}"
            tag = f"{aid} {rule['src']} {rule.get('label') or rule['kind']}"
            if res is None:
                (failed if why.startswith("FAILED") else skipped).append({"rule": tag, "why": why})
                continue
            k = counters.get(aid, 0) + 1; counters[aid] = k
            lab = rule.get("label")
            name = rule["muscle"].replace("_", " ").capitalize() + (f" ({lab})" if lab else "")
            unc = res["uncertainty_mm"]
            part_note = "" if res["is_part"] or not rule.get("sel") else "; head/part located as a sector of this body's single muscle mesh"
            pts.append({
                "id": f"mp.{aid}.{k}", "structure_id": res["structure_id"], "atlas_id": aid,
                "muscle_name": name, "side": s, "kind": rule["kind"],
                "pos": [round(float(x), 1) for x in res["pos"]],
                "depth_from_skin_mm": skin_depth(body, res["pos"]),
                "projection_mm": res["projection_mm"], "uncertainty_mm": unc,
                "nerve": rule.get("nerve"),
                "source": {**{k2: SOURCES[rule["src"]][k2] for k2 in ("citation", "doi", "pmid")}, "rule": rule["rule"]},
                "badge": (f"Rule-based from {short_cite(rule['src'])}; landmarks measured on this body's own "
                          f"{'muscle ends' if str(rule.get('A', '')).startswith('mend_') else 'bones'}; "
                          f"+/-{unc:g} mm ({res['basis']}){part_note}."),
                "_line_len": res["line_len"],
            })
    by = {}
    for p in pts:
        by.setdefault(p["atlas_id"], []).append(p["kind"])
    cov = {
        "label": VIEWERS[key]["label"], "points": len(pts), "muscle_sides_with_points": len(by),
        "muscles_with_points": sorted({k[:-2] for k in by}),
        "per_muscle": {k: len(v) for k, v in sorted(by.items())},
        "reference_line_lengths_mm": {p["id"]: p.pop("_line_len") for p in pts},
        "failed": failed, "not_placed": skipped,
        "uncertainty_mm_range": [min((p["uncertainty_mm"] for p in pts), default=None), max((p["uncertainty_mm"] for p in pts), default=None)],
        "depth_from_skin": "nearest distance to this body's skin mesh" if body.skin is not None else "null: this viewer has no skin mesh",
    }
    print(f"{key}: {len(pts)} points, {len({k[:-2] for k in by})} muscles ({len(by)} muscle-sides), {len(failed)} failed, {len(skipped)} not placed", flush=True)
    return key, {"frame": FRAME, "points": pts}, cov


def run(viewer_keys, jobs=1):
    today = _dt.date.today().isoformat()
    out = {"schema": "nmsk.motor_points.v1",
           "licence": "Private -- owner's clinical layer (see PROJECT_STATE licensing rule)",
           "generated": today, "viewers": {}}
    cov = {"generated": today, "fail_threshold_mm": FAIL_MM, "sources": SOURCES, "viewers": {},
           "muscles_without_usable_source": NOT_COVERED_REASON}
    if jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(jobs) as ex:
            results = list(ex.map(run_one, viewer_keys))
    else:
        results = [run_one(k) for k in viewer_keys]
    for key, v, c in results:
        out["viewers"][key] = v; cov["viewers"][key] = c
    return out, cov


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--viewers", default="vhm,vhf,zan_m,zan_f")
    ap.add_argument("--out", default=str(OUT_JSON))
    ap.add_argument("--coverage", default=str(OUT_COVERAGE))
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    out, cov = run(a.viewers.split(","), a.jobs)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    Path(a.coverage).write_text(json.dumps(cov, indent=1, ensure_ascii=False) + "\n")
    print("wrote", a.out, "and", a.coverage)


if __name__ == "__main__":
    sys.exit(main())
