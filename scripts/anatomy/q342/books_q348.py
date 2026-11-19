"""Q348 reference pass: facts read in the owner's anatomy books (knowledge only - no text or figures copied).

Used by gen_innervation.py (nerve supply / root values per muscle, plexus variations) and documented in
docs/Q348_reference_pass.md. Every entry carries the book key and the PRINTED page number of that book (the
e-book of Fascia in Sport and Movement has no printed pages; gen_lines.py cites its PDF pages and says so).
Root values are given as the book prints them (Mannan writes "5th and 6th cervical" -> C5-C6 here).
"""

BOOKS = {
    'mannan2017': dict(
        short='Mannan 2017',
        citation="Noor MA. Mannan's Regional Dissection and Surface Anatomy. 14th ed. Jaypee Brothers Medical Publishers, New Delhi, 2017. ISBN 978-93-86322-11-1",
        opened='owner-supplied PDF with a text layer (2026-11-16); pages are the printed page numbers', kind='book'),
    'sontakke2023': dict(
        short='Sontakke 2023',
        citation='Sontakke YA. Textbook of Human Anatomy with Color Atlas and Clinical Integration, Vol. 5: Head, Neck and Face (bound with Vol. 6: Brain). CBS Publishers & Distributors, New Delhi, 1st e-book ed. 2023',
        opened='owner-supplied PDF with a text layer (2026-11-16); pages are the printed page numbers of Vol. 5', kind='book'),
    'haviarova2024': dict(
        short='Haviarova 2024',
        citation='Haviarova Z, Matejcik V, Kuruc R. Peripheral Nervous System: Interrelationships and Variations. Springer Nature Switzerland, Cham, 2024. ISBN 978-3-031-73743-5; doi 10.1007/978-3-031-73744-2',
        opened='owner-supplied PDF with a text layer (2026-11-16); pages are the printed page numbers',
        note='Dissection series: extradural cervicobrachial and lumbosacral plexus in 50 cadavers (of 243 examined).', kind='book'),
    'carp2015': dict(
        short='Carp 2015',
        citation='Carp SJ. Peripheral Nerve Injury: An Anatomical and Physiological Approach for Physical Therapy Intervention. F. A. Davis, Philadelphia, 2015',
        opened='owner-supplied PDF with a text layer (2026-11-16)', kind='book',
        note='Clinical (pathology / rehabilitation) book; it does not tabulate muscle root values, so it is not cited per muscle.'),
}


def R(book, page, nerve, roots=None, note=None):
    """One book statement for a muscle. roots: text with levels (C5-C6) or cranial nerve (CN VII); None = nerve named without levels."""
    return dict(ref=book, page=page, nerve=nerve, roots=roots, note=note)


