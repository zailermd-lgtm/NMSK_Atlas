"""Builds data/anatomy/myofascial_lines_q342.json (schema nmsk.myofascial_lines.v1)."""
import json
from common import REPO, TODAY, resolve, empty, scan_banned

REFS = {
    'myers_at': dict(citation='Myers TW. Anatomy Trains: Myofascial Meridians for Manual Therapists and Movement Professionals. Elsevier (1st ed. 2001; 4th ed. 2020)',
                     doi=None, pmid=None, opened=False,
                     note='NOT opened in this session (copyrighted book; no accessible copy). The station lists below are the line routes as Myers publishes them, recorded from the standard description; every list carries verify_against_book=true until checked against the book.'),
    'wilke2016': dict(citation='Wilke J, Krause F, Vogt L, Banzer W. What Is Evidence-Based About Myofascial Chains: A Systematic Review. Arch Phys Med Rehabil 2016;97(3):454-461',
                      doi='10.1016/j.apmr.2015.07.023', pmid='26281953', opened='PubMed abstract (2026-11-15); full text and its transition table NOT opened (publisher and PDF hosts unreachable from this session)',
                      note='62 dissection studies; line-level verdicts from the abstract. Per-transition verdicts are in the full-text table and are not reproduced here.'),
    'krause2016': dict(citation='Krause F, Wilke J, Vogt L, Banzer W. Intermuscular force transmission along myofascial chains: a systematic review. J Anat 2016;228(6):910-918',
                       doi='10.1111/joa.12464', pmid='27001027', pmcid='PMC5341578', opened='PubMed abstract (2026-11-15); PMC full text returned empty',
                       note='Force transfer (not just continuity): SBL moderate evidence at all 3 transitions (6 studies); BFL 1 of 2 transitions (3 studies); FFL one study, slight non-significant transfer at one transition.'),
    'wilke2019': dict(citation='Wilke J, Krause F. Myofascial chains of the upper limb: A systematic review of anatomical studies. Clin Anat 2019;32(7):934-940',
                      doi='10.1002/ca.23424', pmid='31226229', opened='PubMed abstract (2026-11-15)',
                      note='13 dissection studies; three arm chains with "good evidence for direct serial tissue continuity" (composition quoted as facts in the arm-chain entries).'),
    'kalichman2025': dict(citation='Kalichman L. Myofascial continuity: Review of anatomical and functional evidence. J Bodyw Mov Ther 2025',
                          doi=None, pmid='41316622', opened='abstract via the Consensus search tool (2026-11-15)',
                          note='Narrative review: strong anatomical support for SBL, BFL, FFL; moderate for Spiral and Lateral lines; SFL lacks validation.'),
    'petrov2026': dict(citation='Petrov OV. Anatomical prerequisites for the existence of myofascial lines: a dissection study. Russian Osteopathic Journal 2026',
                       doi=None, pmid=None, opened='abstract via the Consensus search tool (2026-11-15)',
                       note='Single cachectic female cadaver: superficial lines reproducible only by adding adjacent fascial/ligamentous components; joints act as switching zones; deep front line could not be separated from visceral structures; concept "only partially confirmed".'),
    'moore2023': dict(citation='Moore JG et al. Anatomization of the upper spiral line: a cadaveric case study of myofascial continuity. Med Sci Sports Exerc 2023 (conference abstract)',
                      doi=None, pmid=None, opened='abstract via the Consensus search tool (2026-11-15)',
                      note='One embalmed male cadaver: splenius capitis, splenius cervicis, rhomboid major and minor, serratus anterior, external oblique, internal oblique and rectus abdominis linked by fascia as an upper spiral line.'),
    'myers2015': dict(citation='Myers T. Anatomy trains in motion. Chapter 6 in: Schleip R, Baker A (eds). Fascia in Sport and Movement. Handspring Publishing, Pencaitland, 1st ed. 2015. ISBN 978-1-909141-07-0',
                      doi=None, pmid=None, opened='owner-supplied e-book (2026-11-16); the e-book has no printed page numbers, pages are those of the PDF (chapter 6 = PDF pp. 91-111)',
                      note='A chapter by Myers, not the Anatomy Trains book. It gives the number of lines (12 meridians of at least three muscles each, PDF p. 93), one figure per line with a caption naming its course or end points (Figs 6.1-6.7, PDF pp. 94-100), and in the text a few named transitions (PDF pp. 101-102, 106, 108-109). It does not list the stations of any line; the figures are unlabelled drawings. Knowledge only: no text or figure reproduced.'),
    'richter2015': dict(citation='Richter P. Purposeful movements as a result of coordinated myofascial chain activity, represented by the models of Kurt Tittel and Leopold Busquet. Chapter 7 in: Schleip R, Baker A (eds). Fascia in Sport and Movement. Handspring Publishing, 1st ed. 2015. ISBN 978-1-909141-07-0',
                        doi=None, pmid=None, opened='owner-supplied e-book (2026-11-16); Table 7.1 on PDF pp. 127-128',
                        note='Compares Busquet\'s five myofascial chains with Tittel\'s muscle slings (Table 7.1). The three Tittel slings "in side bending and rotation" are named muscle sequences (used here as lines); the extension/flexion slings name only muscle groups, and the three "static" shoulder-girdle slings are listed differently in the table and in the text (PDF p. 128), so neither is used.'),
    'schultz1996': dict(citation='Schultz RL, Feitis R. The Endless Web: Fascial Anatomy and Physical Reality. North Atlantic Books, 1996',
                        doi=None, pmid=None, opened=False,
                        note='NOT opened. A web search (2026-11-15) showed only its table of contents: Part III "Body retinacula (bands/straps)" with chapters on a chest band and an inguinal band. No muscle lists were seen.'),
}

