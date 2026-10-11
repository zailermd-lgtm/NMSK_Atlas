"""Shoulder girdle, arm, elbow, forearm, wrist, hand rows."""
from rows_common import P, S

# =================================================================== DELTOID (owner example)
S("deltoid.heads", "deltoid", "head_belly", "Deltoid: number of parts", [
    (3, "rispoli2009", "anterior, middle, posterior heads, each with its own insertion"),
    (3, "vohra2024", "'trisegmented muscle with anterior, middle and posterior components'"),
    (7, "sakoma2011", "60 shoulders: seven anatomical segments delimited by intramuscular tendons (three humeral tendon insertions)"),
    (19, "brown2007", "EMG study: 19 segments across pectoralis major + deltoid + latissimus dorsi (not a per-muscle count)")],
  note="The owner expected 'at least 3 heads, if not more': the classical count is 3 gross parts, the intramuscular-tendon count is 7 (Sakoma 2011).")
_DELT_Z = "zan_{p}_part_of_deltoid_muscle_{{s}}"
P("deltoid", "clavicular_part", "head_belly", "Clavicular (anterior) part",
  "Anterior head of the deltoid; arises from the lateral third of the clavicle; has its own humeral tendon (anterior tendon).",
  ["rispoli2009", "vohra2024", "sakoma2011"], ev="cadaver dissection (10, 8 and 60 shoulders)", setid="deltoid.heads",
  z=[_DELT_Z.format(p="clavicular")], geom=dict(rule="deltoid_sector", sector="clavicular"),
  note="Origin site itself is a separate unverified-textbook row (deltoid.origin_lateral_third_clavicle).")
P("deltoid", "acromial_part", "head_belly", "Acromial (middle) part",
  "Middle head of the deltoid, from the acromion; multipennate: the muscle fibres run between intramuscular tendons (see MTJ rows). Own humeral tendon (middle tendon).",
  ["rispoli2009", "vohra2024", "sakoma2011"], ev="cadaver dissection", setid="deltoid.heads",
  z=[_DELT_Z.format(p="acromial")], geom=dict(rule="deltoid_sector", sector="acromial"))
P("deltoid", "spinal_part", "head_belly", "Spinal (posterior) part",
  "Posterior head of the deltoid, from the spine of the scapula; own humeral tendon (posterior tendon). Its architecture (fibre bundle length) was measured separately in the posterior-deltoid-to-triceps transfer study.",
  ["rispoli2009", "vohra2024", "friden2001"], ev="cadaver dissection; microdissection architecture", setid="deltoid.heads",
  z=[_DELT_Z.format(p="scapular_spinal")], geom=dict(rule="deltoid_sector", sector="spinal"))
P("deltoid", "origin_lateral_third_clavicle", "origin_part", "Origin: lateral third of clavicle (anterior border)",
  "Origin of the clavicular part.", ["gray42"], ver="unverified", ev="textbook", anchor=dict(bone="clavicle", landmark="anterior border, lateral third"),
  note="Textbook origin; Gray's 42nd ed., chapter 'Shoulder girdle' (page not verified). Geometry only on the Z bodies (dedicated part mesh).", geom=dict(rule="end_snap_bone", muscle_part="clavicular", end="proximal", bone="clavicle", tol_mm=8))
P("deltoid", "origin_acromion", "origin_part", "Origin: acromion (lateral margin and superior surface)",
  "Origin of the acromial part.", ["gray42"], ver="unverified", ev="textbook", anchor=dict(bone="scapula", landmark="acromion"),
  geom=dict(rule="end_snap_bone", muscle_part="acromial", end="proximal", bone="scapula", tol_mm=8))
P("deltoid", "origin_scapular_spine", "origin_part", "Origin: inferior lip of the spine of the scapula",
  "Origin of the spinal part (continuous medially with the trapezius insertion line).", ["gray42"], ver="unverified", ev="textbook",
  anchor=dict(bone="scapula", landmark="spine of scapula, inferior lip"), geom=dict(rule="end_snap_bone", muscle_part="spinal", end="proximal", bone="scapula", tol_mm=8))
P("deltoid", "insertion_anterior_tendon", "insertion_point", "Humeral insertion: anterior-head tendon",
  "Insertion of the anterior head on the deltoid tuberosity; mean insertion width 7.3 mm, length 70 mm (n=10).", ["rispoli2009", "sakoma2011"],
  ev="cadaver dissection n=10 (Rispoli); n=60 (Sakoma)", anchor=dict(bone="humerus", landmark="deltoid tuberosity (anterior line)"), setid="deltoid.insertions")
P("deltoid", "insertion_middle_tendon", "insertion_point", "Humeral insertion: middle-head tendon",
  "Insertion of the middle head on the deltoid tuberosity; mean width 4.7 mm, length 48.4 mm (n=10).", ["rispoli2009", "sakoma2011"],
  ev="cadaver dissection n=10", anchor=dict(bone="humerus", landmark="deltoid tuberosity (middle line)"), setid="deltoid.insertions")