M, Y = 'mannan2017', 'sontakke2023'
# muscle id (as in innervation_groups_q342.json) -> list of book statements (paraphrased; levels exactly as printed)
ROOTS = {
    # ---- upper limb and shoulder girdle (Mannan, Superior Extremity) ----
    'pectoralis_major': [R(M, 105, 'lateral and medial pectoral nerves', 'C5-T1')],
    'pectoralis_minor': [R(M, 106, 'lateral and medial pectoral nerves', 'C6-C8')],
    'subclavius': [R(M, 106, 'nerve to subclavius', 'C5-C6')],
    'deltoid': [R(M, 110, 'axillary nerve (anterior and posterior branches)', 'C5-C6')],
    'teres_minor': [R(M, 111, 'posterior branch of the axillary nerve', 'C5-C6')],
    'teres_major': [R(M, 111, 'lower subscapular nerve', 'C6-C7')],
    'subscapularis': [R(M, 121, 'upper and lower subscapular nerves', 'C5-C6')],
    'latissimus_dorsi': [R(M, 121, 'thoracodorsal nerve', 'C6-C8'), R(Y, 218, 'thoracodorsal nerve', 'C6-C8')],
    'serratus_anterior': [R(M, 121, 'long thoracic nerve', 'C5-C7')],
    'supraspinatus': [R(M, 193, 'suprascapular nerve', 'C4-C6')],
    'infraspinatus': [R(M, 193, 'suprascapular nerve', 'C5-C6')],
    'rhomboid_major': [R(M, 192, 'dorsal scapular nerve', 'C4-C5'), R(Y, 218, 'dorsal scapular nerve', 'C5')],
    'rhomboid_minor': [R(M, 193, 'dorsal scapular nerve (as rhomboid major)', 'C4-C5'), R(Y, 218, 'dorsal scapular nerve', 'C5')],
    'levator_scapulae': [R(M, 86, 'branches of the 3rd-5th cervical nerves', 'C3-C5'),
                         R(Y, 218, 'dorsal scapular nerve (C5) and branches of C3 and C4', 'C3-C5')],
    'trapezius': [R(M, 92, 'accessory nerve; ventral rami of C3 and C4', 'CN XI'), R(Y, 218, 'spinal accessory nerve; ventral rami of C3 and C4', 'CN XI')],
    'biceps_brachii': [R(M, 130, 'musculocutaneous nerve', 'C5-C6')],
    'coracobrachialis': [R(M, 130, 'musculocutaneous nerve', 'C5-C7')],
    'brachialis': [R(M, 130, 'mainly the musculocutaneous nerve (large medial part)', 'C5-C6')],
    'triceps_brachii': [R(M, 135, 'radial nerve', 'C6-C8')],
    'anconeus': [R(M, 155, 'radial nerve', 'C7-T1')],
    'brachioradialis': [R(M, 140, 'radial nerve', 'C5-C7')],
    'extensor_carpi_radialis_longus': [R(M, 154, 'radial nerve', 'C6-C7')],
    'extensor_carpi_radialis_brevis': [R(M, 154, 'posterior interosseous nerve', 'C7-C8')],
    'extensor_digitorum': [R(M, 154, 'posterior interosseous nerve', 'C7-C8')],
    'extensor_digiti_minimi': [R(M, 155, 'posterior interosseous nerve', 'C7-C8')],
    'extensor_carpi_ulnaris': [R(M, 155, 'posterior interosseous nerve', 'C7-C8')],
    'supinator': [R(M, 157, 'posterior interosseous nerve (two branches, before and inside the muscle)', 'C5-C6')],
    'abductor_pollicis_longus': [R(M, 157, 'posterior interosseous nerve', 'C7-C8')],
    'extensor_pollicis_brevis': [R(M, 157, 'posterior interosseous nerve', 'C7-C8')],
    'extensor_pollicis_longus': [R(M, 157, 'posterior interosseous nerve', 'C7-C8')],
    'extensor_indicis': [R(M, 158, 'posterior interosseous nerve', 'C7-C8')],
    'pronator_teres': [R(M, 143, 'median nerve', 'C6-C7')],
    'flexor_carpi_radialis': [R(M, 143, 'median nerve', 'C6-C7')],
    'palmaris_longus': [R(M, 143, 'median nerve', 'C7-C8')],
    'flexor_carpi_ulnaris': [R(M, 143, 'ulnar nerve', 'C7-C8')],
    'flexor_digitorum_superficialis': [R(M, 144, 'median nerve', 'C7-T1')],
    'flexor_pollicis_longus': [R(M, 145, 'anterior interosseous branch of the median nerve', 'C8-T1')],
    'flexor_digitorum_profundus': [R(M, 146, 'medial half ulnar nerve; lateral half anterior interosseous branch of the median nerve', 'C8-T1')],
    'pronator_quadratus': [R(M, 146, 'anterior interosseous branch of the median nerve', 'C8-T1')],
    'palmaris_brevis': [R(M, 162, 'superficial branch of the ulnar nerve', 'C8-T1')],
    'lumbricals_hand': [R(M, 169, '1st and 2nd median nerve; 3rd and 4th deep branch of the ulnar nerve', 'C8-T1')],
    'abductor_pollicis_brevis': [R(M, 173, 'lateral terminal branch of the median nerve', 'C8-T1')],
    'flexor_pollicis_brevis': [R(M, 173, 'superficial head: lateral terminal branch of the median nerve (deep head listed separately)')],
    'opponens_pollicis': [R(M, 174, 'lateral terminal branch of the median nerve', 'C8-T1')],
    'adductor_pollicis': [R(M, 174, 'deep terminal branch of the ulnar nerve', 'C8-T1')],
    'abductor_digiti_minimi_hand': [R(M, 175, 'deep terminal branch of the ulnar nerve')],
    'flexor_digiti_minimi_brevis_hand': [R(M, 175, 'deep terminal branch of the ulnar nerve', 'C8-T1')],
    'opponens_digiti_minimi': [R(M, 175, 'deep terminal branch of the ulnar nerve', 'C8-T1')],
    'dorsal_interossei_hand': [R(M, 295, 'all four by the deep branch of the ulnar nerve')],
    'palmar_interossei': [R(M, 295, 'deep branch of the ulnar nerve')],
    # ---- lower limb (Mannan, Inferior Extremity) ----
    'sartorius': [R(M, 212, 'anterior division of the femoral nerve', 'L2-L3')],
    'iliacus': [R(M, 212, 'femoral nerve', 'L2-L3')],
    'psoas_major': [R(M, 213, 'ventral rami of L1-L3', 'L1-L3')],
    'pectineus': [R(M, 213, 'nerve to pectineus from the femoral nerve', 'L2-L3')],
    'rectus_femoris': [R(M, 214, 'posterior division of the femoral nerve (all four parts of quadriceps)', 'L2-L4')],
    'vastus_lateralis': [R(M, 214, 'posterior division of the femoral nerve', 'L2-L4')],
    'vastus_medialis': [R(M, 214, 'posterior division of the femoral nerve', 'L2-L4')],
    'vastus_intermedius': [R(M, 214, 'posterior division of the femoral nerve', 'L2-L4')],
    'adductor_magnus': [R(M, 223, 'posterior branch of the obturator nerve and tibial division of the sciatic nerve',
                          note='the root values printed with this entry are sacral, evidently a misprint; not used')],
    'gluteus_maximus': [R(M, 226, 'inferior gluteal nerve', 'L5-S2')],
    'gluteus_medius': [R(M, 235, 'superior gluteal nerve', 'L5-S1')],
    'gluteus_minimus': [R(M, 235, 'superior gluteal nerve', 'L5-S1')],
    'piriformis': [R(M, 235, 'nerve to piriformis (S1, S2 ventral rami, dorsal branches)', 'S1-S2')],
    'gemellus_superior': [R(M, 236, 'nerve to obturator internus', 'L5-S1')],
    'obturator_internus': [R(M, 236, 'nerve to obturator internus', 'L5-S1')],
    'gemellus_inferior': [R(M, 236, 'nerve to quadratus femoris', 'L5-S1')],
    'quadratus_femoris': [R(M, 236, 'nerve to quadratus femoris', 'L5-S1')],
    'obturator_externus': [R(M, 237, 'posterior branch of the obturator nerve', 'L3-L4')],
    'biceps_femoris': [R(M, 240, 'sciatic nerve: long head tibial part, short head common peroneal part', 'L5-S2')],
    'semitendinosus': [R(M, 240, 'tibial part of the sciatic nerve', 'L5-S2')],
    'semimembranosus': [R(M, 240, 'as semitendinosus (tibial part of the sciatic nerve)', 'L5-S2')],
    'gracilis': [R(M, 242, 'anterior branch of the obturator nerve', 'L2-L3')],
    'adductor_longus': [R(M, 242, 'anterior division of the obturator nerve', 'L2-L4')],
    'adductor_brevis': [R(M, 242, 'anterior division of the obturator nerve', 'L2-L4')],
    'tibialis_anterior': [R(M, 256, 'deep peroneal nerve', 'L4-L5')],
    'extensor_hallucis_longus': [R(M, 256, 'deep peroneal nerve', 'L5-S1')],
    'extensor_digitorum_longus': [R(M, 256, 'deep peroneal nerve', 'L5-S1')],
    'fibularis_tertius': [R(M, 256, 'deep peroneal nerve', 'L5-S1')],
    'fibularis_longus': [R(M, 259, 'superficial peroneal nerve', 'L5-S2')],
    'fibularis_brevis': [R(M, 259, 'as fibularis longus (superficial peroneal nerve)', 'L5-S2')],
    'gastrocnemius': [R(M, 263, 'two branches of the tibial nerve', 'S1-S2')],
    'soleus': [R(M, 263, 'tibial nerve', 'S1-S2')],
    'plantaris': [R(M, 264, 'tibial nerve', 'S1-S2')],
    'flexor_digitorum_longus': [R(M, 265, 'tibial nerve', 'S2-S3')],
    'flexor_hallucis_longus': [R(M, 266, 'tibial nerve', 'S2-S3')],
    'tibialis_posterior': [R(M, 266, 'tibial nerve', 'L4-L5')],
    'quadratus_plantae': [R(M, 268, 'lateral plantar nerve', 'S2-S3')],
    'extensor_digitorum_brevis': [R(M, 273, 'lateral branch of the deep peroneal nerve', 'S1-S2')],
    'abductor_hallucis': [R(M, 281, 'medial plantar nerve', 'S2-S3')],
    'flexor_digitorum_brevis': [R(M, 283, 'medial plantar nerve', 'S2-S3')],
    'abductor_digiti_minimi_foot': [R(M, 283, 'lateral plantar nerve', 'S2-S3')],
    'lumbricals_foot': [R(M, 287, '1st medial plantar nerve; 2nd-4th deep branch of the lateral plantar nerve', 'S2-S3')],
    'flexor_hallucis_brevis': [R(M, 288, 'medial plantar nerve', 'S2-S3')],
    'flexor_digiti_minimi_brevis_foot': [R(M, 289, 'superficial branch of the lateral plantar nerve', 'S2-S3')],
    'adductor_hallucis': [R(M, 290, 'deep branch of the lateral plantar nerve', 'S2-S3')],
    'plantar_interossei': [R(M, 291, '1st and 2nd deep branch, 3rd superficial branch of the lateral plantar nerve', 'S2-S3')],
    'dorsal_interossei_foot': [R(M, 295, '1st-3rd deep branch, 4th superficial branch of the lateral plantar nerve')],
    # ---- trunk, perineum ----
    'rectus_abdominis': [R(M, 310, 'ventral rami of the lower six or seven thoracic nerves', 'T6-T12')],
    'pyramidalis': [R(M, 311, 'subcostal nerve', 'T12')],
    'cremaster': [R(M, 321, 'genital branch of the genitofemoral nerve', 'L1-L2')],
    'external_oblique': [R(M, 329, 'ventral rami of the lower six thoracic nerves', 'T7-T12')],
    'internal_oblique': [R(M, 330, 'ventral rami of the lower six thoracic and the first lumbar nerves', 'T7-L1')],
    'transversus_abdominis': [R(M, 330, 'ventral rami of the lower six thoracic and the first lumbar nerves', 'T7-L1')],
    'quadratus_lumborum': [R(M, 338, 'ventral rami of T12 and the upper four lumbar nerves', 'T12-L4')],
    'bulbospongiosus': [R(M, 355, 'perineal branch of the pudendal nerve', 'S2-S4')],
    'ischiocavernosus': [R(M, 355, 'perineal branch of the pudendal nerve', 'S2-S4')],
    'superficial_transverse_perineal': [R(M, 355, 'perineal branch of the pudendal nerve', 'S2-S4')],
    'deep_transverse_perineal': [R(M, 359, 'perineal branch of the pudendal nerve', 'S2-S4')],
    'transversus_thoracis': [R(M, 406, 'corresponding intercostal nerves')],
    'serratus_posterior_superior': [R(M, 407, '2nd to 5th intercostal nerves', 'T2-T5')],
    # ---- neck and back (Mannan; Sontakke Vol. 5 tables) ----
    'platysma': [R(M, 44, 'cervical branch of the facial nerve', 'CN VII')],
    'sternohyoid': [R(M, 50, 'branch of the ansa cervicalis'), R(Y, 110, 'ansa cervicalis', 'C1-C3')],
    'sternothyroid': [R(M, 50, 'branch of the ansa cervicalis'), R(Y, 110, 'ansa cervicalis', 'C1-C3')],
    'thyrohyoid': [R(M, 76, 'C1 fibres through the hypoglossal nerve', 'C1'), R(Y, 110, 'C1 fibres through the hypoglossal nerve', 'C1')],
    'omohyoid': [R(M, 75, 'superior belly: upper root of the ansa cervicalis'), R(Y, 110, 'ansa cervicalis')],
    'cricothyroid': [R(M, 50, 'external laryngeal nerve', 'CN X')],
    'digastric': [R(M, 74, 'anterior belly: mylohyoid branch of the inferior alveolar nerve; posterior belly: facial nerve', 'CN V3 + CN VII')],
    'mylohyoid': [R(M, 75, 'mylohyoid branch of the inferior alveolar nerve', 'CN V3')],
    'geniohyoid': [R(M, 75, 'branch of the first cervical nerve through the hypoglossal nerve', 'C1')],
    'sternocleidomastoid': [R(M, 77, 'accessory nerve; ventral ramus of C2 and sometimes C3', 'CN XI')],
    'splenius_capitis': [R(M, 86, 'lateral branches of the dorsal rami of C4-C6', 'C4-C6'),
                         R(Y, 219, 'lateral branches of the posterior rami of C2-C3', 'C2-C3')],
    'splenius_cervicis': [R(Y, 219, 'lateral branches of the posterior rami of the lower cervical nerves')],
    'semispinalis_capitis': [R(M, 93, 'dorsal rami of cervical and thoracic nerves')],
    'longissimus': [R(M, 93, 'longissimus capitis: dorsal rami of lower cervical and thoracic nerves'),
                    R(Y, 220, 'posterior rami of spinal nerves')],
    'iliocostalis': [R(Y, 220, 'posterior rami of cervical, thoracic and lumbar nerves')],
    'levatores_costarum': [R(Y, 222, 'posterior rami of T1-T12', 'T1-T12')],
    'intertransversarii': [R(Y, 222, 'anterior rami of spinal nerves (intertransversarii colli and lumborum as tabulated)')],
    'rectus_capitis_anterior': [R(Y, 207, 'ventral ramus of C1', 'C1')],
    'rectus_capitis_lateralis': [R(Y, 207, 'ventral rami of C1 and C2', 'C1-C2')],
    'longus_colli': [R(Y, 207, 'ventral rami of C2-C6', 'C2-C6')],
    'longus_capitis': [R(Y, 207, 'ventral rami of C1-C3', 'C1-C3')],
    'scalenus_anterior': [R(Y, 208, 'ventral rami of C4-C6', 'C4-C6')],
    'scalenus_medius': [R(Y, 208, 'ventral rami of C3-C8', 'C3-C8')],
    'scalenus_posterior': [R(Y, 208, 'ventral rami of C6-C8', 'C6-C8')],
    'rectus_capitis_posterior_major': [R(Y, 225, 'dorsal ramus of C1 (suboccipital nerve)', 'C1')],
    'rectus_capitis_posterior_minor': [R(Y, 225, 'dorsal ramus of C1 (suboccipital nerve)', 'C1')],
    'obliquus_capitis_superior': [R(Y, 225, 'dorsal ramus of C1 (suboccipital nerve)', 'C1')],
    'obliquus_capitis_inferior': [R(Y, 225, 'dorsal ramus of C1 (suboccipital nerve)', 'C1')],
    # ---- head ----
    'frontalis': [R(M, 11, 'temporal branches of the facial nerve', 'CN VII')],
    'auricularis_anterior': [R(M, 12, 'temporal branches of the facial nerve', 'CN VII')],
    'auricularis_superior': [R(M, 12, 'temporal branches of the facial nerve', 'CN VII')],
    'auricularis_posterior': [R(M, 12, 'posterior auricular branch of the facial nerve', 'CN VII')],
    'temporalis': [R(M, 12, 'deep temporal branches of the anterior trunk of the mandibular nerve', 'CN V3')],
    'orbicularis_oculi': [R(M, 33, 'temporal and zygomatic branches of the facial nerve', 'CN VII')],
    'masseter': [R(Y, 126, 'masseteric branch of the mandibular nerve', 'CN V3')],
    'stylopharyngeus': [R(Y, 313, 'glossopharyngeal nerve', 'CN IX')],
    'superior_pharyngeal_constrictor': [R(Y, 313, 'pharyngeal plexus (vagus); every pharyngeal muscle except stylopharyngeus', 'CN X')],
    'middle_pharyngeal_constrictor': [R(Y, 313, 'pharyngeal plexus (vagus)', 'CN X')],
    'inferior_pharyngeal_constrictor': [R(Y, 313, 'pharyngeal plexus (vagus)', 'CN X')],
    'tensor_tympani': [R(Y, 365, 'mandibular nerve', 'CN V3')],
    'stapedius': [R(Y, 365, 'facial nerve', 'CN VII')],
}

