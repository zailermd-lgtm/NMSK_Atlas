"""Definitive test: is any distal phalanx of the hand OUTSIDE the page's own hand-skin surface?
Builds a local skin surface from every skin mesh near the hand and asks, for each phalanx vertex,
whether it lies outside it (ray-parity against the union of the local skin triangles)."""
import sys, re, json
import pathlib
import numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import geo
import trimesh
NUM={'first':1,'second':2,'third':3,'fourth':4,'fifth':5}
def meshes(key, root='build/q296'):
    out=[]
    if geo.DIRS[key][2]=='zan':
        b,me=geo.zan_meshes(key, root)
        for r in me:
            q=np.frombuffer(b,np.uint16,r['vc']*3,r['vo']).reshape(-1,3).astype(np.float64)
            f=np.frombuffer(b,np.uint16,r['ic']*3,r['io']).reshape(-1,3).astype(np.int64)
            out.append((r['id'],r['sys'],np.asarray(r['min'])+q/65535.0*np.asarray(r['span']),f))
    else:
        bj,b,decode=geo.own_structures(key, root)
        for e,v,f in decode(bj,b): out.append((e['id'],e.get('cat'),np.asarray(v,float),np.asarray(f,np.int64)))
    return out
def run(key, root='build/q296'):
    M=meshes(key, root); rows=[]
    for side in 'lr':
        dp={}
        for i,s,v,f in M:
            m=re.match(r'zan_distal_phalanx_of_(\w+)_finger_of_hand_'+side+'$',i)
            if m: dp[NUM[m.group(1)]]=(i,v,f)
        if not dp: continue
        hv=np.vstack([v for _,v,_ in dp.values()]); lo,hi=hv.min(0)-60,hv.max(0)+60
        sv=[];sf=[];o=0
        for i,s,v,f in M:
            if s!='skin': continue
            if (v.max(0)<lo).any() or (v.min(0)>hi).any(): continue
            sel=((v>=lo)&(v<=hi)).all(1)
            if sel.sum()<10: continue
            sv.append(v); sf.append(f+o); o+=len(v)
        if not sv: continue
        SK=trimesh.Trimesh(np.vstack(sv), np.vstack(sf), process=False)
        for n,(pid,v,f) in sorted(dp.items()):
            try: inside=SK.contains(v)
            except Exception as e: rows.append(dict(side=side,finger=n,err=str(e))); continue
            outn=int((~inside).sum())
            d=None
            if outn:
                _,dd,_=trimesh.proximity.closest_point(SK, v[~inside])
                d=round(float(dd.max()),2)
            rows.append(dict(side=side,finger=n,phalanx=pid,nv=len(v),outside=outn,
                             outside_pct=round(100.0*outn/len(v),1), max_outside_mm=d))
    return rows

def REPO_OUT(name):
    return str(pathlib.Path(__file__).resolve().parents[3] / 'data/derived' / name)

if __name__=='__main__':
    allr={}
    for k in (sys.argv[1:] or ['base_m','base_f','comb_m','comb_f']):
        rows=run(k); allr[k]=rows; print('===',k)
        for r in rows:
            if 'err' in r: print('  ',r); continue
            flag='   <-- OUTSIDE THE SKIN' if r['outside'] else ''
            print(f"   {r['side']} F{r['finger']}: {r['outside']:4d}/{r['nv']:4d} vertices outside ({r['outside_pct']:5.1f} %), max {r['max_outside_mm']} mm{flag}")
    json.dump(allr,open(REPO_OUT('Q297_fingertip_containment_rejected.json'),'w'),indent=1)