P("deltoid", "insertion_posterior_tendon", "insertion_point", "Humeral insertion: posterior-head tendon",
  "Insertion of the posterior head; mean width 7.8 mm, length 63.4 mm (n=10).", ["rispoli2009", "sakoma2011"],
  ev="cadaver dissection n=10", anchor=dict(bone="humerus", landmark="deltoid tuberosity (posterior line)"), setid="deltoid.insertions")
S("deltoid.insertions", "deltoid", "insertion_point", "Deltoid: humeral tendon insertions",
  [(3, "sakoma2011", "three tendinous insertions to the humerus (Sakoma 2011); Rispoli 2009 measured three insertion lines"),
   (3, "vohra2024", "anterior/middle/posterior tendons; 2/8 shoulders showed a 'step-off' pattern")])
P("deltoid", "insertion_deltoid_tuberosity_complex", "insertion_point", "Humeral insertion complex (the three tendinous insertions together)",
  "Composite of the anterior, middle and posterior head insertions on/around the deltoid tuberosity (three tendinous insertions, Sakoma 2011; three insertion lines, Rispoli 2009). A muscle mesh cannot separate the three tendons, so geometry is derived for the composite only.",
  ["rispoli2009", "sakoma2011"], ev="cadaver dissection n=10 / n=60", anchor=dict(bone="humerus", landmark="deltoid tuberosity region"), setid="deltoid.insertions",
  geom=dict(rule="end_snap_bone", end="distal", bone="humerus", tol_mm=8), note="Composite row: its coordinates stand for the three rows above, which are text-only.")
P("deltoid", "insertion_step_off_variant", "insertion_point", "Variant: 'step-off' insertion pattern",
  "Anterior, middle and posterior tendons insert superior-medial, directly on and inferior-lateral to the deltoid tuberosity (2 of 8 shoulders).", ["vohra2024"],
  ev="cadaver dissection n=8", var="2/8", anchor=dict(bone="humerus", landmark="deltoid tuberosity"))
P("deltoid", "insertion_lateral_intermuscular_septum_continuity", "insertion_point", "Fascial continuity: lateral intermuscular septum (posterior)",
  "Deltoid tendon and aponeurosis are continuous posteriorly with the lateral intermuscular septum in all 10 specimens, so a partial release keeps continuity.", ["rispoli2009"],
  ev="cadaver dissection n=10", var="10/10", related=["lateral_intermuscular_septum"])
P("deltoid", "insertion_brachialis_deep_brachial_fascia_continuity", "insertion_point", "Fascial continuity: brachialis and deep brachial fascia (anterior)",
  "Anteriorly the deltoid tendon/aponeurosis is continuous with the lateral aspect of brachialis and the deep brachial fascia (10/10).", ["rispoli2009"],
  ev="cadaver dissection n=10", var="10/10", related=["brachial_fascia", "brachialis"])
P("deltoid", "mtj_intramuscular_tendons_humeral_side", "muscle_tendon_junction", "Intramuscular tendons rising from the three humeral insertions",
  "The three humeral tendons continue as intramuscular tendons into the muscle; muscle fibres insert on them, defining the segments (seven in total).", ["sakoma2011"],
  ev="cadaver dissection n=60", setid="deltoid.heads", note="MTJ zone is 3-D intramuscular; no mesh carries it.")
P("deltoid", "mtj_intramuscular_septa_origin_side", "muscle_tendon_junction", "Intramuscular septa descending from the acromion/origin (acromial multipennate part)",
  "Gray's describes four intramuscular septa descending from the acromion and interdigitating with three ascending from the deltoid tuberosity, making the acromial part multipennate.", ["gray42", "sakoma2011"],
  ver="unverified", ev="textbook (Gray's, via secondary source); not confirmed in a primary dissection count by this search",
  note="'Four' is the textbook count; Sakoma 2011 gives seven segments from the intramuscular-tendon distribution. Marked unverified because no primary source for the number four was found.")

# =================================================================== BICEPS BRACHII
P("biceps_brachii", "long_head", "head_belly", "Long head", "Long head; its tendon originates intra-articularly (supraglenoid tubercle + superior labrum) and its distal tendon forms the proximal part of the distal biceps insertion.",
  ["eames2007", "athwal2007", "vangsness1994"], ev="cadaver dissection", setid="biceps_brachii.heads")
P("biceps_brachii", "short_head", "head_belly", "Short head", "Short head; its distal tendon inserts distal on the bicipital tuberosity and gives rise to the lacertus fibrosus.",
  ["eames2007", "athwal2007"], ev="cadaver dissection", setid="biceps_brachii.heads")
S("biceps_brachii.heads", "biceps_brachii", "head_belly", "Biceps brachii: number of heads", [(2, "eames2007", "distal tendon in two distinct parts (long + short head) in 10/17 elbows; interdigitating muscle in 7/17")])
P("biceps_brachii", "origin_supraglenoid_tubercle", "origin_part", "Long head origin: supraglenoid tubercle", "About half of the long head tendon attaches to the supraglenoid tubercle.", ["vangsness1994"],
  ev="cadaver dissection n=105", var="~50 %", anchor=dict(bone="scapula", landmark="supraglenoid tubercle"))
