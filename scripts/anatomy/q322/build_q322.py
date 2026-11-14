#!/usr/bin/env python3
"""Q322 builder (scripts/anatomy/q322; private half in scripts/clinical/build_innervation_private_q322.py): writes data/anatomy/innervation_q322.json (public anatomy) and
clinical/data/innervation_injection_q322.json (private clinical layer). Facts hand-entered from the
sources reviewed in docs/Q322_innervation_sources.md; repo values read from data/muscles + data/nerves."""
import json, re, glob, datetime
from pathlib import Path

REPO = Path('/home/user/NMSK_Atlas')
PAGES = {'base_m': REPO/'build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html',
         'base_f': REPO/'build/q309/viewer_base_female/atlas_viewer_base_female.html'}
REC = re.compile(r'\{"name":"([^"]*)","id":"([^"]+)","side":"(\w*)","sys":"([a-z_]+)"')
page_ids = {}
for k, p in PAGES.items():
    t = p.read_text(encoding='utf-8')
    page_ids[k] = {m[1]: m[3] for m in REC.findall(t)}

# ---------------------------------------------------------------- repo muscle records (nerve, roots)
repo = {}
for f in glob.glob(str(REPO/'data/muscles/*/*_l.json')):
    d = json.load(open(f)); repo[d['id'][:-2]] = d
nreg = {}
for f in glob.glob(str(REPO/'data/nerves/*.json')):
    d = json.load(open(f))
    if isinstance(d, list):
        for n in d: nreg[n['id']] = n

# ---------------------------------------------------------------- landmarks
L = {}
def lm(name, label, bone, kind, definition, **kw):
    L[name] = dict(label=label, bone=bone, kind=kind, definition=definition, **kw)
B, D, S, M = 'bony_point', 'derived', 'soft_tissue', 'muscle_derived'
lm('acromion_tip', 'Acromion, lateral tip', 'scapula', B, 'Most lateral point of the acromion.')
lm('acromion_posterior_angle', 'Acromion, posterior angle', 'scapula', B, 'Posterior (acromial) angle where the spine of the scapula turns into the acromion.')
lm('acromion_anteroinferior_point', 'Acromion, anteroinferior point', 'scapula', B, 'Anterior-inferior corner of the acromion.')
lm('coracoid_tip', 'Coracoid process, apex', 'scapula', B, 'Apex (tip) of the coracoid process.')
lm('scapula_inferior_angle', 'Scapula, inferior angle', 'scapula', B, 'Most caudal point of the scapula.')
lm('scapula_spine_medial_end', 'Scapular spine, medial end', 'scapula', B, 'Root of the spine of the scapula on the medial border.')
lm('subscap_line_lower', 'Midpoint inferior angle - acromion tip', 'scapula', D, 'Midpoint of scapula_inferior_angle and acromion_tip.', of=['scapula_inferior_angle', 'acromion_tip'])
lm('subscap_line_upper', 'Midpoint spine medial end - acromion tip', 'scapula', D, 'Midpoint of scapula_spine_medial_end and acromion_tip.', of=['scapula_spine_medial_end', 'acromion_tip'])
lm('posterior_axillary_fold', 'Posterior axillary fold', None, S, 'Skin fold over the lower border of latissimus dorsi / teres major at the axilla. Not a bony point: on a body without a usable skin surface, take the most lateral-inferior point of the teres major + latissimus dorsi pair at the level of the scapula inferior angle, and say so on the badge.')
lm('t12_spinous', 'T12 spinous process', 'vertebra_t12', B, 'Tip of the T12 spinous process.')
lm('l4_spinous', 'L4 spinous process', 'vertebra_l4', B, 'Tip of the L4 spinous process.')
lm('iliac_crest_top', 'Iliac crest, highest point', 'hip_bone', B, 'Most superior point of the iliac crest (the guide says only "iliac crest").')
lm('medial_epicondyle', 'Medial epicondyle of humerus', 'humerus', B, 'Most prominent point of the medial epicondyle.')
lm('lateral_epicondyle', 'Lateral epicondyle of humerus', 'humerus', B, 'Most prominent point of the lateral epicondyle.')
lm('interepicondylar_mid', 'Interepicondylar line (midpoint)', 'humerus', D, 'Midpoint of medial_epicondyle and lateral_epicondyle; the line through both is the guide\'s "interepicondylar line".', of=['medial_epicondyle', 'lateral_epicondyle'])
lm('olecranon', 'Olecranon (midpoint / tip)', 'ulna', B, 'Midpoint of the olecranon process.')
lm('radial_styloid', 'Radial styloid', 'radius', B, 'Tip of the radial styloid process.')
lm('ulnar_styloid', 'Ulnar styloid', 'ulna', B, 'Tip of the ulnar styloid process.')
lm('interstyloid_mid', 'Interstyloid line (midpoint)', 'radius+ulna', D, 'Midpoint of radial_styloid and ulnar_styloid; the line through both is the guide\'s "interstyloid line".', of=['radial_styloid', 'ulnar_styloid'])
lm('hook_of_hamate', 'Hook of hamate', 'hamate', B, 'Tip of the hamulus of the hamate.')
lm('mc1_head', '1st metacarpal head', 'metacarpal_1', B, 'Centre of the head of the first metacarpal.')
lm('mc2_head', '2nd metacarpal head', 'metacarpal_2', B, 'Centre of the head of the second metacarpal.')
lm('mc5_head', '5th metacarpal head', 'metacarpal_5', B, 'Centre of the head of the fifth metacarpal.')
lm('metacarpal_heads_mid', 'Metacarpal heads / MCP joints 2-5 (midpoint)', 'metacarpals', D, 'Midpoint of mc2_head and mc5_head (the guide names "MCP" for lumbricals and "MC heads" for interossei; both are this level).', of=['mc2_head', 'mc5_head'])
lm('mcp1_joint', '1st MCP joint', 'metacarpal_1', B, 'Centre of the first metacarpophalangeal joint.')
lm('t12_vertebral_body', 'T12 vertebral body', 'vertebra_t12', B, 'Centre of the T12 vertebral body (psoas line).')
lm('asis', 'Anterior superior iliac spine', 'hip_bone', B, 'Most prominent point of the ASIS.')
lm('pubic_tubercle', 'Pubic tubercle', 'hip_bone', B, 'Pubic tubercle.')
lm('inguinal_ligament_mid', 'Midpoint of the inguinal ligament', 'hip_bone', D, 'Midpoint of asis and pubic_tubercle (the ligament spans them).', of=['asis', 'pubic_tubercle'])
lm('ischial_tuberosity', 'Ischial tuberosity', 'hip_bone', B, 'Most prominent (superior-medial) point of the ischial tuberosity.')
lm('greater_trochanter', 'Greater trochanter', 'femur', B, 'Most lateral/superior point of the greater trochanter.')
lm('medial_femoral_epicondyle', 'Medial femoral epicondyle (MFE)', 'femur', B, 'Most prominent point of the medial epicondyle of the femur.')
lm('lateral_femoral_epicondyle', 'Lateral femoral epicondyle', 'femur', B, 'Most prominent point of the lateral epicondyle of the femur.')
lm('medial_femoral_condyle', 'Medial femoral condyle (MFC)', 'femur', B, 'Medial femoral condyle (named once in the guide text for adductor longus where its table says MFE).')
lm('femoral_intercondylar_mid', 'Femoral intercondylar line (midpoint)', 'femur', D, 'Midpoint of medial_femoral_epicondyle and lateral_femoral_epicondyle.', of=['medial_femoral_epicondyle', 'lateral_femoral_epicondyle'])
lm('tibial_condyles_mid', 'Tibial condyles line (midpoint)', 'tibia', D, 'Midpoint of the medial and lateral tibial condyles.', of=['medial_tibial_condyle', 'lateral_tibial_condyle'])
lm('medial_tibial_condyle', 'Medial tibial condyle', 'tibia', B, 'Most prominent point of the medial tibial condyle.')
lm('lateral_tibial_condyle', 'Lateral tibial condyle', 'tibia', B, 'Most prominent point of the lateral tibial condyle.')
lm('patella_base', 'Patella, base (superior pole)', 'patella', B, 'Superior border of the patella. The guide says only "patella"; this point is adopted (see conventions).')
lm('popliteal_fold', 'Popliteal fold', None, S, 'Skin crease behind the knee. Not a bony point: proxy = posterior point of the femoral_intercondylar_mid level (the knee joint line level), badged as a proxy.')
lm('fibular_head', 'Fibular head (most proximal point)', 'fibula', B, 'Most proximal point of the head of the fibula.')
lm('lateral_malleolus_tip', 'Lateral malleolus, inferior margin (tip)', 'fibula', B, 'Most distal point of the lateral malleolus.')
lm('medial_malleolus', 'Medial malleolus (most prominent point)', 'tibia', B, 'Most prominent point of the medial malleolus.')
lm('lateral_malleolus_prominence', 'Lateral malleolus (most prominent point)', 'fibula', B, 'Most prominent (lateral) point of the lateral malleolus.')
lm('intermalleolar_mid', 'Intermalleolar line (midpoint)', 'tibia+fibula', D, 'Midpoint of medial_malleolus and lateral_malleolus_prominence (the guide\'s IML).', of=['medial_malleolus', 'lateral_malleolus_prominence'])
lm('submalleolar_point', 'Submalleolar point', 'fibula', S, 'Named by the guide for EHL but not defined there. Proxy = lateral_malleolus_tip, badged as undefined in the source.')
lm('calcaneal_tuberosity_superior', 'Calcaneal tuberosity, superior margin', 'calcaneus', B, 'Superior margin of the calcaneal tuberosity (used by other sources only).')
lm('sole_posteroinferior_mid', 'Postero-inferior midpoint of the sole', 'calcaneus', B, 'Posterior-inferior midpoint of the calcaneal tuberosity on the plantar surface.')
lm('mtp1_joint', '1st MTP joint', 'metatarsal_1', B, 'Centre of the first metatarsophalangeal joint.')
lm('muscle_origin_end', 'Muscle origin end', None, M, 'Proximal (origin) end of the muscle\'s own mesh along its fascicle axis; used where the guide says "mid-portion of the fascicles / of the muscle".')
lm('muscle_insertion_end', 'Muscle insertion end', None, M, 'Distal (insertion) end of the muscle\'s own mesh along its fascicle axis.')

# ---------------------------------------------------------------- reference lines (0% = 'from', 100% = 'to')
LN = {}
def line(i, a, b, mode, label):
    LN[i] = {'from': a, 'to': b, 'mode': mode, 'label': label}
