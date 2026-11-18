import json, re, hashlib, os, sys
from collections import Counter
from PIL import Image
S = os.path.dirname(os.path.abspath(__file__)); U = os.path.join(S, '..', 'uimap')
d = json.load(open(os.path.join(U, 'inventory.json')))
h = lambda s: hashlib.md5(s.encode()).hexdigest()[:12]
pretty = lambda s: (s.replace('-', ' ').replace('_', ' ').strip() or s)
MODE = {'inj': 'Injection planning', 'us': 'Scan (US)', 'cmp': 'Imaging comparison', 'inn': 'Muscle innervation', 'anat': 'Anatomy'}
def stage_path(sid):
    if sid.endswith('@phone'):
        q = stage_path(sid[:-6]); return q[:-1] + [q[-1] + ' · phone only']
    p = re.split(r'[:/]', sid)
    if p[0] == 'start': return ['1 · Start and mode chooser', 'Page just opened'] if len(p) == 1 else ['2 · Workspace at rest', 'Always on screen']
    if p[0] == 'modes': return ['1 · Start and mode chooser', 'Mode chooser']
    if p[0] == 'group': return ['3 · Toolbar groups'] + [pretty(x).capitalize() for x in p[1:]]
    if p[0] == 'panel': return ['4 · Tool panels'] + [pretty(x).capitalize() for x in p[1:]]
    if p[0] == 'mode': return ['5 · Modes', MODE.get(p[1], pretty(p[1]))] + [pretty(x) for x in p[2:]]
    if p[0] == 'select':
        if len(p) > 1 and p[1] in ('nerve', 'bone'): return ['6 · Name card', p[1].capitalize() + ' selected'] + [pretty(x) for x in p[2:]]
        return ['6 · Name card', 'Muscle selected'] + [pretty(x) for x in p[1:]]
    if p[0] == 'transient': return ['7 · Messages'] + [pretty(x).capitalize() for x in p[1:]]
    if p[0] == 'measure-result': return ['4 · Tool panels', 'Measure', 'After a measurement'] + [pretty(x) for x in p[1:]]
    if p[0] == 'search': return ['3 · Toolbar groups', 'Search', 'With a typed query'] + [pretty(x) for x in p[1:]]
    if p[0] == 'visibility': return ['7 · Messages', 'Hide, fade, show only'] + [pretty(x) for x in p[1:]]
    if p[0] == 'history': return ['7 · Messages', 'Undo and history'] + [pretty(x) for x in p[1:]]
    if p[0] == 'toast': return ['7 · Messages', 'Toasts'] + [pretty(x) for x in p[1:]]
    if p[0] == 'inj-flow': return ['5 · Modes', 'Injection planning', 'Step by step'] + [pretty(x) for x in p[1:]]
    if p[0] == 'us-probe': return ['5 · Modes', 'Scan (US)', 'Probe on the skin'] + [pretty(x) for x in p[1:]]
    if p[0] == 'code-only': return ['9 · In the code only (never captured on screen)']
    return ['8 · Other'] + [pretty(x) for x in p]
os.makedirs(os.path.join(S, 'shots'), exist_ok=True)
stages = []; sidx = {}
for s in sorted(d['stages'], key=lambda s: s['order']):
    sh = {}
    for dev, w in (('desktop', 840), ('phone', 390)):
        src = (s.get('shots') or {}).get(dev)
        if src and os.path.exists(os.path.join(U, src)):
            name = 's%03d_%s.webp' % (s['order'], dev[0]); out = os.path.join(S, 'shots', name)
            if not os.path.exists(out):
                im = Image.open(os.path.join(U, src)).convert('RGB'); im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS); im.save(out, 'WEBP', quality=55, method=6)
            sh[dev[0]] = name
    sidx[s['id']] = len(stages)
    stages.append({'id': s['id'], 'p': stage_path(s['id']), 't': s.get('trigger', ''), 'd': sh.get('d'), 'ph': sh.get('p')})