# side: S = side of the first station of the line ("start side"), O = opposite side, mid = midline, B = both sides (bilateral station)
def st(station, kind, bases, side='S', note=None):
    res = resolve(bases) if bases else None
    on_page = bool(res) and not empty(res)
    return dict(station=station, kind=kind, side=side, page_bases=bases, structures=res if on_page else None,
                on_page=on_page, note=note)


PH_FOOT = 're:^zan_(proximal|middle|distal)_phalanx_of_.*_of_foot_[lr]$'
PH_HAND_1 = 're:^zan_(proximal|distal)_phalanx_of_first_finger_of_hand_[lr]$'
PH_HAND_5 = 're:^zan_(proximal|middle|distal)_phalanx_of_fifth_finger_of_hand_[lr]$'
PH_HAND = 're:^zan_(proximal|middle|distal)_phalanx_of_.*_finger_of_hand_[lr]$'
RIBS = 're:^zan_(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)_rib_[lr]$'
ES = ['iliocostalis', 'zan_iliocostalis_colli_muscle', 'longissimus', 'zan_longissimus_colli_muscle', 'zan_longissimus_capitis_muscle', 'spinalis', 'zan_spinalis_colli_muscle']
TLF_POST = ['zan_posterior_layer_of_thoracolumbar_fascia']
TARSALS = ['calcaneus', 'talus', 'navicular', 'cuboid', 'cuneiform_medial', 'cuneiform_intermediate', 'cuneiform_lateral']

EVID = {  # Wilke 2016 abstract (opened) unless stated
    'SBL': dict(label='strong', wilke2016=dict(examined=True, transitions_verified=3, transitions_total=3, studies=14), krause2016='force transfer: moderate evidence at all 3 transitions (6 studies)'),
    'SFL': dict(label='none', wilke2016=dict(examined=True, transitions_verified=0, transitions_total=None, studies=7), krause2016=None),
    'LL': dict(label='moderate', wilke2016=dict(examined=True, transitions_verified=2, transitions_total=5, studies=10), krause2016=None),
    'SL': dict(label='moderate', wilke2016=dict(examined=True, transitions_verified=5, transitions_total=9, studies=21), krause2016=None,
               also='Moore 2023 (one cadaver) dissected the upper part (splenius -> rhomboids -> serratus anterior -> obliques -> rectus abdominis).'),
    'DFL': dict(label='not_examined', wilke2016=dict(examined=False), krause2016=None,
                also='Not among the six lines Wilke 2016 reviewed. Petrov 2026 (one cadaver): its muscles could not be separated from visceral structures.'),
    'BFL': dict(label='strong', wilke2016=dict(examined=True, transitions_verified=3, transitions_total=3, studies=8), krause2016='force transfer: 1 of 2 transitions (3 studies)'),
    'FFL': dict(label='strong', wilke2016=dict(examined=True, transitions_verified=2, transitions_total=2, studies=6), krause2016='one study: slight, non-significant transfer at one transition'),
    'IFL': dict(label='not_examined', wilke2016=dict(examined=False), krause2016=None),
    'ARM_MYERS': dict(label='not_examined', wilke2016=dict(examined=False), krause2016=None,
                      also='Myers\' four arm lines were not reviewed as defined; Wilke & Krause 2019 found three different arm chains (see the wilke2019_* entries) with good evidence of serial continuity.'),
    'TITTEL': dict(label='not_examined', wilke2016=dict(examined=False), krause2016=None,
                   also='Tittel\'s slings are a textbook model (Richter 2015, Table 7.1); no dissection review of them was opened.'),
    'ARM_W19': dict(label='strong', label_text_override='good evidence of direct serial continuity (wording of Wilke & Krause 2019; one review, 4-6 studies per chain)', wilke2016=dict(examined=False), krause2016=None,
                    wilke2019='identified from 13 dissection studies; "good evidence for direct serial tissue continuity"; mechanical relevance not established'),
}
LABELS = {'strong': 'strong evidence (dissection: all reviewed transitions verified)',
          'moderate': 'moderate evidence (dissection: some transitions verified)',
          'none': 'no evidence (no transition verified in dissection studies)',
          'not_examined': 'not examined by a systematic review (no evidence either way)'}


def line(lid, name, family, sub, src, stations, ev, *, abbr=None, crosses_midline=False, verify=True, note=None, book_check=None):
    e = dict(EVID[ev])
    e['label_text'] = e.pop('label_text_override', None) or LABELS[e['label']]
    e['refs'] = ['richter2015'] if ev == 'TITTEL' else ['wilke2016'] + (['krause2016'] if e.get('krause2016') else []) + (['wilke2019'] if ev.startswith('ARM') else []) + \
        (['moore2023'] if lid == 'spiral_line' else []) + (['petrov2026'] if lid in ('deep_front_line',) else []) + (['kalichman2025'] if lid in ('superficial_back_line', 'superficial_front_line', 'lateral_line', 'spiral_line', 'back_functional_line', 'front_functional_line') else [])
    return dict(id=lid, abbr=abbr, name=name, author_family=family, sub_choices=sub, composition_refs=src,
                verify_against_book=verify, book_check=book_check, crosses_midline=crosses_midline, stations=stations, evidence=e, note=note)


def bc(status, pages, confirmed, open_=None):
    """Q348 check of a Myers line against Myers' 2015 chapter (myers2015). status: 'partly_confirmed' (some transitions or the
    course named in the text/caption; station list still unchecked) | 'course_only' (caption names the course or end points only)."""
    return dict(ref='myers2015', status=status, pages=pages, confirmed=confirmed,
                still_open=open_ or 'The chapter does not list the stations; the full station list still needs Myers\' Anatomy Trains book.')