P("biceps_brachii", "origin_superior_labrum", "origin_part", "Long head origin: superior glenoid labrum", "About 50 % of the tendon arises directly from the superior labrum; main labral origin posterior in >50 %, posterior only in 1/4; four origin types by anterior/posterior labral contribution.", ["vangsness1994"],
  ev="cadaver dissection n=105", var="4 types", anchor=dict(bone="scapula", landmark="superior glenoid labrum"))
P("biceps_brachii", "origin_coracoid_apex_short_head", "origin_part", "Short head origin: apex of coracoid process", "Common tendon with coracobrachialis.", ["gray42"], ver="unverified", ev="textbook",
  anchor=dict(bone="scapula", landmark="coracoid process, apex"))
P("biceps_brachii", "insertion_long_head_tendon_radial_tuberosity", "insertion_point", "Insertion: long-head tendon on the proximal part of the bicipital (radial) tuberosity",
  "Long-head tendon inserts on the proximal aspect of the tuberosity (footprint area 48 mm2); more suited to supination.", ["athwal2007", "eames2007"], ev="cadaver dissection n=15 / n=17",
  anchor=dict(bone="radius", landmark="bicipital (radial) tuberosity, proximal part"))
P("biceps_brachii", "insertion_short_head_tendon_radial_tuberosity", "insertion_point", "Insertion: short-head tendon on the distal part of the bicipital (radial) tuberosity",
  "Short-head tendon inserts on the distal aspect (footprint area 60 mm2); total footprint 108 mm2; more suited to elbow flexion.", ["athwal2007", "eames2007"], ev="cadaver dissection n=15 / n=17",
  anchor=dict(bone="radius", landmark="bicipital (radial) tuberosity, distal part"))
P("biceps_brachii", "insertion_radial_tuberosity_complex", "insertion_point", "Distal biceps insertion complex on the radial tuberosity (long + short head tendons together)",
  "Composite footprint (108 mm2 in 15 arms): long-head tendon proximal, short-head tendon distal on the tuberosity. A muscle mesh cannot separate the two tendons.",
  ["athwal2007", "eames2007"], ev="cadaver dissection n=15 / n=17", anchor=dict(bone="radius", landmark="bicipital (radial) tuberosity"),
  geom=dict(rule="end_snap_bone", end="distal", bone="radius", tol_mm=10), note="Composite row for geometry; the two tendon rows are text-only.")
P("biceps_brachii", "insertion_lacertus_fibrosus", "insertion_point", "Insertion expansion: bicipital aponeurosis (lacertus fibrosus)",
  "Originates from the distal short-head tendon in all 15 specimens; three layers and encircles the ulnar-side forearm flexor muscles.", ["athwal2007", "eames2007"],
  ev="cadaver dissection", related=["bicipital_aponeurosis"])

# =================================================================== BRACHIALIS
P("brachialis", "superficial_head", "head_belly", "Superficial head", "Larger head from the anterolateral humerus; thick round tendon to the ulnar tuberosity.", ["leonello2007"], ev="cadaver dissection n=11", setid="brachialis.heads")
P("brachialis", "deep_head", "head_belly", "Deep head", "Smaller, fan-shaped head from the distal humerus; inserts by aponeurosis on the coronoid process; its inferolateral fibres are supplied by the radial nerve.", ["leonello2007"], ev="cadaver dissection n=11", setid="brachialis.heads")
S("brachialis.heads", "brachialis", "head_belly", "Brachialis: number of heads", [(2, "leonello2007", "two heads in all 11 specimens; contrasts with the single-belly textbook description")])
P("brachialis", "insertion_proximal_ulna_complex", "insertion_point", "Insertion complex on the proximal ulna (ulnar tuberosity + coronoid process)",
  "Composite of the superficial-head tendon (ulnar tuberosity) and the deep-head aponeurosis (coronoid process).", ["leonello2007"], ev="cadaver dissection n=11",
  anchor=dict(bone="ulna", landmark="ulnar tuberosity / coronoid process"), geom=dict(rule="end_snap_bone", end="distal", bone="ulna", tol_mm=10), note="Composite row for geometry; the two rows below are text-only.")
P("brachialis", "insertion_ulnar_tuberosity", "insertion_point", "Insertion: ulnar tuberosity (superficial head)", "Thick round tendon.", ["leonello2007"], ev="cadaver dissection n=11", anchor=dict(bone="ulna", landmark="ulnar tuberosity"))
P("brachialis", "insertion_coronoid_process", "insertion_point", "Insertion: coronoid process (deep head)", "Aponeurotic insertion, more anterior than the superficial head.", ["leonello2007"], ev="cadaver dissection n=11", anchor=dict(bone="ulna", landmark="coronoid process"))

# =================================================================== TRICEPS
P("triceps_brachii", "long_head", "head_belly", "Long head", "Long head (biarticular); architecture measured separately from the lateral and medial heads (fibre bundle length differs).", ["friden2001"], ev="microdissection n=10",
  setid="triceps_brachii.heads", z=["zan_long_head_of_triceps_brachii_{s}"], geom=dict(rule="z_part_mesh"))
