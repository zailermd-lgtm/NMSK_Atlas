"""Fingertip audit v3 -- the measurement used in the Q297 report.
Per distal phalanx of the hand: axis = its own PCA major axis, oriented away from the hand centroid.
Soft tissue / skin is counted only inside a CYLINDER of radius R_CYL mm about that axis (so a neighbouring
finger cannot contribute) and only forward of the bone tip. Reported: how far the skin front reaches past
the bone tip (real distal pulp + nail over the tuft is about 3-8 mm; a negative value means bare bone)."""
import sys, json, re
import pathlib
import numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import geo
NUM={'first':1,'second':2,'third':3,'fourth':4,'fifth':5}
R_CYL=9.0

# Q308: the baseline is ASKED FOR, never written down here. `scripts/anatomy/q241/model.SRC` is the one place
# in this repository that declares which build the six pages come from, and `model.build_root()` reads it. A
# second copy of the literal goes stale silently the moment a round lands -- which is exactly what happened to
# this module: its default stayed `build/q296`, where the provenance audit reports d_unaccounted = 2, so every
# run without an explicit --src kept auditing the PRE-Q297 state and reporting it as today's.
# Q310: delegate to geo, which this module already imports and which defines REPO. The copy that stood here
# referenced a REPO this module never defines, so every call without an explicit root raised NameError -- the
# suite did not catch it because nothing calls these two helpers without one.
def _baseline():
    return geo._baseline()


def page_meshes(key, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    out=[]
    if geo.DIRS[key][2]=='zan':
        b,me=geo.zan_meshes(key, root)
        for r in me:
            q=np.frombuffer(b,np.uint16,r['vc']*3,r['vo']).reshape(-1,3).astype(np.float64)
            out.append((r['id'],r['sys'],np.asarray(r['min'])+q/65535.0*np.asarray(r['span'])))
    else:
        bj,b,decode=geo.own_structures(key, root)
        for e,v,f in decode(bj,b): out.append((e['id'],e.get('cat'),np.asarray(v,float)))
    return out
def run(key, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    M=page_meshes(key, root); rows=[]
    for side in 'lr':
        dp={}
        for i,s,v in M:
            m=re.match(r'zan_distal_phalanx_of_(\w+)_finger_of_hand_'+side+'$',i)
            if m: dp[NUM[m.group(1)]]=(i,v)
        if not dp: continue
        hc=np.vstack([v for _,v in dp.values()]).mean(0)
        SK=[(i,v) for i,s,v in M if s=='skin']
        OTH=[(i,s,v) for i,s,v in M if s not in ('skin',)]
        for n,(pid,pv) in sorted(dp.items()):
            c=pv.mean(0); ax=np.linalg.svd(pv-c,full_matrices=False)[2][0]
            if np.dot(ax,c-hc)<0: ax=-ax
            tp=(pv-c)@ax; tipv=tp.max(); tip=pv[tp.argmax()]
            def cyl(v):
                t=(v-c)@ax; r=np.linalg.norm((v-c)-np.outer(t,ax),axis=1)
                return t, r
            best=None; cnt=0
            for i,v in SK:
                t,r=cyl(v); sel=(r<R_CYL)&(t>tipv-15)&(t<tipv+20)
                if sel.any():
                    cnt+=int(sel.sum()); m_=float(t[sel].max())-tipv
                    best=m_ if best is None else max(best,m_)
            row=dict(side=side,finger=n,phalanx=pid,bone_len_mm=round(float(tipv-tp.min()),2),
                     skin_past_tip_mm=(round(best,2) if best is not None else None), skin_verts_in_cyl=cnt)
            # which non-skin structures reach furthest in the same cylinder
            pr=[]
            for i,s,v in OTH:
                if i==pid: continue
                t,r=cyl(v); sel=(r<R_CYL)&(t>tipv)&(t<tipv+20)
                if sel.any(): pr.append((i,s,round(float(t[sel].max()-tipv),2)))
            pr.sort(key=lambda x:-x[2])
            row['soft_past_tip']=pr[:3]
            row['bone_past_skin_mm']=(round(-best,2) if best is not None and best<0 else 0.0)
            rows.append(row)
    return rows

def REPO_OUT(name):
    return str(pathlib.Path(__file__).resolve().parents[3] / 'data/derived' / name)

if __name__=='__main__':
    allr={}
    for k in (sys.argv[1:] or list(geo.DIRS)):
        rows=run(k); allr[k]=rows
        print('===',k)
        if not rows: print('   (no per-finger distal phalanx structures on this page)'); continue
        for r in rows:
            pr=', '.join(f"{a.replace('zan_','')[:34]}+{c}" for a,b,c in r['soft_past_tip']) or '-'
            v=r['skin_past_tip_mm']
            flag='  <-- BARE BONE' if v is not None and v<1.0 else ('  <-- thin' if v is not None and v<3.0 else '')
            print(f"   {r['side']} F{r['finger']} bone {r['bone_len_mm']:5.1f}  skin past tip {v if v is None else format(v,'6.2f')} mm (n={r['skin_verts_in_cyl']:4d}){flag}   soft: {pr}")
        vs=[r['skin_past_tip_mm'] for r in rows if r['skin_past_tip_mm'] is not None]
        if vs: print(f"   -> min {min(vs):.2f}  max {max(vs):.2f}  mean {sum(vs)/len(vs):.2f} mm   (real pulp+nail 3-8 mm)")
    json.dump(allr,open(REPO_OUT('Q297_fingertips.json'),'w'),indent=1)