L = []
L.append(line('superficial_back_line', 'Superficial Back Line', 'myers', ['vertical'], ['myers_at'], [
    st('plantar surface of the toe phalanges', 'bone', [PH_FOOT]),
    st('plantar fascia and short toe flexors', 'fascia+muscle', ['plantar_aponeurosis', 'zan_plantar_aponeurosis', 'flexor_digitorum_brevis']),
    st('calcaneus', 'bone', ['calcaneus']),
    st('gastrocnemius / calcaneal (Achilles) tendon', 'muscle+tendon', ['gastrocnemius', 'zan_calcaneal_tendon']),
    st('femoral condyles', 'bone', ['femur']),
    st('hamstrings', 'muscle', ['biceps_femoris', 'semitendinosus', 'semimembranosus']),
    st('ischial tuberosity', 'bone', ['hip_bone']),
    st('sacrotuberous ligament', 'ligament', ['sacrotuberous_ligament']),
    st('sacrum', 'bone', ['sacrum'], side='mid'),
    st('sacrolumbar fascia / erector spinae', 'fascia+muscle', TLF_POST + ES),
    st('occipital ridge', 'bone', ['occipital'], side='mid'),
    st('galea aponeurotica / scalp fascia', 'fascia', ['zan_epicranial_aponeurosis', 'zan_occipitalis_muscle', 'frontalis'], side='B'),
    st('frontal bone, supraorbital ridge', 'bone', ['frontal'], side='mid'),
], 'SBL', abbr='SBL', book_check=bc('partly_confirmed', 'PDF pp. 93-94, 108', [
    'course: posterior aspect of the body from the toes to the face (Fig. 6.1 caption, PDF p. 94)',
    'transition hamstrings -> superficial part of the sacrotuberous ligament -> back myofascia of the thoracolumbar region (PDF p. 108)'])))
L.append(line('superficial_front_line', 'Superficial Front Line', 'myers', ['vertical'], ['myers_at'], [
    st('dorsal surface of the toe phalanges', 'bone', [PH_FOOT]),
    st('short and long toe extensors, tibialis anterior, anterior crural compartment', 'muscle+fascia',
       ['extensor_digitorum_brevis', 'extensor_hallucis_brevis', 'extensor_digitorum_longus', 'extensor_hallucis_longus', 'tibialis_anterior',
        'anterior_intermuscular_septum_leg', 'zan_anterior_intermuscular_septum_of_leg']),
    st('tibial tuberosity', 'bone', ['tibia']),
    st('subpatellar tendon (patellar ligament)', 'tendon', [], note='no patellar-ligament mesh on the Base pages'),
    st('patella', 'bone', ['patella']),
    st('rectus femoris / quadriceps', 'muscle', ['rectus_femoris', 'vastus_lateralis', 'vastus_medialis', 'vastus_intermedius']),
    st('anterior inferior iliac spine; pubic tubercle', 'bone', ['hip_bone']),
    st('rectus abdominis', 'muscle', ['rectus_abdominis']),
    st('fifth rib', 'bone', ['zan_fifth_rib']),
    st('sternalis / sternochondral fascia; manubrium', 'fascia+bone', ['sternum'], side='mid', note='fascia not on the page; sternum stands in'),
    st('sternocleidomastoid', 'muscle', ['sternocleidomastoid']),
    st('mastoid process', 'bone', ['temporal']),
    st('scalp fascia', 'fascia', ['zan_epicranial_aponeurosis'], side='B'),
], 'SFL', abbr='SFL', book_check=bc('course_only', 'PDF p. 95 (Fig. 6.2 caption)', ['course: anterior surface of the body; trunk flexion with leg extension'])))
L.append(line('lateral_line', 'Lateral Line', 'myers', ['vertical'], ['myers_at'], [
    st('first and fifth metatarsal bases', 'bone', ['zan_first_metatarsal_bone', 'zan_fifth_metatarsal_bone']),
    st('fibular (peroneal) muscles, lateral crural compartment', 'muscle+fascia', ['fibularis_longus', 'fibularis_brevis', 'posterior_intermuscular_septum_leg', 'zan_posterior_intermuscular_septum_of_leg']),
    st('fibular head', 'bone', ['fibula']),
    st('anterior ligament of the fibular head', 'ligament', ['zan_anterior_ligament_of_fibular_head']),
    st('lateral tibial condyle', 'bone', ['tibia']),
    st('iliotibial tract / abductor muscles (tensor fasciae latae, gluteus maximus; gluteus medius aponeurosis)', 'fascia+muscle', ['iliotibial_tract', 'zan_iliotibial_tract', 'tensor_fasciae_latae', 'gluteus_maximus', 'gluteus_medius'],
       note='Q348: gluteus medius added - Myers 2015 (PDF p. 106) runs the line from the central iliotibial tract through the aponeurosis of gluteus medius to the iliac crest.'),
    st('iliac crest, ASIS, PSIS', 'bone', ['hip_bone']),
    st('lateral abdominal obliques', 'muscle', ['external_oblique', 'internal_oblique']),
    st('ribs', 'bone', [RIBS]),
    st('external and internal intercostals', 'muscle', ['zan_external_intercostal_muscles', 'zan_internal_intercostal_muscles']),
    st('first and second ribs', 'bone', ['zan_first_rib', 'zan_second_rib']),
    st('splenius capitis / sternocleidomastoid', 'muscle', ['splenius_capitis', 'sternocleidomastoid']),
    st('occipital ridge / mastoid process', 'bone', ['occipital', 'temporal']),
], 'LL', abbr='LL', book_check=bc('partly_confirmed', 'PDF pp. 96, 106', [
    'course: outer arch of the foot to the ear (Fig. 6.3 caption, PDF p. 96)',
    'transition fibularis longus -> over the fibular head -> central part of the iliotibial tract -> gluteus medius aponeurosis -> iliac crest (PDF p. 106); the lateral collateral ligament lies deep to the line, not in it'])))
