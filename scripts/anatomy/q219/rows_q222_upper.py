"""Q222 rows, part 1: shoulder girdle, back, forearm, hand (PubMed-verified on 2026-10-12; see refs_q222.py)."""
from rows_common import P, S

# ------------------------------------------------------------------ pectoralis minor
S("pectoralis_minor.coracoid_insertion", "pectoralis_minor", "insertion_point", "Pectoralis minor: attachment surface on the coracoid", [
    (1, "umatani2026", "medial surface only, 11 of 22 shoulders (50 %)"),
    (2, "umatani2026", "medial surface plus superior / medial-to-superior surface (tendon extending toward the glenohumeral joint), 11 of 22 shoulders")],
  note="Two patterns, not two counted attachments: the tendon is on the medial surface in 50 % and reaches the superior surface in the other 50 % (Umatani 2026, 22 shoulders).")
P("pectoralis_minor", "insertion_coracoid_medial_surface", "insertion_point", "Insertion: medial surface of the coracoid process", "Tendon attached to the medial surface of the coracoid in 11 of 22 shoulders; those coracoids were longer and wider.", ["umatani2026"],
  ev="cadaver n=22 shoulders", var="50 %", anchor=dict(bone="scapula", landmark="coracoid process, medial surface"), setid="pectoralis_minor.coracoid_insertion",
  geom=dict(rule="end_snap_bone", end="lateral", bone="scapula", tol_mm=10))
P("pectoralis_minor", "insertion_coracoid_superior_surface", "insertion_point", "Insertion variant: superior or medial-to-superior surface of the coracoid", "In the other 11 of 22 shoulders the tendon attached to the superior or the medial-to-superior surface, extending toward the glenohumeral joint.", ["umatani2026"],
  ev="cadaver n=22 shoulders", var="50 %", anchor=dict(bone="scapula", landmark="coracoid process, superior surface"), setid="pectoralis_minor.coracoid_insertion")
P("pectoralis_minor", "origin_variant_bifid_ribs_4_6", "origin_part", "Origin variant: bifid belly / origin from ribs 4-6 (single case)", "Case report: right pectoralis minor bifid (medial and lateral fibres), left from the superolateral margins of ribs 4-6 to the anterosuperior coracoid; not a prevalence.", ["ogut2024pmi"],
  ev="case report, 1 cadaver", var="case report", note="Single case report of an atypical (inferior) origin; the usual origin pattern is not stated in the abstract and is not recorded here.")

# ------------------------------------------------------------------ latissimus dorsi
S("latissimus_dorsi.humeral_tendon", "latissimus_dorsi", "insertion_point", "Latissimus dorsi tendon: relation to the teres major tendon at the humerus", [
    (1, "kwon2025ld", "fully combined with the teres major tendon, 40.6 % of 32 tendons"),
    (2, "kwon2025ld", "partially combined, 34.4 %"), (3, "kwon2025ld", "fully separated, 25.0 %")],
  note="Three insertion patterns (combined / partially combined / separated), not three insertions.")
P("latissimus_dorsi", "insertion_humerus_tendon_combined", "insertion_point", "Humeral insertion: tendon fully combined with teres major", "Latissimus and teres major tendons fully combined at the humerus.", ["kwon2025ld"],
  ev="dissection, 32 tendons in 16 Korean cadavers", var="40.6 %", anchor=dict(bone="humerus", landmark="intertubercular groove region (landmark wording not in the abstract)"), setid="latissimus_dorsi.humeral_tendon")
P("latissimus_dorsi", "insertion_humerus_tendon_partial", "insertion_point", "Humeral insertion: tendon partially combined with teres major", "Partially combined tendons.", ["kwon2025ld"],
  ev="dissection, 32 tendons", var="34.4 %", anchor=dict(bone="humerus"), setid="latissimus_dorsi.humeral_tendon")
P("latissimus_dorsi", "insertion_humerus_tendon_separate", "insertion_point", "Humeral insertion: tendon fully separate from teres major", "Separate tendons; mean tendon width / length / thickness 48.4 / 56.2 / 6.2 mm (all 32 tendons).", ["kwon2025ld"],
  ev="dissection, 32 tendons", var="25.0 %", anchor=dict(bone="humerus"), setid="latissimus_dorsi.humeral_tendon")
