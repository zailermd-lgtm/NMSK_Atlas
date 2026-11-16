"""Builds data/anatomy/innervation_groups_q342.json (schema nmsk.innervation_groups.v1)."""
import json, re, glob
from collections import defaultdict, Counter
from books_q348 import BOOKS, ROOTS, ADOPT, VARIATIONS
from common import REPO, TODAY, resolve, empty, load_records, record_structures, scan_banned

RECS = load_records()
RSTRUCT = record_structures(RECS)
Q322 = json.load(open(REPO / 'data/anatomy/innervation_q322.json'))
ACT = json.load(open(REPO / 'data/anatomy/muscle_actions_q283.json'))
NERVES = {}
for f in sorted(glob.glob(str(REPO / 'data/nerves/*.json'))):
    for e in json.load(open(f)):
        if isinstance(e, dict):
            NERVES[e['id']] = e
for p in json.load(open(REPO / 'data/anatomy/nerve_parents_q307.json'))['parents']:
    NERVES.setdefault(p['id'], dict(id=p['id'], name=p['name'], parent_id=p['parent_id'], level='branch', plexus=None, source=p['source']))

ORDER = [f'C{i}' for i in range(1, 9)] + [f'T{i}' for i in range(1, 13)] + [f'L{i}' for i in range(1, 6)] + [f'S{i}' for i in range(1, 6)]
IDX = {v: i for i, v in enumerate(ORDER)}


def parse_roots(text):
    """-> (motor_levels[], cranial[], non_motor_levels[], segmental flag)."""
    t = text or ''
    cranial = re.findall(r'CN\s+([IVX]+(?:\s*V[123])?|V[123])', t)
    cranial = ['CN ' + c.replace(' ', '') for c in cranial]
    nonmotor = []
    motor_txt = t
    m = re.search(r'\+\s*(C\d(?:-C\d)?)\s*\((?:proprio)', t)
    if m:
        a = re.findall(r'[CTLS]\d+', m.group(1))
        nonmotor = ORDER[IDX[a[0]]:IDX[a[-1]] + 1]
        motor_txt = t.replace(m.group(0), '')
    motor_txt = re.sub(r'CN\s+[IVX]+(\s*V[123])?', ' ', motor_txt)
    toks = re.findall(r'\b([CTLS]\d{1,2})\b', motor_txt)
    toks = [x for x in toks if x in IDX]
    lv = ORDER[min(IDX[x] for x in toks):max(IDX[x] for x in toks) + 1] if toks else []
    return lv, cranial, nonmotor, 'segmental' in t.lower()


ISNCSCI = {'C5': ['biceps_brachii', 'brachialis'], 'C6': ['extensor_carpi_radialis_longus', 'extensor_carpi_radialis_brevis'],
           'C7': ['triceps_brachii'], 'C8': ['flexor_digitorum_profundus'], 'T1': ['abductor_digiti_minimi_hand'],
           'L2': ['iliacus', 'psoas_major'], 'L3': ['rectus_femoris', 'vastus_lateralis', 'vastus_medialis', 'vastus_intermedius'],
           'L4': ['tibialis_anterior'], 'L5': ['extensor_hallucis_longus'], 'S1': ['gastrocnemius', 'soleus']}
ISN_FUNC = {'C5': 'elbow flexors', 'C6': 'wrist extensors', 'C7': 'elbow extensors', 'C8': 'finger flexors (distal phalanx of the middle finger)',
            'T1': 'finger abductors (little finger)', 'L2': 'hip flexors', 'L3': 'knee extensors', 'L4': 'ankle dorsiflexors',
            'L5': 'long toe extensors', 'S1': 'ankle plantar flexors'}
ISN_OF = {m: lv for lv, ms in ISNCSCI.items() for m in ms}

# ---------------- muscle table ----------------
MUS = {}
covered = set()
for k, q in Q322['muscles'].items():
    covered.add(q['repo_record'])
    st = {b: {'r': sorted(x for x in q['structures'][b] if x.endswith('_r')), 'l': sorted(x for x in q['structures'][b] if x.endswith('_l')),
              'mid': sorted(x for x in q['structures'][b] if not x.endswith(('_r', '_l')))} for b in ('base_m', 'base_f')}
    MUS[k] = dict(muscle_id=k, name=q['name'], region=q['region'], repo_record=q['repo_record'], structures=st,
                  nerves=[n['id'] for n in q['nerve']], roots_text=q['roots']['adopted_text'],
                  roots_range_across_sources=q['roots']['range_across_sources'], roots_conflict=q['roots']['conflict'] or None,
                  sources=sorted({p['src'] for p in q['roots']['per_source']}), from_='innervation_q322')
for rid, d in RECS.items():
    if rid in covered:
        continue
    n = d['innervation']['nerve']
    MUS[rid] = dict(muscle_id=rid, name=d['name_common'], region=d['region'], repo_record=rid, structures=RSTRUCT.get(rid),
                    nerves=n if isinstance(n, list) else [n], roots_text=d['innervation']['root_levels'],
                    roots_range_across_sources=None, roots_conflict=None, sources=['repo_textbook'], from_=d['_file'])
