"""Builds data/anatomy/muscle_parts_q342.json (schema nmsk.muscle_parts.v1)."""
import json
from common import REPO, TODAY, resolve, empty, load_records, scan_banned

SP_PARTS = json.load(open(REPO / 'data/anatomy/structure_parts.json'))
REFS_REPO = SP_PARTS['references']
RECS = load_records()

NEW_REFS = {
    'bhatt2013': dict(citation='Bhatt CR, Prajapati B, Patil DS, Patel VD, Singh BGP, Mehta CD. Variation in the insertion of the latissimus dorsi & its clinical importance. J Orthop 2013;10(1):25-28',
                      doi='10.1016/j.jor.2013.01.002', pmid='24403744', opened='PubMed abstract (2026-11-15)',
                      basis='abstract: origin from spinous processes T7-T12, thoracolumbar fascia, iliac crest, inferior 3 or 4 ribs, inferior angle of scapula; insertion floor of the intertubercular groove'),
    'urquhart2005': dict(citation='Urquhart DM, Barker PJ, Hodges PW, Story IH, Briggs CA. Regional morphology of the transversus abdominis and obliquus internus and externus abdominis muscles. Clin Biomech 2005;20(3):233-241',
                         doi='10.1016/j.clinbiomech.2004.11.007', pmid='15698694', opened='PubMed abstract (2026-11-15)',
                         basis='abstract: 26 embalmed cadavers; upper, middle and lower fascicles of transversus and obliquus internus, upper and middle fascicles of obliquus externus differ in orientation, thickness and length; obliquus internus separable into two layers in the lower and middle regions'),
    'grimaldi2009': dict(citation='Grimaldi A, Richardson C, Durbridge G, Donnelly W, Darnell R, Hides J. The association between degenerative hip joint pathology and size of the gluteus maximus and tensor fascia lata muscles. Man Ther 2009;14(6):611-617',
                         doi='10.1016/j.math.2008.11.002', pmid='19121974', opened='PubMed abstract (2026-11-15)',
                         basis='abstract: volumes measured separately for the upper (UGM) and lower (LGM) portions of gluteus maximus; the portions behave differently in hip osteoarthritis ("functional separation")'),
    'ramirez1984': dict(citation='Ramirez OM, Hurwitz DJ, Futrell JW. The expansive gluteus maximus flap. Plast Reconstr Surg 1984;74(6):757-770',
                        doi='10.1097/00006534-198412000-00003', pmid='6505096', opened='PubMed abstract (2026-11-15)',
                        basis='abstract: superficial and deep segmentation of gluteus maximus'),
    'gottschalk1989': dict(citation='Gottschalk F, Kourosh S, Leveau B. The functional anatomy of tensor fasciae latae and gluteus medius and minimus. J Anat 1989;166:179-189',
                           doi=None, pmid='2621137', pmcid='PMC1256751', opened='PubMed abstract (2026-11-15)',
                           basis='abstract: gluteus medius "with its three parts" and phasic functions'),
    'beck2000': dict(citation='Beck M, Sledge JB, Gautier E, Dora CF, Ganz R. The anatomy and function of the gluteus minimus muscle. J Bone Joint Surg Br 2000;82(3):358-363',
                     doi='10.1302/0301-620x.82b3.10356', pmid='10813169', opened='PubMed abstract (2026-11-15)',
                     basis='abstract: 16 hips; action depends on femoral position and "which part of the muscle is active"; the parts are not named in the abstract'),
    'agur2003': dict(citation='Agur AM, Ng-Thow-Hing V, Ball KA, Fiume E, McKee NH. Documentation and three-dimensional modelling of human soleus muscle architecture. Clin Anat 2003;16(4):285-293',
                     doi='10.1002/ca.10112', pmid='12794910', opened='PubMed abstract (2026-11-15)',
                     basis='abstract: fibre bundle length and pennation documented throughout the marginal, posterior and anterior soleus; architecture non-uniform'),
    'godat2004': dict(citation='Godat DM, Sanger JR, Lifchez SD, et al. Detailed neurovascular anatomy of the serratus anterior muscle: implications for a functional muscle flap with multiple independent force vectors. Plast Reconstr Surg 2004;114(1):21-29',
                      doi='10.1097/01.prs.0000129072.11466.c3', pmid='15220562', opened='PubMed abstract (2026-11-15)',
                      basis='abstract: slips 5-9 (50 specimens) supplied by one dominant thoracodorsal branch and innervated by the long thoracic nerve; slips separable to the common slip arteries'),
    'cho2023': dict(citation='Cho TH, Hong JE, Yang HM. Neuromuscular compartmentation of the subscapularis muscle [title abridged]. Sci Rep 2023;13(1):11167',
                    doi='10.1038/s41598-023-38406-0', pmid='37430018', pmcid='PMC10333283', opened='PubMed abstract (2026-11-15)',
                    basis='abstract: 10 cadavers; a distinct fascia divides subscapularis into superior and inferior compartments; upper and lower subscapular nerves supply territories mostly matching them; type I fibres 22 % superior vs 81 % inferior'),
    'q293_textbook': dict(citation="Repository data/anatomy/muscle_heads_q293.json: Gray's Anatomy for Students 4th ed. (Drake, Vogl, Mitchell); Moore's Clinically Oriented Anatomy 8th ed.",
                          doi=None, pmid=None, opened='repo file (textbook-level; page not verified)', basis='heads and their origins as listed in the repo'),
    'repo_record': dict(citation="Repository muscle records data/muscles/<region>/<muscle>_r.json ('functional_compartments[].innervation_branch'); their 'source' field cites Gray's Anatomy for Students 4th ed. and the muscle-specific papers named there",
                        doi=None, pmid=None, opened='repo file', basis='per-compartment nerve branch text'),
    'q293_rf_reflected': dict(citation='Repository Q293 rule-based mesh rectus_femoris_reflected_head_{l,r} (badge on the page): built by rule because no source mesh of the head exists',
                              doi=None, pmid=None, opened='page manifest badge', basis='rule-based geometry, hidden behind its badge'),
    'q308_psoas_minor': dict(citation='Repository Q308 rule-based mesh psoas_minor_{l,r}: hidden by default, "not demonstrated on this body" (absent in a large share of people)',
                             doi=None, pmid=None, opened='page manifest badge', basis='rule-based geometry'),
    'q219_validation': dict(citation='Repository data/derived/Q219_rule_validation.json: the deltoid azimuth-sector rule was tested leave-one-body-out against the Z-Anatomy deltoid part meshes and rejected (centroid error 6-40 mm)',
                            doi=None, pmid=None, opened='repo file', basis='precedent: a head-partition rule must be validated against real part meshes before use'),
}