P("latissimus_dorsi", "tendinous_slips_accessory", "insertion_point", "Accessory tendinous slips (to triceps tendon, brachial fascia, coracoid, anterior capsule)", "Slips connecting the latissimus tendon to the triceps tendon, adjacent brachial fascia, coracoid process and anterior joint capsule were found in nine specimens.", ["kwon2025ld"],
  ev="dissection, 32 tendons", var="9 specimens")

# ------------------------------------------------------------------ erector spinae (iliocostalis, longissimus, aponeurosis)
S("erector_spinae_lumbar.parts", "iliocostalis", "head_belly", "Lumbar erector spinae: parts", [
    (2, "bustami1986", "a superficial (costal) part and a deep (vertebral) part")],
  note="Bustami 1986 re-describes the lumbar erector spinae by its musculotendinous attachments instead of the iliocostalis / longissimus split; the superficial part = iliocostalis lumborum + upper longissimus thoracis, the deep part = lower longissimus thoracis.")
P("iliocostalis", "lumbar_superficial_costal_part", "head_belly", "Lumbar erector spinae, superficial (costal) part (= iliocostalis lumborum + upper longissimus thoracis)", "Arises by small fleshy slips from the posterior surface and the rostral / lateral margins of the erector spinae aponeurosis and inserts by slender flat tendons into the lower ten ribs.", ["bustami1986"],
  ev="dissection of the lumbar erector spinae (J Anat 1986)", setid="erector_spinae_lumbar.parts", related=["longissimus", "erector_spinae_aponeurosis"],
  note="Count of ribs and the attachments are Bustami's; the iliocostalis / longissimus equivalence is stated in the same abstract.")
P("longissimus", "lumbar_deep_vertebral_part", "head_belly", "Lumbar erector spinae, deep (vertebral) part (= lower longissimus thoracis)", "Arises by large fleshy laminae from the deep surface of the erector spinae aponeurosis and inserts mainly into the upper four lumbar and lower eight thoracic vertebrae.", ["bustami1986"],
  ev="dissection of the lumbar erector spinae (J Anat 1986)", setid="erector_spinae_lumbar.parts", related=["iliocostalis", "erector_spinae_aponeurosis"])
P("erector_spinae_aponeurosis", "posterior_surface_origin_slips", "ligament_component", "Posterior (superficial) surface and margins: origin of the superficial / costal part", "Small fleshy slips of the superficial part arise from the posterior surface and the rostral and lateral margins of the aponeurosis.", ["bustami1986"], cls="fascia",
  ev="dissection (J Anat 1986)")
P("erector_spinae_aponeurosis", "deep_surface_origin_laminae", "ligament_component", "Deep surface: origin of the deep / vertebral part", "Large fleshy laminae of the deep part arise from the deep surface of the aponeurosis.", ["bustami1986"], cls="fascia", ev="dissection (J Anat 1986)")

# ------------------------------------------------------------------ trapezius aponeurosis (structure already covered; three insertion regions)
P("trapezius", "aponeurosis_acromial_insertion", "insertion_point", "Aponeurotic insertion: medial edge of the acromion (fibrocartilaginous)", "Longest aponeurosis (mean 28.9 mm); the only region with a fibrocartilage insertion, just posterior to the AC joint; contiguous with the deltoid origin.", ["sugiura2025"],
  ev="21 cadaveric shoulder girdles (13 donors)", anchor=dict(bone="scapula", landmark="medial edge of the acromion"))
P("trapezius", "aponeurosis_acjoint_insertion", "insertion_point", "Aponeurotic insertion: posterior end of the acromioclavicular joint", "Aponeurosis 20.3 mm; thicker than at the clavicle; forms a contiguous complex with the superior AC capsule.", ["sugiura2025"],
  ev="21 cadaveric shoulder girdles", related=["acromioclavicular_ligament"])