line('subscapular_guide', 'subscap_line_lower', 'subscap_line_upper', 'point', 'Mid(inferior angle-acromion tip) to mid(spine medial end-acromion tip)')
line('ld_t12', 'posterior_axillary_fold', 't12_spinous', 'point', 'Axillary fold - T12')
line('ld_l4', 'posterior_axillary_fold', 'l4_spinous', 'point', 'Axillary fold - L4')
line('ld_iliac', 'posterior_axillary_fold', 'iliac_crest_top', 'point', 'Axillary fold - iliac crest')
line('tm_guide', 'scapula_inferior_angle', 'posterior_axillary_fold', 'point', 'Inferior angle of scapula - posterior axillary fold')
line('fascicle', 'muscle_origin_end', 'muscle_insertion_end', 'level', 'Muscle\'s own fascicle, origin to insertion')
line('coracoid_me', 'coracoid_tip', 'medial_epicondyle', 'level', 'Coracoid process - medial epicondyle')
line('acromion_olecranon', 'acromion_tip', 'olecranon', 'level', 'Acromion tip - olecranon')
line('forearm', 'interepicondylar_mid', 'interstyloid_mid', 'level', 'Interepicondylar line - interstyloid line')
line('hamate_mc1', 'hook_of_hamate', 'mc1_head', 'level', 'Hook of hamate - 1st metacarpal head')
line('radstyloid_mcheads', 'radial_styloid', 'metacarpal_heads_mid', 'level', 'Radial styloid - metacarpal heads / MCP joints')
line('t12_inguinal', 't12_vertebral_body', 'inguinal_ligament_mid', 'level', 'T12 vertebra - midpoint of the inguinal ligament')
line('asis_mfe', 'asis', 'medial_femoral_epicondyle', 'level', 'ASIS - medial femoral epicondyle')
line('pubic_mfe', 'pubic_tubercle', 'medial_femoral_epicondyle', 'level', 'Pubic tubercle - medial femoral epicondyle')
line('it_mfe', 'ischial_tuberosity', 'medial_femoral_epicondyle', 'level', 'Ischial tuberosity - medial femoral epicondyle')
line('asis_patella', 'asis', 'patella_base', 'level', 'ASIS - patella')
line('popliteal_lm', 'popliteal_fold', 'lateral_malleolus_tip', 'level', 'Popliteal fold - inferior margin of lateral malleolus (guide text)')
line('popliteal_iml', 'popliteal_fold', 'intermalleolar_mid', 'level', 'Popliteal fold - intermalleolar line (guide table)')
line('fh_lm', 'fibular_head', 'lateral_malleolus_tip', 'level', 'Fibular head - lateral malleolus')
line('fh_mm', 'fibular_head', 'medial_malleolus', 'level', 'Fibular head - medial malleolus (guide text, FDL/FHL)')
line('fh_submalleolar', 'fibular_head', 'submalleolar_point', 'level', 'Fibular head - submalleolar point')
line('sole_mtp1', 'sole_posteroinferior_mid', 'mtp1_joint', 'level', 'Postero-inferior midpoint of the sole - 1st MTP joint')
# lines used only by other sources (comparison; never averaged with the guide's)
line('olecranon_acromion_ai', 'olecranon', 'acromion_anteroinferior_point', 'level', 'Olecranon midpoint - anteroinferior acromion')
line('acromion_post_olecranon', 'acromion_posterior_angle', 'olecranon', 'level', 'Posterior acromial angle - olecranon midpoint')
line('olecranon_acromion', 'olecranon', 'acromion_tip', 'level', 'Olecranon - acromion')
line('me_ulnar_styloid', 'medial_epicondyle', 'ulnar_styloid', 'level', 'Medial epicondyle - ulnar styloid')
line('tibcond_it', 'tibial_condyles_mid', 'ischial_tuberosity', 'level', 'Tibial condyles line - ischial tuberosity')
line('intercondylar_iml', 'femoral_intercondylar_mid', 'intermalleolar_mid', 'level', 'Femoral intercondylar line - intermalleolar line')
line('lm_fh', 'lateral_malleolus_tip', 'fibular_head', 'level', 'Lateral malleolus - fibular head')
line('fh_calcaneal', 'fibular_head', 'calcaneal_tuberosity_superior', 'level', 'Fibular head line - calcaneal tuberosity line')
line('gt_patella', 'greater_trochanter', 'patella_base', 'level', 'Greater trochanter - base of patella')