# Q348: corrections of the adopted value from an opened book (books_q348.ADOPT), recorded on the muscle
for mid, a in ADOPT.items():
    m = MUS[mid]
    assert m['roots_text'].startswith(a['was']), (mid, m['roots_text'])
    m['corrected_q348'] = dict(was=m['roots_text'], now=a['roots_text'], ref=a['ref'], page=a['page'], why=a['why'])
    m['roots_text'] = a['roots_text']
    m['sources'] = sorted((set(m['sources']) - {'repo_textbook'}) | {a['ref']})
for m in MUS.values():
    lv, cn, nm, seg = parse_roots(m['roots_text'])
    m.update(motor_levels=lv, cranial_nerves=cn, non_motor_levels=nm or None, segmental=seg,
             on_base_pages=bool(m['structures']) and not empty(m['structures']),
             isncsci_key_muscle_for=ISN_OF.get(m['muscle_id']))
    m['source_of_roots'] = m.pop('from_')


def _span(levels):
    return levels[0] if len(levels) == 1 else f'{levels[0]}-{levels[-1]}' if levels else ''


# Q348: book check of every muscle the owner's books describe (books_q348.ROOTS): agrees | differs | nerve_only
for mid, entries in ROOTS.items():
    m = MUS[mid]
    blv, bcn = set(), set()
    for e in entries:
        lv, cn, _, _ = parse_roots(e['roots'] or '')
        e2 = dict(e, levels=_span(lv) or None)
        blv |= set(lv)
        bcn |= set(cn)
        e.update(levels=e2['levels'])
    mine_lv, mine_cn = set(m['motor_levels']), set(m['cranial_nerves'])
    if blv and mine_lv:
        status = 'agrees' if blv == mine_lv else 'differs'
    elif bcn and mine_cn and not blv:
        status = 'agrees' if bcn <= mine_cn else 'differs'
    elif blv or bcn:
        status = 'differs' if (blv and not mine_lv) or (bcn and not mine_cn) else 'agrees'
    else:
        status = 'nerve_only'
    prev = set(parse_roots(m['roots_range_across_sources'] or '')[0])
    union = sorted(blv | mine_lv | prev, key=IDX.get)
    m['book_check_q348'] = dict(status=status, entries=[{k: v for k, v in e.items() if v is not None} for e in entries],
                                books_levels=_span(sorted(blv, key=IDX.get)) or None)
    m['sources'] = sorted(set(m['sources']) | {e['ref'] for e in entries})
    if status == 'differs' and blv:
        was = f"; earlier range {m['roots_range_across_sources']}" if m['roots_range_across_sources'] else ''
        m['roots_range_across_sources'] = (f"{_span(union)} across sources (adopted {m['roots_text']}{was}; "
                                           + '; '.join(f"{BOOKS[e['ref']]['short']} p. {e['page']}: {e['levels']}" for e in entries if e.get('levels')) + ')')
VAR_OUT = []
for v in VARIATIONS:
    for n in v['nerves']:
        assert n in NERVES or any(n == x for x in NERVES), n
    for mid in v['muscles']:
        MUS[mid].setdefault('variation_notes_q348', []).append(v['id'])
    VAR_OUT.append(dict(v))

# ---------------- root family ----------------
root_levels = {lv: [] for lv in ORDER}
cranial = defaultdict(list)
unparsed = []
for m in MUS.values():
    if not m['on_base_pages']:
        continue
    entry = dict(muscle_id=m['muscle_id'], roots_text=m['roots_text'], range_across_sources=m['roots_range_across_sources'],
                 sources=m['sources'], segmental=m['segmental'] or None, isncsci_key_muscle=(m['isncsci_key_muscle_for'] is not None) or None)
    for lv in m['motor_levels']:
        root_levels[lv].append(entry)
    for c in m['cranial_nerves']:
        cranial[c].append(dict(muscle_id=m['muscle_id'], roots_text=m['roots_text'], sources=m['sources']))
    if not m['motor_levels'] and not m['cranial_nerves']:
        unparsed.append(dict(muscle_id=m['muscle_id'], roots_text=m['roots_text']))
root_family = dict(
    label='Root (myotome)',
    rule=('A muscle is listed under every spinal level of its adopted root range (innervation_q322 muscles: the adopted textbook range, with the range '
          'across the sources Q322 reviewed; all other muscles: the repo record\'s root_levels). Ranges are textbook ranges, not the dominant root. '
          'Proprioceptive-only roots (trapezius C3-C4, sternocleidomastoid C2-C3) are not listed as motor levels.'),
    levels={lv: dict(members=sorted(v, key=lambda e: e['muscle_id']),
                     isncsci_key_muscles=dict(function=ISN_FUNC[lv], members=ISNCSCI[lv]) if lv in ISNCSCI else None)
            for lv, v in root_levels.items() if v},
    cranial={k: sorted(v, key=lambda e: e['muscle_id']) for k, v in sorted(cranial.items())},
    no_level_in_source=sorted(unparsed, key=lambda e: e['muscle_id']),
    isncsci_note='Key muscles of the ISNCSCI motor exam (one function per level C5-T1, L2-S1) are flagged; source isncsci2019 (citation as recorded in innervation_q322; the full text was not returned there).')