P("trapezius", "aponeurosis_clavicular_insertion", "insertion_point", "Aponeurotic insertion: posterior edge of the lateral clavicle", "Shortest aponeurosis (mean 7.2 mm).", ["sugiura2025"],
  ev="21 cadaveric shoulder girdles", anchor=dict(bone="clavicle", landmark="posterior edge of the lateral clavicle"))

# ------------------------------------------------------------------ levator scapulae (variant slip)
P("levator_scapulae", "accessory_slip_superior_nuchal_line", "insertion_point", "Variant: accessory slip from the distal third to the superior nuchal line", "Single unilateral case: slip from the distal third of the muscle passing above the superficial branch of the transverse cervical vessels to the superior nuchal line.", ["gaydarski2023"],
  ev="case report, 1 cadaver", var="case report")

# ------------------------------------------------------------------ coracoacromial ligament
S("coracoacromial_ligament.bands", "coracoacromial_ligament", "ligament_component", "Coracoacromial ligament: number of bands", [
    (1, "alraddadi2017", "16 % of 220 shoulders"), (2, "alraddadi2017", "38 %"), (3, "alraddadi2017", "three or more, 46 %"),
    (1, "alraddadi2021", "18 % of 155 shoulders"), (2, "alraddadi2021", "36 %"), (3, "alraddadi2021", "three or more, 46 %"),
    (2, "fealy2005", "most common configuration in 56 shoulders: two bands (anterolateral and posteromedial)")],
  note="There is no single band count: one band in 16-18 %, two in 36-38 %, three or more in 46 %. Shapes in Alraddadi 2017: broadband 6 %, quadrangular 10 %, Y-shaped 38 %, multiple-banded 46 %.")
P("coracoacromial_ligament", "band_anterolateral", "ligament_component", "Anterolateral band (ALB)", "Commonly extends to the posterolateral acromion and may continue anterolaterally to end in a 'coracoacromial falx'; thicker at the acromion than at the coracoid; spurs form in it.", ["fealy2005"], cls="ligament",
  ev="cadaver, 56 shoulders (31 cadavers)", var="two-band configuration most common", setid="coracoacromial_ligament.bands")
P("coracoacromial_ligament", "band_posteromedial", "ligament_component", "Posteromedial band (PMB)", "Second band of the usual two-band ligament; thicker at the coracoid than at the acromion; may be mistaken for the entire ligament at arthroscopy.", ["fealy2005"], cls="ligament",
  ev="cadaver, 56 shoulders", setid="coracoacromial_ligament.bands")
P("coracoacromial_ligament", "band_additional", "ligament_component", "Additional bands (three or more)", "Multiple-banded ligaments (46 %) attach more medially at the acromion and coracoid; more than one band is associated with a rotator cuff tear.", ["alraddadi2017", "alraddadi2021"], cls="ligament",
  ev="cadaver, 220 and 172 shoulders", var="46 %", setid="coracoacromial_ligament.bands")
P("coracoacromial_ligament", "attachment_acromion", "ligament_component", "Acromial attachment: medial aspect vs anterior edge", "Attached to the medial aspect of the acromion in 60 %, restricted to the anterior edge in 40 %.", ["alraddadi2017"], cls="ligament",
  ev="cadaver, 220 shoulders", var="60 % / 40 %", anchor=dict(bone="scapula", landmark="acromion (medial aspect or anterior edge)"))
P("coracoacromial_ligament", "attachment_coracoid", "ligament_component", "Coracoid attachment: medial end vs posterior aspect", "Attached to the medial end of the coracoid in 75 %, to the posterior aspect in 25 %.", ["alraddadi2017"], cls="ligament",
  ev="cadaver, 220 shoulders", var="75 % / 25 %", anchor=dict(bone="scapula", landmark="coracoid process (medial end or posterior aspect)"))

# ------------------------------------------------------------------ acromioclavicular ligament / capsule
P("acromioclavicular_ligament", "capsular_insertion_acromial_side", "ligament_component", "Capsule / ligament insertion on the acromion", "Capsular insertion begins on average 2.8 mm (2.3-3.3) from the medial acromion; mean capsular width 1.6-2.9 mm; the CA ligament insertion lies 3.5 mm from the medial acromion.", ["stine2009"], cls="ligament",
  ev="cadaver, 28 shoulders", anchor=dict(bone="scapula", landmark="medial acromion"))