L.append(line('spiral_line', 'Spiral Line', 'myers', ['diagonal_spiral'], ['myers_at', 'moore2023'], [
    st('lateral occipital ridge / mastoid process / atlas-axis transverse processes', 'bone', ['occipital', 'temporal', 'zan_atlas_c1', 'zan_axis_c2']),
    st('splenius capitis and cervicis', 'muscle', ['splenius_capitis', 'zan_splenius_colli_muscle']),
    st('lower cervical and upper thoracic spinous processes', 'bone', ['zan_vertebra_c7', 'zan_vertebra_t1', 'zan_vertebra_t2', 'zan_vertebra_t3', 'zan_vertebra_t4', 'zan_vertebra_t5'], side='mid'),
    st('rhomboids major and minor', 'muscle', ['rhomboid_major', 'rhomboid_minor'], side='O'),
    st('medial border of the scapula', 'bone', ['scapula'], side='O'),
    st('serratus anterior', 'muscle', ['serratus_anterior'], side='O'),
    st('lateral ribs', 'bone', [RIBS], side='O'),
    st('external oblique', 'muscle', ['external_oblique'], side='O'),
    st('abdominal aponeurosis, linea alba', 'fascia', ['linea_alba'], side='mid'),
    st('internal oblique', 'muscle', ['internal_oblique'], side='S'),
    st('iliac crest / ASIS', 'bone', ['hip_bone']),
    st('tensor fasciae latae, iliotibial tract', 'muscle+fascia', ['tensor_fasciae_latae', 'iliotibial_tract', 'zan_iliotibial_tract']),
    st('lateral tibial condyle', 'bone', ['tibia']),
    st('tibialis anterior', 'muscle', ['tibialis_anterior']),
    st('first metatarsal base', 'bone', ['zan_first_metatarsal_bone']),
    st('fibularis (peroneus) longus', 'muscle', ['fibularis_longus']),
    st('fibular head', 'bone', ['fibula']),
    st('biceps femoris', 'muscle', ['biceps_femoris']),
    st('ischial tuberosity', 'bone', ['hip_bone']),
    st('sacrotuberous ligament', 'ligament', ['sacrotuberous_ligament']),
    st('sacrum', 'bone', ['sacrum'], side='mid'),
    st('sacrolumbar fascia / erector spinae', 'fascia+muscle', TLF_POST + ES),
    st('occipital ridge', 'bone', ['occipital'], side='mid'),
], 'SL', abbr='SL', crosses_midline=True, book_check=bc('partly_confirmed', 'PDF pp. 97, 101-102, 106', [
    'transition tibialis anterior -> anterior part of the iliotibial tract -> tensor fasciae latae -> ASIS (PDF p. 106)',
    'trunk loop: ASIS -> internal oblique of that side -> external oblique and serratus anterior of the other side -> scapula of the other side -> head on the side of the ASIS (PDF pp. 101-102); this matches the S / O sides used here',
    'the line winds through the three cardinal lines (Fig. 6.4 caption, PDF p. 97)'],
    'The lower posterior half (fibularis longus -> biceps femoris -> sacrotuberous ligament -> erector spinae) is not described in the chapter.'),
    note='Side: S = side of the splenius the line starts from; the rhomboids-serratus-external oblique loop is on the opposite side and the line returns to the start side through the internal oblique. Side assignment is part of the book description (verify_against_book).'))