# ---------------- peripheral family ----------------
direct = defaultdict(list)
for m in MUS.values():
    if not m['on_base_pages']:
        continue
    for n in m['nerves']:
        role = 'proprioceptive (record)' if n.startswith('cervical_plexus_root_') and m['non_motor_levels'] else 'motor'
        direct[n].append(dict(muscle_id=m['muscle_id'], role=role))


def chain(n):
    seen, out = set(), []
    while n and n in NERVES and n not in seen:
        seen.add(n); out.append(n); n = NERVES[n].get('parent_id')
    return out


nodes = {}
for n in list(direct):
    for a in chain(n):
        nodes.setdefault(a, dict(id=a, name=NERVES[a].get('name'), parent=NERVES[a].get('parent_id'), level=NERVES[a].get('level'),
                                  plexus=NERVES[a].get('plexus'), roots=NERVES[a].get('root_contributions'), direct_members=[], all_members=[]))
    if n not in NERVES:
        nodes.setdefault(n, dict(id=n, name=n.replace('_', ' '), parent=None, level=None, plexus=None, roots=None,
                                  direct_members=[], all_members=[], note='not in the nerve registry (data/nerves)'))
for n, ms in direct.items():
    nodes[n]['direct_members'] = sorted(ms, key=lambda e: e['muscle_id'])
    for a in (chain(n) or [n]):
        for e in ms:
            if e['muscle_id'] not in [x['muscle_id'] for x in nodes[a]['all_members']]:
                nodes[a]['all_members'].append(dict(muscle_id=e['muscle_id'], via=n, role=e['role']))
for v in nodes.values():
    v['all_members'].sort(key=lambda e: e['muscle_id'])
    v['cranial'] = bool(v['plexus'] and 'cranial' in str(v['plexus'])) or v['id'].startswith(('facial_n', 'trigeminal', 'oculomotor', 'trochlear', 'abducens', 'hypoglossal', 'vagus', 'accessory', 'glossopharyngeal'))
tops = sorted(k for k, v in nodes.items() if not v['parent'] or v['parent'] not in nodes)
peripheral_family = dict(
    label='Peripheral nerve',
    rule=('Members of a nerve = muscles whose record names that nerve or any of its branches (parent links from the repo nerve registry '
          'data/nerves/*.json, Gray\'s Anatomy for Students / Moore / TA, plus data/anatomy/nerve_parents_q307.json). Cranial nerves included.'),
    top_level=tops, nerves=dict(sorted(nodes.items())))

# ---------------- central (upper-motor-neuron) patterns ----------------
GUIDE = {
    'shoulder': ['teres_major', 'subscapularis', 'latissimus_dorsi', 'pectoralis_major', 'pectoralis_minor'],
    'elbow': ['biceps_brachii', 'brachialis', 'brachioradialis', 'extensor_carpi_radialis_longus', 'extensor_carpi_radialis_brevis', 'pronator_teres', 'triceps_brachii'],
    'wrist': ['flexor_carpi_radialis', 'palmaris_longus', 'flexor_carpi_ulnaris', 'flexor_digitorum_superficialis', 'flexor_digitorum_profundus', 'extensor_carpi_ulnaris',
              'extensor_digiti_minimi', 'extensor_digitorum', 'pronator_quadratus', 'flexor_pollicis_longus', 'abductor_pollicis_longus', 'extensor_pollicis_longus',
              'extensor_pollicis_brevis', 'extensor_indicis'],
    'hand': ['abductor_pollicis_brevis', 'opponens_pollicis', 'flexor_pollicis_brevis', 'palmar_interossei', 'dorsal_interossei_hand', 'adductor_pollicis', 'lumbricals_hand'],
    'hip': ['piriformis', 'iliopsoas', 'sartorius', 'adductor_longus', 'adductor_brevis', 'adductor_magnus', 'gracilis'],
    'knee': ['biceps_femoris', 'semitendinosus', 'semimembranosus', 'rectus_femoris', 'vastus_lateralis', 'vastus_medialis', 'vastus_intermedius'],
    'ankle_foot': ['gastrocnemius', 'tibialis_posterior', 'soleus', 'flexor_digitorum_longus', 'tibialis_anterior', 'extensor_digitorum_longus', 'extensor_hallucis_longus',
                   'flexor_hallucis_longus', 'flexor_digitorum_brevis', 'fibularis_longus', 'fibularis_brevis', 'flexor_hallucis_brevis'],
}
F = lambda *j: [f'f{i}_{x}' for x in j for i in range(2, 6)]
FINGER_FLEX = [(['f2_mcp', 'f3_mcp', 'f4_mcp', 'f5_mcp'], 'flex', 1), (['f2_pip', 'f3_pip', 'f4_pip', 'f5_pip'], 'flex', 1), (['f2_dip', 'f3_dip', 'f4_dip', 'f5_dip'], 'flex', 1),
               (['f2_mcp', 'f3_mcp', 'f4_mcp'], 'flex', 1), ('f5_mcp', 'flex', 1)]