P("triceps_brachii", "lateral_head", "head_belly", "Lateral head", "Lateral head (fibre bundle length 66.5 mm in the architectural study).", ["friden2001"], ev="microdissection n=10",
  setid="triceps_brachii.heads", z=["zan_lateral_head_of_triceps_brachii_{s}"], geom=dict(rule="z_part_mesh"))
P("triceps_brachii", "medial_head", "head_belly", "Medial head", "Medial head (fibre bundle length 64.5 mm in the architectural study).", ["friden2001"], ev="microdissection n=10",
  setid="triceps_brachii.heads", z=["zan_medial_head_of_triceps_brachii_{s}"], geom=dict(rule="z_part_mesh"))
S("triceps_brachii.heads", "triceps_brachii", "head_belly", "Triceps brachii: number of heads", [(3, "friden2001", "three heads measured: medial, lateral, long")])
P("triceps_brachii", "origin_infraglenoid_tubercle", "origin_part", "Long head origin: infraglenoid tubercle", "Textbook origin.", ["gray42"], ver="unverified", ev="textbook", anchor=dict(bone="scapula", landmark="infraglenoid tubercle"))
P("triceps_brachii", "insertion_tendon_proper_olecranon", "insertion_point", "Insertion: central triceps tendon on the olecranon",
  "Tendon proper; mean width 23.7 mm; dome-shaped footprint 20.9 x 13.4 mm, 14.8 mm from the olecranon tip (n=36 elbows).", ["keener2010"], ev="cadaver dissection n=36", anchor=dict(bone="ulna", landmark="olecranon, posterior surface"),
  geom=dict(rule="end_snap_bone", end="distal", bone="ulna", tol_mm=10))
P("triceps_brachii", "insertion_lateral_expansion_anconeus_fascia", "insertion_point", "Insertion expansion: lateral triceps expansion into the anconeus fascia",
  "Distinct lateral tendon expansion continuous with the anconeus fascia in all specimens (mean width 16.8 mm).", ["keener2010"], ev="cadaver dissection n=36", var="36/36", related=["anconeus"])
P("triceps_brachii", "insertion_medial_tendon", "insertion_point", "Insertion: medial triceps tendon", "Rolled medial edge, confluent with the central tendon at its insertion.", ["keener2010"], ev="cadaver dissection n=36")

# =================================================================== PECTORALIS MAJOR
P("pectoralis_major", "clavicular_head", "head_belly", "Clavicular head", "Architecturally uniform head; mean pennation 29.4 deg; fibre bundle length increases superior to inferior.", ["fung2009"], ev="dissection + 3-D model n=11",
  setid="pectoralis_major.heads", z=["zan_clavicular_head_of_pectoralis_major_muscle_{s}"], geom=dict(rule="z_part_mesh"))
P("pectoralis_major", "sternocostal_head", "head_belly", "Sternal (sternocostal) head", "Segmented head with 6-7 segments; most inferior segment folds anteriorly to cradle the segment above; mean pennation 20.6 deg.", ["fung2009"],
  ev="dissection + 3-D model n=11", setid="pectoralis_major.heads", z=["zan_sternocostal_head_of_pectoralis_major_muscle_{s}"], geom=dict(rule="z_part_mesh"))
P("pectoralis_major", "abdominal_part", "head_belly", "Abdominal part", "Lowest fibres from the rectus sheath/external oblique aponeurosis (textbook; described as an extra part in some atlases).", ["gray42"], ver="unverified",
  ev="textbook", z=["zan_abdominal_part_of_pectoralis_major_muscle_{s}"], geom=dict(rule="z_part_mesh"))
S("pectoralis_major.heads", "pectoralis_major", "head_belly", "Pectoralis major: heads / segments", [
    (2, "fung2009", "clavicular + sternal head; the sternal head itself has 6-7 segments"), (3, "gray42", "clavicular, sternocostal, abdominal (textbook; unverified)")])
P("pectoralis_major", "insertion_humerus_complex", "insertion_point", "Humeral insertion (anterior + posterior tendon layers together)",
  "Composite of the two continuous tendon layers on the humerus.", ["fung2009"], ev="dissection n=11", anchor=dict(bone="humerus", landmark="(site per source: lateral lip of the intertubercular sulcus; wording not in the abstract)"),
  geom=dict(rule="end_snap_bone", end="distal", bone="humerus", tol_mm=10), note="Composite row for geometry.")
P("pectoralis_major", "insertion_anterior_tendon_layer", "insertion_point", "Humeral tendon: anterior (longer) layer", "Tendon consists of a longer anterior and a shorter posterior layer continuous inferiorly.", ["fung2009"], ev="dissection n=11", anchor=dict(bone="humerus", landmark="lateral lip of intertubercular sulcus / crest of greater tubercle (textbook landmark, not from the cited paper)"))
P("pectoralis_major", "insertion_posterior_tendon_layer", "insertion_point", "Humeral tendon: posterior (shorter) layer", "See anterior layer.", ["fung2009"], ev="dissection n=11", anchor=dict(bone="humerus", landmark="lateral lip of intertubercular sulcus / crest of greater tubercle (textbook landmark, not from the cited paper)"))