# ---------------------------------------------------------------- sources
SRC = {}
def src(i, **kw): SRC[i] = kw
src('guv2026', citation='Güvener O, İnce B, Keçeli C, Tok F, Ricci V, Mezian K, Jačisko J, Chang KV, Kara M, Kaymak B, Özçakar L. Dynamic limb sono-anatomy for botulinum toxin injections: EURO-MUSCULUS/USPRM Spasticity Guide. Eur J Phys Rehabil Med 2026;62(5):441-59.', doi='10.23736/S1973-9087.26.09497-9', pmid=None, licence='CC BY-NC-ND 4.0 (facts extracted; no text, figure or image reproduced)', method='expert consensus guide (narrative); IZ values cite its refs 6, 8, 9', n=None, population='n/a', landmark_match='primary (defines the adopted lines)', verdict='relevant', accessed='full text (owner-supplied PDF)', role='primary')
src('kara2018', citation='Kara M, Kaymak B, Ulaşli AM, et al. Sonographic guide for botulinum toxin injections of the upper limb: EUROMUSCULUS/USPRM spasticity approach. Eur J Phys Rehabil Med 2018;54(3):469-85.', doi='10.23736/S1973-9087.17.04664-0', pmid='28264546', method='narrative guide (predecessor; the guide cites it for every upper-limb IZ)', n=None, population='n/a', landmark_match='same lines (the guide reuses them)', verdict='partly', reason='Same author group and same numbers: not an independent check. Full text not reachable from this session (publisher host blocked); abstract only.', accessed='abstract (PubMed)')
src('kaymak2018ll', citation='Kaymak B, Kara M, Tok F, et al. Sonographic guide for botulinum toxin injections of the lower limb: EUROMUSCULUS/USPRM spasticity approach. Eur J Phys Rehabil Med 2018;54(3):486-98.', doi='10.23736/S1973-9087.17.04667-6', pmid='28382814', method='narrative guide (predecessor; cited for every lower-limb IZ)', n=None, population='n/a', landmark_match='same lines', verdict='partly', reason='Same group, same numbers; abstract only.', accessed='abstract (PubMed)')
src('kaymak2018iz', citation='Kaymak B, Kara M, Yağiz On A, Soylu AR, Özçakar L. Innervation zone targeted botulinum toxin injections. Eur J Phys Rehabil Med 2018;54(1):100-9.', doi='10.23736/S1973-9087.17.04663-9', pmid='28264545', method='narrative review of IZ localisation and toxin spread', n=None, population='n/a', landmark_match='n/a', verdict='partly', reason='Background for the IZ concept; no per-muscle values in the abstract.', accessed='abstract (PubMed)')
src('vancamp2011', citation='Van Campenhout A, Molenaers G. Localization of the motor endplate zone in human skeletal muscles of the lower limb: anatomical guidelines for injection with botulinum toxin. Dev Med Child Neurol 2011;53(2):108-19.', doi='10.1111/j.1469-8749.2010.03816.x', pmid='20964675', method='review of histological + dissection MEP studies, proposes external-landmark sites', n=None, population='adult + child data pooled from older studies', landmark_match='probably the origin of the lower-limb lines (gastrocnemius, soleus, TP, ST, SM, gracilis, BF, RF, adductors, psoas listed)', verdict='partly', reason='Highly relevant by design, but the full text (values) could not be opened (publisher host blocked); not used for numbers.', accessed='abstract (PubMed)')
src('vancamp2010', citation='Van Campenhout A, Hubens G, Fagard K, Molenaers G. Localization of motor nerve branches of the human psoas muscle. Muscle Nerve 2010;42(2):202-7.', doi='10.1002/mus.21660', pmid='20544927', method='cadaveric microdissection of nerve branches to terminal ramifications', n='24 psoas muscles', population='adult cadavers', landmark_match='near-same: T12 to where psoas passes under the inguinal ligament', verdict='relevant', accessed='abstract (PubMed)')
src('lee2009', citation='Lee JH, Kim HW, Im S, An X, Lee MS, Lee UY, Han SH. Localization of motor entry points and terminal intramuscular nerve endings of the musculocutaneous nerve to biceps and brachialis muscles. Surg Radiol Anat 2010;32(3):213-20.', doi='10.1007/s00276-009-0561-4', pmid='19779662', method='cadaveric dissection of terminal intramuscular nerve endings', n='56 arms', population='fresh adult cadavers (Korea)', landmark_match='same line: coracoid process (0%) - medial epicondyle', verdict='relevant', accessed='abstract (PubMed)')
src('park2007', citation='Park BK, Shin YB, Ko HY, Park JH, Baek SY. Anatomic motor point localization of the biceps brachii and brachialis muscles. J Korean Med Sci 2007;22(3):459-62.', doi='10.3346/jkms.2007.22.3.459', pmid='17596654', method='cadaveric dissection, motor points', n='23 limbs / 12 cadavers', population='adult cadavers (Korea)', landmark_match='line starts at the coracoid process; distal end not stated in the abstract', verdict='partly', reason='Distal landmark of the line not verifiable from what could be opened.', accessed='abstract (PubMed)')
src('amirali2007', citation='Amirali A, Mu L, Gracies JM, Simpson DM. Anatomical localization of motor endplate bands in the human biceps brachii. J Clin Neuromuscul Dis 2007;9(2):306-12.', doi='10.1097/CND.0b013e31815c13a7', pmid='18090684', method='Sihler stain (3) + whole-mount acetylcholinesterase (2)', n='5 muscles', population='autopsy', landmark_match='different line: olecranon - acromion', verdict='partly', reason='Different line and tiny sample; qualitatively consistent (distal half).', accessed='abstract (PubMed)')
src('zhang2017', citation='Zhang C, Peng Y, Liu Y, Li S, Zhou P, Rymer WZ, Zhang Y. Imaging three-dimensional innervation zone distribution in muscles from M-wave recordings. J Neural Eng 2017;14(3):036011.', doi='10.1088/1741-2552/aa65dd', pmid='28358718', method='high-density surface EMG, 3-D IZ source reconstruction', n='6 subjects', population='healthy adults', landmark_match='different: absolute distance from the medial-epicondyle plane', verdict='partly', reason='Absolute cm, not a % of a line.', accessed='abstract (PubMed)')
src('zhang2021', citation='Zhang C, Chen YT, Liu Y, et al. Improving botulinum toxin efficiency in treating post-stroke spasticity using 3D innervation zone imaging. Int J Neural Syst 2021;31(4):2150007.', doi='10.1142/S0129065721500076', pmid='33438529', method='randomised trial, IZ-guided vs standard injection (biceps)', n=None, population='stroke', landmark_match='n/a', verdict='not relevant', reason='Supports IZ targeting; gives no IZ position (the guide cites it, oddly, for pectoralis minor).', accessed='abstract (PubMed)')
src('lapatki2011', citation='Lapatki BG, van Dijk JP, van de Warrenburg BP, Zwarts MJ. Botulinum toxin has an increased effect when targeted toward the muscle\'s endplate zone: a high-density surface EMG guided study. Clin Neurophysiol 2011;122(8):1611-6.', doi='10.1016/j.clinph.2010.11.018', pmid='21195024', method='HD-sEMG, toxin efficacy vs distance from endplate zone', n='8 volunteers', population='healthy', landmark_match='n/a (extensor digitorum brevis)', verdict='not relevant', reason='Efficacy evidence only (1 cm away = 46% less effect); no limb-muscle positions.', accessed='abstract (PubMed)')
src('gracies2009', citation='Gracies JM, Lugassy M, Weisz DJ, et al. Botulinum toxin dilution and endplate targeting in spasticity: a double-blind controlled study. Arch Phys Med Rehabil 2009;90(1):9-16.e2.', doi=None, pmid='19154823', method='RCT', n=None, population='spasticity', landmark_match='n/a', verdict='not relevant', reason='Efficacy only; no positions.', accessed='citation only (PubMed match)')
src('tang2018', citation='Tang Y, Zhang X, Yang S. Localization of center of intramuscular nerve dense regions in adult anterior brachial muscles. Am J Transl Res 2018;10(4):1220-8.', doi=None, pmid='29736215', method='Sihler stain + barium marking + spiral CT', n='12 cadavers', population='adult cadavers (China)', landmark_match='body-surface H and L lines whose landmarks are not given in the abstract; PMC full text returned empty', verdict='partly', reason='Biceps 56.6/67.6% and brachialis 71.3/81.6% on its longitudinal line agree in shape, but the line could not be verified, so not compared numerically.', accessed='abstract (PubMed)')
src('koo2019', citation='Koo YJ, Park GY, Park SJ, Han SH, Sohn DG, Im S. Safe needle insertion locations for motor point injection of the triceps brachii muscle: a pilot cadaveric and sonography study. Ann Rehabil Med 2019;43(6):635-41.', doi='10.5535/arm.2019.43.6.635', pmid='31918526', method='cadaveric dissection of motor endplate zones', n='12 limbs / 6 cadavers', population='fresh adult cadavers (Korea)', landmark_match='near-same: posterior acromial angle - olecranon midpoint (guide: acromion tip - olecranon)', verdict='relevant', accessed='abstract (PubMed)')
src('yi2023tri', citation='Yi KH, Lee JH, Hur HW, Lee HJ, Choi YJ, Kim HJ. Distribution of the intramuscular innervation of the triceps brachii: clinical importance in the treatment of spasticity with botulinum neurotoxin. Clin Anat 2023;36(7):964-70.', doi='10.1002/ca.24004', pmid='36606364', method='modified Sihler stain', n='15 specimens', population='adult cadavers (Korea)', landmark_match='near-same, reversed: olecranon (0%) - anteroinferior acromion (100%)', verdict='relevant', accessed='abstract (PubMed)')
src('yi2023tm', citation='Yi KH, Lee KW, Hu HW, Lee JH, Lee HJ. A practical guide to botulinum neurotoxin treatment of teres major muscle in shoulder spasticity: intramuscular neural distribution of teres major muscle in cadaver model. PM R 2024;16(2):160-4.', doi='10.1002/pmrj.13048', pmid='37526565', method='Sihler stain', n='18 cadavers', population='adult cadavers', landmark_match='muscle-relative (middle 20% of the muscle)', verdict='relevant', accessed='abstract (PubMed)')
src('li2021', citation='Li Y, Wang M, Tang S, Zhu X, Yang S. Localization of nerve entry points and the center of intramuscular nerve-dense regions in the adult pectoralis major and pectoralis minor and its clinical significance. J Anat 2021;239(5):1123-33.', doi='10.1111/joa.13493', pmid='34176122', method='Sihler stain + barium + CT', n=None, population='formalin-fixed adult cadavers', landmark_match='different: acromion - jugular notch (H) and jugular notch - xiphisternal joint (L) surface lines', verdict='partly', reason='Two nerve-dense regions in pectoralis major and one in pectoralis minor (agrees with the guide\'s 2+1 count); positions on different lines.', accessed='abstract (PubMed)')
src('zhou2023', citation='Zhou J, Jia F, Chen P, Zhou G, Wang M, Wu J, Yang S. Localisation of the centre of the highest region of muscle spindle abundance of anterior forearm muscles. J Anat 2024;244(5):803-14.', doi='10.1111/joa.14000', pmid='38155435', method='modified Sihler + histology + CT', n='24 cadavers', population='adult cadavers (China)', landmark_match='different: medial epicondyle - ulnar styloid (L) and epicondylar (H) lines', verdict='partly', reason='Same forearm, different line (ulnar-side axis vs the guide\'s epicondylar-to-styloid levels); shown for comparison, never averaged.', accessed='abstract (PubMed)')
src('lepage2005', citation='Lepage D, Parratte B, Tatu L, Vuiller F, Monnier G. Extra- and intramuscular nerve supply of the muscles of the anterior antebrachial compartment: applications for selective neurotomy and for botulinum toxin injection. Surg Radiol Anat 2005;27(5):420-30.', doi='10.1007/s00276-005-0012-9', pmid='16308665', method='macro + microdissection', n='30 forearms', population='adult cadavers (France)', landmark_match='surface topographic landmarks (not given in abstract)', verdict='partly', reason='Relevant by design; no numbers reachable.', accessed='abstract (PubMed)')
src('garg2026', citation='Garg et al. Localization of the motor entry point of the adductor pollicis muscle using surface landmarks. Ann Anat 2026;267:152881.', doi='10.1016/j.aanat.2026.152881', pmid='42413630', method='cadaveric dissection', n='21 hands', population='formalin-fixed adult', landmark_match='different: mm from 1st MCP joint (13.7 +/- 6.6) and radial styloid (48.5 +/- 8.2)', verdict='partly', reason='Motor entry point, mm not %; consistent with a distal (near-MCP) target.', accessed='abstract (PubMed)')
src('xie2013', citation='Xie P, Jiang Y, Zhang X, Yang S. The study of intramuscular nerve distribution patterns and relative spindle abundance of the thenar and hypothenar muscles in human hand. PLoS One 2012;7(12):e51538.', doi=None, pmid='23251569', method='Sihler + histology', n=None, population='adult cadavers', landmark_match='different: origin-insertion thirds', verdict='partly', reason='Already in the repo (data/muscles); not comparable with hamate-MC1 line.', accessed='repo record')
src('kwon2009', citation='Kwon JY, Kim JS, Lee WI. Anatomic localization of motor points of hip adductors. Am J Phys Med Rehabil 2009;88(4):336-41.', doi='10.1097/PHM.0b013e3181619435', pmid='18174845', method='cadaveric dissection, motor points', n='19 limbs / 10 cadavers', population='adult cadavers (Korea)', landmark_match='same line: pubic tubercle - medial femoral epicondyle', verdict='relevant', accessed='abstract (PubMed)')
src('an2010', citation='An XC, Lee JH, Im S, Lee MS, Hwang K, Kim HW, Han SH. Anatomic localization of motor entry points and intramuscular nerve endings in the hamstring muscles. Surg Radiol Anat 2010;32(6):529-37.', doi='10.1007/s00276-009-0609-5', pmid='20063163', method='cadaveric dissection: motor entry points + proximal/distal limits of terminal nerve endings', n='50 lower limbs', population='adult cadavers (Korea)', landmark_match='same line (x): ischial tuberosity - medial femoral epicondyle', verdict='relevant', accessed='abstract (PubMed)')
src('rha2016', citation='Rha DW, Yi KH, Park ES, Park C, Kim HJ. Intramuscular nerve distribution of the hamstring muscles: application to treating spasticity. Clin Anat 2016;29(6):746-51.', doi='10.1002/ca.22735', pmid='27213466', method='Sihler stain', n=None, population='adult cadavers (Korea)', landmark_match='near-same, reversed: tibial condyles line (0%) - ischial tuberosity (100%)', verdict='relevant', accessed='abstract (PubMed)')
src('kurtys2023', citation='Kurtys K, et al. Localization of the gracilis muscle motor points - key considerations for botulinum neurotoxin injection and electrical stimulation. Ann Anat 2023;248:152072.', doi='10.1016/j.aanat.2023.152072', pmid='36863619', method='cadaveric dissection (multiple motor points, median 12)', n='93 muscles', population='formalin-fixed', landmark_match='reference line not defined in the abstract', verdict='partly', reason='Motor points 15-40% of its line; line unverified.', accessed='abstract (PubMed)')
src('wang2020', citation='Wang et al. Localization of the center of the intramuscular nerve dense region of the medial femoral muscles and the significance for blocking spasticity. Ann Anat 2020;231:151529.', doi='10.1016/j.aanat.2020.151529', pmid='32437866', method='Sihler + barium + CT', n='12 cadavers', population='adult (China)', landmark_match='different: greater trochanter - pubic tubercle (H) and a lateral femoral epicondyle line (L)', verdict='partly', reason='One nerve-dense region each for gracilis, AL, AB and two for adductor magnus (agrees with the guide\'s AM 2 bands); positions on different lines.', accessed='abstract (PubMed)')
src('yi2021sar', citation='Yi KH, Lee JH, Lee DK, Hu HW, Seo KK, Kim HJ. Anatomical locations of the motor endplates of sartorius muscle for botulinum toxin injections in treatment of muscle spasticity. Surg Radiol Anat 2021;43(12):2025-30.', doi='10.1007/s00276-021-02813-7', pmid='34378107', method='modified Sihler stain', n='15 specimens', population='adult cadavers', landmark_match='same line: ASIS (0%) - medial femoral epicondyle', verdict='relevant', accessed='abstract (PubMed)')
src('page2019', citation='Page BJ, Mrowczynski OD, Payne RA, et al. The relative location of the major femoral nerve motor branches in the thigh. Cureus 2019;11(1):e3882.', doi='10.7759/cureus.3882', pmid='30899633', method='dissection, motor branch entry ratios', n='16 specimens', population='embalmed', landmark_match='different: femoral nerve at inguinal ligament - (distal end per repo record: superior patellar margin)', verdict='partly', reason='Branch entry points, not IZ.', accessed='abstract (PubMed)')
src('yi2024vm', citation='Yi KH, Hu H, Hwang SO, Ahn H, Lee JH, Lee HJ. Intramuscular neural distribution of the vastus medialis for botulinum neurotoxin injection: application to spasticity. Surg Radiol Anat 2024;46(12):2067-73.', doi='10.1007/s00276-024-03482-y', pmid='39400571', method='modified Sihler stain', n='20 specimens', population='adult cadavers', landmark_match='same line: ASIS - base of patella (areas 1-10)', verdict='relevant', accessed='abstract (PubMed)')
src('yi2026vl', citation='Yi KH, Hu H, Hwang SO, Lee JH, Lee HJ. Intramuscular neural distribution of the vastus lateralis informs effective and safe botulinum neurotoxin injection. Sci Rep 2026;16(1):5353.', doi='10.1038/s41598-026-37960-7', pmid='41644588', method='modified Sihler stain', n='12 cadavers', population='fresh cadavers', landmark_match='different (repo record: greater trochanter - base of patella; not stated in the abstract)', verdict='partly', accessed='abstract (PubMed)')
src('kim2005', citation='Kim MW, Kim JH, Yang YJ, Ko YJ. Anatomic localization of motor points in gastrocnemius and soleus muscles. Am J Phys Med Rehabil 2005;84(9):680-3.', doi='10.1097/01.phm.0000176341.85398.a9', pmid='16141745', method='cadaveric dissection, terminal motor points', n='8 limbs / 4 cadavers', population='male adult cadavers', landmark_match='near-same: femoral intercondylar line - intermalleolar line (guide: popliteal fold - IML)', verdict='relevant', accessed='abstract (PubMed)')
src('parratte2002', citation='Parratte B, Tatu L, Vuillier F, Diop M, Monnier G. Intramuscular distribution of nerves in the human triceps surae muscle: anatomical bases for treatment of spastic drop foot with botulinum toxin. Surg Radiol Anat 2002;24(2):91-6.', doi='10.1007/s00276-002-0022-9', pmid='12197026', method='macro + stereoscopic microdissection', n='40 legs', population='adult cadavers (France)', landmark_match='% of a standard leg length (values not in abstract)', verdict='partly', reason='Relevant by design; values not reachable.', accessed='abstract (PubMed)')
src('yi2023gas', citation='Yi KH, Park HJ, Kim JH, Kim SO, Cheon GW, An MH. Intramuscular neural distribution of the gastrocnemius for botulinum neurotoxin injection: application to cosmetic calf shaping. Yonsei Med J 2023;64(8):511-7.', doi='10.3349/ymj.2023.0124', pmid='37488703', method='modified Sihler stain', n='16 specimens', population='adult cadavers', landmark_match='different: fibular head line - superior margin of calcaneal tuberosity; counting direction not stated in the abstract', verdict='partly', reason='7/10-8/10 (medial) and 7.5/10-8.5/10 (lateral) only make anatomical sense counted from the calcaneal end (= 20-30% / 15-25% below the fibular head), which agrees with the guide.', accessed='abstract (PubMed)')
src('yi2025sol', citation='Yi KH, Hu H, Hwang SO, Lee JH, Lee HJ. Intramuscular neural distribution of the soleus for botulinum neurotoxin injection: application to spasticity. Sci Rep 2026;16(1):279.', doi='10.1038/s41598-025-07508-2', pmid='41444715', method='modified Sihler stain', n='20 specimens', population='adult cadavers', landmark_match='different: fibular head line - calcaneal tuberosity line, zones 1-10, direction not stated in the abstract', verdict='partly', reason='Zone 5 (lateral, medial) and zone 3 (middle); not converted because the counting direction is not stated.', accessed='abstract (PubMed)')
src('lee2011pl', citation='Lee JH, Lee BN, An X, Chung RH, Kwon SO, Han SH. Anatomic localization of motor entry point of superficial peroneal nerve to peroneus longus and brevis muscles. Clin Anat 2011;24(2):232-6.', doi='10.1002/ca.21076', pmid='21322046', method='cadaveric dissection, motor entry points', n='43 legs / 25 bodies', population='fresh adult', landmark_match='same line: most proximal fibular head - most distal lateral malleolus', verdict='relevant', accessed='abstract (PubMed)')
src('choi2019', citation='Choi YJ, Cho TH, Won SY, Yang HM. Guideline for botulinum toxin injections in the effective treatment of fibular spasticity. Clin Anat 2020;33(3):365-9.', doi='10.1002/ca.23487', pmid='31581308', method='modified Sihler stain, nerve endings per quarter', n='10 specimens / 5 cadavers', population='fixed cadavers', landmark_match='quarters of the leg from proximal (repo record: fibular head - lateral malleolus)', verdict='relevant', accessed='abstract (PubMed)')
src('yi2016ta', citation='Yi KH, Cong L, Bae JH, Park ES, Rha DW, Kim HJ. Neuromuscular structure of the tibialis anterior muscle for functional electrical stimulation. Surg Radiol Anat 2017;39(1):77-83.', doi='10.1007/s00276-016-1698-6', pmid='27206542', method='dissection + modified Sihler stain', n='110 legs (10 stained)', population='Korean and Thai cadavers', landmark_match='same line, reversed: lateral malleolus (0%) - fibular head', verdict='relevant', accessed='abstract (PubMed)')
src('saitou2000', citation='Saitou K, Masuda T, Michikami D, Kojima R, Okada M. Innervation zones of the upper and lower limb muscles estimated by using multichannel surface EMG. J Hum Ergol (Tokyo) 2000;29(1-2):35-52.', doi=None, pmid='12696320', method='multichannel surface EMG', n='3 subjects', population='healthy', landmark_match='qualitative', verdict='partly', reason='Confirms narrow bands in parallel-fibred muscles (biceps, VL, VM, TA, soleus, peronei) and scattered IZs in pennate/complex ones (forearm, RF, sartorius, hamstrings, gastrocnemius); no % lines in the abstract.', accessed='abstract (PubMed)')
src('beretta2014', citation='Beretta Piccoli M, Rainoldi A, Heitz C, et al. Innervation zone locations in 43 superficial muscles: toward a standardization of electrode positioning. Muscle Nerve 2014;49(3):413-21.', doi='10.1002/mus.23934', pmid='24741685', method='multichannel surface EMG', n='40 subjects', population='healthy adults', landmark_match='landmark lines in the full text (not reachable)', verdict='partly', reason='The best in-vivo IZ map of superficial muscles, but its values could not be opened; candidate for the next round.', accessed='abstract (PubMed)')
src('barbero2012', citation='Barbero M, Merletti R, Rainoldi A. Atlas of Muscle Innervation Zones. Milan: Springer; 2012.', doi=None, pmid=None, method='surface EMG atlas (book)', n=None, population='healthy', landmark_match='landmark-based lines per muscle (book not opened)', verdict='not used', reason='Book; not reachable from this session. Do not quote values from memory.', accessed='not opened')
src('christensen1959', citation='Christensen E. Topography of terminal motor innervation in striated muscles from stillborn infants. Am J Phys Med 1959;38(2):65-78.', doi=None, pmid='13637190', method='histology', n=None, population='stillborn infants', landmark_match='not available', verdict='not used', reason='No abstract; infant material; the historical base of later reviews.', accessed='citation only')
src('diaconu', citation='Diaconu S et al. Visual-guide review series on image-guided botulinum toxin injection in spasticity, parts II-IV (Elias University Hospital approach); title withheld here because it contains a term the public pages must not carry. PMIDs 40423325, 41150208 (as recorded in the repo).', doi=None, pmid='40423325', method='secondary synthesis (review series)', n=None, population='n/a', landmark_match='mixed; already in data/muscles', verdict='partly', reason='Secondary source; at least two of its records in data/muscles carry a reversed counting direction (gastrocnemius) or swapped heads (triceps) relative to the primary papers - see conflicts.', accessed='repo record')
src('levin1996', citation='Levin KH, Maggiano HJ, Wilbourn AJ. Cervical radiculopathies: comparison of surgical and EMG localization of single-root lesions. Neurology 1996;46(4):1022-5.', doi='10.1212/wnl.46.4.1022', pmid='8780083', method='needle EMG vs surgically proven single-root lesions', n='50 patients', population='cervical radiculopathy', landmark_match='n/a (root levels)', verdict='relevant', accessed='abstract (PubMed)')
src('tsao2003', citation='Tsao BE, Levin KH, Bodner RA. Comparison of surgical and electrodiagnostic findings in single root lumbosacral radiculopathies. Muscle Nerve 2003;27(1):60-4.', doi='10.1002/mus.10291', pmid='12508296', method='needle EMG vs surgically confirmed single-level lesions', n='45 patients', population='lumbosacral radiculopathy', landmark_match='n/a (root levels)', verdict='relevant', accessed='abstract (PubMed)')
src('schirmer2011', citation='Schirmer CM, Shils JL, Arle JE, et al. Heuristic map of myotomal innervation in humans using direct intraoperative nerve root stimulation. J Neurosurg Spine 2011;15(1):64-70.', doi='10.3171/2011.2.SPINE1068', pmid='21476796', method='intraoperative root stimulation + EMG', n='129 patients / 1589 stimulations', population='spinal surgery', landmark_match='n/a', verdict='partly', reason='Shows roots supply a broader set of muscles than textbooks; per-muscle map not in the abstract.', accessed='abstract (PubMed)')
src('isncsci2019', citation='Rupp R, Biering-Sørensen F, Burns SP, et al. International Standards for Neurological Classification of Spinal Cord Injury: revised 2019. Top Spinal Cord Inj Rehabil 2021;27(2):1-22.', doi='10.46292/sci2702-1', pmid='34108832', method='consensus standard (key muscles per myotome)', n=None, population='n/a', landmark_match='n/a', verdict='relevant', reason='One representative key muscle group per root (C5-T1, L2-S1); not a full root range. Full text not returned by the tool; the key-muscle list is the standard\'s published worksheet.', accessed='citation (PubMed); content = the standard key-muscle list')
src('repo_textbook', citation='Repository registry (data/muscles/*, data/nerves/*): Gray\'s Anatomy for Students 4th ed. (Drake, Vogl, Mitchell); Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy 8th ed.; Terminologia Anatomica (FICAT 1998).', doi=None, pmid=None, method='textbook', n=None, population='n/a', landmark_match='n/a', verdict='relevant', reason='Nerve, branch and textbook root levels; not re-opened this round, reconciled as-is.', accessed='repo record')