THUMB_IN = [('thumb_cmc', 'abd', -1), ('thumb_cmc', 'flex', 1), ('thumb_mcp', 'flex', 1), ('thumb_ip', 'flex', 1)]
TOE_FLEX = [(['t2_pip', 't3_pip', 't4_pip', 't5_pip'], 'flex', 1), (['t2_dip', 't3_dip', 't4_dip', 't5_dip'], 'flex', 1), ('t1_ip', 'flex', 1)]


def C(label, moves, src, opened=True, all_of=False):
    return dict(label=label, moves=[list(m) for m in moves], source=src, opened=opened, all_of=all_of)


def key(j):
    return tuple(j) if isinstance(j, list) else (j,)


def match_rows(moves, all_of):
    want = {(key(j), d, s) for j, d, s in moves}
    hits = defaultdict(list)
    for r in ACT['rows']:
        have = {(key(mv[0]), mv[1], mv[2]) for mv in r["mv"]}
        ok = want <= have if all_of else bool(want & have)
        if ok:
            hits[(r['m'], r['c'])].append(r['q'])
    return hits


PART_MESH = {('deltoid', 'anterior_1'): 'zan_clavicular_part_of_deltoid_muscle', ('deltoid', 'anterior_2'): 'zan_clavicular_part_of_deltoid_muscle',
             ('deltoid', 'anterior_3'): 'zan_clavicular_part_of_deltoid_muscle', ('deltoid', 'posterior'): 'zan_scapular_spinal_part_of_deltoid_muscle',
             ('pectoralis_major', 'clavicular'): 'zan_clavicular_head_of_pectoralis_major_muscle', ('pectoralis_major', 'sternocostal'): 'zan_sternocostal_head_of_pectoralis_major_muscle',
             ('pectoralis_major', 'abdominal'): 'zan_abdominal_part_of_pectoralis_major_muscle', ('triceps_brachii', 'long_head'): 'zan_long_head_of_triceps_brachii',
             ('iliopsoas', 'iliacus'): 'zan_iliacus_muscle', ('iliopsoas', 'psoas_major'): 'zan_psoas_major'}


def structures_for(m, c):
    if (m, c) in PART_MESH:
        return resolve([PART_MESH[(m, c)]])
    return RSTRUCT.get(m)


def pattern(pid, name, limb, kind, comps, refs, *, sections=None, named=None, note=None, status='ok', not_opened_components=None):
    members = {}
    for comp in comps:
        if not comp['moves']:
            continue
        for (m, c), qs in match_rows(comp['moves'], comp['all_of']).items():
            k = f'{m}.{c}' if c else m
            e = members.setdefault(k, dict(muscle_id=m, part=c, components=[], action_quotes=[], structures=structures_for(m, c)))
            e['components'].append(comp['label'])
            e['action_quotes'] += [q for q in qs if q not in e['action_quotes']]
    in_sec = set(x for s in (sections or []) for x in GUIDE[s])
    for e in members.values():
        e['tier'] = 'named_in_guide' if named and e['muscle_id'] in named else 'guide_section_and_action' if e['muscle_id'] in in_sec else 'action_only'
    act_muscles = {r['m'] for r in ACT['rows']}
    for mname in sorted(in_sec - {e['muscle_id'] for e in members.values()}):
        if mname in act_muscles:
            continue  # has sourced actions, none of them produces this posture -> not a member
        members[mname] = dict(muscle_id=mname, part=None, components=[], action_quotes=[], structures=RSTRUCT.get(mname),
                              tier='named_in_guide' if named and mname in named else 'guide_section_only')
    for mname in (named or []):
        if mname not in {e['muscle_id'] for e in members.values()}:
            members[mname] = dict(muscle_id=mname, part=None, components=[], action_quotes=[], structures=RSTRUCT.get(mname), tier='named_in_guide')
    for e in members.values():
        opp = []
        for comp in comps:
            if not comp['moves'] or comp['all_of']:
                continue
            rev = [(j, d, -sg) for j, d, sg in comp['moves']]
            if (e['muscle_id'], e['part']) in match_rows(rev, False) and comp['label'] not in e['components']:
                opp.append(comp['label'])
        e['opposes'] = opp or None
    mem = sorted(members.values(), key=lambda e: (['named_in_guide', 'guide_section_and_action', 'action_only', 'guide_section_only'].index(e['tier']), e['muscle_id'], e['part'] or ''))
    for e in mem:
        if not e['structures'] or empty(e['structures']):
            e['structures'] = None
    return dict(id=pid, name=name, limb=limb, kind=kind, status=status, components=comps, components_not_in_opened_sources=not_opened_components,
                guide_sections=sections, refs=refs, members=mem, note=note, rule_based_membership=True)