# =================================================================== ROTATOR CUFF
P("supraspinatus", "insertion_greater_tuberosity_footprint", "insertion_point", "Humeral insertion: greater tuberosity (anterior-most area of the highest impression)",
  "Triangular footprint, mean 6.9 mm medial-lateral x 12.6 mm antero-posterior; much smaller than previously taught; the long tendinous portion lies in the anterior half of the muscle.", ["mochizuki2008"],
  ev="cadaver dissection n=113", anchor=dict(bone="humerus", landmark="greater tuberosity, highest impression"), geom=dict(rule="end_snap_bone", end="distal", bone="humerus", tol_mm=10))
P("supraspinatus", "insertion_lesser_tuberosity_slip", "insertion_point", "Humeral insertion: superior-most lesser tuberosity (slip)", "Present in 21 % of specimens.", ["mochizuki2008"], ev="cadaver dissection n=97", var="21 %",
  anchor=dict(bone="humerus", landmark="lesser tuberosity, superior-most area"))
P("supraspinatus", "mtj_anterior_tendinous_portion", "muscle_tendon_junction", "Intramuscular tendon: long tendinous portion in the anterior half of the muscle",
  "The anterior half of the muscle carries a long intramuscular tendinous portion that reaches the anterior-most footprint; the posterior half is more muscular.", ["mochizuki2008"], ev="cadaver dissection n=16 (muscle removed, tendon kept)")
P("infraspinatus", "insertion_greater_tuberosity_footprint", "insertion_point", "Humeral insertion: greater tuberosity (trapezoidal footprint)",
  "Trapezoidal footprint, mean 10.2 mm x 32.7 mm; occupies part of the area previously assigned to supraspinatus.", ["mochizuki2008"], ev="cadaver dissection n=113",
  anchor=dict(bone="humerus", landmark="greater tuberosity"), geom=dict(rule="end_snap_bone", end="distal", bone="humerus", tol_mm=10))
P("infraspinatus", "mtj_superior_tendinous_portion", "muscle_tendon_junction", "Intramuscular tendon: long tendinous portion in the superior half of the muscle",
  "Curves anteriorly to the anterolateral area of the highest impression on the greater tuberosity.", ["mochizuki2008"], ev="cadaver dissection n=16")
P("subscapularis", "insertion_lesser_tuberosity_footprint", "insertion_point", "Humeral insertion: lesser tuberosity (trapezoidal footprint)",
  "Mean footprint length 2.5 cm; superior width 1.8 cm held over the upper 60 %, narrowing to 0.3 cm inferiorly.", ["richards2007"], ev="cadaver dissection n=19", anchor=dict(bone="humerus", landmark="lesser tuberosity"),
  geom=dict(rule="end_snap_bone", end="distal", bone="humerus", tol_mm=10))
P("rotator_cuff_tendon_complex", "layers_five", "insertion_point", "Layered structure of the cuff tendons (supraspinatus/infraspinatus region)",
  "Microscopically five layers defined by the attachments and orientation of fibrous elements; the tendons interdigitate and form one continuous insertion on the humerus; biceps tendon ensheathed by subscapularis/supraspinatus fibres.", ["clark1992"],
  cls="tendon", ev="histology + dissection n=32 cuffs")
P("coracohumeral_ligament", "origin_coracoid_horizontal_limb", "ligament_component", "Coracoid origin (horizontal limb and base)", "Originates from the horizontal limb and base of the coracoid.", ["arai2014"], cls="ligament", ev="dissection + histology n=19")
P("coracohumeral_ligament", "subscapularis_envelope", "ligament_component", "Superficial layer enveloping subscapularis", "Envelops the cranial subscapularis; laterally protrudes between the long head of biceps and subscapularis and attaches to the tendinous floor.", ["arai2014"], cls="ligament", ev="dissection + histology n=19")

# =================================================================== GLENOHUMERAL LIGAMENTS
P("glenohumeral_ligament_complex", "superior_ghl", "ligament_component", "Superior glenohumeral ligament", "One of the three classic glenohumeral ligaments.", ["turkel1981"], cls="ligament", ev="dissection n=36", setid="glenohumeral_ligament_complex.components")
P("glenohumeral_ligament_complex", "middle_ghl", "ligament_component", "Middle glenohumeral ligament", "Provides stability at ~45 deg abduction together with subscapularis and anterosuperior IGHL.", ["turkel1981"], cls="ligament", ev="dissection n=36", setid="glenohumeral_ligament_complex.components")
P("glenohumeral_ligament_complex", "inferior_ghl_anterior_band", "ligament_component", "Inferior GHL complex: anterior band", "Thickened, well-organised collagen band.", ["obrien1990"], cls="ligament", ev="dissection + histology n=11", setid="glenohumeral_ligament_complex.components")
P("glenohumeral_ligament_complex", "inferior_ghl_posterior_band", "ligament_component", "Inferior GHL complex: posterior band", "Thickened band; present in all 11.", ["obrien1990"], cls="ligament", ev="dissection + histology n=11", setid="glenohumeral_ligament_complex.components")
P("glenohumeral_ligament_complex", "inferior_ghl_axillary_pouch", "ligament_component", "Inferior GHL complex: axillary pouch", "Interposed between the two bands; humeral attachment either collar-like (6/11) or V-shaped (5/11).", ["obrien1990"], cls="ligament", ev="dissection + histology n=11", var="collar 6/11, V 5/11", setid="glenohumeral_ligament_complex.components")
S("glenohumeral_ligament_complex.components", "glenohumeral_ligament_complex", "ligament_component", "Glenohumeral ligaments: components", [(3, "turkel1981", "superior, middle, inferior"), (5, "obrien1990", "SGHL, MGHL + IGHL as anterior band, posterior band, axillary pouch (5 distinguishable parts)")])