# ---------------------------------------------------------------- root-level evidence by muscle
ISN = {'biceps_brachii': 'C5', 'brachialis': 'C5', 'extensor_carpi_radialis_longus': 'C6', 'extensor_carpi_radialis_brevis': 'C6',
       'triceps_brachii': 'C7', 'flexor_digitorum_profundus': 'C8', 'psoas_major': 'L2', 'iliacus': 'L2', 'rectus_femoris': 'L3',
       'vastus_intermedius': 'L3', 'vastus_medialis': 'L3', 'vastus_lateralis': 'L3', 'tibialis_anterior': 'L4',
       'extensor_hallucis_longus': 'L5', 'gastrocnemius': 'S1', 'soleus': 'S1'}
ISN_GROUP = {'C5': 'elbow flexors', 'C6': 'wrist extensors', 'C7': 'elbow extensors', 'C8': 'finger flexors (middle finger distal phalanx)',
             'L2': 'hip flexors', 'L3': 'knee extensors', 'L4': 'ankle dorsiflexors', 'L5': 'long toe extensors', 'S1': 'ankle plantar flexors'}
LEVIN = {'biceps_brachii': (['C5'], 'C5 pattern; half of C6 lesions looked like C5'),
         'brachioradialis': (['C5'], 'C5 pattern; half of C6 lesions looked like C5'),
         'pronator_teres': (['C6', 'C7'], 'involved in C7 and in C6 lesions'),
         'flexor_carpi_radialis': (['C7'], 'C7 pattern; half of C6 lesions looked like C7'),
         'triceps_brachii': (['C7'], 'C7 pattern; half of C6 lesions looked like C7'),
         'extensor_indicis': (['C8'], 'C8 pattern'), 'abductor_pollicis_brevis': (['C8'], 'C8 pattern'),
         'flexor_pollicis_longus': (['C8'], 'C8 pattern'), 'dorsal_interossei_hand': (['C8'], 'C8 pattern (first dorsal interosseous)')}
TSAO = {'tibialis_anterior': (['L5'], 'predominantly L5 in this series'), 'gastrocnemius': (['S1'], 'predominantly S1 (both heads)'),
        'biceps_femoris': (['S1'], 'exclusively S1 in this series (both heads); none affected in L5 lesions')}