USED = set()


def R(*keys):
    USED.update(keys)
    return list(keys)


def nerve_of(mid, comp):
    d = RECS.get(mid)
    if not d:
        return None
    for c in d['functional_compartments']:
        if c['id'] == f'{mid}_r_{comp}':
            return c.get('innervation_branch')
    return None


# ---------------- delimitation rules (proposals; none validated) ----------------
RULES = {
    'separate_mesh': dict(
        label='Separate structure on the page',
        method='The part is its own mesh on the page (a Z-Anatomy part object, fitted with the body). Select the listed ids; no rule needed.',
        validated=True, error='as the page mesh (its own fit badge)'),
    'separate_mesh_rule_based': dict(
        label='Separate rule-based structure on the page',
        method='The part is its own mesh, but that mesh was itself built by a documented rule (see its badge on the page). Selectable; keep its rule-based badge visible.',
        validated=False, error='see the structure badge'),
    'fan_projection_from_insertion': dict(
        label='Fan projection from the insertion (convergent muscle)',
        method=('For a muscle whose fibres converge on a compact insertion: take the centroid I of the insertion footprint '
                '(data/derived/Q220_parts_zbase_{m,f}.json insertion placement, else the contact patch on the insertion bone). '
                'For every vertex v of the muscle mesh, extend the ray I->v until it meets the origin footprint (the band where the mesh '
                'touches its origin bones / fascia). v belongs to the part whose named origin segment that ray reaches. '
                'Origin segments are the sourced ones listed in the part rows (e.g. latissimus dorsi: spinous processes T7-T12 + '
                'thoracolumbar fascia | iliac crest | lower ribs | inferior angle of scapula). Boundaries between segments are the '
                'named bony landmarks on the page (vertebra / rib / iliac-crest / scapula meshes).'),
        validated=False,
        validation_plan=('Leave-one-out against the three Z-Anatomy pectoralis major part meshes (clavicular / sternocostal / abdominal: '
                         'origin segments clavicle | sternum + costal cartilages | rectus sheath) on both Base bodies; report vertex accuracy '
                         'and centroid error. The deltoid azimuth rule failed this kind of test (q219_validation); do not display a fan '
                         'partition until it passes.'),
        error='unknown until validated'),
    'boundary_fibre_plane': dict(
        label='Boundary-fibre plane (fan with a long insertion)',
        method=('Where both origin and insertion are long lines and the parts are defined by consecutive origin segments: the boundary '
                'between two parts is the fibre running from the origin boundary landmark O_b to the insertion boundary landmark I_b. '
                'The cut is the plane through O_b and I_b that also contains the local surface normal of the muscle sheet at the midpoint '
                '(for a back muscle the body\'s antero-posterior axis). Vertices are assigned by the side of the plane.'),
        validated=False,
        validation_plan='No Z part meshes exist for trapezius or adductor magnus parts to validate against; show only as an explicitly rule-based overlay, never as anatomy.',
        error='unknown; fibres are not straight lines on a curved sheet'),
    'two_belly_axial_split': dict(
        label='Two side-by-side bellies split along the muscle axis',
        method=('Fit the principal axis of the muscle mesh (PCA). Cut by the plane that contains this axis and the antero-posterior direction '
                'of the limb segment; the named head on each side is the textbook topography (biceps brachii: long head lateral, short head '
                'medial; gastrocnemius: medial head medial, lateral head lateral).'),
        validated=False,
        validation_plan='No Z part meshes for these heads; heads are unequal in size (gastrocnemius medial head larger and longer), so a mid-plane is known to be approximate.',
        error='unknown; heads unequal'),
    'transverse_level_planes': dict(
        label='Transverse planes at named levels',
        method='Cut the mesh by planes perpendicular to the body long axis (+Y) at named bony levels given in the part rows.',
        validated=False,
        validation_plan='Check against visible tendinous intersections on the mesh if the mesh shows them; otherwise display as rule-based only.',
        error='the textbook levels are typical, not individual'),
    'nearest_origin_bone_lower_segment': dict(
        label='Nearest origin bone (only where the heads are still separate)',
        method=('For two heads that arise from different bones and fuse further along: within the segment where the heads are separate '
                '(between the origin and the point where they meet), each vertex goes to the head whose origin bone contact patch is nearer '
                'along the muscle axis. Above the fusion level the vertices are not assigned to a head.'),
        validated=False,
        validation_plan='No Z part meshes; the fusion level is not sourced numerically -> coverage incomplete by design.',
        error='unknown'),
    'not_delimitable': dict(
        label='Not delimitable honestly on this mesh',
        method=('The parts are layers (superficial / deep), are defined by fibre direction or by intramuscular septa that the mesh does not show, '
                'or the opened sources give no boundary. Listing the part (name, nerve, source) is fine; drawing it would be invented geometry.'),
        validated=None, error=None),
}


