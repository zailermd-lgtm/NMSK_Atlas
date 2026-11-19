#!/usr/bin/env python3
"""Q322 private clinical layer: injection technique facts from the guide (counts, scan start, manoeuvres,
structures at risk). Written to clinical/data/ (owner's private licence). Keys = data/anatomy/innervation_q322.json."""
import json
from pathlib import Path
REPO = Path('/home/user/NMSK_Atlas')
pub = json.load(open(REPO/'data/anatomy/innervation_q322.json'))
G = 'guv2026'
# key: (injection points, per-site counts as in Table I/II, scan start (paraphrase), dynamic/positioning aid, at risk, page cite)
R = {
 'subscapularis': (3, 'superior, middle, inferior portion: 1 each', 'start at the caudal tip of the scapula in the horizontal plane, move cranially past teres major and infraspinatus; only part of the muscle is visible (scapular shadow)', None, None, 'Table I; p.444'),
 'pectoralis_major': (3, 'clavicular head 1, sternal head 2 (mid-fascicle)', 'cranial sternum in long axis, then lateral to the clavicular part', None, None, 'Table I; p.445'),
 'pectoralis_minor': (2, 'mid-portion of superior and inferior parts: 1 each', 'horizontal plane over the coracoid, move caudally past coracobrachialis; deep to pectoralis major', None, None, 'Table I; p.445'),
 'latissimus_dorsi': (3, 'mid-point of each of three lines: 1 each', 'caudal end of the scapula in short axis, move caudally', None, 'thin muscle close to intercostal muscles and pleura', 'Table I; p.444'),
 'teres_major': (None, 'not in Table I (text: midpoint inferior angle - posterior axillary fold)', 'caudal tip of the scapula, horizontal plane; first muscle appearing cranially', None, None, 'p.444'),
 'biceps_brachii': (2, 'short head 1, long head 1 (65%)', 'just distal to the bicipital groove where the long-head tendon passes under the pectoralis major tendon, scan caudally', None, 'lateral antebrachial cutaneous nerve between biceps and brachialis', 'Table I; p.445'),
 'brachialis': (2, 'medial 1, lateral 1 (75%)', 'continue caudally from biceps', None, 'median nerve and brachial artery medially', 'Table I; p.445'),
 'brachioradialis': (1, '20%', 'lateral to brachialis at the elbow; BR, ECRL, ECRB superficial to deep', None, 'superficial branch of radial nerve between BR and ECRB', 'Table I; p.446'),
 'triceps_brachii': (3, 'lateral head 50%, long head 60%, medial head 60%: 1 each', 'start at the humeral articular surface; long head becomes muscle last', None, None, 'Table I; p.446'),
 'pronator_teres': (1, '20%', 'start at the humeral articular surface', None, 'median nerve and brachial artery between brachialis and pronator teres', 'Table I; p.446'),
 'pronator_quadratus': (1, '90%', 'distal approach between radius and ulna', None, 'superficial radial nerve and radial artery superficial to the target', 'Table I; p.448'),
 'flexor_carpi_radialis': (1, '35%', 'proximal forearm; PT, FCR, PL lateral to medial', None, None, 'Table I; p.447'),
 'palmaris_longus': (1, '25%', 'as FCR', None, None, 'Table I; p.447'),
 'flexor_carpi_ulnaris': (2, 'ventral (deep) 30%, dorsal (superficial) 50%', 'most medial superficial forearm muscle', None, 'ulnar nerve between FCU, FDP and FDS', 'Table I; p.447'),
 'flexor_digitorum_superficialis': (2, 'humeroulnar part 30%, radial part 50%', 'from the humeral articular surface, scan caudally', None, 'median nerve, ulnar artery and ulnar nerve in the FDS/FDP septum', 'Table I; p.447'),
 'flexor_digitorum_profundus': (2, 'medial part 40%, lateral part 60%', 'deepest muscle wrapping the ulna, move distally/medially', None, 'as FDS', 'Table I; p.448'),
 'flexor_pollicis_longus': (2, '50% and 65%', 'distal approach; tendon to muscle between median nerve and FCR tendon', None, 'superficial radial nerve and radial artery', 'Table I; p.448'),
 'extensor_carpi_radialis_longus': (1, '20%', 'with brachioradialis', None, 'superficial branch of radial nerve', 'Table I; p.446'),
 'extensor_carpi_radialis_brevis': (1, '40%', 'with brachioradialis', None, 'superficial branch of radial nerve', 'Table I; p.446'),
 'extensor_carpi_ulnaris': (1, '40%', 'most proximal dorsal forearm in short axis (anconeus between humerus and ulna), move distally', None, None, 'Table I; p.448'),
 'extensor_digitorum': (1, '40%', 'as ECU', None, None, 'Table I; p.448'),
 'extensor_digiti_minimi': (1, '60%', 'as ECU', None, None, 'Table I; p.449'),
 'abductor_pollicis_longus': (1, '60%', 'distal approach possible', None, None, 'Table I; p.449'),
 'extensor_pollicis_longus': (1, '70%', 'distal approach possible', None, None, 'Table I; p.449'),
 'extensor_pollicis_brevis': (1, '75%', 'distal approach possible', None, None, 'Table I; p.449'),
 'extensor_indicis': (1, '85%', 'distal approach possible', None, None, 'Table I; p.449'),
 'abductor_pollicis_brevis': (1, '40%', 'transducer perpendicular to the long axis of the thumb', None, None, 'Table I; p.450'),
 'opponens_pollicis': (1, '60%', 'deep and medial to APB toward the thumb', None, None, 'Table I; p.450'),
 'flexor_pollicis_brevis': (1, '60%', 'thenar scan', None, None, 'Table I; p.450'),
 'adductor_pollicis': (2, '50%: 1 oblique head, 1 transverse head', 'thenar scan; transverse head deep to deep head of FPB', None, None, 'Table I; p.450'),
 'lumbricals_hand': (1, '75%', 'ulnar to adductor pollicis along the 2nd metacarpal', None, None, 'Table I; p.450'),
 'palmar_interossei': (7, '75% (palmar and dorsal together: 7)', 'dorsal hand, slide from 1st to 5th metacarpal', 'fingers abducted', None, 'Table I; p.450'),
 'dorsal_interossei_hand': (7, '75% (palmar and dorsal together: 7); 1st dorsal interosseous: 1 at mid-muscle', 'dorsal hand, slide from 1st to 5th metacarpal', 'fingers abducted', None, 'Table I; p.450'),
 'psoas_major': (1, '50% (just above the iliac crest)', 'posterior approach: posterior superior iliac spine in short axis, iliac crest and gluteus medius', None, None, 'Table II; p.451'),
 'iliacus': (None, 'no IZ / count given', None, None, None, 'p.451'),
 'piriformis': (None, 'no IZ / count given', 'posterior superior iliac spine in short axis; long axis by tilting the lateral transducer edge caudally', 'passive knee flexion with hip internal/external rotation shows piriformis moving under gluteus maximus', 'sciatic nerve (may pass under, through or above the muscle)', 'p.451'),
 'sartorius': (3, '25%, 50%, 75%', 'axial over the medial femoral condyle, move proximally', None, None, 'Table II; p.452'),
 'adductor_longus': (2, '20% (lateral), 35% (medial)', 'distal third of medial thigh (adductor canal), move proximally', None, None, 'Table II; p.452'),
 'adductor_brevis': (1, '20%', 'from the 30% level, between adductor longus and magnus', None, None, 'Table II; p.452'),
 'adductor_magnus': (2, 'adductor part 20% and 40%', 'axial over the adductor canal at mid-femur', None, None, 'Table II; p.452'),
 'gracilis': (2, '30%, 60%', 'supine, axial over the medial femoral condyle, slide proximally', 'hip abducted and externally rotated', None, 'Table II; p.453'),
 'semitendinosus': (2, '30% (upper-lateral), 70% (lower-medial)', 'axial over the posterior medial femoral condyle (ST superficial, SM deep tendons)', None, None, 'Table II; p.453'),
 'semimembranosus': (1, '75%', 'as semitendinosus', None, None, 'Table II; p.453'),
 'biceps_femoris': (2, 'short head 80% (1), long head 50% (1)', 'axial over the posterior lateral femoral condyle', None, 'sciatic nerve shifts under biceps femoris proximally', 'Table II; p.453'),
 'rectus_femoris': (2, '40%, 60%', 'axial over the quadriceps tendon, slide proximally', None, None, 'Table II; p.454'),
 'vastus_intermedius': (2, '50% and 65%: medial 1, lateral 1', 'as rectus femoris', None, None, 'Table II; p.454'),
 'vastus_medialis': (2, '75% (proximal-lateral), 85% (distal-medial)', 'as rectus femoris', None, None, 'Table II; p.454'),
 'vastus_lateralis': (2, '50% (proximal-medial), 65% (distal-lateral)', 'as rectus femoris; may not fit one image', None, None, 'Table II; p.454'),
 'gastrocnemius': (4, 'lateral 20% and 30% (2), medial 25% and 35% (2)', 'axial on the posteromedial popliteal fossa for the medial head', None, None, 'Table II; p.455'),
 'soleus': (6, 'posterior part 35% and 45%, anterior part 45%, medial and lateral: 2 each', 'most distal posterior leg in short axis (tibia, FHL, Kager fat pad, Achilles tendon), move proximally', None, None, 'Table II; p.455'),
 'tibialis_posterior': (2, '25%, 40%', None, None, None, 'Table II; p.455'),
 'flexor_digitorum_longus': (1, '65%', 'axial behind the medial malleolus (FDL tendon posterior to TP tendon), move proximally', None, None, 'Table II; p.456'),
 'flexor_hallucis_longus': (1, '65%', 'short axis over the medial malleolus', 'passive flexion/extension of the great toe identifies FHL', 'muscle-belly apex in close contact with the tibial nerve', 'Table II; p.456'),
 'tibialis_anterior': (1, '35%', 'axial between fibular head and tibia on the anterior leg, scan distally', None, 'anterior tibial artery and deep peroneal nerve beneath EDL', 'Table II; p.456'),
 'extensor_digitorum_longus': (None, 'no IZ / count given', 'between fibula and tibialis anterior', None, 'anterior tibial artery and deep peroneal nerve beneath EDL', 'p.456'),
 'extensor_hallucis_longus': (1, '65%', None, 'passive movement of the great toe identifies it', 'anterior tibial artery and deep peroneal nerve beneath EHL', 'Table II; p.457'),
 'fibularis_longus': (1, '35%', 'from the lateral malleolus (distal) or the fibular head (proximal)', None, None, 'Table II; p.457'),
 'fibularis_brevis': (1, '65%', 'as fibularis longus', None, None, 'Table II; p.457'),
 'flexor_digitorum_brevis': (1, '50%', 'axial over the calcaneus, move toward the toes; beneath the plantar fascia', None, None, 'Table II; p.457'),
 'flexor_hallucis_brevis': (2, '70%: medial 1, lateral 1', 'axial on the plantar 1st metatarsal head, move proximally (heads from the sesamoids)', None, None, 'Table II; p.457'),
}
missing = set(pub['muscles']) ^ set(R)
assert not missing, missing
out = {
 'schema': 'nmsk.innervation_injection.v1',
 'licence': "Private -- owner's clinical layer (see clinical/LICENSE_PRIVATE.md and PROJECT_STATE licensing rule)",
 'generated': '2026-11-14', 'round': 'Q322',
 'references': 'data/anatomy/innervation_q322.json (same muscle keys; sources table there, source id guv2026)',
 'doc': 'Injection-technique facts from the guide, paraphrased (no text copied): injection_points = the "Number" column of Tables I-II; sites = the Table "Site" cell; scan_start = where the guide starts the dynamic scan; manoeuvre = positioning / passive movement the guide uses to identify the muscle; at_risk = neurovascular structures the guide says to avoid. Technique notes: the guide recommends IZ-targeted injection with the "seeding" technique (its ref 7: Kaymak 2024, Can J Neurol Sci), e.g. two biceps IZ points reached through one lateral-to-medial puncture with a long (>= 5 cm) needle, and soleus compartments the same way (p.443). Per-muscle scan videos are in the guide\'s supplementary material.',
 'technique_refs': [{'id': 'kaymak2024seeding', 'citation': 'Kaymak B, Kara M, Abdulsalam AJ, Ricci V, Özçakar L. Optimizing botulinum toxin injections by minding the muscle architecture and its innervation zone: the "seeding" technique. Can J Neurol Sci 2024;25:1-3 (as cited by the guide, ref 7).'}],
 'muscles': {k: {'injection_points': v[0], 'sites': v[1], 'scan_start': v[2], 'manoeuvre': v[3], 'at_risk': v[4], 'src': G, 'cite': v[5]} for k, v in R.items()},
}
(REPO/'clinical/data/innervation_injection_q322.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('private muscles', len(out['muscles']), 'with count', sum(1 for m in out['muscles'].values() if m['injection_points']))