P("acromioclavicular_ligament", "capsular_insertion_clavicular_side", "ligament_component", "Capsule / ligament insertion on the lateral clavicle", "Capsular insertion begins on average 3.5 mm (2.9-3.9) from the distal clavicle; the trapezoid ligament begins 14.7 mm and the conoid 32.1 mm from the lateral clavicle.", ["stine2009"], cls="ligament",
  ev="cadaver, 28 shoulders", anchor=dict(bone="clavicle", landmark="distal (lateral) clavicle"), related=["coracoclavicular_ligament"],
  note="Measured on the anterior, posterior, superior and inferior edges (the abstract gives pooled means); separate superior / inferior ligament names are not defined in the abstract and are not used.")

# ------------------------------------------------------------------ sternoclavicular ligament
P("sternoclavicular_ligament", "posterior_capsule", "ligament_component", "Posterior capsule (posterior sternoclavicular ligament)", "Review: the posterior capsule is the most important structure for sternoclavicular stability whichever the direction of injury; the costoclavicular, interclavicular and capsular ligaments stabilise the joint.", ["morell2016"], cls="ligament",
  ev="literature review", related=["costoclavicular_ligament", "interclavicular_ligament"], note="Review article; the anterior capsule is not separately characterised in the abstract.")

# ------------------------------------------------------------------ supinator
S("supinator.layers", "supinator", "head_belly", "Supinator: heads / layers", [
    (1, "thomas2000", "one semicircular head or layer in 71 % of 31 specimens"), (2, "thomas2000", "two distinct heads or layers in 29 %")],
  note="Superficial layer to the lateral epicondyle, deep layer to the ulna below the radial notch (Thomas 2000).")
P("supinator", "superficial_layer", "head_belly", "Superficial layer / head (to the lateral epicondyle)", "In the two-layer pattern (29 %) the superficial layer extends to the lateral epicondyle; its proximal margin is the arcade of Frohse (membranous 68 %, tendinous 32 %).", ["thomas2000"],
  ev="cadaver, 31 specimens of 16 adults", var="two-layer pattern 29 %", setid="supinator.layers", anchor=dict(bone="humerus", landmark="lateral epicondyle"), related=["arcade_of_frohse"])
P("supinator", "deep_layer", "head_belly", "Deep layer / head (to the ulna below the radial notch)", "In the two-layer pattern the deep layer extends to the ulna below the radial notch.", ["thomas2000"],
  ev="cadaver, 31 specimens", var="29 %", setid="supinator.layers", anchor=dict(bone="ulna", landmark="below the radial notch"))
P("supinator", "pin_exit_through_muscle", "fascial_passage", "Posterior interosseous nerve through the supinator", "The radial nerve divides 3.6 cm proximal to the leading edge of the supinator; the posterior interosseous nerve passes beneath the arcade and leaves the muscle 3.8 +/- 0.9 cm distal to its proximal margin.", ["thomas2000"],
  ev="cadaver, 31 specimens", passes=dict(kind="nerve", traversing=["posterior_interosseous_nerve"], through="supinator (beneath the arcade of Frohse)"), related=["arcade_of_frohse"])

# ------------------------------------------------------------------ extensor carpi radialis brevis / extensor digitorum common origin
P("extensor_carpi_radialis_brevis", "origin_lateral_epicondyle", "origin_part", "Origin: lateral epicondylar prominence (footprint 8.3 x 7.6 mm)", "Origin footprint 8.3 +/- 0.8 mm proximal-distal x 7.6 +/- 0.3 mm anterior-posterior, 0 mm from the joint capsule.", ["kacena2025"],
  ev="cadaver, 6 arms", anchor=dict(bone="humerus", landmark="lateral epicondyle"), related=["lateral_collateral_ligament_complex_elbow"],
  note="Small footprint: far below the resolution of the body meshes -> text only.")