# =================================================================== CORACOCLAVICULAR
P("coracoclavicular_ligament", "conoid", "ligament_component", "Conoid ligament", "Primary restraint to anterior/superior rotation and displacement of the clavicle; clavicular conoid tuberosity centre at ratio 0.24 of clavicle length from the lateral edge (fresh) / medial edge of tuberosity at 0.31 (dry).",
  ["fukuda1986", "rios2007"], cls="ligament", ev="biomechanics n=12; osteology n=120 + fresh n=19", z=["zan_conoid_ligament_{s}"], geom=dict(rule="cc_ligament_ratio", component="conoid", ratio=0.24, ratio_sd_mm=4.6), setid="coracoclavicular_ligament.components")
P("coracoclavicular_ligament", "trapezoid", "ligament_component", "Trapezoid ligament", "Trapezoid tuberosity centre at ratio 0.17 of clavicle length from the lateral edge (dry and fresh); resists axial compression of the clavicle toward the acromion.",
  ["fukuda1986", "rios2007"], cls="ligament", ev="biomechanics n=12; osteology n=120 + fresh n=19", z=["zan_trapezoid_ligament_{s}"], geom=dict(rule="cc_ligament_ratio", component="trapezoid", ratio=0.17, ratio_sd_mm=3.7), setid="coracoclavicular_ligament.components")
S("coracoclavicular_ligament.components", "coracoclavicular_ligament", "ligament_component", "Coracoclavicular ligament: components", [(2, "fukuda1986", "conoid + trapezoid")])

# =================================================================== PERIPHERAL / SHOULDER-GIRDLE MUSCLE PARTS (textbook-level, flagged)
P("trapezius", "descending_part", "head_belly", "Descending (upper) part", "Upper fibres from the superior nuchal line / ligamentum nuchae to the lateral clavicle and acromion.", ["gray42"], ver="unverified", ev="textbook")
P("trapezius", "transverse_part", "head_belly", "Transverse (middle) part", "Middle fibres from C7-T3 spinous processes to acromion and spine of scapula.", ["gray42"], ver="unverified", ev="textbook")
P("trapezius", "ascending_part", "head_belly", "Ascending (lower) part", "Lower fibres from T4-T12 spinous processes to the root of the scapular spine (via aponeurotic tendon).", ["gray42"], ver="unverified", ev="textbook")
P("serratus_anterior", "superior_part", "head_belly", "Superior part (digitations 1-2)", "Textbook: three functional parts of serratus anterior.", ["gray42"], ver="unverified", ev="textbook")
P("serratus_anterior", "intermediate_part", "head_belly", "Intermediate part (digitations 2-3)", "See superior part.", ["gray42"], ver="unverified", ev="textbook")
P("serratus_anterior", "inferior_part", "head_belly", "Inferior part (digitations 4-9)", "See superior part.", ["gray42"], ver="unverified", ev="textbook")

# =================================================================== ELBOW LIGAMENTS
P("radial_collateral_ligament_complex_elbow", "superior_band", "ligament_component", "Lateral collateral complex: superior band", "Y-shaped LCL complex consists of superior, anterior and posterior bands.", ["seki2002"], cls="ligament", ev="dissection + kinematics n=5", setid="radial_collateral_ligament_complex_elbow.components")
P("radial_collateral_ligament_complex_elbow", "anterior_band", "ligament_component", "Lateral collateral complex: anterior band", "Transection produced significant varus and external-rotation laxity.", ["seki2002"], cls="ligament", ev="kinematics n=5", setid="radial_collateral_ligament_complex_elbow.components")
P("radial_collateral_ligament_complex_elbow", "posterior_band", "ligament_component", "Lateral collateral complex: posterior band", "Further transection causes gross instability with dislocation.", ["seki2002"], cls="ligament", ev="kinematics n=5", setid="radial_collateral_ligament_complex_elbow.components")
P("radial_collateral_ligament_complex_elbow", "conjoined_ulnar_insertion", "ligament_component", "Conjoined insertion of lateral collateral + annular ligament on the ulna", "Broad conjoined insertion, bilobed (type I, 22/40) or broad (type II, 18/40).", ["cohen1997"], cls="ligament", ev="dissection n=40", var="type I 22/40, type II 18/40")
S("radial_collateral_ligament_complex_elbow.components", "radial_collateral_ligament_complex_elbow", "ligament_component", "Elbow lateral collateral complex: bands", [(3, "seki2002", "superior, anterior, posterior bands (Y configuration)")])
P("ulnar_collateral_ligament_elbow", "anterior_bundle_anterior_band", "ligament_component", "MCL anterior bundle: anterior band", "Primary restraint to valgus and internal rotatory forces.", ["floris1998"], cls="ligament", ev="dissection + kinematics n=18", setid="ulnar_collateral_ligament_elbow.components")
P("ulnar_collateral_ligament_elbow", "anterior_bundle_posterior_band", "ligament_component", "MCL anterior bundle: posterior band", "Secondary restraint.", ["floris1998"], cls="ligament", ev="dissection + kinematics n=18", setid="ulnar_collateral_ligament_elbow.components")
P("ulnar_collateral_ligament_elbow", "posterior_bundle", "ligament_component", "MCL posterior bundle", "Tertiary restraint (internal rotatory laxity at high flexion).", ["floris1998"], cls="ligament", ev="dissection + kinematics n=18", setid="ulnar_collateral_ligament_elbow.components")
S("ulnar_collateral_ligament_elbow.components", "ulnar_collateral_ligament_elbow", "ligament_component", "Elbow medial collateral ligament: bundles/bands", [(3, "floris1998", "anterior bundle (anterior + posterior bands) and posterior bundle")])