L.append(line('deep_front_line', 'Deep Front Line', 'myers', ['vertical'], ['myers_at'], [
    st('plantar tarsal bones, plantar surface of the toes', 'bone', TARSALS + [PH_FOOT]),
    st('tibialis posterior, long toe flexors', 'muscle', ['zan_tibialis_posterior_muscle', 'flexor_digitorum_longus', 'flexor_hallucis_longus']),
    st('upper posterior tibia / fibula; fascia of popliteus, knee capsule', 'bone+muscle', ['tibia', 'fibula', 'popliteus']),
    st('medial femoral epicondyle', 'bone', ['femur']),
    st('medial knee: tibial (medial) collateral ligament region', 'ligament', ['tibial_collateral_ligament'],
       note='Q348: Myers 2015 (PDF p. 109) places the Deep Front Line tissues on the inside of the knee, from the pes anserinus to the medial collateral ligament. Not a station in the earlier recorded route; the pes anserinus tendons are not added (the chapter does not assign them to a line).'),
    st('posterior intermuscular septum; adductor magnus and minimus', 'fascia+muscle', ['adductor_magnus', 'zan_adductor_minimus']),
    st('ischial ramus', 'bone', ['hip_bone']),
    st('pelvic floor fascia, levator ani, obturator internus fascia', 'fascia+muscle', ['levator_ani', 'zan_pubococcygeus_muscle', 'zan_iliococcygeus_muscle', 'zan_pubo_analis_muscle', 'obturator_internus']),
    st('coccyx', 'bone', ['coccyx'], side='mid'),
    st('anterior sacral fascia, anterior longitudinal ligament', 'ligament', ['anterior_longitudinal_ligament'], side='mid'),
    st('lumbar vertebral bodies', 'bone', ['zan_vertebra_l1', 'zan_vertebra_l2', 'zan_vertebra_l3', 'zan_vertebra_l4', 'zan_vertebra_l5'], side='mid'),
    st('(anterior track) linea aspera; anterior intermuscular septum, adductor brevis and longus; lesser trochanter', 'muscle+bone', ['adductor_brevis', 'adductor_longus', 'femur']),
    st('psoas, iliacus, pectineus', 'muscle', ['zan_psoas_major', 'zan_iliacus_muscle', 'pectineus']),
    st('posterior diaphragm, crura, central tendon', 'muscle', ['diaphragm'], side='mid'),
    st('pericardium, mediastinum, parietal pleura', 'fascia', ['zan_pleura'], note='only the pleura is on the page'),
    st('prevertebral fascia, pharyngeal raphe, scalenes, longus colli and capitis', 'fascia+muscle', ['scalenus_anterior', 'scalenus_medius', 'scalenus_posterior', 'longus_colli', 'longus_capitis']),
    st('basilar part of the occiput', 'bone', ['occipital'], side='mid'),
    st('(anterior upper track) anterior diaphragm, endothoracic fascia, transversus thoracis', 'muscle', ['diaphragm', 'transversus_thoracis']),
    st('infrahyoid muscles, pretracheal fascia', 'muscle', ['sternohyoid', 'sternothyroid', 'omohyoid', 'thyrohyoid']),
    st('hyoid', 'bone', ['hyoid'], side='mid'),
    st('suprahyoid muscles', 'muscle', ['digastric', 'mylohyoid', 'geniohyoid', 'stylohyoid']),
    st('mandible', 'bone', ['mandible'], side='mid'),
], 'DFL', abbr='DFL', book_check=bc('partly_confirmed', 'PDF pp. 100, 109', [
    'course: inner arch of the foot to the underside of the skull; includes the core (Fig. 6.7 caption, PDF p. 100)',
    'medial knee tissues from the pes anserinus to the medial collateral ligament belong to the line (PDF p. 109)']), note='A core line with branching tracks (posterior lower, anterior lower, posterior upper, anterior upper); stations are listed in one order for selection only.'))