P("extensor_digitorum", "origin_lateral_epicondyle_footprint", "origin_part", "Common extensor origin of EDC: footprint 5.1 x 7.3 mm", "EDC origin 5.1 +/- 0.6 x 7.3 +/- 0.9 mm; its distal-most edge touches the proximal edge of the lateral collateral ligament; LCL lies 10.3 +/- 1.5 mm from the epicondyle.", ["kacena2025"],
  ev="cadaver, 6 arms", anchor=dict(bone="humerus", landmark="lateral epicondyle"))

# ------------------------------------------------------------------ flexor carpi ulnaris
P("flexor_carpi_ulnaris", "humeral_head", "head_belly", "Humeral head (flexor-pronator origin)", "The humeral head shares a common aponeurosis with flexor digitorum superficialis of the ring finger; this septum within the flexor-pronator origin must be released from the proximal ulna to transpose the ulnar nerve.", ["inserra1986"],
  ev="cadaver dissection + surgical series (J Hand Surg 1986)", anchor=dict(bone="humerus", landmark="medial epicondyle (flexor-pronator origin)"), related=["flexor_digitorum_superficialis", "ulnar_collateral_ligament_elbow"],
  note="The abstract names the humeral head (and the ring-finger FDS septum); the ulnar head is not described in the abstract.")

# ------------------------------------------------------------------ thenar muscles
P("abductor_pollicis_brevis", "origin_flexor_retinaculum", "origin_part", "Origin: proximal-radial quadrant of the transverse carpal ligament", "Origin area 105.8 +/- 30.3 mm2 = 18.4 +/- 4.8 % of the TCL volar surface (386.2 mm2).", ["loss2020"],
  ev="cadaver, 10 specimens", anchor=dict(landmark="flexor retinaculum (TCL), proximal-radial quadrant"), related=["flexor_retinaculum"])
P("flexor_pollicis_brevis", "superficial_head", "head_belly", "Superficial head (median nerve)", "Superficial head (sFPB) with its own median nerve branch arising 8.3 +/- 5.3 mm distal to the thenar branch (6 hands).", ["rein2025", "loss2020"],
  ev="cadaver, 6 hands; 10 specimens", setid=None)
P("flexor_pollicis_brevis", "deep_head", "head_belly", "Deep head (ulnar nerve territory)", "A deep head exists distinct from the superficial head; it is among the muscles reinnervated through the deep branch of the ulnar nerve.", ["rein2025"], ev="cadaver, 6 hands",
  note="Abstract: the transfer to the deep branch of the ulnar nerve shortens the reinnervation distance of 'the deep head of the FPB' (and 1st dorsal interosseous, adductor pollicis); its origin site is not given.")
P("flexor_pollicis_brevis", "origin_superficial_head_distal_aponeurosis", "origin_part", "Origin of the superficial head: distal aponeurosis outside the TCL (64.6 mm2)", "sFPB origin area 64.6 +/- 15.2 mm2, on the distal aponeurosis outside the transverse carpal ligament.", ["loss2020"],
  ev="cadaver, 10 specimens", related=["flexor_retinaculum"])
P("opponens_pollicis", "origin_trapezium_ridge_tcl", "origin_part", "Origin: around the ridge of the trapezium and the TCL (245.9 mm2)", "Largest thenar origin area (245.9 +/- 70.7 mm2; 17.3 +/- 9.6 % of the TCL surface), located around the ridge of the trapezium.", ["loss2020"],
  ev="cadaver, 10 specimens", anchor=dict(bone="trapezium", landmark="ridge of the trapezium"), related=["flexor_retinaculum"])

# ------------------------------------------------------------------ hypothenar muscles
S("flexor_digiti_minimi_hand.bellies", "flexor_digiti_minimi_brevis_hand", "head_belly", "Flexor digiti minimi brevis (hand): number of bellies", [
    (1, "may2020", "one belly in 58 % of hands (38 donors)"), (2, "may2020", "two bellies in 21 %"), (0, "may2020", "missing in 21 %")])
P("flexor_digiti_minimi_brevis_hand", "belly_main", "head_belly", "Main belly (single in 58 %, double in 21 %, absent in 21 %)", "Appearance varies: one belly 58 %, two bellies 21 %, absent 21 %.", ["may2020"],
  ev="dissection of both hands of 38 donors", var="absent 21 %", setid="flexor_digiti_minimi_hand.bellies")
