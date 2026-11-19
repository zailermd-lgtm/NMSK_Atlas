"""Q241 skeleton landmarks: joint centres / axes / bone axes computed from the page's OWN bone meshes (no external model).
All numbers are in the page's atlas frame (mm; +X right, +Y up, +Z anterior).  Left-side limbs are processed with the lateral direction = -n.
Every landmark carries a method note and, where there is one, a fit error (sphere RMS, ...). Merged own-model meshes (all fingers in one mesh ...) are split into
connected components and assigned to fingers / toes by geometry (see split_hand / split_foot)."""
from __future__ import annotations
import re
import numpy as np
from geom import *  # noqa
import model as MD

SIDES = ("r", "l")
VERT_ORDER = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"] + ["t%d" % i for i in range(1, 13)] + ["l%d" % i for i in range(1, 6)]


def cen(v):
    return v.mean(0)


class Skel:
    def __init__(self, M: "MD.Model"):
        self.M = M
        self.mirror = True
        self.B = M.bones()
        self.n = M.plane.n                    # points to the subject's right
        self.notes = {}                       # landmark -> dict(method, err)
        self.err = {}
        self._frame()
        self._spine()

    # ------------------------------------------------------------------ helpers
    def bv(self, k):
        """vertices of bone k; LEFT-side bones are reflected about the midsagittal plane, so every limb is processed as a RIGHT limb ('right-limb space')"""
        v = self.B[k]["v"]
        return self.M.plane.reflect(v) if (k.endswith("_l") and self.mirror) else v

    def V(self, name, side=None):
        k = name if side is None else "%s_%s" % (name, side)
        return self.bv(k) if k in self.B else None

    def lat(self, s):
        return self.n if (s == "r" or self.mirror) else -self.n

    def note(self, k, method, err=None):
        self.notes[k] = dict(method=method, err=err)

    # ------------------------------------------------------------------ trunk frame
    def to_true(self, s, p):
        """right-limb space -> the model's own space (reflects back for the left side)"""
        return self.M.plane.reflect(np.asarray(p, float)) if s == "l" else np.asarray(p, float)

    def _spine(self):
        """ordered vertebrae (top C1 -> bottom L5/L6): list of dict(key, region, label, c, v)"""
        L = []
        B = self.B
        for lv in VERT_ORDER:
            k = "vert_" + lv
            if k in B:
                L.append(dict(key=k, region=dict(c="cervical", t="thoracic", l="lumbar")[lv[0]], label=lv.upper(), v=self.bv(k), c=cen(self.bv(k))))
        if not L:                                   # own pages: numbered groups, order by height
            for reg in ("cervical", "thoracic", "lumbar"):
                ks = sorted([k for k in B if k.startswith(reg + "_vertebrae#")], key=lambda k: -cen(self.bv(k))[1])
                for i, k in enumerate(ks):
                    L.append(dict(key=k, region=reg, label="%s%d" % (reg[0].upper(), i + 1), v=self.bv(k), c=cen(self.bv(k))))
        L.sort(key=lambda d: -d["c"][1])
        self.spine = L

    def _frame(self):
        B = self.B
        sac = self.bv("sacrum")
        # upper trunk landmark: centroid of the highest thoracic/cervical vertebra bodies is not needed: use sternum / clavicles / vertebra stack
        vt = [cen(b["v"]) for k, b in B.items() if k.startswith(("vert_t", "thoracic_vertebrae"))]
        vc = [cen(b["v"]) for k, b in B.items() if k.startswith(("vert_c", "cervical_vertebrae"))]
        top = np.mean(vc, 0) if vc else np.mean(vt, 0)
        low = cen(sac)
        n = self.n
        up = top - low; up = unit(up - (up @ n) * n)
        ant = np.cross(n, up) if True else None
        ant = unit(ant)
        st = cen(self.bv("sternum")) if "sternum" in B else None
        # anterior = from the vertebral column towards the sternum
        ref = (st - np.mean(vt, 0)) if (st is not None and vt) else np.array([0, 0, 1.0])
        if ant @ ref < 0:
            ant = -ant
        self.E = np.c_[n, up, ant]            # columns: right, up, anterior (an orthonormal basis; handedness of the atlas frame is not assumed)
        self.up, self.ant = up, ant


    # ------------------------------------------------------------------ generic bone helpers
    def long_axis(self, v, down=True, ref_prox=None):
        """unit axis along the bone, oriented proximal -> distal ('down' = distal is the lower end; else distal is the end farther from ref_prox)"""
        c, w, V = pca(v)
        u = V[:, 0]
        t = (v - c) @ u
        if ref_prox is not None:
            if np.linalg.norm(c + u * t.max() - ref_prox) < np.linalg.norm(c + u * t.min() - ref_prox):
                u = u          # +u end is nearer to ref_prox -> that is the PROXIMAL end -> distal = -u
                u = -u
        elif (u @ self.up) > 0:
            u = -u
        if ref_prox is not None:
            # u currently points proximal -> distal after the flip above only when +u end was proximal; recheck
            if (c + u * ((v - c) @ u).max() - ref_prox) @ u < 0:
                pass
        return u

    def region(self, v, u, which, frac):
        """vertices in the proximal / distal `frac` of the bone along u (u points proximal -> distal)"""
        t = v @ u; lo, hi = t.min(), t.max(); L = hi - lo
        m = t <= lo + frac * L if which == "prox" else t >= hi - frac * L
        return v[m], L

    def ml_axis(self, R, u, s, hint=None):
        """medio-lateral axis of an end region R (largest variance perpendicular to the shaft axis u), oriented lateral (+): by the bone-derived `hint` vector when given
        (radial head vs ulna for the humerus, fibular head vs tibia for the femur: valid for any limb rotation), else toward the side of the midsagittal plane"""
        P = R - R.mean(0)
        P = P - np.outer(P @ u, u)
        w, V = np.linalg.eigh(np.cov(P.T))
        a = V[:, -1]
        ref = self.lat(s) if hint is None else hint
        return a if (a @ ref) > 0 else -a

    def end_pair(self, v, u, which, frac, s, hint=None):
        """medial / lateral extreme points of an end region (epicondyles of the humerus / femur, malleoli ...) and the unit ML axis"""
        R, L = self.region(v, u, which, frac)
        a = self.ml_axis(R, u, s, hint)
        lat = trimmed_extreme(R, a, 0.03); med = trimmed_extreme(R, -a, 0.03)
        return med, lat, unit(lat - med), R

    # ------------------------------------------------------------------ the limbs
    def upper(self, s):
        """arm landmarks of side s -> dict"""
        B, n = self.B, self.n
        L = {}
        hum = self.V("humerus", s)
        u = self.long_axis(hum)                                   # proximal -> distal
        Rp, Lh = self.region(hum, u, "prox", 0.14)
        # head: medial / posterior bulb of the proximal humerus; sphere RANSAC restricted to the half of the region facing the trunk
        side_to_trunk = -self.lat(s)
        t = (Rp - Rp.mean(0)) @ side_to_trunk
        cand = Rp[t > np.percentile(t, 25)]
        fit = sphere_ransac(cand, 16.0, 30.0, tol=1.3, seed=1)
        if fit is None:
            fit = (*sphere_fit(cand)[:3], len(cand))
        gh, r, rms, nin = fit
        L["gh"] = gh; self.note("gh_" + s, "humeral head sphere (RANSAC on the proximal 14% of the humerus, radius 16-30 mm)", dict(radius_mm=round(float(r), 1), rms_mm=round(float(rms), 2), inliers=int(nin)))
        rad, uln = self.V("radius", s), self.V("ulna", s)
        Rd0, _ = self.region(hum, u, "dist", 0.10)
        el0 = Rd0.mean(0)
        # lateral hint: in the proximal quarter of the forearm the radius lies lateral (and slightly anterior) to the ulna in every forearm rotation
        ur0 = self.long_axis(rad, ref_prox=el0); uu0 = self.long_axis(uln, ref_prox=el0)
        def section(b, ua, f0, f1):
            t = b @ ua; lo, hi = t.min(), t.max(); m = (t >= lo + f0 * (hi - lo)) & (t <= lo + f1 * (hi - lo))
            return b[m].mean(0)
        fa0 = unit(section(rad, ur0, 0.8, 1.0) + section(uln, uu0, 0.8, 1.0) - section(rad, ur0, 0.0, 0.1) - section(uln, uu0, 0.0, 0.1))
        hint = section(rad, ur0, 0.12, 0.30) - section(uln, uu0, 0.12, 0.30)
        hint = hint - (hint @ fa0) * fa0
        hint = hint - (hint @ u) * u
        med, lat, ml, Rd = self.end_pair(hum, u, "dist", 0.12, s, hint)
        L.update(epi_med=med, epi_lat=lat, elbow=(med + lat) / 2, elbow_axis=ml, hum_u=u, hum_len=float(Lh))
        # forearm
        el = L["elbow"]
        ur = self.long_axis(rad, ref_prox=el); uu = self.long_axis(uln, ref_prox=el)
        if (ur @ (rad.mean(0) - el)) < 0: ur = -ur
        if (uu @ (uln.mean(0) - el)) < 0: uu = -uu
        rp, _ = self.region(rad, ur, "prox", 0.06); rd, Lr = self.region(rad, ur, "dist", 0.08)
        up_, _ = self.region(uln, uu, "prox", 0.10); ud, Lu = self.region(uln, uu, "dist", 0.05)
        L.update(rad_head=rp.mean(0), rad_dist=rd.mean(0), uln_prox=up_.mean(0), uln_head=ud.mean(0), rad_u=ur, uln_u=uu, rad_len=float(Lr), uln_len=float(Lu))
        # radial styloid: most radial-lateral point of the distal radius; ulnar styloid: the distal-most point of the ulna head
        fa = unit(L["rad_dist"] - L["rad_head"])           # pronation axis (forearm axis)
        L["fore_axis"] = fa
        rdir = unit((rd.mean(0) - ud.mean(0)) - ((rd.mean(0) - ud.mean(0)) @ fa) * fa)      # ulna -> radius at the wrist (thumb side), valid in any rotation
        L["radial_dir"] = rdir
        L["wrist_ends"] = (rd.mean(0), ud.mean(0))
        # carpus
        carp = [self.bv(k) for k in B if k.startswith("carpal_") and k.endswith("_" + s)] or ([self.bv("carpals_" + s)] if "carpals_" + s in B else [])
        cv = np.vstack(carp)
        tt = cv @ fa
        prox = cv[tt <= np.median(tt)]
        L["carpus"] = cen(cv); L["wrist"] = cen(prox)
        self.note("wrist_" + s, "centroid of the proximal half of the carpal bones")
        L["hand_bones"] = self.hand_bones(s, L)
        return L

    def hand_bones(self, s, L):
        """-> dict finger(1..5) -> dict(mc=verts, prox=verts, mid=verts, dist=verts) (verts None when absent); merged own meshes are split by geometry"""
        B = self.B
        out = {f: {} for f in range(1, 6)}
        mcs = {f: self.bv("mc_%d_%s" % (f, s)) for f in range(1, 6) if "mc_%d_%s" % (f, s) in B}
        phs = {}
        for f in range(1, 6):
            for seg in ("prox", "midd", "dist"):
                k = "ph_hand_%d_%s_%s" % (f, seg, s)
                if k in B:
                    phs[(f, seg)] = self.bv(k)
        for f in range(1, 6):
            out[f] = dict(mc=mcs.get(f), prox=phs.get((f, "prox")), mid=phs.get((f, "midd")), dist=phs.get((f, "dist")))
        return out

    def split_mcs(self, b, s, L):
        lab = components(b["f"], len(b["v"]))
        comps = [b["v"][lab == i] for i in np.unique(lab)]
        comps = [c for c in comps if len(c) > 30]
        # order radial -> ulnar by the radial direction
        comps.sort(key=lambda c: -(cen(c) @ L["radial_dir"]))
        return {i + 1: c for i, c in enumerate(comps[:5])} if len(comps) >= 5 else {}

    def assign_phalanges(self, b, mcs, s, L):
        if not mcs:
            return {}
        lab = components(b["f"], len(b["v"]))
        comps = [b["v"][lab == i] for i in np.unique(lab)]
        comps = [c for c in comps if len(c) > 20]
        # each finger's metacarpal gives a base->head ray; a phalanx belongs to the finger whose ray extension passes closest to its centroid
        rays = {}
        for f, m in mcs.items():
            c, w, V = pca(m); a = V[:, 0]
            if (a @ (cen(m) - L["wrist"])) < 0: a = -a
            tt = (m - c) @ a
            rays[f] = (c + a * tt.max(), a)
        asg = {f: [] for f in rays}
        for c in comps:
            cc = cen(c); best = None
            for f, (h, a) in rays.items():
                d = cc - h; tpar = d @ a
                perp = np.linalg.norm(d - tpar * a)
                score = perp + (30.0 if tpar < -8 else 0.0)
                if best is None or score < best[0]:
                    best = (score, f)
            asg[best[1]].append((np.linalg.norm(cc - rays[best[1]][0]), c))
        out = {}
        for f, lst in asg.items():
            lst.sort(key=lambda t: t[0])
            names = ("prox", "dist") if f == 1 else ("prox", "midd", "dist")
            if len(lst) == len(names):
                for nme, (_, c) in zip(names, lst):
                    out[(f, nme)] = c
            elif len(lst) > len(names):               # keep the nearest ones in order, the farthest = distal
                sel = lst[:len(names) - 1] + [lst[-1]]
                for nme, (_, c) in zip(names, sel):
                    out[(f, nme)] = c
        return out

    def lower(self, s):
        B = self.B
        L = {}
        fem = self.V("femur", s)
        u = self.long_axis(fem)
        Rp, Lf = self.region(fem, u, "prox", 0.14)
        t = (Rp - Rp.mean(0)) @ (-self.lat(s))
        cand = Rp[t > np.percentile(t, 30)]
        fit = sphere_ransac(cand, 18.0, 32.0, tol=1.3, seed=2)
        if fit is None:
            fit = (*sphere_fit(cand)[:3], len(cand))
        hip, r, rms, nin = fit
        L["hip"] = hip
        self.note("hip_" + s, "femoral head sphere (RANSAC on the proximal 14% of the femur, radius 18-32 mm)", dict(radius_mm=round(float(r), 1), rms_mm=round(float(rms), 2), inliers=int(nin)))
        # acetabulum cross-check: the concave sphere of the hip bone around the head centre
        hb = self.V("hip_bone", s)
        near = hb[np.linalg.norm(hb - hip, axis=1) < r + 14]
        ac = sphere_ransac(near, 18.0, 36.0, tol=1.5, seed=3) if len(near) > 40 else None
        if ac is not None:
            L["acetab"] = ac[0]
            self.note("hip_" + s, self.notes["hip_" + s]["method"], dict(self.notes["hip_" + s]["err"], acetabulum_centre_distance_mm=round(float(np.linalg.norm(ac[0] - hip)), 1), acetabulum_radius_mm=round(float(ac[1]), 1)))
        tib, fib = self.V("tibia", s), self.V("fibula", s)
        ek = self.region(fem, u, "dist", 0.10)[0].mean(0)
        ut0 = self.long_axis(tib, ref_prox=ek); uf0 = self.long_axis(fib, ref_prox=ek)
        def section(b, ua, f0, f1):
            t = b @ ua; lo, hi = t.min(), t.max(); m = (t >= lo + f0 * (hi - lo)) & (t <= lo + f1 * (hi - lo))
            return b[m].mean(0)
        # in the proximal third of the leg the fibula lies lateral (and posterior) to the tibia
        hint = section(fib, uf0, 0.05, 0.30) - section(tib, ut0, 0.05, 0.30)
        hint = hint - (hint @ ut0) * ut0
        hint = hint - (hint @ u) * u
        med, lat, ml, Rd = self.end_pair(fem, u, "dist", 0.14, s, hint)
        L.update(fem_u=u, fem_len=float(Lf), epi_med=med, epi_lat=lat, knee=(med + lat) / 2, knee_axis=ml)
        ut = self.long_axis(tib)
        Rt, Ltb = self.region(tib, ut, "dist", 0.10)
        uf = self.long_axis(fib)
        Rf, _ = self.region(fib, uf, "dist", 0.06)
        dm = Rt.mean(0) - Rf.mean(0)                              # fibula is lateral to the tibia: medial direction at the ankle
        dm = unit(dm - (dm @ ut) * ut)
        mmed = Rt[(Rt - Rt.mean(0)) @ dm > 0]
        L["mal_med"] = trimmed_extreme(mmed, ut, 0.04)
        L["mal_lat"] = trimmed_extreme(Rf, uf, 0.06)
        L["ankle"] = (L["mal_med"] + L["mal_lat"]) / 2
        ax = unit(L["mal_lat"] - L["mal_med"])
        if ax @ self.lat(s) < 0: ax = -ax
        L["ankle_axis"] = ax; L["tib_u"] = ut; L["tib_len"] = float(Ltb)
        Rpt, _ = self.region(tib, ut, "prox", 0.06)
        L["tib_prox"] = Rpt.mean(0)
        tal, cal = self.V("talus", s), self.V("calcaneus", s)
        L["talus"], L["calcaneus"] = cen(tal), cen(cal)
        mts = self.foot_bones(s, L)
        L["foot_bones"] = mts
        fvs = [m["mt"] for m in mts.values() if m.get("mt") is not None]
        if not fvs and ("metatarsals_" + s) in B:
            fvs = [self.bv("metatarsals_" + s)]
        L["forefoot"] = cen(np.vstack(fvs))
        # foot frame: heel point + medial and lateral forefoot (metatarsal head) points define the sole plane (works for plantar-flexed feet); n = dorsal normal
        fk = [k for k in self.B if k.endswith("_" + s) and re.match(r"(calcaneus|cuboid|navicular|cuneiform|mt_|metatarsals|ph_foot|phalanges_foot|talus)", k)]
        fv_all = np.vstack([self.bv(k) for k in fk])
        fw0 = unit(L["forefoot"] - L["calcaneus"])
        cal = self.V("calcaneus", s)
        heel = trimmed_extreme(cal, -fw0, 0.05)
        mt_all = np.vstack(fvs)
        tm = mt_all @ fw0
        dist_mt = mt_all[tm >= np.percentile(tm, 85)]
        lat0 = unit(self.lat(s) - (self.lat(s) @ fw0) * fw0)
        p_med = trimmed_extreme(dist_mt, -lat0, 0.06); p_lat = trimmed_extreme(dist_mt, lat0, 0.06)
        nrm = np.cross(p_lat - p_med, (p_lat + p_med) / 2 - heel)
        nrm = unit(nrm)
        if nrm @ (-L["tib_u"]) < 0: nrm = -nrm                    # dorsal side = toward the shank
        L["foot_n"] = nrm
        L["heel"], L["mt_med"], L["mt_lat"] = heel, p_med, p_lat
        fw = (p_lat + p_med) / 2 - heel
        fw = fw - (fw @ nrm) * nrm
        L["foot_fwd"] = unit(fw)
        return L

    def foot_bones(self, s, L):
        B = self.B
        mts = {f: self.bv("mt_%d_%s" % (f, s)) for f in range(1, 6) if "mt_%d_%s" % (f, s) in B}
        phs = {}
        for f in range(1, 6):
            for seg in ("prox", "midd", "dist"):
                k = "ph_foot_%d_%s_%s" % (f, seg, s)
                if k in B:
                    phs[(f, seg)] = self.bv(k)
        out = {f: {} for f in range(1, 6)}
        if False:
            b = B["metatarsals_" + s]
            lab = components(b["f"], len(b["v"]))
            comps = [b["v"][lab == i] for i in np.unique(lab)]
            comps = [c for c in comps if len(c) > 40]
            fwd = unit(cen(np.vstack(comps)) - L["calcaneus"])
            lat = self.lat(s)
            comps.sort(key=lambda c: (cen(c) @ lat))          # medial -> lateral
            mts = {i + 1: c for i, c in enumerate(comps[:5])} if len(comps) >= 5 else {}
        if False:
            b = B["phalanges_foot_" + s]
            lab = components(b["f"], len(b["v"]))
            comps = [b["v"][lab == i] for i in np.unique(lab)]
            comps = [c for c in comps if len(c) > 15]
            fwd = unit(cen(np.vstack(list(mts.values()))) - L["calcaneus"])
            rays = {}
            for f, m in mts.items():
                c, w, V = pca(m); a = V[:, 0]
                if (a @ fwd) < 0: a = -a
                tt = (m - c) @ a
                rays[f] = (c + a * tt.max(), a)
            asg = {f: [] for f in rays}
            for c in comps:
                cc = cen(c); best = None
                for f, (h, a) in rays.items():
                    d = cc - h; tpar = d @ a; perp = np.linalg.norm(d - tpar * a)
                    sc = perp + (30.0 if tpar < -8 else 0.0)
                    if best is None or sc < best[0]: best = (sc, f)
                asg[best[1]].append((np.linalg.norm(cc - rays[best[1]][0]), c))
            for f, lst in asg.items():
                lst.sort(key=lambda t: t[0])
                names = ("prox", "dist") if f == 1 else ("prox", "midd", "dist")
                if len(lst) >= len(names):
                    sel = lst[:len(names) - 1] + [lst[-1]] if len(lst) > len(names) else lst
                    for nme, (_, c) in zip(names, sel):
                        phs[(f, nme)] = c
        for f in range(1, 6):
            out[f] = dict(mt=mts.get(f), prox=phs.get((f, "prox")), mid=phs.get((f, "midd")), dist=phs.get((f, "dist")))
        return out


if __name__ == "__main__":
    import sys, json
    M = MD.Model(sys.argv[1])
    K = Skel(M)
    np.set_printoptions(precision=1, suppress=True)
    print("E", K.E.round(3).tolist())
    for s in SIDES:
        U = K.upper(s); Lw = K.lower(s)
        print(s, "gh", U["gh"], "elbow", U["elbow"], "wrist", U["wrist"], "hum_len", round(U["hum_len"], 1), "hip", Lw["hip"], "knee", Lw["knee"], "ankle", Lw["ankle"])
        print(" fingers", {f: [k for k, v in d.items() if v is not None] for f, d in U["hand_bones"].items()})
    print(json.dumps(K.notes, indent=0)[:1800])