ARM = []
ARM.append(line('superficial_front_arm_line', 'Superficial Front Arm Line', 'myers', ['arm'], ['myers_at'], [
    st('medial clavicle, costal cartilages, thoracolumbar fascia, iliac crest', 'bone+fascia', ['clavicle', 'costal_cartilage', 'hip_bone'] + TLF_POST),
    st('pectoralis major, latissimus dorsi', 'muscle', ['zan_clavicular_head_of_pectoralis_major_muscle', 'zan_sternocostal_head_of_pectoralis_major_muscle', 'zan_abdominal_part_of_pectoralis_major_muscle', 'latissimus_dorsi']),
    st('medial humeral line; medial intermuscular septum', 'bone+fascia', ['humerus', 'medial_intermuscular_septum', 'zan_medial_intermuscular_septum_of_arm']),
    st('medial humeral epicondyle', 'bone', ['humerus']),
    st('flexor group', 'muscle', ['flexor_carpi_radialis', 'zan_palmaris_longus_muscle', 'flexor_carpi_ulnaris', 'flexor_digitorum_superficialis', 'zan_humero_ulnar_head_of_flexor_digitorum_superficialis', 'flexor_digitorum_profundus']),
    st('carpal tunnel', 'fascia', ['flexor_retinaculum', 'zan_flexor_retinaculum_of_wrist']),
    st('palmar surface of the fingers', 'bone', [PH_HAND]),
], 'ARM_MYERS', abbr='SFAL', book_check=bc('course_only', 'PDF p. 98 (Fig. 6.5 A-D)', ['four arm lines exist (unlabelled drawings; no stations named)'])))
ARM.append(line('deep_front_arm_line', 'Deep Front Arm Line', 'myers', ['arm'], ['myers_at'], [
    st('third to fifth ribs', 'bone', ['zan_third_rib', 'zan_fourth_rib', 'zan_fifth_rib']),
    st('pectoralis minor, clavipectoral fascia', 'muscle+fascia', ['pectoralis_minor', 'clavipectoral_fascia']),
    st('coracoid process', 'bone', ['scapula']),
    st('biceps brachii (and coracobrachialis)', 'muscle', ['biceps_brachii', 'coracobrachialis']),
    st('radial tuberosity; radial periosteum to the styloid process', 'bone', ['radius']),
    st('radial collateral ligaments, thenar muscles', 'muscle', ['abductor_pollicis_brevis', 'flexor_pollicis_brevis', 'opponens_pollicis']),
    st('scaphoid, trapezium', 'bone', ['zan_scaphoid_bone', 'zan_trapezium_bone']),
    st('outside of the thumb', 'bone', ['zan_first_metacarpal_bone', PH_HAND_1]),
], 'ARM_MYERS', abbr='DFAL', book_check=bc('course_only', 'PDF p. 98 (Fig. 6.5 A-D)', ['four arm lines exist (unlabelled drawings; no stations named)'])))
ARM.append(line('superficial_back_arm_line', 'Superficial Back Arm Line', 'myers', ['arm'], ['myers_at'], [
    st('occipital ridge, nuchal ligament, thoracic spinous processes', 'bone+ligament', ['occipital', 'nuchal_ligament'] + [f'zan_vertebra_t{i}' for i in range(1, 13)], side='mid'),
    st('trapezius', 'muscle', ['trapezius']),
    st('spine of scapula, acromion, lateral clavicle', 'bone', ['scapula', 'clavicle']),
    st('deltoid', 'muscle', ['zan_clavicular_part_of_deltoid_muscle', 'zan_acromial_part_of_deltoid_muscle', 'zan_scapular_spinal_part_of_deltoid_muscle']),
    st('deltoid tuberosity; lateral intermuscular septum', 'bone+fascia', ['humerus', 'lateral_intermuscular_septum', 'zan_lateral_intermuscular_septum_of_arm']),
    st('lateral epicondyle', 'bone', ['humerus']),
    st('extensor group', 'muscle', ['extensor_carpi_radialis_longus', 'extensor_carpi_radialis_brevis', 'extensor_digitorum', 'extensor_digiti_minimi', 'extensor_carpi_ulnaris']),
    st('dorsal surface of the fingers', 'bone', [PH_HAND]),
], 'ARM_MYERS', abbr='SBAL', book_check=bc('course_only', 'PDF p. 98 (Fig. 6.5 A-D)', ['four arm lines exist (unlabelled drawings; no stations named)'])))
ARM.append(line('deep_back_arm_line', 'Deep Back Arm Line', 'myers', ['arm'], ['myers_at'], [
    st('spinous processes of lower cervical / upper thoracic vertebrae; transverse processes C1-C4', 'bone', ['zan_vertebra_c7', 'zan_vertebra_t1', 'zan_vertebra_t2', 'zan_vertebra_t3', 'zan_vertebra_t4', 'zan_atlas_c1', 'zan_axis_c2', 'zan_vertebra_c3', 'zan_vertebra_c4'], side='mid'),
    st('rhomboids, levator scapulae', 'muscle', ['rhomboid_major', 'rhomboid_minor', 'levator_scapulae']),
    st('medial border of the scapula', 'bone', ['scapula']),
    st('rotator cuff muscles', 'muscle', ['supraspinatus', 'infraspinatus', 'teres_minor', 'subscapularis']),
    st('head of the humerus', 'bone', ['humerus']),
    st('triceps brachii', 'muscle', ['zan_long_head_of_triceps_brachii', 'zan_lateral_head_of_triceps_brachii', 'zan_medial_head_of_triceps_brachii']),
    st('olecranon; fascia along the ulnar periosteum; ulnar styloid', 'bone', ['ulna']),
    st('ulnar collateral ligaments; triquetrum, hamate', 'bone', ['zan_triquetrum_bone', 'zan_hamate_bone']),
    st('hypothenar muscles', 'muscle', ['abductor_digiti_minimi_hand', 'flexor_digiti_minimi_brevis_hand', 'opponens_digiti_minimi']),
    st('outside of the little finger', 'bone', ['zan_fifth_metacarpal_bone', PH_HAND_5]),
], 'ARM_MYERS', abbr='DBAL', book_check=bc('course_only', 'PDF p. 98 (Fig. 6.5 A-D)', ['four arm lines exist (unlabelled drawings; no stations named)'])))
# Wilke & Krause 2019 arm chains: composition from the opened abstract
ARM.append(line('wilke2019_ventral_arm_chain', 'Ventral arm chain (Wilke & Krause 2019)', 'wilke2019', ['arm'], ['wilke2019'], [
    st('pectoralis major', 'muscle', ['zan_clavicular_head_of_pectoralis_major_muscle', 'zan_sternocostal_head_of_pectoralis_major_muscle', 'zan_abdominal_part_of_pectoralis_major_muscle']),
    st('brachial fascia / biceps brachii', 'fascia+muscle', ['brachial_fascia', 'biceps_brachii']),
    st('flexor carpi ulnaris / brachioradialis / supinator', 'muscle', ['flexor_carpi_ulnaris', 'brachioradialis', 'supinator']),
], 'ARM_W19', verify=False, note='5 studies.'))
ARM.append(line('wilke2019_lateral_arm_chain', 'Lateral arm chain (Wilke & Krause 2019)', 'wilke2019', ['arm'], ['wilke2019'], [
    st('trapezius', 'muscle', ['trapezius']),
    st('deltoid', 'muscle', ['zan_clavicular_part_of_deltoid_muscle', 'zan_acromial_part_of_deltoid_muscle', 'zan_scapular_spinal_part_of_deltoid_muscle']),
    st('lateral intermuscular septum / brachialis', 'fascia+muscle', ['lateral_intermuscular_septum', 'zan_lateral_intermuscular_septum_of_arm', 'brachialis']),
    st('brachioradialis', 'muscle', ['brachioradialis']),
], 'ARM_W19', verify=False, note='4 studies.'))
ARM.append(line('wilke2019_dorsal_arm_chain', 'Dorsal arm chain (Wilke & Krause 2019)', 'wilke2019', ['arm'], ['wilke2019'], [
    st('latissimus dorsi / teres minor / infraspinatus', 'muscle', ['latissimus_dorsi', 'teres_minor', 'infraspinatus']),
    st('triceps brachii', 'muscle', ['zan_long_head_of_triceps_brachii', 'zan_lateral_head_of_triceps_brachii', 'zan_medial_head_of_triceps_brachii']),
    st('anconeus', 'muscle', ['anconeus']),
    st('extensor carpi ulnaris', 'muscle', ['extensor_carpi_ulnaris']),
], 'ARM_W19', verify=False, note='6 studies.'))
L += ARM