G = 'guv2026'
P = []
# --- synergies
P.append(pattern('ul_flexion_synergy', 'Upper-limb flexion synergy', 'upper', 'synergy', [
    C('shoulder abduction', [('shoulder', 'abd', 1)], 'mcpherson2019'),
    C('shoulder flexion with elbow flexion', [('shoulder', 'flex', 1)], 'avni2024'),
    C('elbow flexion', [('elbow', 'flex', 1)], 'avni2024'),
    C('wrist and finger flexion', [('wrist', 'flex', 1)] + FINGER_FLEX, 'mcpherson2019')], ['mcpherson2019', 'avni2024', 'brunnstrom1970'],
    not_opened_components=['scapular retraction / elevation', 'shoulder external rotation', 'forearm supination (classic Brunnstrom description; book not opened)'],
    note='Components from the opened abstracts: shoulder abduction elicits elbow, wrist and finger flexion torque (McPherson 2019); "flexor synergy (shoulder and elbow flexion)" (Avni 2024).'))
P.append(pattern('ul_extension_synergy', 'Upper-limb extension synergy', 'upper', 'synergy', [
    C('shoulder adduction', [('shoulder', 'abd', -1)], 'mcpherson2019'),
    C('elbow extension (opposite to the flexion synergy at the elbow)', [('elbow', 'flex', -1)], 'mcpherson2019'),
    C('wrist and finger flexion', [('wrist', 'flex', 1)] + FINGER_FLEX, 'mcpherson2019')], ['mcpherson2019', 'brunnstrom1970'],
    not_opened_components=['shoulder internal rotation', 'forearm pronation (classic Brunnstrom description; book not opened)'],
    note='McPherson 2019: shoulder adduction produced mainly wrist and finger flexion; elbow and forearm torques were opposite in direction to those of the flexion synergy.'))
P.append(pattern('ll_extension_synergy', 'Lower-limb extension synergy', 'lower', 'synergy', [
    C('hip extension', [('hip', 'flex', -1)], 'sheffler2015'), C('hip adduction', [('hip', 'abd', -1)], 'sheffler2015'),
    C('knee extension', [('knee', 'flex', -1)], 'sheffler2015'), C('ankle plantar flexion', [('ankle', 'dp', -1)], 'sheffler2015'),
    C('foot inversion', [('subtalar', 'inv', 1)], 'sheffler2015')], ['sheffler2015'],
    note='Sheffler 2015 (abstract): hemiparetic gait is associated with an extensor synergy pattern of hip extension and adduction, knee extension, ankle plantar flexion and inversion.'))
P.append(dict(id='ll_flexion_synergy', name='Lower-limb flexion synergy', limb='lower', kind='synergy', status='not_sourced_in_session', components=[],
              refs=['brunnstrom1970'], members=[], rule_based_membership=True,
              note='No opened source lists its components this round (Brunnstrom 1970 not opened). Hidden until sourced.'))
# --- Hefter arm spasticity patterns
SH = [C('shoulder adduction', [('shoulder', 'abd', -1)], 'hefter2012'), C('shoulder internal rotation', [('shoulder', 'rot', 1)], 'hefter2012')]
EF = C('elbow flexion', [('elbow', 'flex', 1)], 'hefter2012')
P.append(pattern('hefter_asp_i', 'Arm spasticity pattern I (Hefter)', 'upper', 'hefter_asp', SH + [EF,
    C('forearm supination', [('forearm', 'sup', 1)], 'filippetti2024'), C('wrist flexion', [('wrist', 'flex', 1)], 'filippetti2024')], ['hefter2012', 'filippetti2024'],
    note='Definition as restated by Filippetti 2024 (full text opened); 24.8 % of 665 stroke patients.'))
P.append(pattern('hefter_asp_ii', 'Arm spasticity pattern II (Hefter)', 'upper', 'hefter_asp', [
    C('wrist extension', [('wrist', 'flex', -1)], 'filippetti2024')], ['hefter2012', 'filippetti2024'],
    not_opened_components=['shoulder', 'elbow', 'forearm (the opened sources state only that pattern II has an extended wrist)'],
    note='Incomplete definition in the opened sources.'))
P.append(pattern('hefter_asp_iii', 'Arm spasticity pattern III (Hefter)', 'upper', 'hefter_asp', SH + [EF,
    C('forearm neutral', [], 'hefter2012'), C('wrist neutral', [], 'hefter2012')], ['hefter2012'],
    note='Most frequent pattern: 41.8 % of 665 stroke patients (Hefter 2012 abstract).'))
