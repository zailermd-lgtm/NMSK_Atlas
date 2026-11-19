"""Shared helpers for the Q342 data generators (kept in scripts/anatomy/q342 so the data files can be regenerated)."""
import json, re, glob
from pathlib import Path

REPO = Path('/home/user/NMSK_Atlas')
SP = Path(__file__).parent
TODAY = '2026-11-15'
BODIES = {'base_m': 'm', 'base_f': 'f'}
IDS = json.load(open(SP / 'ids.json'))
IDSET = {b: set(IDS[k]) for b, k in BODIES.items()}
BANNED = ['ultrasound', 'hounsfield', 't1_se', 'imaging_tissues', 'tissue table', 'nmskultrasound',
          'acoustic', 'mrayl', 'b-mode', 'inject', 'needle', 'botulinum', 'toxin', 'dosage', 'dose ']


def side_of(i):
    return 'r' if i.endswith('_r') else 'l' if i.endswith('_l') else 'mid'


def base_of(i):
    return re.sub(r'_[lr]$', '', i)


def resolve(bases):
    """bases: list of base ids or 're:<regex>' -> {body: {'r':[], 'l':[], 'mid':[]}} of ids present on each page."""
    out = {}
    for b in BODIES:
        d = {'r': [], 'l': [], 'mid': []}
        for x in bases:
            if x.startswith('re:'):
                rx = re.compile(x[3:])
                hits = [i for i in IDSET[b] if rx.search(i)]
            else:
                hits = [i for i in IDSET[b] if base_of(i) == x or i == x]
            for h in hits:
                if h not in d[side_of(h)]:
                    d[side_of(h)].append(h)
        out[b] = {k: sorted(v) for k, v in d.items()}
    return out


def empty(res):
    return all(not v for b in res.values() for v in b.values())


def load_records():
    recs = {}
    for f in sorted(glob.glob(str(REPO / 'data/muscles/*/*_r.json'))):
        d = json.load(open(f))
        recs[d['id'][:-2]] = dict(d, _file=str(Path(f).relative_to(REPO)))
    return recs


# record base id -> extra page base ids the record-to-mesh pass (part_of_id / name) did not find
ALIASES = {
    'buccinator': ['zan_bucinator'], 'extensor_pollicis_longus': ['zan_extensor_pollicis_longus'],
    'external_intercostals': ['zan_external_intercostal_muscles'], 'internal_intercostals': ['zan_internal_intercostal_muscles'],
    'innermost_intercostals': ['zan_innermost_intercostal_muscles'], 'lumbricals_hand': ['zan_lumbrical_muscles_of_hand'],
    'lumbricals_foot': ['zan_lumbrical_muscles_of_foot'], 'lateral_cricoarytenoid': ['zan_lateral_crico_arytenoid_muscle'],
    'posterior_cricoarytenoid': ['zan_posterior_crico_arytenoid_muscle'], 'splenius_cervicis': ['zan_splenius_colli_muscle'],
    'semispinalis_cervicis': ['zan_semispinalis_colli_muscle'],
    'thyroarytenoid': ['zan_external_part_of_thyro_arytenoid_muscle', 'zan_thyro_epiglottic_part_of_thyro_arytenoid_muscle'],
    'intertransversarii': ['zan_dorsal_parts_of_lateral_intertransversarii_lumborum_muscles', 'zan_ventral_parts_of_lateral_intertransversarii_lumborum_muscles'],
    'occipitofrontalis': ['frontalis', 'zan_occipitalis_muscle'], 'stapedius': ['oa_stapedius'],
    'ischiocavernosus': ['ischiocavernosus_cvh'], 'bulbospongiosus': ['bulbospongiosus_cvh'],
    'superficial_transverse_perineal': ['superficial_transverse_perineal_cvh'],
    'adductor_magnus': ['zan_adductor_minimus'], 'rectus_femoris': ['rectus_femoris_reflected_head'],
}


def record_structures(recs):
    """record base id -> resolve() dict, from the page manifests' record links (rec.part_of_id / id / name) + ALIASES."""
    r2m = json.load(open(SP / 'rec2mesh.json'))
    out = {}
    for rid in recs:
        bases = set()
        for k in BODIES.values():
            for side in ('r', 'l'):
                bases.update(base_of(x) for x in r2m[k].get(f'{rid}_{side}', []))
        bases.update(ALIASES.get(rid, []))
        res = resolve(sorted(bases)) if bases else None
        out[rid] = res if res and not empty(res) else None
    return out


def scan_banned(obj):
    s = json.dumps(obj, ensure_ascii=False).lower()
    return [w for w in BANNED if w in s]