L.append(line('back_functional_line', 'Back Functional Line', 'myers', ['diagonal_spiral', 'functional'], ['myers_at'], [
    st('shaft of the humerus', 'bone', ['humerus']),
    st('latissimus dorsi', 'muscle', ['latissimus_dorsi']),
    st('thoracolumbar fascia, sacral fascia', 'fascia', TLF_POST, side='mid'),
    st('sacrum', 'bone', ['sacrum'], side='mid'),
    st('gluteus maximus', 'muscle', ['gluteus_maximus'], side='O'),
    st('shaft of the femur (gluteal tuberosity)', 'bone', ['femur'], side='O'),
    st('vastus lateralis', 'muscle', ['vastus_lateralis'], side='O'),
    st('patella; subpatellar tendon; tibial tuberosity', 'bone', ['patella', 'tibia'], side='O'),
], 'BFL', abbr='BFL', crosses_midline=True, book_check=bc('course_only', 'PDF p. 99 (Fig. 6.6 caption)', ['three functional lines exist and link the shoulder to the contralateral leg (two) and to the ipsilateral leg (one)'])))
L.append(line('front_functional_line', 'Front Functional Line', 'myers', ['diagonal_spiral', 'functional'], ['myers_at'], [
    st('shaft of the humerus', 'bone', ['humerus']),
    st('pectoralis major (lower edge)', 'muscle', ['zan_sternocostal_head_of_pectoralis_major_muscle', 'zan_abdominal_part_of_pectoralis_major_muscle']),
    st('cartilages of ribs 5 and 6', 'cartilage', ['costal_cartilage']),
    st('lateral sheath of rectus abdominis', 'muscle', ['rectus_abdominis']),
    st('pubic tubercle and symphysis', 'bone', ['hip_bone', 'pubic_symphysis_disc'], side='mid'),
    st('adductor longus', 'muscle', ['adductor_longus'], side='O'),
    st('linea aspera of the femur', 'bone', ['femur'], side='O'),
], 'FFL', abbr='FFL', crosses_midline=True, book_check=bc('course_only', 'PDF p. 99 (Fig. 6.6 caption)', ['three functional lines exist and link the shoulder to the contralateral leg (two) and to the ipsilateral leg (one)'])))
L.append(line('ipsilateral_functional_line', 'Ipsilateral Functional Line', 'myers', ['functional'], ['myers_at'], [
    st('shaft of the humerus', 'bone', ['humerus']),
    st('latissimus dorsi (outer edge)', 'muscle', ['latissimus_dorsi']),
    st('lower ribs (10-12)', 'bone', ['zan_tenth_rib', 'zan_eleventh_rib', 'zan_twelfth_rib']),
    st('external oblique (posterior fibres)', 'muscle', ['external_oblique']),
    st('anterior superior iliac spine', 'bone', ['hip_bone']),
    st('sartorius', 'muscle', ['sartorius']),
    st('medial tibial condyle (pes anserinus)', 'bone', ['tibia']),
], 'IFL', abbr='IFL', book_check=bc('course_only', 'PDF p. 99 (Fig. 6.6 caption)', ['three functional lines exist and link the shoulder to the contralateral leg (two) and to the ipsilateral leg (one)']),
    note='The line exists (Myers 2015 names three functional lines, one ipsilateral, PDF p. 99); its stations were recorded from recall with lower confidence than the other routes and are not described in the chapter - check every station.'))

# Q348: Tittel's three muscle slings "in side bending and rotation" (Richter 2015, Table 7.1, PDF p. 127). The table names the
# muscles in order and says each sling ends in the OPPOSITE leg; the side of a trunk muscle at the crossing is not stated (side B).
TIT_NOTE = 'Side: S = side of the shoulder blade / arm; the leg muscles are on the opposite side (stated in the source); where the line crosses the midline is not stated, so the trunk muscle is marked on both sides (B).'
L.append(line('tittel_sling_scapula_opposite_leg', 'Tittel sling: shoulder blade to opposite leg', 'tittel', ['diagonal_spiral'], ['richter2015'], [
    st('rhomboids', 'muscle', ['rhomboid_major', 'rhomboid_minor']),
    st('serratus anterior', 'muscle', ['serratus_anterior']),
    st('external oblique', 'muscle', ['external_oblique'], side='B'),
    st('adductors of the other side', 'muscle', ['adductor_longus', 'adductor_brevis', 'adductor_magnus', 'zan_adductor_minimus'], side='O'),
    st('biceps femoris (short head)', 'muscle', ['biceps_femoris'], side='O', note='the short head is not a separate mesh; the whole biceps femoris is marked'),
    st('fibular (peroneal) muscles', 'muscle', ['fibularis_longus', 'fibularis_brevis'], side='O'),
], 'TITTEL', abbr='T-a', crosses_midline=True, verify=False, note=TIT_NOTE))
L.append(line('tittel_sling_arm_opposite_leg_anterior', 'Tittel sling: arm to opposite leg (front)', 'tittel', ['diagonal_spiral'], ['richter2015'], [
    st('pectoralis major', 'muscle', ['zan_clavicular_head_of_pectoralis_major_muscle', 'zan_sternocostal_head_of_pectoralis_major_muscle', 'zan_abdominal_part_of_pectoralis_major_muscle']),
    st('internal oblique', 'muscle', ['internal_oblique'], side='B'),
    st('tensor fasciae latae', 'muscle', ['tensor_fasciae_latae'], side='O'),
    st('tibialis anterior', 'muscle', ['tibialis_anterior'], side='O'),
], 'TITTEL', abbr='T-b', crosses_midline=True, verify=False, note=TIT_NOTE))
L.append(line('tittel_sling_arm_opposite_leg_posterior', 'Tittel sling: arm to opposite leg (back)', 'tittel', ['diagonal_spiral'], ['richter2015'], [
    st('latissimus dorsi', 'muscle', ['latissimus_dorsi']),
    st('gluteus maximus', 'muscle', ['gluteus_maximus'], side='O'),
    st('iliotibial tract', 'fascia', ['iliotibial_tract', 'zan_iliotibial_tract'], side='O'),
    st('tibialis anterior', 'muscle', ['tibialis_anterior'], side='O'),
], 'TITTEL', abbr='T-c', crosses_midline=True, verify=False,
    note='Side: S = side of the latissimus dorsi; the leg structures are on the opposite side (stated in the source). The gluteus maximus is taken as part of the opposite leg.'))

