"""Q241 normal range of motion (population averages, degrees) used as the HARD bounds of the pose sliders.
Source: AAOS 'Joint Motion: Method of Measuring and Recording' (1965; Greene & Heckman, The Clinical Measurement of Joint Motion, AAOS 1994) and the AMA Guides to the Evaluation of Permanent Impairment
(5th/6th ed.) average values, Norkin & White 'Measurement of Joint Motion' (5th ed. 2016), Kapandji 'The Physiology of the Joints'; spine split between regions after White & Panjabi 'Clinical Biomechanics
of the Spine' (2nd ed. 1990).  The numbers below are quoted from these references AS REMEMBERED, they were NOT re-read from the books in this session; every entry marked ASSUMPTION is a modelling
choice (no single standard value).  They are population AVERAGES (young adults); an individual's range differs with age, sex, and measurement method.
Each entry: key -> (lo, hi, label, note)  with the sign convention given in the label (lo..hi is the allowed range of the displayed value)."""

# (lo, hi, label, source/assumption)
ROM = {
    # shoulder (glenohumeral + scapulothoracic together, as measured clinically)
    "shoulder_flex": (-60, 180, "Flexion (+) / extension (-)", "AAOS: flexion 0-180, extension 0-60"),
    "shoulder_abd": (-30, 180, "Abduction (+) / adduction (-)", "AAOS: abduction 0-180; adduction 0-30 (AMA 5th: 50 cross-body) - 30 used (ASSUMPTION: from the side, in the frontal plane)"),
    "shoulder_rot": (-90, 70, "Internal rotation (+) / external rotation (-)", "AAOS: internal 0-70, external 0-90 (arm at the side)"),
    "elbow_flex": (0, 150, "Flexion (+) / extension (0)", "AAOS: 0-150; AMA 140 (hyperextension 0-10 not allowed here)"),
    "forearm_sup": (-80, 80, "Supination (+) / pronation (-)", "AAOS: pronation 0-80, supination 0-80, zero = neutral (thumb forward), AMA 80/80"),
    "wrist_flex": (-70, 80, "Flexion (+) / extension (-)", "AAOS: flexion 0-80, extension 0-70"),
    "wrist_dev": (-30, 20, "Radial deviation (+) / ulnar deviation (-)", "AAOS: radial 0-20, ulnar 0-30"),
    "thumb_cmc_flex": (-20, 15, "CMC flexion (+) / extension (-)", "AAOS thumb: flexion 15 (CMC), extension 20"),
    "thumb_cmc_abd": (0, 70, "CMC palmar abduction (+)", "AAOS: abduction 0-70 (radial + palmar abduction together; ASSUMPTION: all at the CMC joint)"),
    "thumb_mcp": (-5, 50, "MCP flexion (+)", "AAOS: thumb MCP flexion 0-50"),
    "thumb_ip": (-20, 80, "IP flexion (+) / extension (-)", "AAOS: thumb IP flexion 0-80, extension 0-20"),
    "finger_mcp": (-45, 90, "MCP flexion (+) / extension (-)", "AAOS: MCP flexion 0-90, hyperextension 0-45"),
    "finger_pip": (0, 100, "PIP flexion (+)", "AAOS: PIP flexion 0-100"),
    "finger_dip": (0, 80, "DIP flexion (+)", "AAOS: DIP flexion 0-70/90 (80 used, ASSUMPTION: mid value)"),
    "hip_flex": (-30, 120, "Flexion (+) / extension (-)", "AAOS: flexion 0-120, extension 0-30"),
    "hip_abd": (-30, 45, "Abduction (+) / adduction (-)", "AAOS: abduction 0-45, adduction 0-30"),
    "hip_rot": (-45, 45, "Internal rotation (+) / external rotation (-)", "AAOS: internal 0-45, external 0-45"),
    "knee_flex": (0, 135, "Flexion (+) / extension (0)", "AAOS: 0-135 (active; passive up to 150), AMA 140"),
    "ankle_dp": (-50, 20, "Dorsiflexion (+) / plantarflexion (-)", "AAOS: dorsiflexion 0-20, plantarflexion 0-50"),
    "ankle_inv": (-15, 35, "Inversion (+) / eversion (-)", "AAOS: inversion 0-35, eversion 0-15 (the clinical value is subtalar + transverse tarsal together; all given to the subtalar joint here, ASSUMPTION)"),
    "toe_mtp": (-40, 40, "MTP flexion (+) / extension (-)", "ASSUMPTION: lesser toes ~ +40 / -40 (AAOS lists the great toe: flexion 45, extension 70)"),
    "toe1_mtp": (-70, 45, "Great toe MTP flexion (+) / extension (-)", "AAOS: great toe MTP flexion 0-45, extension 0-70"),
    "toe_pip": (0, 35, "PIP flexion (+)", "ASSUMPTION: lesser toes PIP flexion ~35 (few standard values)"),
    "toe_dip": (0, 60, "DIP flexion (+)", "ASSUMPTION: lesser toes DIP flexion ~60 (few standard values)"),
    "toe1_ip": (-5, 90, "Great toe IP flexion (+)", "AAOS: great toe IP flexion 0-90"),
    # spine: regional totals (as measured clinically); the per-level split is an ASSUMPTION (equal shares, except cervical rotation)
    "cerv_flex": (-45, 45, "Flexion (+) / extension (-)", "AAOS: cervical flexion 0-45, extension 0-45 (AMA 5th: 50 / 60) - includes the atlanto-occipital joint (head)"),
    "cerv_lat": (-45, 45, "Lateral bend right (+) / left (-)", "AAOS: lateral flexion 0-45 each side"),
    "cerv_rot": (-60, 60, "Rotation right (+) / left (-)", "AAOS: rotation 0-60 each side (AMA 80)"),
    "thor_flex": (-20, 30, "Flexion (+) / extension (-)", "White & Panjabi: thoracic flexion ~20-40, extension ~15-25 (ASSUMPTION: 30 / 20)"),
    "thor_lat": (-25, 25, "Lateral bend right (+) / left (-)", "White & Panjabi: ~25 each side"),
    "thor_rot": (-35, 35, "Rotation right (+) / left (-)", "AAOS thoracolumbar rotation 0-45 each side, mostly thoracic (ASSUMPTION: 35)"),
    "lumb_flex": (-25, 60, "Flexion (+) / extension (-)", "AAOS: lumbar flexion 0-60, extension 0-25"),
    "lumb_lat": (-25, 25, "Lateral bend right (+) / left (-)", "AAOS: lateral flexion 0-25 each side"),
    "lumb_rot": (-5, 5, "Rotation right (+) / left (-)", "White & Panjabi: lumbar axial rotation ~5 each side"),
}

# spine: share of the REGIONAL total taken by each level joint (child vertebra), per DOF.  ASSUMPTION: equal shares, cervical rotation 50% at C1/C2 (White & Panjabi), head (occiput/C1) gets part of the flexion.
def spine_weights(region, labels, dof):
    """labels: child vertebra labels top->bottom of the region (head joint 'OCC' included for cervical).  -> list of weights summing to 1"""
    n = len(labels)
    w = [1.0 / n] * n
    if region == "cervical":
        if dof == "rot" and "C1" in labels:                         # C1/C2 carries ~50% of the cervical rotation
            w = [0.5 if l == "C1" else (0.0 if l == "OCC" else 0.5 / (n - 2)) for l in labels]
        elif dof == "flex" and "OCC" in labels:                     # occiput/C1 ~ 20% of the flexion-extension arc
            w = [0.2 if l == "OCC" else 0.8 / (n - 1) for l in labels]
    return w