P("flexor_digiti_minimi_brevis_hand", "accessory_heads", "origin_part", "Accessory heads (flexor retinaculum, antebrachial fascia, long forearm flexors)", "Accessory heads with origin from the flexor retinaculum, the antebrachial fascia or the long flexor muscles of the forearm have been reported.", ["claassen2013"],
  ev="literature review + 1 case", var="reported variants")
P("abductor_digiti_minimi_hand", "bellies_one_to_three", "head_belly", "Bellies: one to three (most variable hypothenar muscle)", "The abductor digiti minimi is the most variable hypothenar muscle, with one to three muscle bellies; supernumerary muscles associated with it in 2.5 % of 38 donors.", ["claassen2013", "may2020"],
  ev="review; dissection of 38 donors", var="supernumerary 2.5 %")
P("abductor_digiti_minimi_hand", "accessory_origins", "origin_part", "Additional heads: flexor retinaculum, palmaris longus tendon, pronator quadratus tendon, antebrachial fascia", "Additional heads can arise from the flexor retinaculum, the palmaris longus tendon, the pronator quadratus tendon or the deep fascia of the palmar forearm (relevant to Guyon's canal).", ["claassen2013"],
  ev="literature review", var="reported variants", related=["guyons_canal"])
P("opponens_digiti_minimi", "additional_head_aponeurosis", "head_belly", "Additional head from the forearm aponeurosis (rare)", "Opponens digiti minimi is constantly present and mostly without variation; in few cases an additional head arises from the lower arm aponeurosis.", ["claassen2013", "may2020"],
  ev="review; dissection 38 donors", var="rare")

# ------------------------------------------------------------------ Gantzer's muscle (accessory head of FPL / FDP)
P("flexor_pollicis_longus", "gantzer_accessory_head", "head_belly", "Accessory head (Gantzer's muscle) from the coronoid process", "Disputed prevalence: 20.3 % of 473 limbs by MRI / US (all from the coronoid process, 79.1 % attached to FPL, 20.9 % to FDS in the US sample) vs 48 % pooled from 59 cadaveric studies (5903 limbs); the anterior interosseous nerve lies posterior to it.", ["torun2022", "asghar2022"],
  ev="MRI / US n=473; meta-analysis of 59 cadaveric studies", var="20.3 % (imaging) vs 48 % (cadaver meta-analysis)", anchor=dict(bone="ulna", landmark="coronoid process"),
  note="Prevalence disagreement recorded, not resolved: imaging series vs pooled cadaver series.")
P("flexor_digitorum_profundus", "gantzer_accessory_head", "head_belly", "Accessory head to FDP (Gantzer's muscle variant)", "Accessory head of flexor digitorum profundus in 17 % (14 studies, 1627 limbs); the FPL accessory head is about three times more common.", ["asghar2022"],
  ev="meta-analysis of cadaveric studies", var="17 %")

# ------------------------------------------------------------------ quadratus lumborum / psoas on the lumbar transverse processes
P("quadratus_lumborum", "attachment_transverse_process_lateral_border", "insertion_point", "Attachment to the lumbar transverse processes: lateral border (upper and lower corners)", "Quadratus lumborum attaches to the lateral border of each lumbar transverse process, at its upper and lower corners; transversus abdominis (via the middle layer of lumbar fascia) to the tip.", ["barker2007"],
  ev="cadaver, 18 embalmed", anchor=dict(bone="lumbar_vertebrae", landmark="lateral border of the transverse process, upper and lower corners"), related=["middle_layer_tlf", "transversus_abdominis"])
P("iliopsoas", "psoas_attachment_transverse_process_anteromedial", "origin_part", "Psoas major: anteromedial surface of the lumbar transverse processes", "Psoas attaches to the anteromedial surface of each lumbar transverse process.", ["barker2007"],
  ev="cadaver, 18 embalmed", anchor=dict(bone="lumbar_vertebrae", landmark="anteromedial surface of the transverse process"))