P.append(pattern('hefter_asp_iv', 'Arm spasticity pattern IV (Hefter)', 'upper', 'hefter_asp', SH + [EF,
    C('forearm pronation', [('forearm', 'sup', -1)], 'filippetti2024'), C('wrist flexion', [('wrist', 'flex', 1)], 'filippetti2024')], ['hefter2012', 'filippetti2024'],
    note='Components from Filippetti 2024, whose MS pattern 4 is described as "similar" to Hefter pattern IV; check against Hefter 2012 Table.'))
P.append(pattern('hefter_asp_v', 'Arm spasticity pattern V (Hefter)', 'upper', 'hefter_asp', [
    C('elbow extension', [('elbow', 'flex', -1)], 'filippetti2024')], ['hefter2012', 'filippetti2024'],
    not_opened_components=['shoulder', 'forearm', 'wrist (the opened sources state only that pattern V has an extended elbow)'],
    note='Incomplete definition in the opened sources.'))
# --- regional patterns named in the 2026 guide (full text opened)
P.append(pattern('shoulder_adduction_internal_rotation', 'Adducted, internally rotated shoulder', 'upper', 'regional', SH[:1] + SH[1:], [G], sections=['shoulder']))
P[-1]['components'] = [dict(c, source=G) for c in P[-1]['components']]
P.append(pattern('elbow_flexion_pronation', 'Flexed elbow with pronated forearm', 'upper', 'regional', [
    C('elbow flexion', [('elbow', 'flex', 1)], G), C('forearm pronation', [('forearm', 'sup', -1)], G)], [G], sections=['elbow'],
    note='Guide: the most prevalent upper-extremity pattern.'))
P.append(pattern('elbow_extension', 'Extended elbow', 'upper', 'regional', [C('elbow extension', [('elbow', 'flex', -1)], G)], [G], sections=['elbow'], named=['triceps_brachii'],
                 note='Guide: less frequent; spasticity of the triceps.'))
P.append(pattern('wrist_flexion_ulnar_deviation', 'Flexed wrist with ulnar deviation', 'upper', 'regional', [
    C('wrist flexion', [('wrist', 'flex', 1)], G), C('ulnar deviation', [('wrist', 'dev', -1)], G)], [G], sections=['wrist']))
P.append(pattern('wrist_extension', 'Extended wrist', 'upper', 'regional', [C('wrist extension', [('wrist', 'flex', -1)], G)], [G], sections=['wrist'],
                 note='Guide: may manifest in some cases.'))
P.append(pattern('clenched_fist_thumb_in_palm', 'Clenched fist with thumb-in-palm', 'upper', 'regional', [
    C('finger flexion', FINGER_FLEX, G), C('thumb flexion / adduction into the palm', THUMB_IN, G)], [G], sections=['hand', 'wrist'],
    note='Guide: the most prevalent hand pattern.'))
P.append(pattern('intrinsic_plus_hand', 'Intrinsic-plus hand', 'upper', 'regional', [
    C('MCP flexion with IP extension (both actions in one muscle)', [(['f2_mcp', 'f3_mcp', 'f4_mcp', 'f5_mcp'], 'flex', 1), (['f2_pip', 'f3_pip', 'f4_pip', 'f5_pip'], 'flex', -1)], G, all_of=True),
    C('MCP flexion with IP extension (index-ring)', [(['f2_mcp', 'f3_mcp', 'f4_mcp'], 'flex', 1), (['f2_pip', 'f3_pip', 'f4_pip'], 'flex', -1)], G, all_of=True)], [G], sections=['hand'],
    note='Guide names the pattern; "MCP flexion with IP extension" is the definition used for the action rule (definition not given in the guide).'))
P.append(pattern('hip_flexion', 'Flexed hip', 'lower', 'regional', [C('hip flexion', [('hip', 'flex', 1)], G)], [G], sections=['hip']))
P.append(pattern('thigh_adduction', 'Adducted thigh (scissoring)', 'lower', 'regional', [C('hip adduction', [('hip', 'abd', -1)], G)], [G], sections=['hip']))
P.append(pattern('stiff_knee', 'Stiff knee', 'lower', 'regional', [C('knee extension', [('knee', 'flex', -1)], G)], [G], sections=['knee'],
                 named=['rectus_femoris', 'vastus_lateralis', 'vastus_medialis', 'vastus_intermedius'], note='Guide: knee-extensor spasticity is a primary contributor to stiff-knee gait.'))
P.append(pattern('flexed_knee', 'Flexed knee (crouch)', 'lower', 'regional', [C('knee flexion', [('knee', 'flex', 1)], G)], [G], sections=['knee'],
                 named=['biceps_femoris', 'semitendinosus', 'semimembranosus'], note='Guide: hamstring spasticity causes excessive knee flexion.'))
P.append(pattern('equinovarus_foot', 'Equinovarus foot', 'lower', 'regional', [
    C('ankle plantar flexion (equinus)', [('ankle', 'dp', -1)], G), C('foot inversion (varus)', [('subtalar', 'inv', 1)], G)], [G], sections=['ankle_foot'],
    note='Guide: the most commonly seen lower-limb pattern.'))