# =================================================================== FOREARM
P("interosseous_membrane_forearm", "central_band", "ligament_component", "Central band", "Radial origin 53-64 % of radial length from the styloid tip; ulnar insertion 29-44 % of ulnar length from the ulnar head.", ["noda2009"], cls="fascia", ev="dissection n=30 forearms", setid="interosseous_membrane_forearm.components")
P("interosseous_membrane_forearm", "accessory_band", "ligament_component", "Accessory band", "Centre of radial origin 37 %, ulnar insertion 23 %.", ["noda2009"], cls="fascia", ev="dissection n=30", setid="interosseous_membrane_forearm.components")
P("interosseous_membrane_forearm", "distal_oblique_bundle", "ligament_component", "Distal oblique bundle", "Ulnar origin 15 %, radial insertion 10 %.", ["noda2009"], cls="fascia", ev="dissection n=30", setid="interosseous_membrane_forearm.components")
P("interosseous_membrane_forearm", "proximal_oblique_cord", "ligament_component", "Proximal oblique cord", "Ulnar origin 80 %, radial insertion 79 %.", ["noda2009"], cls="fascia", ev="dissection n=30", setid="interosseous_membrane_forearm.components")
P("interosseous_membrane_forearm", "dorsal_oblique_accessory_cord", "ligament_component", "Dorsal oblique accessory cord", "Ulnar origin 64 %, radial insertion 62 %.", ["noda2009"], cls="fascia", ev="dissection n=30", setid="interosseous_membrane_forearm.components")
S("interosseous_membrane_forearm.components", "interosseous_membrane_forearm", "ligament_component", "Forearm interosseous membrane: ligaments", [(5, "noda2009", "central band, accessory band, distal oblique bundle, proximal oblique cord, dorsal oblique accessory cord")])
P("pronator_teres", "humeral_head", "head_belly", "Humeral head", "Textbook: two heads (humeral + ulnar) with the median nerve passing between them.", ["gray42", "hartz1981"], ver="unverified", ev="textbook; Hartz 1981 is a clinical series on median nerve compression, not a head count")
P("pronator_teres", "ulnar_head", "head_belly", "Ulnar head", "See humeral head.", ["gray42"], ver="unverified", ev="textbook")
P("flexor_digitorum_superficialis", "humeroulnar_head", "head_belly", "Humero-ulnar head", "Z-Anatomy carries this head as a separate mesh (zan_humero_ulnar_head_of_flexor_digitorum_superficialis).", ["gray42"], ver="unverified", ev="textbook; Z-Anatomy part mesh",
  z=["zan_humero_ulnar_head_of_flexor_digitorum_superficialis_{s}"], geom=dict(rule="z_part_mesh"))
P("flexor_digitorum_superficialis", "radial_head", "head_belly", "Radial head", "Second head of FDS (textbook).", ["gray42"], ver="unverified", ev="textbook")