P("middle_layer_tlf", "transverse_process_tip_thickening", "ligament_component", "Thickened attachment to the tips of the lumbar transverse processes", "The middle layer is thicker at the level of the transverse processes (0.62 mm) than between them (0.40 mm) and attaches to the tips; in 3 cadavers tension on it fractured a transverse process.", ["barker2007"], cls="fascia",
  ev="cadaver, 18 embalmed", related=["transversus_abdominis", "quadratus_lumborum"])

# ================================================================== batch 2 (forearm variants, ECU subsheath, EPL tendon)
P("palmaris_longus", "muscle_belly_variable_presence", "head_belly", "Muscle belly (absent in 37-60 % depending on the series)", "Clinical (Schaeffer / Thompson) series: absent in 37.2 % of 500 forearms (Pakistani sample) and in 59.75 % of 82 individuals of 20 families; the sources do not agree and use clinical tests, not dissection.", ["javaid2023", "vucinic2025"],
  ev="clinical tests, n=500 forearms; n=82 individuals", var="agenesis 37.2 % vs 59.75 %", note="Prevalence of absence is population- and method-dependent (ethnicity differences reported); not a count of parts.")
S("brachioradialis.accessory_forms", "brachioradialis", "head_belly", "Brachioradialis: accessory forms", [
    (2, "triantafyllou2024abr", "typical belly + accessory brachioradialis (brachioradialis brevis) in 2.4 % of 83 limbs"),
    (2, "triantafyllou2024brl", "typical belly + 'brachioradialis longus' accessory form (single case)")])
P("brachioradialis", "accessory_brachioradialis_brevis", "head_belly", "Accessory brachioradialis (to the proximal third of the radius, 2.4 %)", "Origin alongside the typical BR, insertion on the anterior surface of the proximal third of the radius (radial tuberosity in earlier reports), radial nerve supply coursing deep.", ["triantafyllou2024abr"],
  ev="dissection of 83 limbs", var="2.4 %", setid="brachioradialis.accessory_forms", anchor=dict(bone="radius", landmark="anterior surface, proximal third"))
P("brachioradialis", "accessory_brachioradialis_longus_case", "head_belly", "Variant 'brachioradialis longus' (single case)", "From the lateral humerus between deltoid and triceps lateral head, joined by a second head from brachialis, inserting on the radial styloid process.", ["triantafyllou2024brl"],
  ev="case report", var="case report", setid="brachioradialis.accessory_forms", anchor=dict(bone="radius", landmark="styloid process"))
P("extensor_carpi_ulnaris", "subsheath_distal_ulna", "ligament_component", "ECU subsheath at the distal ulna (about 9 mm wide, 10 mm long)", "Distinct subsheath 8.9 mm wide proximally and 9.0 mm distally; its distal ulnar insertion lies 0.5 mm proximal to the styloid tip and stretches 10.2 mm proximally; roughly 1 cm square; groove depth up to 2.5 mm; sectioning increases tendon travel from 3.3 to 5.4 mm.", ["shoap2022"],
  ev="fresh-frozen upper extremities n=12", anchor=dict(bone="ulna", landmark="ulnar styloid (distal ulna groove)"), related=["tfcc_disc", "extensor_retinaculum"])
P("extensor_pollicis_longus_tendon", "normal_third_compartment_ulnar_to_lister", "fascial_passage", "Normal course: third compartment, ulnar to Lister's tubercle", "The normal EPL tendon occupies the third dorsal compartment ulnar to Lister's tubercle.", ["munn2023"], cls="tendon",
  ev="case report (statement of the normal course)", passes=dict(kind="tendon", traversing=["extensor_pollicis_longus"], through="third dorsal compartment of the extensor retinaculum"), related=["extensor_retinaculum"],
  note="Only a statement within a case report; no separate anatomical series retrieved.")
P("extensor_pollicis_longus_tendon", "accessory_tendon_fourth_compartment", "insertion_point", "Variant: accessory EPL tendon (and accessory EIP tendon) in the fourth compartment (single case)", "Two anomalous accessory tendons, an accessory EPL and an accessory extensor indicis proprius, were present in the fourth compartment of a 57-year-old patient.", ["munn2023"], cls="tendon",
  ev="case report", var="case report")