P.append(pattern('great_toe_hyperextension', "Hyperextended great toe (hitchhiker's great toe)", 'lower', 'regional', [
    C('great-toe MTP extension', [('t1_mtp', 'flex', -1)], G)], [G], sections=['ankle_foot']))
P.append(pattern('clawing_toes', 'Clawing toes', 'lower', 'regional', [C('flexion of the lesser toes and great-toe IP', TOE_FLEX, G)], [G], sections=['ankle_foot'],
                 note='Guide names "clawing toes" without defining it; the action rule uses toe interphalangeal flexion.'))

central_family = dict(
    label='Central pattern (upper-motor-neuron posture)',
    rule=('Each pattern is a set of joint positions taken from an opened source. Members are DERIVED BY RULE (badge: rule-based): a muscle is a member '
          'when one of its sourced actions in data/anatomy/muscle_actions_q283.json (actions quoted from data/muscles records or cited papers) '
          'produces one of the pattern\'s joint positions. tier: named_in_guide (the source names the muscle for this pattern) > guide_section_and_action '
          '(listed in the guide\'s section for that region and the action matches) > action_only (action matches; not listed by the guide) > '
          'guide_section_only (listed in the guide\'s region section and the repo action table has no action for it at all). Default view: the first two tiers.'),
    excluded=('Decorticate and decerebrate postures: no muscle-level source was opened -> not offered. "Striatal toe" is not used: the opened guide '
              'names "hyperextension of the great toe" / "Hitchhiker\'s great toe".'),
    patterns=P)

REFS = {
    'guv2026': dict(citation='Güvener O, İnce B, Keçeli C, Tok F, Ricci V, Mezian K, Jačisko J, Chang KV, Kara M, Kaymak B, Özçakar L. EURO-MUSCULUS/USPRM Spasticity Guide [title abridged]. Eur J Phys Rehabil Med 2026;62(5):441-459',
                    doi='10.23736/S1973-9087.26.09497-9', pmid=None, opened='full text (owner-supplied PDF, read 2026-11-15)', licence='CC BY-NC-ND 4.0 (facts extracted; no text or figures reproduced)'),
    'hefter2012': dict(citation='Hefter H, Jost WH, Reissig A, Zakine B, Bakheit AM, Wissel J. Classification of posture in poststroke upper limb spasticity [title abridged]. Int J Rehabil Res 2012;35(3):227-233',
                       doi='10.1097/MRR.0b013e328353e3d4', pmid='22555318', opened='PubMed abstract (2026-11-15); full text not opened'),
    'filippetti2024': dict(citation='Filippetti M, et al. Classification of upper limb spasticity patterns in patients with multiple sclerosis: a pilot observational study. J Rehabil Med 2024;56:jrm40548',
                           doi='10.2340/jrm.v56.40548', pmid='39185546', pmcid='PMC11367677', opened='PMC full text (2026-11-15)',
                           note='Restates Hefter patterns I (shoulder IR/adduction, elbow flexion, supination, wrist flexion), III (shoulder IR/adduction, elbow flexion, forearm and wrist neutral); II has an extended wrist, V an extended elbow; frequencies III > I > IV > II > V.'),
    'mcpherson2019': dict(citation='McPherson LM, Dewald JPA. Differences between flexion and extension synergy-driven coupling at the elbow, wrist, and fingers of individuals with chronic hemiparetic stroke. Clin Neurophysiol 2019',
                          doi=None, pmid=None, opened='abstract via the Consensus search tool (2026-11-15)'),
    'avni2024': dict(citation='Avni I, et al. The kinematics of 3D arm movements in sub-acute stroke: impaired inter-joint coordination is attributable to both weakness and flexor synergy intrusion. Neurorehabil Neural Repair 2024',
                     doi=None, pmid=None, opened='abstract via the Consensus search tool (2026-11-15)'),
    'sheffler2015': dict(citation='Sheffler LR, Chae J. Hemiparetic gait. Phys Med Rehabil Clin N Am 2015',
                         doi=None, pmid=None, opened='abstract via the Consensus search tool (2026-11-15)'),
    'brunnstrom1970': dict(citation='Brunnstrom S. Movement Therapy in Hemiplegia: A Neurophysiological Approach. Harper & Row, 1970',
                           doi=None, pmid=None, opened=False, note='NOT opened; cited only to name the classic components that are missing from the opened sources.'),
    'repo_textbook': dict(citation=Q322['sources']['repo_textbook']['citation'], doi=None, pmid=None, opened='repo files (textbook-level)'),
    'repo_registry': dict(citation="Repository nerve registry data/nerves/*.json (Gray's Anatomy for Students 4th ed.; Moore 8th ed.; TA) + data/anatomy/nerve_parents_q307.json", doi=None, pmid=None, opened='repo files'),
    'q283_actions': dict(citation='Repository data/anatomy/muscle_actions_q283.json (each row quotes a muscle action from data/muscles records or a cited paper)', doi=None, pmid=None, opened='repo file'),
}
for k, b in BOOKS.items():
    if k == 'carp2015' or any(k in m['sources'] for m in MUS.values()) or any(v['ref'] == k for v in VARIATIONS):
        REFS[k] = {kk: vv for kk, vv in b.items() if kk != 'kind'}