def part(pid, name, refs, *, ta=None, nerve=None, nerve_src=None, origin=None, verification='verified', note=None):
    return dict(id=pid, name=name, ta_latin=ta, origin=origin, nerve_supply=nerve, nerve_source=nerve_src,
                refs=R(*refs), verification=verification, note=note)


def mapping(status, bases=None, rule=None, **kw):
    m = dict(status=status)
    if bases:
        res = resolve(bases)
        m['structures'] = res
        if empty(res):
            m['status'] = 'missing_on_page'
    if rule:
        m['rule'] = rule
    m.update(kw)
    return m


M = []  # muscle entries


def muscle(mid, name, region, parts, *, page_whole=None, note=None, contested=None):
    whole = resolve(page_whole) if page_whole else None
    M.append(dict(muscle_id=mid, name=name, region=region,
                  whole_muscle_structures=whole if whole and not empty(whole) else None,
                  parts=parts, contested=contested, note=note))


# ---- pectoralis major
muscle('pectoralis_major', 'Pectoralis major', 'upper_limb', [
    dict(part('clavicular_head', 'Clavicular head', ['fung2009', 'q293_textbook'], ta='Pars clavicularis', origin='anterior surface of the medial half of the clavicle',
              nerve=nerve_of('pectoralis_major', 'clavicular'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_clavicular_head_of_pectoralis_major_muscle'])),
    dict(part('sternocostal_head', 'Sternocostal head', ['fung2009', 'q293_textbook'], ta='Pars sternocostalis', origin='anterior sternum and upper six costal cartilages',
              nerve=nerve_of('pectoralis_major', 'sternocostal'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_sternocostal_head_of_pectoralis_major_muscle'])),
    dict(part('abdominal_part', 'Abdominal part', ['gray42', 'q293_textbook'], ta='Pars abdominalis', origin='aponeurosis of the external oblique / anterior rectus sheath',
              nerve=nerve_of('pectoralis_major', 'abdominal'), nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('separate_mesh', ['zan_abdominal_part_of_pectoralis_major_muscle'])),
], note='No whole-muscle mesh on the Base pages: the three Z-Anatomy parts are the muscle. Validation target for the fan-projection rule (three real part meshes).')

# ---- deltoid
muscle('deltoid', 'Deltoid', 'upper_limb', [
    dict(part('clavicular_part', 'Clavicular (anterior) part', ['rispoli2009', 'vohra2024', 'sakoma2011'], ta='Pars clavicularis', origin='lateral third of the clavicle',
              nerve='axillary n., anterior branch (repo record: proximal/mid/distal fascicles)', nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_clavicular_part_of_deltoid_muscle'])),
    dict(part('acromial_part', 'Acromial (middle) part', ['rispoli2009', 'vohra2024', 'sakoma2011'], ta='Pars acromialis', origin='acromion',
              nerve=nerve_of('deltoid', 'middle_1') + ' (and central / posterior acromial fascicles)', nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_acromial_part_of_deltoid_muscle'])),
    dict(part('spinal_part', 'Spinal (posterior) part', ['rispoli2009', 'vohra2024', 'friden2001'], ta='Pars spinalis', origin='spine of the scapula',
              nerve=nerve_of('deltoid', 'posterior'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_scapular_spinal_part_of_deltoid_muscle'])),
], note='Sakoma 2011 describes seven segments delimited by intramuscular tendons; the page carries the three classical parts only.',
   contested='Segment count reported 3 or 7 (structure_parts part_set deltoid.heads).')

# ---- trapezius
TRAP_RULE = lambda a, b, oi, ii: dict(name='boundary_fibre_plane', boundary=f'{a} | {b}', origin_boundary=oi, insertion_boundary=ii,
                                      page_inputs=['trapezius', 'zan_vertebra_c7', 'zan_vertebra_t3', 'zan_vertebra_t4', 'clavicle', 'scapula'])
muscle('trapezius', 'Trapezius', 'trunk', [
    dict(part('descending_part', 'Descending (upper) part', ['gray42'], ta='Pars descendens', origin='superior nuchal line, external occipital protuberance, ligamentum nuchae',
              nerve='accessory n. (CN XI), spinal root; C3-C4 proprioceptive fibres', nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('rule', ['trapezius'], rule=TRAP_RULE('descending', 'transverse', 'spinous process of C7', 'acromioclavicular junction (lateral end of clavicle / acromion)'))),
    dict(part('transverse_part', 'Transverse (middle) part', ['gray42'], ta='Pars transversa', origin='spinous processes C7-T3',
              nerve='accessory n. (CN XI)', nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('rule', ['trapezius'], rule=dict(name='boundary_fibre_plane', between=['descending | transverse', 'transverse | ascending']))),
    dict(part('ascending_part', 'Ascending (lower) part', ['gray42'], ta='Pars ascendens', origin='spinous processes T4-T12',
              nerve='accessory n. (CN XI)', nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('rule', ['trapezius'], rule=TRAP_RULE('transverse', 'ascending', 'between the spinous processes of T3 and T4', 'root (medial end) of the spine of the scapula'))),
], page_whole=['trapezius'], note='Single mesh per side. Part definitions are textbook (Gray\'s 42nd, page not verified in the repo).')

# ---- latissimus dorsi
LD_IN = ['latissimus_dorsi', 'zan_vertebra_t7', 'zan_vertebra_t12', 'hip_bone', 'zan_ninth_rib', 'zan_tenth_rib', 'zan_eleventh_rib', 'zan_twelfth_rib', 'scapula', 'humerus']
LD = lambda seg: dict(name='fan_projection_from_insertion', origin_segment=seg, insertion='floor of the intertubercular groove (Q220 insertion placement latissimus_dorsi.insertion_q323)', page_inputs=LD_IN)
muscle('latissimus_dorsi', 'Latissimus dorsi', 'trunk', [
    dict(part('vertebral_part', 'Vertebral part (T7-T12 spinous processes, thoracolumbar fascia)', ['bhatt2013'], origin='spinous processes T7-T12 and thoracolumbar fascia',
              nerve='thoracodorsal n. (whole muscle)', nerve_src=R('repo_record'), note='Origin-defined region, not a separately sheathed head.'),
         body=mapping('rule', ['latissimus_dorsi'], rule=LD('T7-T12 + thoracolumbar fascia'))),
    dict(part('iliac_part', 'Iliac part', ['bhatt2013'], origin='iliac crest', nerve='thoracodorsal n.', nerve_src=R('repo_record'), note='Origin-defined region.'),
         body=mapping('rule', ['latissimus_dorsi'], rule=LD('iliac crest'))),
    dict(part('costal_part', 'Costal part', ['bhatt2013'], origin='inferior 3 or 4 ribs', nerve='thoracodorsal n.', nerve_src=R('repo_record'), note='Origin-defined region.'),
         body=mapping('rule', ['latissimus_dorsi'], rule=LD('lower 3-4 ribs'))),
    dict(part('scapular_part', 'Scapular part', ['bhatt2013'], origin='inferior angle of the scapula', nerve='thoracodorsal n.', nerve_src=R('repo_record'), note='Origin-defined region; inconstant.'),
         body=mapping('rule', ['latissimus_dorsi'], rule=LD('inferior angle of scapula'))),
], page_whole=['latissimus_dorsi'], note='The four regions are named here by their origin as listed in the opened source; the TA does not name latissimus parts.')

# ---- triceps
muscle('triceps_brachii', 'Triceps brachii', 'upper_limb', [
    dict(part('long_head', 'Long head', ['friden2001', 'q293_textbook'], ta='Caput longum', origin='infraglenoid tubercle', nerve=nerve_of('triceps_brachii', 'long_head'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_long_head_of_triceps_brachii'])),
    dict(part('lateral_head', 'Lateral head', ['friden2001', 'q293_textbook'], ta='Caput laterale', origin='posterior humerus above the radial groove', nerve=nerve_of('triceps_brachii', 'lateral_head'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_lateral_head_of_triceps_brachii'])),
    dict(part('medial_head', 'Medial head', ['friden2001', 'q293_textbook'], ta='Caput mediale', origin='posterior humerus below the radial groove', nerve=nerve_of('triceps_brachii', 'medial_head_superficial'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_medial_head_of_triceps_brachii'])),
])

# ---- biceps brachii
BB = dict(name='two_belly_axial_split', page_inputs=['biceps_brachii', 'humerus'], topography='long head lateral, short head medial (textbook)')
muscle('biceps_brachii', 'Biceps brachii', 'upper_limb', [
    dict(part('long_head', 'Long head', ['eames2007', 'athwal2007', 'vangsness1994', 'q293_textbook'], ta='Caput longum', origin='supraglenoid tubercle (intra-articular tendon)',
              nerve=nerve_of('biceps_brachii', 'long_head'), nerve_src=R('repo_record')),
         body=mapping('rule', ['biceps_brachii'], rule=dict(BB, side='lateral'))),
    dict(part('short_head', 'Short head', ['eames2007', 'athwal2007', 'q293_textbook'], ta='Caput breve', origin='tip of the coracoid process',
              nerve=nerve_of('biceps_brachii', 'short_head'), nerve_src=R('repo_record')),
         body=mapping('rule', ['biceps_brachii'], rule=dict(BB, side='medial'))),
], page_whole=['biceps_brachii'], note='Bellies unite distally; the split is meaningful only proximal to their junction.')

# ---- brachialis
muscle('brachialis', 'Brachialis', 'upper_limb', [
    dict(part('superficial_head', 'Superficial head', ['leonello2007']), body=mapping('not_delimitable', ['brachialis'], reason='layered heads')),
    dict(part('deep_head', 'Deep head', ['leonello2007'], note='Inferolateral fibres supplied by the radial nerve (structure_parts row).'), body=mapping('not_delimitable', ['brachialis'], reason='layered heads')),
], page_whole=['brachialis'])

# ---- quadriceps
muscle('rectus_femoris', 'Rectus femoris', 'lower_limb', [
    dict(part('straight_head', 'Straight (direct) head', ['q293_textbook'], ta='Caput rectum', origin='anterior inferior iliac spine',
              nerve=nerve_of('rectus_femoris', 'straight_head'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['rectus_femoris'], note='the whole-muscle mesh; the reflected head is the separate mesh below')),
    dict(part('reflected_head', 'Reflected (indirect) head', ['q293_textbook', 'q293_rf_reflected'], ta='Caput reflexum', origin='groove above the acetabular rim, hip capsule',
              nerve=nerve_of('rectus_femoris', 'reflected_head'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh_rule_based', ['rectus_femoris_reflected_head'])),
], page_whole=['rectus_femoris'], contested='A third (tendinous) head in 83 % of 96 sides (Tubbs 2006, PMID 17171618, muscle_heads_q293 variants); not modelled.')
muscle('vastus_lateralis', 'Vastus lateralis', 'lower_limb', [
    dict(part('oblique_head', 'Oblique head (VLO)', ['waligora2009'], note='Distinct in 60 % of 20 limbs.'),
         body=mapping('not_delimitable', ['vastus_lateralis'], reason='defined by fibre direction and a fat/fascia plane present in 60 % only')),
    dict(part('longitudinal_head', 'Longitudinal part (VLL)', ['waligora2009']), body=mapping('not_delimitable', ['vastus_lateralis'], reason='complement of the oblique head')),
], page_whole=['vastus_lateralis'])
muscle('vastus_medialis', 'Vastus medialis', 'lower_limb', [
    dict(part('longus_part', 'Vastus medialis longus (VML)', ['castanov2019'], nerve=nerve_of('vastus_medialis', 'longus'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['vastus_medialis'], reason='partition defined by fibre-bundle angle; the mesh has no fibre field')),
    dict(part('obliquus_part', 'Vastus medialis obliquus (VMO)', ['castanov2019', 'waligora2009'], nerve=nerve_of('vastus_medialis', 'obliquus'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['vastus_medialis'], reason='partition defined by fibre-bundle angle; the mesh has no fibre field')),
], page_whole=['vastus_medialis'], contested='Waligora 2009 found no distinct VMO in any of 20 limbs; Castanov 2019 describes VMO/VML partitions by architecture.')

# ---- hamstrings
muscle('biceps_femoris', 'Biceps femoris', 'lower_limb', [
    dict(part('long_head', 'Long head', ['terry1996', 'miller2007', 'q293_textbook'], ta='Caput longum', origin='ischial tuberosity (with semitendinosus)',
              nerve=nerve_of('biceps_femoris', 'long_head'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['biceps_femoris'], reason='the short head lies deep to the long head along the distal thigh; no surface boundary')),
    dict(part('short_head', 'Short head', ['terry1996', 'q293_textbook'], ta='Caput breve', origin='lateral lip of the linea aspera',
              nerve=nerve_of('biceps_femoris', 'short_head'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['biceps_femoris'], reason='deep, overlapped by the long head')),
], page_whole=['biceps_femoris'])

# ---- gluteals
muscle('gluteus_maximus', 'Gluteus maximus', 'lower_limb', [
    dict(part('upper_portion', 'Upper portion (UGM)', ['grimaldi2009'], nerve=nerve_of('gluteus_maximus', 'superior'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['gluteus_maximus'], reason='the opened abstract does not state where UGM ends; no sourced boundary')),
    dict(part('lower_portion', 'Lower portion (LGM)', ['grimaldi2009'], nerve=nerve_of('gluteus_maximus', 'inferior'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['gluteus_maximus'], reason='as above')),
], page_whole=['gluteus_maximus'], note='A superficial / deep segmentation is also described (Ramirez 1984) - layers, not drawable.', contested=None)
USED.add('ramirez1984')
muscle('gluteus_medius', 'Gluteus medius', 'lower_limb', [
    dict(part(p, f'{p.capitalize()} part', ['gottschalk1989', 'flack2012'], nerve=nerve_of('gluteus_medius', p), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['gluteus_medius'], reason='part boundaries not given in the opened source; compartments not confirmed by the systematic review (flack2012)'))
    for p in ('anterior', 'middle', 'posterior')
], page_whole=['gluteus_medius'], contested='Gottschalk 1989: three parts; Flack 2012 review: compartments suggested clinically but not confirmed.')
muscle('gluteus_minimus', 'Gluteus minimus', 'lower_limb', [], page_whole=['gluteus_minimus'],
       note='No named parts in the opened sources: Beck 2000 (abstract) reports that the action depends on "which part of the muscle is active" without naming parts. Nothing to select.')
USED.add('beck2000')

# ---- adductor magnus
AM_BFP = dict(name='boundary_fibre_plane', boundary='adductor part | hamstring part',
              origin_boundary='junction of the ischial ramus and the ischial tuberosity',
              insertion_boundary='upper margin of the adductor hiatus (between the linea-aspera and adductor-tubercle insertions)',
              page_inputs=['adductor_magnus', 'hip_bone', 'femur'])
muscle('adductor_magnus', 'Adductor magnus', 'lower_limb', [
    dict(part('adductor_minimus', 'Adductor minimus (APm)', ['maguchi2026'], nerve=nerve_of('adductor_magnus', 'adductor_part'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_adductor_minimus'])),
    dict(part('adductor_part', 'Adductor part (APs + APi)', ['maguchi2026', 'takizawa2014', 'q293_textbook'], origin='inferior pubic ramus, ischial ramus',
              nerve=nerve_of('adductor_magnus', 'adductor_part') + '; Takizawa 2014: AM2-AM4 also receive tibial-division branches', nerve_src=R('repo_record', 'takizawa2014')),
         body=mapping('rule', ['adductor_magnus'], rule=dict(AM_BFP, side='adductor'))),
    dict(part('hamstring_part', 'Hamstring (ischiocondylar) part', ['maguchi2026', 'takizawa2014', 'q293_textbook'], origin='ischial tuberosity',
              nerve=nerve_of('adductor_magnus', 'hamstring_part'), nerve_src=R('repo_record')),
         body=mapping('rule', ['adductor_magnus'], rule=dict(AM_BFP, side='hamstring'))),
], page_whole=['adductor_magnus'], contested='Component count 2 or 4 (structure_parts part_set adductor_magnus.parts).')

# ---- triceps surae
GA = dict(name='two_belly_axial_split', page_inputs=['gastrocnemius', 'femur', 'tibia'], topography='medial head medial, lateral head lateral')
muscle('gastrocnemius', 'Gastrocnemius', 'lower_limb', [
    dict(part('medial_head', 'Medial head', ['edama2015', 'szaro2009', 'delgado2002', 'q293_textbook'], ta='Caput mediale', origin='popliteal surface above the medial condyle',
              nerve=nerve_of('gastrocnemius', 'medial_head'), nerve_src=R('repo_record')),
         body=mapping('rule', ['gastrocnemius'], rule=dict(GA, side='medial'))),
    dict(part('lateral_head', 'Lateral head', ['edama2015', 'szaro2009', 'q293_textbook'], ta='Caput laterale', origin='lateral surface of the lateral femoral condyle',
              nerve=nerve_of('gastrocnemius', 'lateral_head'), nerve_src=R('repo_record')),
         body=mapping('rule', ['gastrocnemius'], rule=dict(GA, side='lateral'))),
], page_whole=['gastrocnemius'], note='The repo already records a "gastrocnemius_sector" rule as text-only for lack of a validation mesh (scripts/anatomy/q219/build_geometry.py).')
muscle('soleus', 'Soleus', 'lower_limb', [
    dict(part('fibular_head', 'Fibular head', ['q293_textbook'], origin='posterior head and upper quarter of the fibula', verification='unverified_textbook'),
         body=mapping('not_delimitable', ['soleus'], reason='heads fuse into one sheet below the tendinous arch')),
    dict(part('tibial_head', 'Tibial head', ['q293_textbook'], origin='soleal line and medial border of the tibia', verification='unverified_textbook'),
         body=mapping('not_delimitable', ['soleus'], reason='as above')),
    dict(part('architectural_parts', 'Marginal, posterior and anterior soleus', ['agur2003']),
         body=mapping('not_delimitable', ['soleus'], reason='internal (anterior bipennate) compartment; not a surface region')),
], page_whole=['soleus'])

# ---- serratus anterior
muscle('serratus_anterior', 'Serratus anterior', 'trunk', [
    dict(part(p, n, ['gray42', 'godat2004'], nerve='long thoracic n.', nerve_src=R('repo_record', 'godat2004'), verification='unverified_textbook'),
         body=mapping('not_delimitable', ['serratus_anterior'], reason='parts overlap at rib 2 in the textbook definition; a rib-of-origin rule holds near the ribs but not where the slips converge on the medial border'))
    for p, n in (('superior_part', 'Superior part (digitations 1-2)'), ('intermediate_part', 'Intermediate part (digitations 2-3)'), ('inferior_part', 'Inferior part (digitations 4-9)'))
], page_whole=['serratus_anterior'])

# ---- abdominal wall
muscle('rectus_abdominis', 'Rectus abdominis', 'trunk', [
    dict(part(f'segment_{i}', label, ['gray42'], nerve=nerve_of('rectus_abdominis', comp), nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('rule', ['rectus_abdominis'], rule=dict(name='transverse_level_planes', planes=planes, page_inputs=['rectus_abdominis', 'sternum'])))
    for i, (label, comp, planes) in enumerate([
        ('Segment 1 (above the 1st tendinous intersection)', 'seg1_superior', ['1st intersection: level of the xiphoid tip (textbook, typical)']),
        ('Segment 2', 'seg2', ['1st intersection', '2nd intersection: midway xiphoid-umbilicus (typical)']),
        ('Segment 3', 'seg3', ['2nd intersection', '3rd intersection: level of the umbilicus (typical)']),
        ('Segment 4 (below the umbilical intersection)', 'seg4_inferior', ['3rd intersection'])], 1)
], page_whole=['rectus_abdominis'], note='The umbilicus is not a structure on the page; its level would have to come from a sourced landmark (e.g. L3-L4 disc), which is itself variable -> display as rule-based only.')
muscle('external_oblique', 'External oblique', 'trunk', [
    dict(part(p, n, ['urquhart2005'], nerve='thoracoabdominal nn. T7-T11, subcostal n. (whole muscle)', nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['external_oblique'], reason='region boundaries are not given in the opened abstract'))
    for p, n in (('upper_fascicles', 'Upper fascicles'), ('middle_fascicles', 'Middle fascicles'))
], page_whole=['external_oblique'])
muscle('internal_oblique', 'Internal oblique', 'trunk', [
    dict(part('upper_fascicles', 'Upper fascicles', ['urquhart2005'], nerve=nerve_of('internal_oblique', 'main'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['internal_oblique'], reason='region boundaries not given in the opened abstract')),
    dict(part('middle_fascicles', 'Middle fascicles', ['urquhart2005'], nerve=nerve_of('internal_oblique', 'main'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['internal_oblique'], reason='as above; two layers in this region')),
    dict(part('lower_fascicles', 'Lower fascicles', ['urquhart2005'], nerve=nerve_of('internal_oblique', 'inferior_conjoint'), nerve_src=R('repo_record')),
         body=mapping('not_delimitable', ['internal_oblique'], reason='as above; two layers in this region')),
], page_whole=['internal_oblique'])

# ---- erector spinae (columns are separate meshes)
muscle('erector_spinae', 'Erector spinae', 'trunk', [
    dict(part('iliocostalis', 'Iliocostalis column', ['bustami1986', 'q293_textbook'], ta='Musculus iliocostalis', nerve='dorsal rami, segmental', nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['iliocostalis', 'zan_iliocostalis_colli_muscle'], note='zan_iliocostalis_colli_muscle exists on the left only (Q186)')),
    dict(part('longissimus', 'Longissimus column', ['bustami1986', 'q293_textbook'], ta='Musculus longissimus', nerve='dorsal rami, segmental', nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['longissimus', 'zan_longissimus_colli_muscle', 'zan_longissimus_capitis_muscle'])),
    dict(part('spinalis', 'Spinalis column', ['q293_textbook'], ta='Musculus spinalis', nerve='dorsal rami, segmental', nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('separate_mesh', ['spinalis', 'zan_spinalis_colli_muscle'])),
], note='Erector spinae is a group; each column is its own record and mesh. Bustami 1986 lumbar superficial/deep parts are not drawable (structure_parts rows).')

# ---- neck / head
SCM = dict(name='nearest_origin_bone_lower_segment', bones=['sternum', 'clavicle'], page_inputs=['sternocleidomastoid', 'sternum', 'clavicle'],
           coverage='lower segment only (below the fusion of the heads); the upper muscle is not assigned')
muscle('sternocleidomastoid', 'Sternocleidomastoid', 'head_neck', [
    dict(part('sternal_head', 'Sternal head', ['q293_textbook'], ta='Caput sternale', origin='anterior surface of the manubrium', nerve=nerve_of('sternocleidomastoid', 'sternal'), nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('rule', ['sternocleidomastoid'], rule=dict(SCM, head='sternum'))),
    dict(part('clavicular_head', 'Clavicular head', ['q293_textbook'], ta='Caput claviculare', origin='medial third of the clavicle', nerve=nerve_of('sternocleidomastoid', 'clavicular'), nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('rule', ['sternocleidomastoid'], rule=dict(SCM, head='clavicle'))),
], page_whole=['sternocleidomastoid'])
muscle('masseter', 'Masseter', 'head_neck', [
    dict(part('superficial_part', 'Superficial part', ['zwijnenburg1999'], ta='Pars superficialis', nerve=nerve_of('masseter', 'superficial'), nerve_src=R('repo_record')), body=mapping('not_delimitable', ['masseter'], reason='layers')),
    dict(part('deep_part', 'Deep part', ['zwijnenburg1999'], ta='Pars profunda', nerve=nerve_of('masseter', 'deep'), nerve_src=R('repo_record')), body=mapping('not_delimitable', ['masseter'], reason='layers')),
    dict(part('zygomaticomandibularis', 'Zygomaticomandibularis (deepest layer)', ['hwang2005']), body=mapping('not_delimitable', ['masseter'], reason='deepest layer, covered by the masseter')),
], page_whole=['masseter'])
muscle('temporalis', 'Temporalis', 'head_neck', [
    dict(part(p, n, ['sedlmayr2009']), body=mapping('not_delimitable', ['zan_temporalis_muscle'], reason='parts are layers / a deep complex; Sedlmayr 2009 treats them as one structural unit'))
    for p, n in (('superficial_part', 'Superficial part'), ('zygomatic_part', 'Zygomatic part'), ('deep_part', 'Deep part (complex)'))
], page_whole=['zan_temporalis_muscle'])

# ---- shoulder / forearm
muscle('subscapularis', 'Subscapularis', 'upper_limb', [
    dict(part('superior_compartment', 'Superior compartment', ['cho2023'], nerve='upper subscapular n.', nerve_src=R('cho2023', 'repo_record')),
         body=mapping('not_delimitable', ['subscapularis'], reason='the dividing fascia is described but its level is not given in the opened abstract')),
    dict(part('inferior_compartment', 'Inferior compartment', ['cho2023'], nerve='lower subscapular n.', nerve_src=R('cho2023', 'repo_record')),
         body=mapping('not_delimitable', ['subscapularis'], reason='as above')),
], page_whole=['subscapularis'], note='Cho 2023 is open access (PMC10333283); its full text may give the compartment boundary - not opened this round.')
muscle('supinator', 'Supinator', 'upper_limb', [
    dict(part('superficial_layer', 'Superficial layer', ['thomas2000']), body=mapping('not_delimitable', ['supinator'], reason='layers (two-layer pattern in 29 %)')),
    dict(part('deep_layer', 'Deep layer', ['thomas2000']), body=mapping('not_delimitable', ['supinator'], reason='layers')),
], page_whole=['supinator'])
muscle('flexor_digitorum_superficialis', 'Flexor digitorum superficialis', 'upper_limb', [
    dict(part('humeroulnar_head', 'Humero-ulnar head', ['gray42', 'q293_textbook'], ta='Caput humeroulnare', origin='medial epicondyle, ulnar collateral ligament, coronoid process', verification='unverified_textbook'),
         body=mapping('separate_mesh', ['zan_humero_ulnar_head_of_flexor_digitorum_superficialis'])),
    dict(part('radial_head', 'Radial head', ['gray42', 'q293_textbook'], ta='Caput radiale', origin='superior half of the anterior border of the radius', verification='unverified_textbook'),
         body=mapping('separate_mesh', ['flexor_digitorum_superficialis'],
                      note='Z-Anatomy names this mesh only "Flexor digitorum superficialis"; it lies along the anterior radius (atlas x 230-262 mm vs radius 227-289 mm, Base-M right) which fits the radial head. Name-level confirmation pending -> label "probably the radial head".')),
], note='Per-digit slips (repo record compartments digit2-digit5) are not separate meshes.')
muscle('flexor_digitorum_profundus', 'Flexor digitorum profundus', 'upper_limb', [
    dict(part('radial_part', 'Radial (index) part', ['q293_textbook'], nerve=nerve_of('flexor_digitorum_profundus', 'index'), nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('not_delimitable', ['flexor_digitorum_profundus'], reason='side-by-side bellies without a sourced boundary on the mesh')),
    dict(part('ulnar_part', 'Ulnar (middle, ring, little) part', ['q293_textbook'], nerve=nerve_of('flexor_digitorum_profundus', 'middle_ring_little'), nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('not_delimitable', ['flexor_digitorum_profundus'], reason='as above')),
], page_whole=['flexor_digitorum_profundus'], contested='Accessory (Gantzer) head to FDP in 17 % (asghar2022).')
USED.add('asghar2022')
muscle('pronator_teres', 'Pronator teres', 'upper_limb', [
    dict(part('humeral_head', 'Humeral head', ['gray42', 'hartz1981', 'q293_textbook'], ta='Caput humerale', origin='medial epicondyle', nerve='median n.', nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('not_delimitable', ['pronator_teres'], reason='the ulnar head is small and deep; the median nerve between the heads is the only boundary')),
    dict(part('ulnar_head', 'Ulnar head', ['gray42', 'q293_textbook'], ta='Caput ulnare', origin='coronoid process of the ulna', nerve='median n.', nerve_src=R('repo_record'), verification='unverified_textbook'),
         body=mapping('not_delimitable', ['pronator_teres'], reason='as above')),
], page_whole=['pronator_teres'])

# ---- iliopsoas
muscle('iliopsoas', 'Iliopsoas', 'lower_limb', [
    dict(part('psoas_major', 'Psoas major', ['q293_textbook'], ta='Musculus psoas major', origin='T12-L5 bodies, discs, transverse processes',
              nerve=nerve_of('iliopsoas', 'psoas_major'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_psoas_major'])),
    dict(part('iliacus', 'Iliacus', ['q293_textbook'], ta='Musculus iliacus', origin='iliac fossa, iliac crest, ala of sacrum',
              nerve=nerve_of('iliopsoas', 'iliacus'), nerve_src=R('repo_record')),
         body=mapping('separate_mesh', ['zan_iliacus_muscle'])),
    dict(part('psoas_minor', 'Psoas minor (inconstant)', ['q308_psoas_minor'], note='Absent in a large share of people; hidden by default on the page.'),
         body=mapping('separate_mesh_rule_based', ['psoas_minor'])),
])

# ---- pelvic floor (separate Z meshes)
muscle('levator_ani', 'Levator ani', 'trunk', [
    dict(part('pubococcygeus', 'Pubococcygeus', ['kearney2004'], ta='Musculus pubococcygeus'), body=mapping('separate_mesh', ['zan_pubococcygeus_muscle'])),
    dict(part('puboanal', 'Puboanal part (pubo-analis)', ['kearney2004'], ta='Musculus puboanalis'), body=mapping('separate_mesh', ['zan_pubo_analis_muscle'])),
    dict(part('iliococcygeus', 'Iliococcygeus', ['kearney2004'], ta='Musculus iliococcygeus'), body=mapping('separate_mesh', ['zan_iliococcygeus_muscle'])),
    dict(part('levator_ani_remainder', 'Levator ani (remaining mesh)', ['kearney2004'], note='The page also ships a mesh named "Levator ani"; which parts it holds is not stated.'),
         body=mapping('separate_mesh', ['levator_ani'])),
], note='Kearney 2004 names five origin-insertion pairs (puboperineal, pubovaginal, puboanal, puborectal, iliococcygeal); the page carries Z-Anatomy\'s pubococcygeus / pubo-analis / iliococcygeus objects.')

# ---------------- counts ----------------
def count():
    c = dict(muscles=len(M), muscles_with_parts=sum(1 for m in M if m['parts']), parts=sum(len(m['parts']) for m in M), by_status={})
    per_body = {}
    for b in ('base_m', 'base_f'):
        sep = rule = nd = sep_rb = miss = 0
        for m in M:
            for p in m['parts']:
                st = p['body']['status']
                if st == 'missing_on_page':
                    miss += 1
                elif st in ('separate_mesh', 'separate_mesh_rule_based'):
                    ok = any(p['body']['structures'][b][s] for s in ('r', 'l', 'mid'))
                    if not ok:
                        miss += 1
                    elif st == 'separate_mesh':
                        sep += 1
                    else:
                        sep_rb += 1
                elif st == 'rule':
                    rule += 1
                else:
                    nd += 1
        per_body[b] = dict(separate_mesh=sep, separate_mesh_rule_based=sep_rb, needs_rule=rule, not_delimitable=nd, missing_on_page=miss)
    c['per_body'] = per_body
    from collections import Counter
    c['by_status'] = dict(Counter(p['body']['status'] for m in M for p in m['parts']))
    c['rules_used'] = dict(Counter(p['body']['rule']['name'] for m in M for p in m['parts'] if p['body'].get('rule')))
    return c


refs = {}
for k in sorted(USED):
    if k in NEW_REFS:
        refs[k] = NEW_REFS[k]
    else:
        r = REFS_REPO[k]
        refs[k] = dict(citation=r['citation'], doi=r.get('doi'), pmid=r.get('pmid'),
                       opened=('PubMed record, verified by the project ' + r['verified'][7:]) if str(r.get('verified', '')).startswith('pubmed-') else 'not opened (textbook; page not verified)',
                       basis=r.get('basis'))

out = dict(
    schema='nmsk.muscle_parts.v1', round='Q342', generated=TODAY,
    scope='Base · Male (build/q309/viewer_zan_atlas, key base_m) and Base · Female (build/q309/viewer_base_female, key base_f) only',
    doc=dict(
        what='Selectable parts (heads, parts, fibre groups) of large or multi-part muscles, and how each maps onto the Base pages.',
        schema=('muscles[]: {muscle_id (repo record base id, or a group id such as erector_spinae), name, region, whole_muscle_structures '
                '(page ids per body and side, or null when the page has only the parts), parts[], contested, note}. '
                'parts[]: {id, name, ta_latin (Terminologia Anatomica Latin part name where standard, else null), origin, nerve_supply, '
                'nerve_source[], refs[] (keys into references), verification (verified = opened PubMed record; unverified_textbook = textbook, '
                'page not checked), note, body}. body: {status, structures {base_m|base_f: {r:[], l:[], mid:[]}}, rule?, reason?, note?}. '
                'status: separate_mesh | separate_mesh_rule_based | rule | not_delimitable | missing_on_page. '
                'rule.name is a key of rules{}; every rule is a PROPOSAL (validated=false) and must be validated before a part is drawn.'),
        ui=('Parts chooser: offer "whole muscle" + each part. separate_mesh -> select those ids. separate_mesh_rule_based -> select, keep the '
            'rule badge. rule -> show greyed with "rule-based, not validated" until an implementation passes its validation_plan; then draw '
            'with a rule-based badge citing the rule + refs. not_delimitable -> list the part (name, nerve, source) without geometry. '
            'Side: use the clicked structure\'s side; ids are given per side.'),
        honesty=('No geometry was made here. Rules are written out so an implementer can test them; the project rejected a deltoid sector rule '
                 'after validation (q219_validation), so none of these rules may be shown as anatomy before it is validated.')),
    rules=RULES, muscles=M, references=refs, counts=count())
bad = scan_banned(out)
assert not bad, bad
json.dump(out, open(REPO / 'data/anatomy/muscle_parts_q342.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out['counts'], indent=1))