ORDER = ['C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'T1', 'T12', 'L1', 'L2', 'L3', 'L4', 'L5', 'S1', 'S2', 'S3', 'S4']
def levels(s):
    s = s.split('(')[0]
    m = re.findall(r'([CTLS])(\d+)', s)
    toks = [a+b for a, b in m]
    if len(toks) >= 2 and '-' in s:
        i, j = ORDER.index(toks[0]), ORDER.index(toks[-1]); return ORDER[i:j+1]
    return toks

# ---------------------------------------------------------------- muscles
MUS = {}
def mus(key, name, region, structures, repo_id, iz, others=(), decision='', conflicts=(), parts=None, nerve=None, branch=None, guide_cite='', page_nerves=(), notes=''):
    MUS[key] = dict(name=name, region=region, structures=structures, repo_id=repo_id, iz=list(iz), others=list(others), decision=decision,
                    conflicts=list(conflicts), parts=parts or [], nerve=nerve, branch=branch, guide_cite=guide_cite, page_nerves=list(page_nerves), notes=notes)
def Z(part, line, pct, cite, src=('guv2026',), note=None):
    z = {'part': part, 'line': line, 'pct': pct, 'src': list(src), 'cite': cite}
    if note: z['note'] = note
    return z
def O(src, line, pct, part=None, kind='iz', same_line='no', agreement='not_comparable', note=None):
    o = {'src': src, 'line': line, 'pct': pct, 'kind': kind, 'same_line': same_line, 'agreement': agreement}
    if part: o['part'] = part
    if note: o['note'] = note
    return o
T1 = 'Table I p.442'; T2 = 'Table II p.443'

# ---- upper limb
mus('subscapularis', 'Subscapularis', 'upper_limb', ['subscapularis'], 'subscapularis',
    [Z('superior', 'subscapular_guide', None, T1, note='Qualitative site only ("superior portion"); no % given'),
     Z('middle', 'subscapular_guide', None, T1, note='Qualitative site only ("middle portion")'),
     Z('inferior', 'subscapular_guide', None, T1, note='Qualitative site only ("inferior portion")')],
    decision='Guide gives a line and three portions but no percentages: the mode shows the line and three labelled thirds of it as qualitative sites (no % invented).',
    page_nerves=['zan_superior_subscapular_nerve', 'zan_inferior_subscapular_nerve'], guide_cite=T1+'; text p.444')
mus('pectoralis_major', 'Pectoralis major', 'upper_limb',
    ['zan_clavicular_head_of_pectoralis_major_muscle', 'zan_sternocostal_head_of_pectoralis_major_muscle', 'zan_abdominal_part_of_pectoralis_major_muscle'], 'pectoralis_major',
    [Z('clavicular_head', 'fascicle', 50, T1+'; text p.445', note='"mid-portion of the fascicles" read as 50%'),
     Z('sternal_head', 'fascicle', 50, T1+'; text p.445', note='"mid-portion of the fascicles" read as 50%')],
    others=[O('diaconu', 'fascicle', 60, part='clavicular_head', same_line='muscle-relative', agreement='near'),
            O('diaconu', 'fascicle', 55, part='sternal_head', same_line='muscle-relative', agreement='near'),
            O('li2021', None, None, note='2 nerve-dense regions (clavicular, sternal) on acromion-jugular notch / sternal lines; count agrees')],
    decision='Adopt 50% of each head\'s own fascicle length (guide). The repo record\'s 55-60% is a secondary synthesis on the same muscle-relative axis and lies within one IZ band width.',
    parts=[{'id': 'clavicular_head', 'structures': ['zan_clavicular_head_of_pectoralis_major_muscle']},
           {'id': 'sternal_head', 'structures': ['zan_sternocostal_head_of_pectoralis_major_muscle']}],
    page_nerves=['lateral_pectoral_n', 'medial_pectoral_n'], guide_cite=T1)
mus('pectoralis_minor', 'Pectoralis minor', 'upper_limb', ['pectoralis_minor'], 'pectoralis_minor',
    [Z('superior_part', 'fascicle', 50, T1+'; text p.445'), Z('inferior_part', 'fascicle', 50, T1+'; text p.445')],
    others=[O('diaconu', 'fascicle', 75, same_line='muscle-relative', agreement='conflict', note='repo record (secondary) puts it at three-quarters of origin-insertion'),
            O('li2021', None, None, note='one nerve-dense region')],
    conflicts=['Guide 50% (mid-fascicle) vs repo record 75% of origin-insertion (secondary source). The guide\'s supporting citation here is its ref 5 (a biceps study), so neither is strongly sourced; guide value kept as the primary, repo value shown as "other source".'],
    decision='Adopt guide (mid-fascicle) - primary source of this round; conflict shown.', page_nerves=['medial_pectoral_n', 'lateral_pectoral_n'], guide_cite=T1)
mus('latissimus_dorsi', 'Latissimus dorsi', 'upper_limb', ['latissimus_dorsi'], 'latissimus_dorsi',
    [Z('t12_line', 'ld_t12', 50, T1+'; text p.444'), Z('l4_line', 'ld_l4', 50, T1+'; text p.444'), Z('iliac_line', 'ld_iliac', 50, T1+'; text p.444')],
    others=[O('diaconu', None, [30, 90], note='repo record: three bands on a T5-spine-to-humerus line; different line')],
    conflicts=['Table I names the proximal end "axillary fossa"; the text names "axillary fold". Adopted: posterior axillary fold (text, and it is where the muscle is).'],
    decision='Adopt guide: midpoints of three lines from the posterior axillary fold.', page_nerves=['thoracodorsal_n'], guide_cite=T1)
mus('teres_major', 'Teres major', 'upper_limb', ['teres_major'], 'teres_major',
    [Z('main', 'tm_guide', 50, 'text p.444 (not in Table I)')],
    others=[O('yi2023tm', 'fascicle', [40, 60], same_line='muscle-relative', agreement='agree')],
    decision='Adopt guide midpoint; Yi 2023 (cadaver, n=18) middle 20% of the muscle agrees.', page_nerves=['zan_inferior_subscapular_nerve'], guide_cite='text p.444')
mus('biceps_brachii', 'Biceps brachii', 'upper_limb', ['biceps_brachii'], 'biceps_brachii',
    [Z('short_head', 'coracoid_me', 65, T1+'; text p.445'), Z('long_head', 'coracoid_me', 65, T1+'; text p.445')],
    others=[O('lee2009', 'coracoid_me', [64.6, 70.3], kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('park2007', None, 50, kind='motor_point', note='line from the coracoid; distal end not verifiable'),
            O('amirali2007', 'olecranon_acromion', [25, 39], kind='endplate_band', note='inverted-V band: 0.25 lateral edge, 0.39 midline, 0.28 medial edge of olecranon-acromion length'),
            O('zhang2017', None, None, note='IZ centre 9.4 +/- 1.4 cm proximal to the medial-epicondyle plane (HD-sEMG, n=6)'),
            O('tang2018', None, [56.6, 67.6], note='two nerve-dense centres on an unverified longitudinal line'),
            O('diaconu', None, [67, 100], note='repo record: distal third of the arm (acromion-elbow)')],
    decision='Adopt 65% coracoid-ME (guide); the same-line cadaver study (Lee 2009, n=56) puts the densest endings at 64.6-70.3%.', page_nerves=['musculocutaneous_n'], guide_cite=T1)
mus('brachialis', 'Brachialis', 'upper_limb', ['brachialis'], 'brachialis',
    [Z('medial_part', 'coracoid_me', 75, T1+'; text p.445'), Z('lateral_part', 'coracoid_me', 75, T1+'; text p.445')],
    others=[O('lee2009', 'coracoid_me', 75.4, kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('park2007', None, 70, kind='motor_point', note='line from the coracoid; distal end not verifiable'),
            O('tang2018', None, [71.3, 81.6], note='unverified line')],
    decision='Adopt 75% (guide); Lee 2009 same line 75.4%.', page_nerves=['musculocutaneous_n'], guide_cite=T1)
mus('brachioradialis', 'Brachioradialis', 'upper_limb', ['brachioradialis'], 'brachioradialis',
    [Z('main', 'forearm', 20, T1+'; text p.446')],
    others=[O('repo', 'fascicle', [39.0, 61.9], note='repo record, origin-insertion (different axis: BR originates on the humerus above the epicondyles)')],
    decision='Adopt guide 20%.', page_nerves=['radial_n'], guide_cite=T1)
mus('triceps_brachii', 'Triceps brachii', 'upper_limb',
    ['zan_long_head_of_triceps_brachii', 'zan_lateral_head_of_triceps_brachii', 'zan_medial_head_of_triceps_brachii'], 'triceps_brachii',
    [Z('lateral_head', 'acromion_olecranon', 50, T1+'; text p.446'), Z('long_head', 'acromion_olecranon', 60, T1+'; text p.446'), Z('medial_head', 'acromion_olecranon', 60, T1+'; text p.446')],
    others=[O('koo2019', 'acromion_post_olecranon', 43.8, part='long_head', kind='endplate_zone', same_line='near', agreement='conflict', note='median'),
            O('koo2019', 'acromion_post_olecranon', 54.8, part='lateral_head', kind='endplate_zone', same_line='near', agreement='agree'),
            O('koo2019', 'acromion_post_olecranon', 60.4, part='medial_head', kind='endplate_zone', same_line='near', agreement='agree'),
            O('yi2023tri', 'olecranon_acromion_ai', [30, 50], part='long_head', same_line='near_reversed', agreement='agree', note='= 50-70% from the acromion'),
            O('yi2023tri', 'olecranon_acromion_ai', [60, 70], part='long_head', same_line='near_reversed', agreement='second_zone', note='= 30-40% from the acromion: a second, proximal long-head zone'),
            O('yi2023tri', 'olecranon_acromion_ai', [30, 40], part='medial_head', same_line='near_reversed', agreement='agree', note='= 60-70% from the acromion'),
            O('yi2023tri', 'olecranon_acromion_ai', [30, 60], part='lateral_head', same_line='near_reversed', agreement='agree', note='= 40-70% from the acromion')],
    conflicts=['Long head: guide 60% vs Koo 2019 43.8% (n=12, near-same line). Yi 2023 (n=15) finds TWO long-head zones (50-70% and 30-40% from the acromion): the guide\'s 60% sits in the distal one, Koo\'s 43.8% between them. Adopt guide 60%; show Yi\'s proximal zone as an "other source" band.',
               'Repo data/muscles/upper_limb/triceps_brachii_*.json records lateral head 30-40% and medial head 30-60% (via Diaconu); the primary paper (Yi 2023 abstract) gives medial 30-40% and lateral 30-60% - the two heads look swapped in the repo record (not edited this round).'],
    decision='Adopt guide values per head; agreement with Koo 2019 and Yi 2023 for lateral and medial heads.',
    parts=[{'id': 'long_head', 'structures': ['zan_long_head_of_triceps_brachii']}, {'id': 'lateral_head', 'structures': ['zan_lateral_head_of_triceps_brachii']},
           {'id': 'medial_head', 'structures': ['zan_medial_head_of_triceps_brachii']}],
    page_nerves=['radial_n'], guide_cite=T1)
FA = lambda part, pct, cite: Z(part, 'forearm', pct, T1 + ('; text ' + cite if cite else ''))
mus('pronator_teres', 'Pronator teres', 'upper_limb', ['pronator_teres'], 'pronator_teres', [FA('main', 20, 'p.446')],
    others=[O('zhou2023', 'me_ulnar_styloid', 12.5, part='humeral_head'), O('zhou2023', 'me_ulnar_styloid', 18.4, part='ulnar_head')],
    decision='Adopt guide 20%.', page_nerves=['zan_muscular_branches_of_median_nerve'], guide_cite=T1)
mus('pronator_quadratus', 'Pronator quadratus', 'upper_limb', ['pronator_quadratus'], 'pronator_quadratus', [FA('main', 90, 'p.448')],
    decision='Adopt guide 90%.', page_nerves=['anterior_interosseous_n'], guide_cite=T1)
mus('flexor_carpi_radialis', 'Flexor carpi radialis', 'upper_limb', ['flexor_carpi_radialis'], 'flexor_carpi_radialis', [FA('main', 35, 'p.447')],
    others=[O('zhou2023', 'me_ulnar_styloid', 28.8)], decision='Adopt guide 35%.', page_nerves=['zan_muscular_branches_of_median_nerve'], guide_cite=T1)
mus('palmaris_longus', 'Palmaris longus', 'upper_limb', ['zan_palmaris_longus_muscle'], 'palmaris_longus', [FA('main', 25, 'p.447')],
    decision='Adopt guide 25%.', page_nerves=['zan_muscular_branches_of_median_nerve'], guide_cite=T1)
mus('flexor_carpi_ulnaris', 'Flexor carpi ulnaris', 'upper_limb', ['flexor_carpi_ulnaris'], 'flexor_carpi_ulnaris',
    [FA('ventral_deep_part', 30, 'p.447'), FA('dorsal_superficial_part', 50, 'p.447')],
    others=[O('zhou2023', 'me_ulnar_styloid', 17.7)], decision='Adopt guide: two compartments, two bands.', page_nerves=['ulnar_n', 'zan_muscular_branches_of_ulnar_nerve'], guide_cite=T1)
mus('flexor_digitorum_superficialis', 'Flexor digitorum superficialis', 'upper_limb',
    ['flexor_digitorum_superficialis', 'zan_humero_ulnar_head_of_flexor_digitorum_superficialis'], 'flexor_digitorum_superficialis',
    [FA('humeroulnar_head', 30, 'p.447'), FA('radial_head', 50, 'p.447')],
    others=[O('zhou2023', 'me_ulnar_styloid', 57.3, part='radial_head')],
    parts=[{'id': 'humeroulnar_head', 'structures': ['zan_humero_ulnar_head_of_flexor_digitorum_superficialis']}, {'id': 'radial_head', 'structures': ['flexor_digitorum_superficialis']}],
    decision='Adopt guide.', page_nerves=['zan_muscular_branches_of_median_nerve'], guide_cite=T1)
mus('flexor_digitorum_profundus', 'Flexor digitorum profundus', 'upper_limb', ['flexor_digitorum_profundus'], 'flexor_digitorum_profundus',
    [FA('medial_part', 40, 'p.448'), FA('lateral_part', 60, 'p.448')],
    others=[O('zhou2023', 'me_ulnar_styloid', 45.9, part='lateral_part', note='"radial half"')],
    parts=[{'id': 'medial_part', 'nerve': 'ulnar_n', 'note': 'digits 4-5 (ulnar n.)'}, {'id': 'lateral_part', 'nerve': 'anterior_interosseous_n', 'note': 'digits 2-3 (anterior interosseous n.)'}],
    decision='Adopt guide; the two parts carry different nerves (repo record).', page_nerves=['anterior_interosseous_n', 'ulnar_n'], guide_cite=T1)
mus('flexor_pollicis_longus', 'Flexor pollicis longus', 'upper_limb', ['flexor_pollicis_longus'], 'flexor_pollicis_longus',
    [FA('band_1', 50, 'p.448'), FA('band_2', 65, '')],
    others=[O('zhou2023', 'me_ulnar_styloid', 64.1)],
    conflicts=['Table I gives 50% and 65%; the FPL paragraph (p.448) gives no IZ - Table I adopted.'],
    decision='Adopt Table I.', page_nerves=['anterior_interosseous_n'], guide_cite=T1)
for k, nm, pct, pg, nv in [('extensor_carpi_radialis_longus', 'Extensor carpi radialis longus', 20, 'p.446', 'radial_n'),
                           ('extensor_carpi_radialis_brevis', 'Extensor carpi radialis brevis', 40, 'p.446', 'posterior_interosseous_n'),
                           ('extensor_carpi_ulnaris', 'Extensor carpi ulnaris', 40, 'p.448-449', 'posterior_interosseous_n'),
                           ('extensor_digitorum', 'Extensor digitorum', 40, 'p.448-449', 'posterior_interosseous_n'),
                           ('extensor_digiti_minimi', 'Extensor digiti minimi', 60, 'p.449', 'posterior_interosseous_n'),
                           ('abductor_pollicis_longus', 'Abductor pollicis longus', 60, 'p.449', 'posterior_interosseous_n'),
                           ('extensor_pollicis_brevis', 'Extensor pollicis brevis', 75, 'p.449', 'posterior_interosseous_n'),
                           ('extensor_indicis', 'Extensor indicis', 85, 'p.449', 'posterior_interosseous_n')]:
    mus(k, nm, 'upper_limb', [k], k, [FA('main', pct, pg)], decision=f'Adopt guide {pct}%.', page_nerves=[nv, 'zan_posterior_interosseous_nerve_of_forearm'], guide_cite=T1)
mus('extensor_pollicis_longus', 'Extensor pollicis longus', 'upper_limb', ['zan_extensor_pollicis_longus'], 'extensor_pollicis_longus', [FA('main', 70, 'p.449')],
    decision='Adopt guide 70%.', page_nerves=['posterior_interosseous_n', 'zan_posterior_interosseous_nerve_of_forearm'], guide_cite=T1)
for k, nm, pct, nv in [('abductor_pollicis_brevis', 'Abductor pollicis brevis', 40, 'recurrent_branch_of_median_n'), ('opponens_pollicis', 'Opponens pollicis', 60, 'recurrent_branch_of_median_n'),
                       ('flexor_pollicis_brevis', 'Flexor pollicis brevis', 60, 'recurrent_branch_of_median_n')]:
    mus(k, nm, 'upper_limb', [k], k, [Z('main', 'hamate_mc1', pct, T1+'; text p.450')],
        others=[O('xie2013', 'fascicle', [33, 67], note='repo record; origin-insertion thirds')] if k != 'opponens_pollicis' else [],
        decision=f'Adopt guide {pct}%.', page_nerves=[nv, 'ulnar_n_deep_branch'] if k == 'flexor_pollicis_brevis' else [nv], guide_cite=T1,
        parts=[{'id': 'superficial_head', 'nerve': 'median_n_recurrent_thenar_branch'}, {'id': 'deep_head', 'nerve': 'ulnar_n_deep_branch'}] if k == 'flexor_pollicis_brevis' else None)
mus('adductor_pollicis', 'Adductor pollicis', 'upper_limb', ['adductor_pollicis'], 'adductor_pollicis',
    [Z('oblique_head', 'hamate_mc1', 50, T1+'; text p.450'), Z('transverse_head', 'hamate_mc1', 50, T1+'; text p.450')],
    others=[O('garg2026', None, None, kind='motor_entry_point', note='13.7 +/- 6.6 mm from the 1st MCP joint; 48.5 +/- 8.2 mm from the radial styloid')],
    decision='Adopt guide 50% (one level, both heads).', page_nerves=['ulnar_n_deep_branch'], guide_cite=T1)
mus('lumbricals_hand', 'Lumbricals (hand)', 'upper_limb', ['zan_lumbrical_muscles_of_hand'], 'lumbricals_hand',
    [Z('main', 'radstyloid_mcheads', 75, T1+'; text p.450')],
    parts=[{'id': 'lumbricals_1_2', 'nerve': 'median_n_palmar_digital_nn'}, {'id': 'lumbricals_3_4', 'nerve': 'ulnar_n_lumbrical_branches'}],
    decision='Adopt guide 75%.', page_nerves=['zan_common_palmar_digital_branches_of_median_nerve', 'ulnar_n_deep_branch'], guide_cite=T1)
mus('palmar_interossei', 'Palmar interossei', 'upper_limb', ['palmar_interossei'], 'palmar_interossei',
    [Z('main', 'radstyloid_mcheads', 75, T1+'; text p.450')], decision='Adopt guide 75%.', page_nerves=['ulnar_n_deep_branch'], guide_cite=T1)
mus('dorsal_interossei_hand', 'Dorsal interossei (hand)', 'upper_limb', ['dorsal_interossei_hand'], 'dorsal_interossei_hand',
    [Z('main', 'radstyloid_mcheads', 75, T1+'; text p.450'), Z('first_dorsal_interosseous', 'fascicle', 50, T1, note='"mid-portion of the muscle"; the page has one structure for all four dorsal interossei')],
    decision='Adopt guide: 75% radial styloid-MC heads for the group, mid-muscle for the 1st dorsal interosseous.', page_nerves=['ulnar_n_deep_branch'], guide_cite=T1)

# ---- lower limb
mus('psoas_major', 'Psoas major', 'lower_limb', ['zan_psoas_major'], 'iliopsoas', [Z('main', 't12_inguinal', 50, T2+'; text p.451', note='"just above the iliac crest"')],
    others=[O('vancamp2010', 't12_inguinal', [30, 70], kind='endplate_zone', same_line='near', agreement='agree', note='T12 to where psoas passes under the inguinal ligament; n=24')],
    decision='Adopt 50% (guide), the centre of Van Campenhout\'s 30-70% zone.', nerve=['lumbar_root_L1', 'lumbar_root_L2', 'lumbar_root_L3'], branch='direct muscular branches of the lumbar plexus (repo record)',
    page_nerves=['lumbar_root_L3', 'lumbar_root_T12'], guide_cite=T2)
mus('iliacus', 'Iliacus', 'lower_limb', ['zan_iliacus_muscle'], 'iliopsoas', [], decision='The guide describes iliacus but gives no IZ; nerve/roots only.',
    nerve=['femoral_n_branch_to_iliacus'], page_nerves=['femoral_n'], guide_cite='text p.451')
mus('piriformis', 'Piriformis', 'lower_limb', ['piriformis'], 'piriformis', [],
    others=[O('diaconu', None, [60, 80], note='repo record: greater trochanter -> sacrum (secondary); not adopted - sacral point undefined')],
    decision='The guide describes piriformis but gives no IZ; no primary-source % adopted.', page_nerves=['nerve_to_piriformis'], guide_cite='text p.451')
mus('sartorius', 'Sartorius', 'lower_limb', ['sartorius'], 'sartorius',
    [Z('band_1', 'asis_mfe', 25, T2+'; text p.452'), Z('band_2', 'asis_mfe', 50, T2+'; text p.452'), Z('band_3', 'asis_mfe', 75, T2+'; text p.452')],
    others=[O('yi2021sar', 'asis_mfe', [20, 40], same_line='yes', agreement='agree'), O('yi2021sar', 'asis_mfe', [60, 80], same_line='yes', agreement='agree'),
            O('page2019', None, [20, 43], kind='motor_branch_entry', note='proximal and distal branches at 0.20 and 0.43 from the femoral nerve at the inguinal ligament')],
    conflicts=['Middle band (50%): Yi 2021 (same line, n=15) finds dense innervation at 20-40% and 60-80% but not at 50%. Guide 25% and 75% agree; 50% is guide-only.'],
    decision='Adopt guide 25/50/75%, the 50% band flagged guide-only.', page_nerves=['femoral_n'], guide_cite=T2)
mus('adductor_longus', 'Adductor longus', 'lower_limb', ['adductor_longus'], 'adductor_longus',
    [Z('lateral_portion', 'pubic_mfe', 20, T2+'; text p.452'), Z('medial_portion', 'pubic_mfe', 35, T2+'; text p.452')],
    others=[O('kwon2009', 'pubic_mfe', 26.0, kind='motor_point', same_line='yes', agreement='agree', note='SD 4.8; n=19 limbs')],
    conflicts=['Text says pubic tubercle - MFC (medial femoral condyle), Table II says MFE: adopted MFE (table, and Kwon 2009 uses MFE); the two points differ by about 1-2 cm.'],
    decision='Adopt guide; Kwon 2009 motor point 26.0% lies between the two bands.', page_nerves=['obturator_n'], guide_cite=T2)
mus('adductor_brevis', 'Adductor brevis', 'lower_limb', ['adductor_brevis'], 'adductor_brevis', [Z('main', 'pubic_mfe', 20, T2+'; text p.452')],
    others=[O('kwon2009', 'pubic_mfe', 21.0, kind='motor_point', same_line='yes', agreement='agree', note='SD 4.8')],
    decision='Adopt guide 20%.', page_nerves=['obturator_n'], guide_cite=T2)
mus('adductor_magnus', 'Adductor magnus', 'lower_limb', ['adductor_magnus'], 'adductor_magnus',
    [Z('adductor_part', 'pubic_mfe', 20, T2+'; text p.452'), Z('adductor_part', 'pubic_mfe', 40, T2+'; text p.452')],
    others=[O('kwon2009', 'pubic_mfe', 30.4, kind='motor_point', same_line='yes', agreement='agree', note='SD 4.1'),
            O('wang2020', None, None, note='two nerve-dense regions (agrees with two bands)')],
    parts=[{'id': 'adductor_part', 'nerve': 'obturator_n_branch_to_adductor_magnus_adductor_part'}, {'id': 'hamstring_part', 'nerve': 'sciatic_n_branch_to_adductor_magnus_hamstring_part', 'note': 'no IZ given by the guide'}],
    decision='Adopt guide 20% and 40% (adductor part only).', page_nerves=['obturator_n', 'sciatic_n_branch_to_adductor_magnus_hamstring_part'], guide_cite=T2)
mus('gracilis', 'Gracilis', 'lower_limb', ['gracilis'], 'gracilis', [Z('band_1', 'pubic_mfe', 30, T2+'; text p.453'), Z('band_2', 'pubic_mfe', 60, T2+'; text p.453')],
    others=[O('kwon2009', 'pubic_mfe', 32.1, kind='motor_point', same_line='yes', agreement='agree', note='SD 2.1'),
            O('kurtys2023', None, [15, 40], kind='motor_points', note='n=93; line not defined in the abstract'),
            O('diaconu', None, [25, 35], note='repo record (secondary)')],
    conflicts=['Distal band (60%): no other source reviewed reports it (motor points cluster at 15-40%). Kept, flagged guide-only.'],
    decision='Adopt guide 30% and 60%.', page_nerves=['obturator_n'], guide_cite=T2)
mus('semitendinosus', 'Semitendinosus', 'lower_limb', ['semitendinosus'], 'semitendinosus',
    [Z('upper_lateral_compartment', 'it_mfe', 30, T2+'; text p.453'), Z('lower_medial_compartment', 'it_mfe', 70, T2+'; text p.453')],
    others=[O('an2010', 'it_mfe', [18.6, 36.8], part='upper_lateral_compartment', kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('an2010', 'it_mfe', [56.6, 79.1], part='lower_medial_compartment', kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('rha2016', 'tibcond_it', [60, 80], part='upper_lateral_compartment', same_line='near_reversed', agreement='agree', note='= 20-40% from the ischial tuberosity'),
            O('rha2016', 'tibcond_it', [25, 40], part='lower_medial_compartment', same_line='near_reversed', agreement='agree', note='= 60-75% from the ischial tuberosity')],
    decision='Adopt guide 30% and 70%; both lie inside An 2010\'s nerve-ending ranges on the same line (n=50).', page_nerves=['sciatic_n_branch_to_semitendinosus', 'sciatic_n'], guide_cite=T2)
mus('semimembranosus', 'Semimembranosus', 'lower_limb', ['semimembranosus'], 'semimembranosus', [Z('main', 'it_mfe', 75, T2+'; text p.453')],
    others=[O('an2010', 'it_mfe', [55.9, 89.1], kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('rha2016', 'tibcond_it', [20, 40], same_line='near_reversed', agreement='agree', note='= 60-80% from the ischial tuberosity')],
    decision='Adopt guide 75%.', page_nerves=['sciatic_n_branch_to_semimembranosus', 'sciatic_n'], guide_cite=T2)
mus('biceps_femoris', 'Biceps femoris', 'lower_limb', ['biceps_femoris'], 'biceps_femoris',
    [Z('long_head', 'it_mfe', 50, T2+'; text p.453'), Z('short_head', 'it_mfe', 80, T2+'; text p.453')],
    others=[O('an2010', 'it_mfe', [39.7, 72.9], part='long_head', kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('an2010', 'it_mfe', [58.9, 80.2], part='short_head', kind='terminal_nerve_endings', same_line='yes', agreement='agree'),
            O('rha2016', 'tibcond_it', [50, 60], same_line='near_reversed', agreement='agree', note='= 40-50% from the ischial tuberosity (long head region)'),
            O('rha2016', 'tibcond_it', [15, 30], same_line='near_reversed', agreement='agree', note='= 70-85% from the ischial tuberosity (short head region)')],
    parts=[{'id': 'long_head', 'nerve': 'sciatic_n_branch_to_biceps_femoris_long_head', 'note': 'tibial division'}, {'id': 'short_head', 'nerve': 'sciatic_n_branch_to_biceps_femoris_short_head', 'note': 'common fibular division'}],
    decision='Adopt guide; one page structure carries both heads, so the mode draws both bands on it.', page_nerves=['sciatic_n'], guide_cite=T2)
mus('rectus_femoris', 'Rectus femoris', 'lower_limb', ['rectus_femoris', 'rectus_femoris_reflected_head'], 'rectus_femoris',
    [Z('proximal', 'asis_patella', 40, T2+'; text p.454'), Z('distal', 'asis_patella', 60, T2+'; text p.454')],
    others=[O('diaconu', 'asis_patella', [40, 60], same_line='yes', agreement='agree', note='repo record (secondary, same lineage - not independent)'),
            O('page2019', None, [19, 29], kind='motor_branch_entry')],
    decision='Adopt guide 40% and 60%.', page_nerves=['femoral_n_branch_to_rectus_femoris', 'femoral_n'], guide_cite=T2)
mus('vastus_intermedius', 'Vastus intermedius', 'lower_limb', ['vastus_intermedius'], 'vastus_intermedius',
    [Z('band_1', 'asis_mfe', 50, T2+'; text p.454'), Z('band_2', 'asis_mfe', 65, T2+'; text p.454')],
    others=[O('page2019', None, 30, kind='motor_branch_entry', note='branch entry ratio 0.30 from the femoral nerve at the inguinal ligament')],
    conflicts=['Line is ASIS-MFE here but ASIS-patella for the other three quadriceps heads (table and text agree): kept as published.'],
    decision='Adopt guide 50% and 65%.', page_nerves=['femoral_n_branch_to_vastus_intermedius', 'femoral_n'], guide_cite=T2)
mus('vastus_medialis', 'Vastus medialis', 'lower_limb', ['vastus_medialis'], 'vastus_medialis',
    [Z('proximal_lateral', 'asis_patella', 75, T2+'; text p.454'), Z('distal_medial', 'asis_patella', 85, T2+'; text p.454')],
    others=[O('yi2024vm', 'asis_patella', [50, 90], same_line='yes', agreement='agree', note='areas 6-9 of 10; n=20')],
    decision='Adopt guide.', page_nerves=['femoral_n'], guide_cite=T2)
mus('vastus_lateralis', 'Vastus lateralis', 'lower_limb', ['vastus_lateralis'], 'vastus_lateralis',
    [Z('proximal_medial', 'asis_patella', 50, T2+'; text p.454'), Z('distal_lateral', 'asis_patella', 65, T2+'; text p.454')],
    others=[O('yi2026vl', 'gt_patella', [25, 75], note='zones 2-3 (repo record line)'), O('page2019', None, [26, 39], kind='motor_branch_entry')],
    decision='Adopt guide.', page_nerves=['femoral_n_branch_to_vastus_lateralis', 'femoral_n'], guide_cite=T2)
mus('gastrocnemius', 'Gastrocnemius', 'lower_limb', ['gastrocnemius'], 'gastrocnemius',
    [Z('lateral_head', 'popliteal_lm', 20, T2+'; text p.455'), Z('lateral_head', 'popliteal_lm', 30, T2+'; text p.455'),
     Z('medial_head', 'popliteal_lm', 25, T2+'; text p.455'), Z('medial_head', 'popliteal_lm', 35, T2+'; text p.455')],
    others=[O('kim2005', 'intercondylar_iml', [9.6, 37.5], part='medial_head', kind='motor_points', same_line='near', agreement='agree'),
            O('kim2005', 'intercondylar_iml', [12.0, 37.9], part='lateral_head', kind='motor_points', same_line='near', agreement='agree'),
            O('yi2023gas', 'fh_calcaneal', [70, 80], part='medial_head', note='counting from the calcaneal end (inferred) = 20-30% below the fibular head line', agreement='agree'),
            O('yi2023gas', 'fh_calcaneal', [75, 85], part='lateral_head', note='= 15-25% below the fibular head line (inferred direction)', agreement='agree'),
            O('diaconu', 'intercondylar_iml', [75, 80], agreement='conflict', note='repo record: 75% (medial) / 80% (lateral) FROM the intercondylar line - almost certainly counted from the other end (cf. Yi 2023)')],
    conflicts=['Line: Table II says popliteal fold - IML (intermalleolar line); the text says popliteal fold - inferior margin of the LATERAL malleolus. Adopted the text (names a point); the table variant is kept as line popliteal_iml. Difference ~1-2% of leg length.',
               'Repo data/muscles/lower_limb/gastrocnemius_*.json: 75% / 80% along intercondylar -> intermalleolar line contradicts the guide, Kim 2005 (same-ish line, 9.6-37.9%) and Yi 2023; likely a reversed counting direction in that secondary record (not edited this round).'],
    decision='Adopt guide (2 bands per head).', page_nerves=['tibial_n_branch_to_gastrocnemius', 'tibial_n'], guide_cite=T2)
mus('soleus', 'Soleus', 'lower_limb', ['soleus'], 'soleus',
    [Z('posterior_part_medial', 'popliteal_lm', 35, T2+'; text p.455'), Z('posterior_part_medial', 'popliteal_lm', 45, T2+'; text p.455'),
     Z('posterior_part_lateral', 'popliteal_lm', 35, T2+'; text p.455'), Z('posterior_part_lateral', 'popliteal_lm', 45, T2+'; text p.455'),
     Z('anterior_part_medial', 'popliteal_lm', 45, T2+'; text p.455'), Z('anterior_part_lateral', 'popliteal_lm', 45, T2+'; text p.455')],
    others=[O('kim2005', 'intercondylar_iml', [20.5, 46.7], kind='motor_points', same_line='near', agreement='agree'),
            O('yi2025sol', 'fh_calcaneal', None, note='zone 5 lateral/medial, zone 3 middle of 10; direction not stated - not converted'),
            O('repo', None, 60, note='repo record: 60% medial malleolus -> medial tibial condyle (= 40% from the knee)', agreement='agree')],
    decision='Adopt guide; Kim 2005 (near-same line) brackets it.', page_nerves=['tibial_n_branch_to_soleus', 'tibial_n'], guide_cite=T2)
mus('tibialis_posterior', 'Tibialis posterior', 'lower_limb', ['zan_tibialis_posterior_muscle'], 'tibialis_posterior',
    [Z('band_1', 'fh_lm', 25, T2+'; text p.455'), Z('band_2', 'fh_lm', 40, T2+'; text p.455')],
    others=[O('diaconu', None, [10, 40], note='repo record on a medial tibial plateau - medial malleolus line; also 70-80%')],
    decision='Adopt guide.', page_nerves=['tibial_n'], guide_cite=T2)
mus('flexor_digitorum_longus', 'Flexor digitorum longus', 'lower_limb', ['flexor_digitorum_longus'], 'flexor_digitorum_longus', [Z('main', 'fh_mm', 65, T2+'; text p.456')],
    others=[O('diaconu', 'lm_fh', [40, 50], same_line='near_reversed', agreement='conflict', note='= 50-60% from the fibular head (repo record, secondary)')],
    conflicts=['Line: Table II says FH - LM, the text says FH - medial malleolus. Adopted the text (FDL lies on the tibial side; the table footnote defines MM though no table row uses it). Alternative kept as fh_lm 65%.',
               'Repo secondary record 50-60% from the fibular head vs guide 65%: mild, within one band width.'],
    decision='Adopt guide 65% on FH-MM.', page_nerves=['tibial_n'], guide_cite=T2)
mus('flexor_hallucis_longus', 'Flexor hallucis longus', 'lower_limb', ['flexor_hallucis_longus'], 'flexor_hallucis_longus', [Z('main', 'fh_mm', 65, T2+'; text p.456')],
    others=[O('diaconu', 'lm_fh', [30, 40], same_line='near_reversed', agreement='agree', note='= 60-70% from the fibular head; also a 60-70% (= 30-40%) zone')],
    conflicts=['Same table (FH-LM) vs text (FH-MM) discrepancy as FDL; text adopted.'],
    decision='Adopt guide 65%.', page_nerves=['tibial_n'], guide_cite=T2)
mus('tibialis_anterior', 'Tibialis anterior', 'lower_limb', ['tibialis_anterior'], 'tibialis_anterior', [Z('main', 'fh_lm', 35, T2+'; text p.456')],
    others=[O('yi2016ta', 'lm_fh', [70, 80], same_line='yes_reversed', agreement='near', note='dense arborisation = 20-30% from the fibular head; nerve entry points 86.5-90.6% (= 9-13%)'),
            O('diaconu', 'lm_fh', [70, 80], note='repo record, same as Yi 2016')],
    conflicts=['Guide 35% vs Yi 2016 (same line, Sihler) 20-30% from the fibular head: the guide band sits ~5% distal to the densest arborisation. Guide kept; Yi shown.'],
    decision='Adopt guide 35%.', page_nerves=['deep_fibular_n', 'zan_muscular_branches_of_deep_fibular_nerve'], guide_cite=T2)
mus('extensor_digitorum_longus', 'Extensor digitorum longus', 'lower_limb', ['extensor_digitorum_longus'], 'extensor_digitorum_longus', [],
    decision='The guide describes EDL but gives no IZ; nerve/roots only.', page_nerves=['deep_fibular_n', 'zan_muscular_branches_of_deep_fibular_nerve'], guide_cite='text p.456')
mus('extensor_hallucis_longus', 'Extensor hallucis longus', 'lower_limb', ['extensor_hallucis_longus'], 'extensor_hallucis_longus', [Z('main', 'fh_submalleolar', 65, T2+'; text p.457')],
    conflicts=['"Submalleolar point" is not defined by the guide; proxy = lateral malleolus tip, badged.'],
    decision='Adopt guide 65%.', page_nerves=['deep_fibular_n', 'zan_muscular_branches_of_deep_fibular_nerve'], guide_cite=T2)
mus('fibularis_longus', 'Fibularis (peroneus) longus', 'lower_limb', ['fibularis_longus'], 'fibularis_longus', [Z('main', 'fh_lm', 35, T2+'; text p.457')],
    others=[O('lee2011pl', 'fh_lm', [20, 40], kind='motor_entry_points', same_line='yes', agreement='agree'), O('choi2019', 'fh_lm', [25, 50], same_line='yes', agreement='agree', note='quarter 2 densest')],
    decision='Adopt guide 35%.', page_nerves=['superficial_fibular_n'], guide_cite=T2)
mus('fibularis_brevis', 'Fibularis (peroneus) brevis', 'lower_limb', ['fibularis_brevis'], 'fibularis_brevis', [Z('main', 'fh_lm', 65, T2+'; text p.457')],
    others=[O('lee2011pl', 'fh_lm', [40, 60], kind='motor_entry_points', same_line='yes', agreement='near', note='entry points lie proximal to endings, as expected'),
            O('choi2019', 'fh_lm', [50, 75], same_line='yes', agreement='agree', note='quarter 3 densest')],
    decision='Adopt guide 65% (inside Choi 2019\'s densest quarter).', page_nerves=['superficial_fibular_n'], guide_cite=T2)
mus('flexor_digitorum_brevis', 'Flexor digitorum brevis', 'lower_limb', ['flexor_digitorum_brevis'], 'flexor_digitorum_brevis', [Z('main', 'sole_mtp1', 50, T2+'; text p.457')],
    decision='Adopt guide 50%.', page_nerves=['medial_plantar_n'], guide_cite=T2)
mus('flexor_hallucis_brevis', 'Flexor hallucis brevis', 'lower_limb', ['flexor_hallucis_brevis'], 'flexor_hallucis_brevis',
    [Z('medial_head', 'sole_mtp1', 70, T2+'; text p.457'), Z('lateral_head', 'sole_mtp1', 70, T2+'; text p.457')],
    others=[O('diaconu', None, [50, 70], note='repo record (sole -> great toe, secondary)', agreement='agree')],
    decision='Adopt guide 70%.', page_nerves=['medial_plantar_n'], guide_cite=T2)

# ---------------------------------------------------------------- assemble
def page_struct(base):
    out = {}
    for pg, ids in page_ids.items():
        out[pg] = sorted(i for i in (base + '_l', base + '_r', base) if i in ids)
    return out
def page_nerve(nid):
    return {pg: sorted(i for i in (nid + '_l', nid + '_r', nid) if i in ids) for pg, ids in page_ids.items()}

unmapped, muscles = [], {}
for key, m in MUS.items():
    r = repo.get(m['repo_id'])
    inn = r['innervation'] if r else {}
    nerve = m['nerve'] or inn.get('nerve')
    nerve = nerve if isinstance(nerve, list) else [nerve]
    if key == 'psoas_major': repo_roots = 'L1-L3'
    elif key == 'iliacus': repo_roots = 'L2-L4'
    else: repo_roots = inn.get('root_levels', '')
    rlev = levels(repo_roots)
    per = [{'src': 'repo_textbook', 'levels': rlev, 'note': f'repo record data/muscles ({m["repo_id"]}): "{inn.get("root_levels", "")}"' + (' -- psoas = lumbar plexus direct branches L1-L3, iliacus = femoral n. L2-L4 (registry)' if key in ('psoas_major', 'iliacus') else '')}]
    if key in ISN: per.append({'src': 'isncsci2019', 'levels': [ISN[key]], 'note': f'key muscle group for {ISN[key]}: {ISN_GROUP[ISN[key]]} (representative root, not a range)'})
    if key in LEVIN: per.append({'src': 'levin1996', 'levels': LEVIN[key][0], 'note': LEVIN[key][1]})
    if key in TSAO: per.append({'src': 'tsao2003', 'levels': TSAO[key][0], 'note': TSAO[key][1]})
    allv = sorted({l for p in per for l in p['levels']}, key=ORDER.index)
    rng = (allv[0] + '-' + allv[-1]) if len(allv) > 1 else (allv[0] if allv else None)
    rconf = [p for p in per[1:] if not set(p['levels']) <= set(rlev)]
    nerves_out = []
    for n in nerve:
        reg = nreg.get(n)
        nerves_out.append({'id': n, 'label': reg['name'] if reg else n.replace('_', ' '), 'parent': reg.get('parent_id') if reg else None,
                           'registry_roots': reg.get('root_contributions') if reg else None, 'in_registry': bool(reg)})
    st = {}
    for s in m['structures']:
        for pg, v in page_struct(s).items(): st.setdefault(pg, []).extend(v)
        if not any(page_struct(s).values()): unmapped.append((key, s))
    pn = {pg: sorted({i for n in m['page_nerves'] + nerve for i in page_nerve(n)[pg]}) for pg in page_ids}
    iz_parts = sorted({z['part'] for z in m['iz']})
    rec = {
        'name': m['name'], 'region': m['region'], 'repo_record': m['repo_id'] if r else None,
        'structures': st,
        'parts': m['parts'],
        'nerve': nerves_out,
        'branch': m['branch'],
        'nerve_structures_on_page': pn,
        'roots': {'adopted': rlev, 'adopted_text': repo_roots, 'range_across_sources': rng, 'per_source': per,
                  'conflict': [f'{p["src"]}: {"/".join(p["levels"])} outside textbook {repo_roots}' for p in rconf],
                  'rule': 'Adopted = textbook range (repo registry). Clinical/EMG sources name the dominant root(s) only and are shown, not merged.'},
        'iz': m['iz'],
        'iz_band_count': len(m['iz']),
        'iz_parts': iz_parts,
        'iz_other_sources': m['others'],
        'iz_decision': m['decision'],
        'conflicts': m['conflicts'] + ([f'Root levels: ' + '; '.join(f'{p["src"]} {"/".join(p["levels"])}' for p in rconf) + f' vs textbook {repo_roots}'] if rconf else []),
        'sources': {'nerve': ['repo_textbook'], 'roots': sorted({p['src'] for p in per}),
                    'iz': sorted({s for z in m['iz'] for s in z['src']}) or [],
                    'iz_comparison': sorted({o['src'] for o in m['others'] if o['src'] in SRC})},
        'guide_cite': m['guide_cite'],
    }
    if m['notes']: rec['notes'] = m['notes']
    muscles[key] = rec

# 'repo' pseudo-source used in a few comparisons -> make it a real entry
SRC['repo'] = dict(citation='This repository\'s own data/muscles record (motor_endplate_zones) for the muscle; see that file for its source.', doi=None, pmid=None, method='repo record', n=None, population='n/a', landmark_match='as stated per entry', verdict='partly', reason='Prior repo value shown for reconciliation.', accessed='repo record')
for k, m in muscles.items():
    m['sources']['iz_comparison'] = sorted({o['src'] for o in MUS[k]['others']})

used_lines = sorted({z['line'] for m in muscles.values() for z in m['iz'] if z['line']} | {o['line'] for m in muscles.values() for o in m['iz_other_sources'] if o.get('line')} | {'popliteal_iml'})
used_lm = set()
for i in used_lines:
    for e in (LN[i]['from'], LN[i]['to']):
        used_lm.add(e); used_lm.update(L[e].get('of', []))
needed_guide = set()
for m in muscles.values():
    for z in m['iz']:
        for e in (LN[z['line']]['from'], LN[z['line']]['to']):
            needed_guide.add(e); needed_guide.update(L[e].get('of', []))

out = {
    'schema': 'nmsk.innervation.v1',
    'round': 'Q322',
    'generated': datetime.date(2026, 11, 14).isoformat(),
    'scope': ['base_m', 'base_f'],
    'doc': {
        'what': 'Per-muscle innervation for the MUSCLE INNERVATION mode: nerve, branch, root levels and innervation-zone (IZ) bands as a percentage along a named reference line between two named landmarks. Anatomy only; injection technique (counts of injection points, approach, manoeuvres) is in the private clinical layer (clinical/data/innervation_injection_q322.json).',
        'primary_source': 'guv2026 (Tables I-II, pp.442-443, and the per-muscle text). Facts only are extracted; no text, figures or images reproduced (CC BY-NC-ND).',
        'fields': {
            'landmarks.<name>': '{label, bone, kind (bony_point | derived | soft_tissue | muscle_derived), definition, of? (the two landmarks a derived midpoint is taken between)}. soft_tissue points need a proxy on the body, described in definition; badge it.',
            'lines.<id>': '{from, to, mode, label}: 0% = from, 100% = to. mode "level" = the % fixes a level along the line; the IZ band is the muscle\'s cross-section at that level (a plane perpendicular to the line). mode "point" = a point on the line itself.',
            'muscles.<key>': 'key = muscle without side. structures.<page> = the page structure ids (both sides) the record applies to; parts[] = heads/compartments, optional structures / nerve per part.',
            'muscles.<key>.nerve[]': '{id (repo nerve registry id), label, parent, registry_roots, in_registry}. nerve_structures_on_page.<page> = nerve structure ids present on that page for this muscle (may be empty: the nerve is then not modelled on the page).',
            'muscles.<key>.roots': 'adopted (list of levels, from the textbook registry), range_across_sources, per_source[] {src, levels, note}, conflict[]. EMG / ISNCSCI values name the dominant root only and are never merged into the adopted range.',
            'muscles.<key>.iz[]': '{part, line, pct (number, [lo, hi] or null when the source gives only a qualitative site), src[], cite (page/table in the source), note?}. One entry = one IZ band.',
            'muscles.<key>.iz_other_sources[]': '{src, line|null, pct|null, kind, same_line (yes | near | near_reversed | yes_reversed | muscle-relative | no), agreement (agree | near | conflict | second_zone | not_comparable), part?, note?}. Shown for comparison; never averaged with iz[] when the lines differ.',
            'sources.<id>': '{citation, doi, pmid, method, n, population, landmark_match, verdict (relevant | partly | not relevant | not used), reason?, accessed}.',
        },
        'conventions': [
            'Percentages run from the first-named landmark of a line (the guide always says "% of the distal part of the line", i.e. measured from the proximal landmark).',
            'Where the guide names an unspecified point ("patella", "lateral malleolus") the adopted point is given in landmarks.<name>.definition and applies to every muscle on that line.',
            'Where Table and text disagree on a landmark, the text (which names a specific point) is adopted and the conflict is listed in the muscle\'s conflicts[].',
            'IZ placement on a body is RULE-BASED: landmarks measured on that body\'s own bones, the band drawn at the stated level; it is badged as such with these citations.',
        ],
        'not_in_this_file': 'Injection point counts, needle/probe technique, dynamic manoeuvres, structures at risk -> clinical/data/innervation_injection_q322.json (private).',
    },
    'landmarks': L,
    'landmarks_needed_for_guide_iz': sorted(needed_guide),
    'lines': LN,
    'muscles': muscles,
    'sources': SRC,
    'coverage': {
        'muscles': len(muscles),
        'upper_limb': sum(1 for m in muscles.values() if m['region'] == 'upper_limb'),
        'lower_limb': sum(1 for m in muscles.values() if m['region'] == 'lower_limb'),
        'with_numeric_iz': sum(1 for m in muscles.values() if any(isinstance(z['pct'], (int, float, list)) for z in m['iz'])),
        'iz_bands': sum(len(m['iz']) for m in muscles.values()),
        'unmapped_structures': unmapped,
    },
}
(REPO/'data/anatomy/innervation_q322.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('muscles', out['coverage'], 'lines', len(LN), 'landmarks', len(L))
print('needed', sorted(needed_guide))
for k, m in muscles.items():
    miss = [pg for pg, v in m['structures'].items() if not v]
    if miss or not all(m['nerve_structures_on_page'].values()): print('  gap', k, 'struct-missing' if miss else '', {pg: len(v) for pg, v in m['nerve_structures_on_page'].items()})
    for n in m['nerve']:
        if not n['in_registry']: print('  nerve not in registry', k, n['id'])
    if m['roots']['conflict']: print('  roots', k, m['roots']['conflict'])