for k, s in Q322['sources'].items():
    if k in REFS or not any(k in m['sources'] for m in MUS.values()):
        continue
    REFS[k] = dict(citation=s['citation'], doi=s.get('doi'), pmid=s.get('pmid'), opened=f"as recorded in innervation_q322 ({s.get('accessed')})")

muscles_out = {k: {kk: vv for kk, vv in v.items()} for k, v in sorted(MUS.items())}
out = dict(
    schema='nmsk.innervation_groups.v1', round='Q342', generated=TODAY,
    scope='Base · Male (base_m) and Base · Female (base_f)',
    doc=dict(
        what='Innervation group families for the "Related structures" menu: root (myotome), peripheral nerve, central pattern.',
        schema=('muscles{id: {muscle_id, name, region, repo_record, structures {base_m|base_f: {r,l,mid}}, nerves[], roots_text, motor_levels[], '
                'cranial_nerves[], non_motor_levels, segmental, roots_range_across_sources, roots_conflict, sources[], source_of_roots, on_base_pages, '
                'isncsci_key_muscle_for, book_check_q348 {status agrees|differs|nerve_only, entries[] {ref, page, nerve, roots, levels, note}, '
                'books_levels}, corrected_q348 {was, now, ref, page, why}, variation_notes_q348[] (ids in variations_q348)}}. '
                'variations_q348[] {id, ref, pages[], nerves[], muscles[], fact}. families.root.levels{C5: {members[], isncsci_key_muscles}}; families.root.cranial{CN VII: [...]}. '
                'families.peripheral.nerves{id: {name, parent, level, plexus, roots, cranial, direct_members[], all_members[] {muscle_id, via, role}}}. '
                'families.central.patterns[] {id, name, limb, kind synergy|hefter_asp|regional, status, components[] {label, moves [[joint, dof, sign]], '
                'source, opened}, members[] {muscle_id, part, tier, components[], action_quotes[], structures}}.'),
        ui=('Innervation -> sub-menu root | peripheral | central. Root: offer the clicked muscle\'s motor_levels; selecting a level marks all members '
            '(flag ISNCSCI key muscles). Peripheral: offer the clicked muscle\'s nerves and their parent chain; selecting marks all_members. Central: '
            'offer patterns whose members include the clicked muscle (status ok only); show the rule-based badge and the tier legend. Side: '
            'mark the clicked side only by default (central patterns are one-sided), with a "both sides" toggle for root and peripheral.'),
        public_content='Anatomy and neurology only: no treatment technique, amounts or approach is recorded here.'),
    muscles=muscles_out,
    families=dict(root=root_family, peripheral=peripheral_family, central=central_family),
    variations_q348=VAR_OUT,
    references=REFS,
    counts=dict(muscles=len(MUS), muscles_on_base_pages=sum(1 for m in MUS.values() if m['on_base_pages']),
                from_innervation_q322=sum(1 for m in MUS.values() if m['source_of_roots'] == 'innervation_q322'),
                root_levels_with_members=len(root_family['levels']), cranial_groups=len(root_family['cranial']),
                muscles_without_parsable_level=len(root_family['no_level_in_source']),
                nerves=len(nodes), nerves_with_direct_members=len(direct),
                patterns=len(P), patterns_ok=sum(1 for p in P if p['status'] == 'ok'),
                pattern_members=sum(len(p['members']) for p in P),
                book_check_q348={k: sum(1 for m in MUS.values() if (m.get('book_check_q348') or {}).get('status') == k) for k in ('agrees', 'differs', 'nerve_only')},
                book_checked_repo_only=sum(1 for m in MUS.values() if m.get('book_check_q348') and m['source_of_roots'] != 'innervation_q322'),
                repo_only_unchecked=sorted(k for k, m in MUS.items() if not m.get('book_check_q348') and m['source_of_roots'] != 'innervation_q322'),
                corrected_q348=sorted(k for k, m in MUS.items() if m.get('corrected_q348')), variations_q348=len(VAR_OUT)))
bad = scan_banned(out)
assert not bad, bad
json.dump(out, open(REPO / 'data/anatomy/innervation_groups_q342.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out['counts'], indent=1))
print('not on pages:', sorted(k for k, m in MUS.items() if not m['on_base_pages']))
print('no level:', [e['muscle_id'] for e in root_family['no_level_in_source']])
for p in P:
    print(p['id'], p['status'], len(p['members']), Counter(e['tier'] for e in p['members']))