# =================================================================== WRIST
P("wrist_ligament_complex", "scapholunate_dorsal_region", "ligament_component", "Scapholunate interosseous ligament: dorsal region", "Thick; short transversely oriented collagen fibres.", ["berger1996"], cls="ligament", ev="dissection + histology 37 wrists", setid="wrist_ligament_complex.sl_regions")
P("wrist_ligament_complex", "scapholunate_proximal_region", "ligament_component", "Scapholunate interosseous ligament: proximal region", "Principally fibrocartilage with few longitudinal fibres; may extend distally like a meniscus.", ["berger1996"], cls="ligament", ev="dissection + histology 37 wrists", setid="wrist_ligament_complex.sl_regions")
P("wrist_ligament_complex", "scapholunate_palmar_region", "ligament_component", "Scapholunate interosseous ligament: palmar region", "Thin; obliquely oriented fascicles; separate from the long radiolunate ligament.", ["berger1996"], cls="ligament", ev="dissection + histology 37 wrists", setid="wrist_ligament_complex.sl_regions")
S("wrist_ligament_complex.sl_regions", "wrist_ligament_complex", "ligament_component", "Scapholunate ligament: regions", [(3, "berger1996", "dorsal, proximal, palmar")])
P("wrist_ligament_complex", "radioscaphocapitate", "ligament_component", "Palmar radiocarpal: radioscaphocapitate ligament", "From radial styloid to scaphoid waist and capitate.", ["berger1990"], cls="ligament", ev="dissection n=54 adult + 23 fetal", z=["zan_radioscaphocapitate_ligament_{s}"], geom=dict(rule="z_part_mesh"))
P("wrist_ligament_complex", "long_radiolunate", "ligament_component", "Palmar radiocarpal: long radiolunate ligament", "Separated from RSC by the interligamentous sulcus.", ["berger1990"], cls="ligament", ev="dissection n=54")
P("wrist_ligament_complex", "short_radiolunate", "ligament_component", "Palmar radiocarpal: short radiolunate ligament", "Flat sheet to the proximal palmar margin of the lunate.", ["berger1990"], cls="ligament", ev="dissection n=54")
P("wrist_ligament_complex", "dorsal_radiocarpal", "ligament_component", "Dorsal radiocarpal ligament", "From the dorsal margin of the distal radius to the dorsal tubercle of the triquetrum; distribution has four subtypes.", ["viegas1999", "mizuseki1989"], cls="ligament", ev="dissection", z=["zan_dorsal_radiocarpal_ligament_{s}"], geom=dict(rule="z_part_mesh"))
P("wrist_ligament_complex", "dorsal_intercarpal", "ligament_component", "Dorsal intercarpal ligament", "Triquetrum to lunate, scaphoid and trapezium; together with the DRC forms the lateral V.", ["viegas1999"], cls="ligament", ev="dissection + mechanics", z=["zan_dorsal_intercarpal_ligaments_{s}"], geom=dict(rule="z_part_mesh"))
P("wrist_ligament_complex", "tfcc_articular_disc", "ligament_component", "TFCC: articular disc", "Part of the TFCC (homogeneous structure).", ["palmer1981", "nakamura2000"], cls="ligament", ev="dissection n=61; serial histology", setid="wrist_ligament_complex.tfcc")
P("wrist_ligament_complex", "tfcc_radioulnar_ligaments", "ligament_component", "TFCC: dorsal and volar radioulnar ligaments", "Radioulnar ligament originates from fovea and basistyloid; bifurcates palmar/dorsal around the disc.", ["palmer1981", "nakamura2000"], cls="ligament", ev="dissection; histology", setid="wrist_ligament_complex.tfcc",
  z=["zan_palmar_radio_ulnar_ligament_{s}"], geom=dict(rule="z_part_mesh"))
P("wrist_ligament_complex", "tfcc_meniscus_homologue", "ligament_component", "TFCC: meniscus homologue", "Ulnar internal wall of the wrist joint.", ["palmer1981", "nakamura2000"], cls="ligament", ev="dissection; histology", setid="wrist_ligament_complex.tfcc")
P("wrist_ligament_complex", "tfcc_ulnar_collateral_ligament", "ligament_component", "TFCC: ulnar collateral ligament", "Component of the TFCC.", ["palmer1981"], cls="ligament", ev="dissection n=61", setid="wrist_ligament_complex.tfcc", z=["zan_ulnar_collateral_ligament_of_wrist_joint_{s}"], geom=dict(rule="z_part_mesh"))
P("wrist_ligament_complex", "tfcc_ecu_sheath", "ligament_component", "TFCC: sheath of extensor carpi ulnaris", "Component of the TFCC.", ["palmer1981"], cls="ligament", ev="dissection n=61", setid="wrist_ligament_complex.tfcc")
S("wrist_ligament_complex.tfcc", "wrist_ligament_complex", "ligament_component", "TFCC components", [(5, "palmer1981", "articular disc, dorsal + volar radioulnar ligaments, meniscus homologue, ulnar collateral ligament, ECU sheath (counted as 5 groups)")])
P("flexor_retinaculum", "proximal_segment", "ligament_component", "Flexor retinaculum: proximal segment", "Thin proximal segment = thickened deep investing fascia of the forearm.", ["cobb1993"], cls="fascia", ev="gross, histology, radiographic n=26", setid="flexor_retinaculum.segments")
P("flexor_retinaculum", "transverse_carpal_ligament", "ligament_component", "Flexor retinaculum: transverse carpal ligament (central segment)", "Mean proximal limit 11 mm distal to the capitate-lunate joint; carpal tunnel width at hook of hamate 20 mm.", ["cobb1993"], cls="fascia", ev="n=26", setid="flexor_retinaculum.segments", z=["zan_flexor_retinaculum_of_wrist_{s}"], geom=dict(rule="z_part_mesh"))
P("flexor_retinaculum", "distal_segment", "ligament_component", "Flexor retinaculum: distal segment", "Aponeurosis between the thenar and hypothenar muscles; its distal limit reaches ~10 mm distal to the 3rd CMC joint.", ["cobb1993"], cls="fascia", ev="n=26", setid="flexor_retinaculum.segments")
S("flexor_retinaculum.segments", "flexor_retinaculum", "ligament_component", "Flexor retinaculum: segments", [(3, "cobb1993", "proximal segment, transverse carpal ligament, distal segment")])