# Corrections of the adopted value (only where the repo value had no opened source and the book contradicts it).
ADOPT = {
    'serratus_posterior_superior': dict(roots_text='T2-T5 (2nd-5th intercostal nerves)', ref=M, page=407,
                                        was='T1-T4', why='Mannan names the 2nd to 5th intercostal nerves; the earlier T1-T4 had no opened source.'),
}

# Clinically relevant variations (Haviarova 2024 unless stated). nerves / muscles: ids as used in innervation_groups_q342.json.
H = 'haviarova2024'
VARIATIONS = [
    dict(id='prefixed_brachial_plexus', ref=H, pages=[15, 24],
         nerves=['suprascapular_n', 'axillary_n', 'radial_n', 'musculocutaneous_n'],
         muscles=['deltoid', 'biceps_brachii', 'brachialis', 'brachioradialis', 'supinator', 'pronator_teres'],
         fact=('Prefixed brachial plexus (C4 joins): seen in 2 of 50 dissected plexuses (4 %). The roots then receive more fibres from higher roots; C4 can '
               'contribute much of the suprascapular and even the axillary nerve, and a C5 root injury can then weaken not only deltoid, biceps and '
               'brachialis but also brachioradialis, supinator and pronator teres.')),
    dict(id='postfixed_brachial_plexus', ref=H, pages=[15, 25],
         nerves=['radial_n', 'ulnar_n', 'median_n'], muscles=['triceps_brachii'],
         fact=('Postfixed brachial plexus (T2 joins): 1 of 50 (2 %). T1 then carries the fibres usually carried by C8; T1 also partly supplies '
               'triceps brachii. C4 and T2 were never seen joining the same plexus.')),
    dict(id='musculocutaneous_median_fusion', ref=H, pages=[42, 44],
         nerves=['musculocutaneous_n', 'median_n'], muscles=['biceps_brachii', 'brachialis', 'coracobrachialis'],
         fact=('Musculocutaneous and median nerves (Table 7.1): running together / fused and separating at various levels (left 3, right 3, '
               'bilateral 1); a communicating branch to the median nerve (left 3, right 2, bilateral 1); in 8 cases no separate musculocutaneous '
               'nerve, the lateral root of the median nerve being thicker (p. 44).')),
    dict(id='median_nerve_formation', ref=H, pages=[42, 44],
         nerves=['median_n'], muscles=[],
         fact=('Median nerve formation varies (Table 7.1, counted as left / right / bilateral): anastomotic branches from the medial cord (6/3/1), '
               'the posterior cord (1/3/1) or the lateral cord (2/1/0); in 9 cases the common trunk formed only in the lower half of the arm; in 5 the '
               'axillary artery lay superficial to the fork (p. 44).')),
    dict(id='radial_ulnar_and_cord_contributions', ref=H, pages=[42],
         nerves=['radial_n', 'ulnar_n'], muscles=[],
         fact='Radial-to-ulnar communicating branch (left 1, right 1); a branch of the lateral cord (left 1, right 1) or of the posterior cord (1) joining the ulnar nerve (Table 7.2).'),
    dict(id='lumbosacral_prefixed_postfixed', ref=H, pages=[15, 56, 69],
         nerves=['femoral_n', 'obturator_n', 'sciatic_n', 'pudendal_n'], muscles=[],
         fact=('Lumbosacral plexus: prefixed (2 cases: thick lumbosacral trunk, sacral plexus from L5-S2) and postfixed (1 case: thin trunk, S3-S5 '
               'distinct) patterns; never prefixed on one side and postfixed on the other. The pudendal nerve takes mainly S1-S2 when prefixed and '
               'S3 (with S4) when postfixed; S2 is its main root.')),
    dict(id='accessory_lumbar_nerves', ref=H, pages=[56, 64],
         nerves=['obturator_n', 'femoral_n', 'ilioinguinal_n'], muscles=[],
         fact=('When a T12 branch joins the lumbar plexus, accessory ilioinguinal, accessory femoral and accessory obturator nerves can arise (p. 56). '
               'The obturator nerve forms from L1-L4 in some bodies and from L2-L5 in others; a high division of its trunk and accessory obturator '
               'nerves are often seen (p. 64).')),
    dict(id='high_sciatic_division', ref=H, pages=[69],
         nerves=['sciatic_n', 'tibial_n', 'common_fibular_n'], muscles=[],
         fact='The sciatic nerve divided into tibial and common fibular parts already in the lower pelvis in 2 of 50 dissections.'),
]