groups = []; gid = {}
def group(path, stage=None):
    key = ' › '.join(path)
    if key in gid: return gid[key]
    par = group(path[:-1]) if len(path) > 1 else None
    g = {'id': 'g' + h(key), 't': path[-1], 'par': par, 's': stage}; gid[key] = g['id']; groups.append(g); return g['id']
for s in stages: group(s['p'], sidx[s['id']])
meaning = re.compile(r'[A-Za-z֐-׿]{3,}')
d1 = json.load(open(os.path.join(U, 'inventory_v1.json'))) if os.path.exists(os.path.join(U, 'inventory_v1.json')) else d
n_old = len(d1['items'])
for k in range(n_old):
    assert all(d['items'][k][f] == d1['items'][k][f] for f in ('stage', 'key', 'text')), 'inventory is not append-only at %d' % k
def box(w): return [w['zone'], [round(x) for x in w['box']]] if w else None
def order(i):
    w = i['where'].get('desktop') or i['where'].get('phone') or {'box': [0, 0, 0, 0]}; return (w['box'][1] // 12, w['box'][0])
def layout(src, idx, ns):
    ct = Counter((i['stage'], i.get('container_title') or '') for i in src); seen = Counter(); out = {}
    for k, i in sorted(zip(idx, src), key=lambda t: (sidx.get(t[1]['stage'], 999), order(t[1]))):
        if i['stage'] not in sidx: continue
        sp = stages[sidx[i['stage']]]['p']; c = (i.get('container_title') or '').strip()
        path = sp + [c[:60]] if (meaning.search(c) and ct[(i['stage'], c)] >= 2 and c.lower() != sp[-1].lower() and c != i['text']) else sp
        kk = i['stage'] + '|' + i['key'] + '|' + i['text']; seen[kk] += 1
        out[k] = ('i' + h(ns + kk + '|%d' % seen[kk]), path)
    return out
lay = layout(d1['items'], list(range(n_old)), '')                       # exactly the first build's ids and groups
lay.update(layout(d['items'][n_old:], list(range(n_old, len(d['items']))), 'v2|'))
items = []
for k, i in sorted(enumerate(d['items']), key=lambda t: (sidx.get(t[1]['stage'], 999), order(t[1]))):
    if k not in lay: continue
    iid, path = lay[k]; par = group(path)
    items.append({'id': iid, 'par': par, 'x': i['text'] or ('(' + (i.get('tooltip') or i['kind']) + ')'), 'tip': (i.get('tooltip') or '')[:140], 'k': i['kind'],
                  's': sidx[i['stage']], 'm': i.get('mode', 'any'), 'd': box(i['where'].get('desktop')), 'p': box(i['where'].get('phone')),
                  'pr': 1 if i.get('private') else 0, 'l': i.get('lang', 'en'), 'dy': 1 if i.get('dynamic_content') else 0,
                  'al': [sidx[a] for a in (i.get('also_in') or []) if a in sidx], 'src': (i.get('source') or '')[:80] if i['stage'] == 'code-only' else ''})
data = {'page': d['page'], 'captured': d['captured'], 'stages': stages, 'groups': groups, 'items': items, 'obs': d['observations'], 'nr': d['not_reached'], 'fd': (d.get('female_diff') or [])[:400], 'fds': d.get('female_diff_scope', '')}
js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
tpl = open(os.path.join(S, 'template.html'), encoding='utf8').read()
open(os.path.join(S, 'index.html'), 'w', encoding='utf8').write(tpl.replace('/*__DATA__*/', js))
sz = sum(os.path.getsize(os.path.join(S, 'shots', f)) for f in os.listdir(os.path.join(S, 'shots')))
print('stages', len(stages), 'groups', len(groups), 'items', len(items), 'data KB', len(js) // 1024, 'shots', len(os.listdir(os.path.join(S, 'shots'))), 'MB %.1f' % (sz / 1e6))
json.dump({'shots/' + f: 'shots/' + f for f in sorted(os.listdir(os.path.join(S, 'shots')))}, open(os.path.join(S, 'files.json'), 'w'))