SUB = {
    'vertical': dict(label='Vertical (longitudinal) lines', members=[l['id'] for l in L if 'vertical' in l['sub_choices']],
                     source='Myers\' cardinal lines (SBL, SFL, LL) and the DFL run along the body (Myers 2015 figure captions, PDF pp. 94-96, 100)'),
    'diagonal_spiral': dict(label='Diagonal / spiral lines', members=[l['id'] for l in L if 'diagonal_spiral' in l['sub_choices']],
                            source='Spiral Line and the two contralateral Functional Lines cross the midline; Tittel\'s three slings in side bending and rotation (Richter 2015, Table 7.1) link a shoulder blade or arm to the opposite leg'),
    'functional': dict(label='Functional lines', members=[l['id'] for l in L if 'functional' in l['sub_choices']], source='Myers'),
    'arm': dict(label='Arm lines', members=[l['id'] for l in L if 'arm' in l['sub_choices']],
                source='Myers (four lines, not examined by a review) + Wilke & Krause 2019 (three chains, reviewed)'),
    'horizontal': dict(label='Horizontal bands', members=[], status='not_offered',
                       why=('No "horizontal line" exists among Myers\' lines or in the reviews opened. Q348: Fascia in Sport and Movement (2015) does '
                            'not add one either - Myers\' chapter lists 12 longitudinal/spiral/functional/arm lines (PDF p. 93), Richter\'s chapter has no '
                            'horizontal sling (Table 7.1), and the limb retinacula are mentioned only as obliquely running fascial bands rich in sensory '
                            'endings (PDF p. 75), not as a set of bands. The only sourced horizontal concept remains Schultz & Feitis 1996 "body retinacula '
                            '(bands/straps)", seen only as a table of contents without members. Offer this sub-choice only after a source with members is opened.'),
                       refs=['schultz1996', 'myers2015', 'richter2015']),
}

refs_used = set(r for l in L for r in l['composition_refs'] + l['evidence']['refs']) | {'schultz1996', 'myers2015', 'richter2015'}
out = dict(
    schema='nmsk.myofascial_lines.v1', round='Q342', generated=TODAY,
    scope='Base · Male (base_m) and Base · Female (base_f)',
    doc=dict(
        what='Myofascial lines ("Anatomy Trains", Myers) as a group family, with the evidence each line has from dissection reviews.',
        contested=('Myofascial lines are a contested concept. Dissection reviews support continuity for some lines (SBL, BFL, FFL), part of others '
                   '(Spiral, Lateral), none for the Superficial Front Line; the Deep Front Line, the Ipsilateral Functional Line and Myers\' four arm lines '
                   'were not examined by a systematic review. Continuity is not proof of force transmission or of clinical effect. The UI must show the '
                   'evidence label next to every line.'),
        schema=('sub_choices{key: {label, members[] (line ids), ...}}; lines[]: {id, abbr, name, author_family (myers | wilke2019 | tittel), sub_choices[], '
                'composition_refs[], verify_against_book (true: station list recorded from the book\'s standard description without opening Myers\' book), '
                'book_check {ref, status partly_confirmed | course_only, pages, confirmed[], still_open} or null (Q348: what Myers\' 2015 chapter confirms), '
                'crosses_midline, stations[] {station, kind, side (S start side | O opposite | mid | B both), page_bases[], structures {base_m|base_f: '
                '{r,l,mid}} or null, on_page, note}, evidence {label strong|moderate|none|not_examined, label_text, wilke2016 {...}, krause2016, refs[]}, note}.'),
        ui=('Family "Myofascial lines" -> sub-choice (vertical / diagonal-spiral / functional / arm; horizontal is shown disabled with its "why") -> '
            'line list with evidence badges -> selecting a line marks every station\'s structures. Side: pick the clicked structure\'s side as S; '
            'stations with side O use the other side, mid/B use both lists; when the wanted side list is empty for a body (some midline or one-sided meshes carry an _l/_r suffix) fall back to mid, then to both sides. Bones and fasciae are stations, not the line itself: offer "muscles only" '
            '(kind contains "muscle") as the default view.')),
    sub_choices=SUB, lines=L, references={k: REFS[k] for k in sorted(refs_used)},
    counts=dict(lines=len(L), myers_lines=sum(1 for l in L if l['author_family'] == 'myers'), wilke2019_chains=sum(1 for l in L if l['author_family'] == 'wilke2019'),
                tittel_slings=sum(1 for l in L if l['author_family'] == 'tittel'),
                book_check={k: [l['id'] for l in L if (l.get('book_check') or {}).get('status') == k] for k in ('partly_confirmed', 'course_only')},
                stations=sum(len(l['stations']) for l in L), stations_on_page=sum(1 for l in L for s in l['stations'] if s['on_page']),
                stations_missing=[f"{l['id']}: {s['station']}" for l in L for s in l['stations'] if not s['on_page']],
                by_evidence={k: [l['id'] for l in L if l['evidence']['label'] == k] for k in LABELS}))
bad = scan_banned(out)
assert not bad, bad
json.dump(out, open(REPO / 'data/anatomy/myofascial_lines_q342.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out['counts'], indent=1))