# Muscle parts (gen_parts.py): what the books say about a part. verify=True upgrades verification 'unverified_textbook' ->
# 'verified_book' (attachment and/or nerve read in the book); the body status is never changed here (no book gives a boundary
# that can be drawn on the page mesh beyond what the existing rule already uses).
BOOK_PARTS = {
    ('trapezius', 'descending_part'): dict(ref=M, page=92, verify=True, fact=(
        'Upper fibres insert on the posterior border of the lateral third of the clavicle; origin listed for the whole muscle only '
        '(external occipital protuberance, medial third of the superior nuchal line, ligamentum nuchae, C7 and thoracic spines). Nerve: '
        'accessory nerve plus ventral rami of C3-C4.'), rule_check='insertion boundary of the rule (acromioclavicular junction) agrees; the origin split at C7 is not in the book'),
    ('trapezius', 'transverse_part'): dict(ref=M, page=92, verify=True, fact=(
        'Middle fibres run transversely to the medial margin of the acromion and the upper lip of the crest of the scapular spine.'),
        rule_check='insertion boundaries agree; origin levels C7-T3 are not stated in the book'),
    ('trapezius', 'ascending_part'): dict(ref=M, page=92, verify=True, fact=(
        'Lower fibres converge upward and laterally to a tendon on the tubercle at the medial end of the scapular spine.'),
        rule_check='insertion boundary (root of the spine) agrees; origin levels T4-T12 are not stated in the book'),
    ('sternocleidomastoid', 'sternal_head'): dict(ref=M, page=76, verify=True, fact=(
        'Medial (sternal) head from the upper lateral part of the anterior surface of the manubrium.')),
    ('sternocleidomastoid', 'clavicular_head'): dict(ref=M, page=77, verify=True, fact=(
        'Lateral (clavicular) head from the superior surface of the medial third of the clavicle.')),
    ('soleus', 'fibular_head'): dict(ref=M, page=263, verify=True, fact=(
        'From the back of the head of the fibula and the upper quarter of the posterior surface of its shaft.')),
    ('soleus', 'tibial_head'): dict(ref=M, page=263, verify=True, fact=(
        'From the soleal line and the middle third of the medial border of the tibia; the muscle also arises from the deep transverse fascia.')),
    ('pronator_teres', 'humeral_head'): dict(ref=M, page=140, verify=True, fact=(
        'Humeral (superficial) head from the front of the medial epicondyle, the common flexor tendon, the intermuscular septum and the '
        'antebrachial fascia; the median nerve passes between the two heads.')),
    ('pronator_teres', 'ulnar_head'): dict(ref=M, page=140, verify=True, fact=(
        'Ulnar (deep) head from the medial margin of the coronoid process; it separates the median nerve from the ulnar artery.')),
    ('flexor_digitorum_profundus', 'radial_part'): dict(ref=M, page=146, verify=True, fact=(
        'Lateral half supplied by the anterior interosseous branch of the median nerve (C8, T1). The book divides the muscle in halves by '
        'nerve, not by finger.')),
    ('flexor_digitorum_profundus', 'ulnar_part'): dict(ref=M, page=146, verify=True, fact='Medial half supplied by the ulnar nerve.'),
    ('serratus_anterior', 'superior_part'): dict(ref=M, page=121, verify=False, fact=(
        'Insertion groups: the 1st digitation to the costal surface of the superior angle; the 2nd-4th along the medial margin; the lower '
        '4 or 5 converge on the inferior angle; origin from the upper 8 or 9 ribs. This grouping (1 / 2-4 / lower 4-5) differs from the '
        'part limits recorded here (digitations 1-2 / 2-3 / 4-9).')),
    ('serratus_anterior', 'intermediate_part'): dict(ref=M, page=121, verify=False, fact='See superior part: the book\'s middle group is the 2nd-4th digitations.'),
    ('serratus_anterior', 'inferior_part'): dict(ref=M, page=121, verify=False, fact='See superior part: the book\'s lower group is the lower 4 or 5 digitations.'),
    ('latissimus_dorsi', 'iliac_part'): dict(ref=M, page=121, verify=False, fact=(
        'Origin from the posterior part of the outer lip of the iliac crest (with the lower six thoracic spines, the posterior layer of the '
        'thoracolumbar fascia and the lower 3 or 4 ribs).')),
}
