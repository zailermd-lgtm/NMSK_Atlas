"""Q241 pose rig: segments, joints (centre / axes / normal range / rest value) computed from the page's own bones, plus a python forward-kinematics that the viewer re-implements.

Convention (shared with viewer/pose/pose.js):
  * everything is in the page's atlas frame (mm; +X = subject right).  Joint axes are fixed in the PARENT's rest frame; the delta rotation of a joint for the displayed values q is
        dR = R(q) R(q0)^T ,   R(q) = Rot(a1,q1) Rot(a2,q2) Rot(a3,q3)        (intrinsic order = list order; Rot = Rodrigues, math convention)
    so the rest pose (q = q0) is reproduced exactly.  segment matrix  M = M_parent * about(dR, c)   (about(): rotate around the joint centre c).
    A joint with ref >= 0 measures its orientation against segment `ref` instead of its parent (the shoulder: humerus against the thorax, centre carried by the shoulder girdle).
  * all landmarks are computed in 'right-limb space' (the left limb reflected about the midsagittal plane); a LEFT joint's axes are converted back with a = -P a (reflection of an axis vector
    flips the sense of a rotation), so equal displayed values mean the same anatomical motion on both sides.
  * regions (spine): total angle of the region distributed over level joints with fixed weights; coupled joints (patella, shoulder girdle) are driven by other joints."""
from __future__ import annotations
import re
import numpy as np
from geom import *  # noqa
import model as MD
from skeleton import Skel, SIDES, cen
from rom import ROM, spine_weights


def axis_for(v, target, cand):
    """sign of `cand` such that a positive rotation about it moves v toward target"""
    c = unit(cand)
    return c if (np.cross(c, v) @ target) >= 0 else -c


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def orth(a, ref):
    """component of a perpendicular to ref, unit"""
    return unit(a - (a @ ref) * ref)


class RigBuilder:
    def __init__(self, M: "MD.Model", K: Skel = None):
        self.M = M
        self.K = K or Skel(M)
        self.P = M.plane
        self.segs = []          # dict(id, name, par(index|-1), side, label)
        self.joints = []        # dict(...)
        self.regions = []
        self.sid = {}
        self.notes = []
        self.info = {}          # diagnostics (landmark errors etc.)
        self.bone_seg = {}      # bone key -> segment index (rigid)
        self.soft_bones = set() # bone keys that are skinned between segments (ribs)

    # ------------------------------------------------------------ helpers
    def seg(self, id_, par, name, side="m"):
        if id_ in self.sid:
            return self.sid[id_]
        i = len(self.segs)
        self.segs.append(dict(id=id_, name=name, par=(self.sid[par] if par is not None else -1), side=side))
        self.sid[id_] = i
        return i

    def T(self, s, p):                  # right-limb space point -> model space
        return self.K.to_true(s, p)

    def A(self, s, a):                  # right-limb space AXIS -> model space axis (reflection flips the sense of rotation)
        a = np.asarray(a, float)
        if s == "l":
            n = self.P.n
            a = -(a - 2 * (a @ n) * n)
        return a

    def vec(self, s, a):                # plain direction vector to model space
        a = np.asarray(a, float)
        if s == "l":
            n = self.P.n
            a = a - 2 * (a @ n) * n
        return a

    def add_joint(self, id_, name, group, s, seg, par, c, dofs, ref=None, driven=None, note=None, label=None):
        """dofs: list of dict(k, label, a (right-limb space axis), lo, hi, q0)  -> stored with model-space axes"""
        j = dict(id=id_, name=name, group=group, side=s, seg=self.sid[seg], par=self.sid[par], ref=(self.sid[ref] if ref else -1),
                 c=[float(x) for x in self.T(s, c)], dof=[], note=note)
        for d in dofs:
            j["dof"].append(dict(k=d["k"], l=d.get("label", ""), a=[float(x) for x in self.A(s, d["a"])], lo=float(d["lo"]), hi=float(d["hi"]), q0=float(d["q0"]),
                                 rk=d.get("rk", ""), drv=d.get("drv")))
        if driven:
            j["driven"] = driven
        self.joints.append(j)
        return j

    # ------------------------------------------------------------ build
    def build(self):
        K = self.K
        n = K.n
        E = K.E
        self.R_, self.U_, self.A_ = E[:, 0], E[:, 1], E[:, 2]
        self.seg("pelvis", None, "Pelvis (sacrum, hip bones, coccyx)")
        self._spine()
        self.UU = {s: K.upper(s) for s in SIDES}
        self.LL = {s: K.lower(s) for s in SIDES}
        self._hips = {s: self.T(s, self.LL[s]["hip"]) for s in SIDES}
        self._pelvis_frame()
        for s in SIDES:
            self.U = self.UU[s]
            self.Lw = self.LL[s]
            self._palmar(s)
            self._arm(s)
            self._leg(s)
        self._assign_bones()
        return self.export()

    # ------------------------------------------------------------ spine / head
    def _spine(self):
        K = self.K
        sp = K.spine                                   # top -> bottom
        self.vsegs = []
        prev = "pelvis"
        sac = K.bv("sacrum")
        tops = sac[sac[:, 1] > np.percentile(sac[:, 1], 80)]
        below_c = cen(tops)
        lev = list(reversed(sp))                       # bottom -> top
        ids = []
        for v in lev:
            sid = "v" + v["label"]
            self.seg(sid, prev, "Vertebra " + v["label"])
            ids.append((sid, v, prev))
            prev = sid
        self.seg("head", prev, "Head (skull, mandible)")
        self.vsegs = ids
        # level joints bottom -> top; centre = midpoint between the vertebra centroid and the one below
        reg_joints = {"lumbar": [], "thoracic": [], "cervical": []}
        below = below_c
        for sid, v, par in ids:
            c = (below + v["c"]) / 2.0
            reg_joints[v["region"]].append(dict(seg=sid, par=par, c=c, label=v["label"]))
            below = v["c"]
        # head (occiput / C1): centre above C1
        if sp:
            c1 = sp[0]["c"]; c2 = sp[1]["c"] if len(sp) > 1 else c1 - self.U_ * 25
            ch = c1 + 0.5 * (c1 - c2)
            reg_joints["cervical"].append(dict(seg="head", par=ids[-1][0], c=ch, label="OCC"))
        self.reg_joints = reg_joints
        flex_a = axis_for(self.U_, self.A_, self.R_)
        lat_a = axis_for(self.U_, self.R_, self.A_)
        rot_a = axis_for(self.A_, self.R_, self.U_)
        names = {"lumbar": "Lumbar spine", "thoracic": "Thoracic spine", "cervical": "Head / neck (cervical spine + atlanto-occipital)"}
        rk = {"lumbar": "lumb", "thoracic": "thor", "cervical": "cerv"}
        for reg in ("lumbar", "thoracic", "cervical"):
            J = reg_joints[reg]
            if not J:
                continue
            labels = [j["label"] for j in J]
            top = [j["label"] for j in reversed(J)]
            dof = []
            for key, ax, nm in (("flex", flex_a, "flex"), ("lat", lat_a, "lat"), ("rot", rot_a, "rot")):
                lo, hi, lab, src = ROM["%s_%s" % (rk[reg], nm)]
                w = spine_weights(reg, labels, nm)
                dof.append(dict(k=key, a=[float(x) for x in ax], lo=lo, hi=hi, q0=0.0, l=lab, rk="%s_%s" % (rk[reg], nm), w=[float(x) for x in w]))
            self.regions.append(dict(id=reg, name=names[reg], group=names[reg], levels=[dict(seg=self.sid[j["seg"]], par=self.sid[j["par"]], c=[float(x) for x in j["c"]], label=j["label"]) for j in J], dof=dof,
                                     note="Zero = the spine as built; the displayed range is the regional average range of motion, shared between the levels (equal shares; the C1/C2 joint carries 50% of cervical rotation, the occiput/C1 joint 20% of flexion) - ASSUMPTION"))

    # ------------------------------------------------------------ palmar direction / pelvis frame
    def _palmar(self, s):
        """palmar direction of the hand of side s (right-limb space) from the forearm flexor vs extensor muscles of this model (the only reliable palmar/dorsal cue in every model)"""
        K, U = self.K, self.U
        el, wr = U["elbow"], U["wrist"]
        fa = U["fore_axis"]
        S = self.M.S
        fl = re.compile(r"(^|_)(flexor_(carpi|digitorum_(superficialis|profundus)|pollicis_longus)|palmaris_longus|pronator_quadratus)(_|$)")
        ex = re.compile(r"(^|_)(extensor_(carpi|digitorum|pollicis|indicis)|abductor_pollicis_longus|extensor_digiti_minimi)(_|$)")
        sfx = "_" + s
        cf, ce = [], []
        for x in S:
            if x["sys"] != "muscle" or not x["id"].lower().replace("zan_", "").rstrip("_").endswith(("_" + s, "_" + s + "_zfill", "_" + s + "_zfill203", "_" + s + "_zfill203s")) and ("_" + s + "_") not in x["id"].lower():
                continue
            i = x["id"].lower()
            if "brevis_l" in i and "digitorum" in i or "longus" in i and "digitorum" in i and "extensor" in i and "carpi" not in i and "leg" in i:
                pass
            if (fl.search(i) or ex.search(i)):
                v = self.K.bv("humerus_" + s) if False else x["v"]
                v = self.P.reflect(v) if s == "l" else v
                # forearm range: between wrist and elbow along the forearm axis, within 70 mm of it
                t = (v - el) @ fa; L = (wr - el) @ fa
                d = np.linalg.norm((v - el) - np.outer(t, fa), axis=1)
                m = (t > 0.35 * L) & (t < 1.0 * L) & (d < 70)
                if m.sum() < 30:
                    continue
                (cf if fl.search(i) else ce).append(v[m])
        if cf and ce:
            p = cen(np.vstack(cf)) - cen(np.vstack(ce))
            p = orth(p, fa)
            self.info["palmar_" + s] = "forearm flexor vs extensor muscles (%d / %d structures)" % (len(cf), len(ce))
        else:
            # fallback: the anterior side of the supinated forearm (ASSUMPTION)
            p = orth(self.A_, fa)
            self.info["palmar_" + s] = "ASSUMPTION: no forearm flexor/extensor muscles found, palm = anterior"
        self.pal = p

    def _pelvis_frame(self):
        """pelvis frame (right, up, anterior) in MODEL space, ISB-like: right = left hip centre -> right hip centre; forward = mid-PSIS -> mid-ASIS (perpendicular to right); ASIS / PSIS = the most anterior / posterior
        points of the upper ilium (hip-bone vertices more than 40 mm above the hip centres), up = forward x right"""
        K = self.K
        rp = unit(self._hips["r"] - self._hips["l"])
        hy = (self._hips["r"][1] + self._hips["l"][1]) / 2
        pts = {}
        for s in SIDES:
            hb = K.B["hip_bone_" + s]["v"]
            up_il = hb[hb[:, 1] > hy + 40.0]
            if len(up_il) < 50:
                up_il = hb[hb[:, 1] > hb[:, 1].min() + 0.6 * np.ptp(hb[:, 1])]
            pts[s] = (trimmed_extreme(up_il, self.A_, 0.02), trimmed_extreme(up_il, -self.A_, 0.02))
        asis = (pts["r"][0] + pts["l"][0]) / 2; psis = (pts["r"][1] + pts["l"][1]) / 2
        f = orth(asis - psis, rp)
        up = np.cross(f, rp)
        if up @ self.U_ < 0:
            up = -up
        if np.cross(rp, up) @ f < 0:
            pass
        self.pelvis_frame = np.c_[rp, unit(up), f]
        self.info["asis_psis"] = dict(asis_r=pts["r"][0].round(1).tolist(), asis_l=pts["l"][0].round(1).tolist(), psis_r=pts["r"][1].round(1).tolist(), psis_l=pts["l"][1].round(1).tolist())

    def pelvis_m(self, s):
        """pelvis frame in right-limb space of side s"""
        F = self.pelvis_frame
        if s == "r":
            return F
        return np.c_[-self.P.reflect(F[:, 0] + self.P.n * 0) + 0, self.vecr(F[:, 1]), self.vecr(F[:, 2])] if False else np.c_[-self.vecr(F[:, 0]), self.vecr(F[:, 1]), self.vecr(F[:, 2])]

    def vecr(self, a):
        n = self.P.n
        return a - 2 * (a @ n) * n

    # ------------------------------------------------------------ arm
    def _arm(self, s):
        K, U, E = self.K, self.U, self.K.E
        R_, U_, A_ = self.R_, self.U_, self.A_
        S = s
        # segments
        thor = "v" + self._thorax_vert()
        self.seg("clav_" + s, thor, "Clavicle " + s.upper(), s)
        self.seg("scap_" + s, "clav_" + s, "Scapula " + s.upper(), s)
        self.seg("hum_" + s, "scap_" + s, "Humerus " + s.upper(), s)
        self.seg("uln_" + s, "hum_" + s, "Ulna " + s.upper(), s)
        self.seg("rad_" + s, "uln_" + s, "Radius " + s.upper(), s)
        self.seg("hand_" + s, "rad_" + s, "Hand " + s.upper(), s)
        cl = K.V("clavicle", s); sc = K.V("scapula", s)
        st = cen(K.bv("sternum")) if "sternum" in K.B else cen(K.spine[0]["v"])
        d = np.linalg.norm(cl - st, axis=1)
        sc_pt = cl[d <= np.percentile(d, 4)].mean(0)           # sternoclavicular joint: the sternal end of the clavicle
        ac_pt = cl[d >= np.percentile(d, 96)].mean(0)          # acromioclavicular joint: the acromial end
        gh, elbow, wrist = U["gh"], U["elbow"], U["wrist"]
        cs_, ws_, Vs_ = pca(sc)
        n_sc = Vs_[:, 2]                                       # scapular plane normal (blade = thinnest direction)
        # ---- shoulder
        up_h = unit(gh - elbow)
        lat_h = orth(U["elbow_axis"], up_h)
        # the sign of the lateral (epicondylar) axis comes from the bones (radius lateral to ulna); the elbow does not hyperextend, so a flexion angle below -15 deg means the sign is wrong
        fl_ = signed_angle(-up_h, unit(wrist - elbow), axis_for(-up_h, np.cross(lat_h, up_h), lat_h))
        if fl_ < -15.0:
            lat_h = -lat_h
            self.info["elbow_lat_flipped_" + s] = True
        ant_h = unit(np.cross(lat_h, up_h))
        H = np.c_[lat_h, up_h, ant_h]
        Tm = np.c_[R_, U_, A_]
        D0 = H @ Tm.T
        a_fl = axis_for(-U_, A_, R_); a_ab = axis_for(-U_, R_, A_); a_ro = axis_for(R_, A_, U_)
        q, err = solve_euler([a_fl, a_ab, a_ro], D0)
        self.info["shoulder_fit_rms_%s" % s] = err
        dofs = [dict(k="flex", a=a_fl, q0=q[0], **self._r("shoulder_flex")), dict(k="abd", a=a_ab, q0=q[1], **self._r("shoulder_abd")), dict(k="rot", a=a_ro, q0=q[2], **self._r("shoulder_rot"))]
        thor = "v" + self._thorax_vert()
        self.add_joint("shoulder_" + s, "Shoulder", "Shoulder", s, "hum_" + s, "scap_" + s, gh, dofs, ref=thor,
                       note="Flexion about the mediolateral axis, then abduction about the anteroposterior axis, then rotation about the humeral axis (intrinsic order); angles relative to the trunk. "
                            "Clavicle and scapula follow with a fixed scapulohumeral rhythm (scapula rotates by 1/3 of the humeral elevation)")
        self.joints[-1]["down"] = [float(x) for x in self.vec(s, -U_)]       # anatomical arm direction (model space), reference of the humeral elevation e
        # scapulohumeral rhythm (coupled joints, driven by the shoulder elevation e): clavicle about SC by e/12, scapula about AC by e/4 (total e/3 = 2:1 GH:ST ratio, Inman 1944)
        sc_ax = axis_for(ac_pt - sc_pt, U_, A_)                 # elevation of the lateral clavicle end about the AP axis
        self.add_joint("sc_" + s, "Sternoclavicular (coupled)", "Shoulder", s, "clav_" + s, thor, sc_pt,
                       [dict(k="elev", a=sc_ax, q0=0.0, lo=0, hi=0, label="driven by the shoulder", drv=dict(src="shoulder_" + s, k=1.0 / 12.0))],
                       driven="rhythm", note="coupled: clavicle elevation = 1/12 of the humeral elevation")
        ac_ax = axis_for(gh - ac_pt, U_, n_sc)                  # upward rotation of the scapula about its plane normal through the AC joint
        self.add_joint("ac_" + s, "Acromioclavicular (coupled)", "Shoulder", s, "scap_" + s, "clav_" + s, ac_pt,
                       [dict(k="rot", a=ac_ax, q0=0.0, lo=0, hi=0, label="driven by the shoulder", drv=dict(src="shoulder_" + s, k=0.25))],
                       driven="rhythm", note="coupled: scapular upward rotation = 1/4 of the humeral elevation")
        # ---- elbow
        a_el = axis_for(-up_h, ant_h, lat_h)
        q0 = signed_angle(-up_h, unit(wrist - elbow), a_el)
        self.add_joint("elbow_" + s, "Elbow", "Elbow / forearm", s, "uln_" + s, "hum_" + s, elbow, [dict(k="flex", a=a_el, q0=q0, **self._r("elbow_flex"))],
                       note="hinge about the transepicondylar axis")
        # ---- forearm
        fa = U["fore_axis"]
        w_ant = unit(np.cross(fa, lat_h))
        a_pr = axis_for(orth(lat_h, fa), w_ant, fa)
        rdir = U["radial_dir"]
        p0 = signed_angle(lat_h, rdir, a_pr)               # ISB pronation angle from supination (rotation lateral -> anterior)
        q0 = wrap(90.0 - p0)
        self.add_joint("forearm_" + s, "Forearm rotation", "Elbow / forearm", s, "rad_" + s, "uln_" + s, U["rad_head"], [dict(k="sup", a=-a_pr, q0=q0, **self._r("forearm_sup"))],
                       note="radius rotates about the line radial head - ulnar head; 0 = neutral (thumb up, AAOS)")
        # ---- wrist
        p = self.pal
        hv = [self.K.bv(k) for k in self.K.B if k.startswith(("mc_", "metacarpal", "metacarpals_")) and k.endswith("_" + s)]
        hv = np.vstack(hv) if hv else U["carpus"][None, :]
        d_h = unit(cen(hv) - U["wrist"])
        r = rdir
        a_wf = axis_for(d_h, p, r); a_wd = axis_for(d_h, r, p)
        q0f = signed_angle(fa, d_h, a_wf); q0d = signed_angle(fa, d_h, a_wd)
        self.add_joint("wrist_" + s, "Wrist", "Wrist / hand", s, "hand_" + s, "rad_" + s, U["wrist"],
                       [dict(k="flex", a=a_wf, q0=q0f, **self._r("wrist_flex")), dict(k="dev", a=a_wd, q0=q0d, **self._r("wrist_dev"))],
                       note="flexion about the radio-ulnar axis of the wrist, then radial/ulnar deviation about the axis normal to the palm; carpal bones move with the hand (no intercarpal motion)")
        self.hand = dict(d_h=d_h, r=r, p=p)
        self._fingers(s)

    def _thorax_vert(self):
        if not hasattr(self, "_tv"):
            K = self.K
            st = cen(K.bv("sternum")) if "sternum" in K.B else None
            thor = [v for v in K.spine if v["region"] == "thoracic"]
            if st is not None and thor:
                v = min(thor, key=lambda v: abs(v["c"][1] - st[1]))
            elif thor:
                v = thor[len(thor) // 2]
            else:
                v = K.spine[len(K.spine) // 2]
            self._tv = v["label"]
        return self._tv

    def _r(self, key):
        lo, hi, lab, src = ROM[key]
        return dict(lo=lo, hi=hi, label=lab, rom=src, rk=key)

    # ------------------------------------------------------------ fingers (individual bones only)
    def _head_center(self, v, u, rmin=4.5, rmax=12.0):
        """centre of the distal head of a metacarpal / phalanx: sphere fit to the distal 30% (RANSAC) when it lies within 7 mm of the distal-end centroid, else that centroid (distal 15%)"""
        R, L = self.K.region(v, u, "dist", 0.30)
        Rd, _ = self.K.region(v, u, "dist", 0.15)
        cd = Rd.mean(0)
        f = sphere_ransac(R, rmin, rmax, tol=0.8, iters=600, seed=5) if len(R) > 20 else None
        if f is not None and np.linalg.norm(f[0] - cd) < 7.0:
            return f[0]
        return cd

    def _tip(self, v, u):
        return trimmed_extreme(v, u, 0.04)

    def _bone_u(self, v, ref_prox):
        c, w, V = pca(v)
        u = V[:, 0]
        if (u @ (c - ref_prox)) < 0:
            u = -u
        return u

    def _fingers(self, s):
        hb = self.U["hand_bones"]
        if not any(hb[f].get("prox") is not None for f in range(1, 6)):
            self.info["fingers_" + s] = "not available: phalanges are merged into one mesh on this page (hand moves as one rigid segment)"
            return
        wr = self.U["wrist"]; r, p, d_h = self.hand["r"], self.hand["p"], self.hand["d_h"]
        info = []
        for f in range(1, 6):
            b = hb[f]
            if b.get("mc") is None or b.get("prox") is None or b.get("dist") is None:
                continue
            mc, pp, dp = b["mc"], b["prox"], b["dist"]
            mp = b.get("mid")
            u_mc = self._bone_u(mc, wr)
            mc_base = self.K.region(mc, u_mc, "prox", 0.12)[0].mean(0)
            mcp_c = self._head_center(mc, u_mc)
            u_pp0 = self._bone_u(pp, mcp_c)
            if f == 1:
                ip_c = self._head_center(pp, u_pp0)
                u_dp0 = self._bone_u(dp, ip_c)
                tip = self._tip(dp, u_dp0)
                d_mc, d_pp, d_dp = unit(mcp_c - mc_base), unit(ip_c - mcp_c), unit(tip - ip_c)
                self.seg("th_mc_" + s, "hand_" + s, "Thumb metacarpal " + s.upper(), s)
                self.seg("th_p_" + s, "th_mc_" + s, "Thumb proximal phalanx " + s.upper(), s)
                self.seg("th_d_" + s, "th_p_" + s, "Thumb distal phalanx " + s.upper(), s)
                d1 = d_mc
                a_f = axis_for(d1, unit(-r), p)                        # flexion: across the palm (toward the ulnar side)
                a_a = axis_for(d1, p, orth(np.cross(p, d1), d1))        # palmar abduction: away from the palm plane
                d2 = self._bone_u(hb[2]["mc"], wr) if hb[2].get("mc") is not None else d_h
                q0f = signed_angle(d2, d1, a_f); q0a = signed_angle(d2, d1, a_a)
                self.add_joint("thumb_cmc_" + s, "Thumb CMC", "Thumb", s, "th_mc_" + s, "hand_" + s, mc_base,
                               [dict(k="flex", a=a_f, q0=q0f, **self._r("thumb_cmc_flex")), dict(k="abd", a=a_a, q0=q0a, **self._r("thumb_cmc_abd"))],
                               note="saddle joint approximated by two axes: flexion across the palm, palmar abduction out of it")
                tg = unit(-r + 0.5 * p)
                a1 = axis_for(d_mc, tg, np.cross(d_mc, tg)); q1 = signed_angle(d_mc, d_pp, a1)
                self.add_joint("thumb_mcp_" + s, "Thumb MCP", "Thumb", s, "th_p_" + s, "th_mc_" + s, mcp_c, [dict(k="flex", a=a1, q0=q1, **self._r("thumb_mcp"))])
                a2 = axis_for(d_pp, tg, np.cross(d_pp, tg)); q2 = signed_angle(d_pp, d_dp, a2)
                self.add_joint("thumb_ip_" + s, "Thumb IP", "Thumb", s, "th_d_" + s, "th_p_" + s, ip_c, [dict(k="flex", a=a2, q0=q2, **self._r("thumb_ip"))])
                info.append(1)
                continue
            if mp is None:
                continue
            self.seg("f%d_p_%s" % (f, s), "hand_" + s, "Finger %d proximal phalanx %s" % (f, s.upper()), s)
            self.seg("f%d_m_%s" % (f, s), "f%d_p_%s" % (f, s), "Finger %d middle phalanx %s" % (f, s.upper()), s)
            self.seg("f%d_d_%s" % (f, s), "f%d_m_%s" % (f, s), "Finger %d distal phalanx %s" % (f, s.upper()), s)
            pip_c = self._head_center(pp, u_pp0)
            u_mp0 = self._bone_u(mp, pip_c)
            dip_c = self._head_center(mp, u_mp0)
            u_dp0 = self._bone_u(dp, dip_c)
            tip = self._tip(dp, u_dp0)
            d_mc, d_pp, d_mp, d_dp = unit(mcp_c - mc_base), unit(pip_c - mcp_c), unit(dip_c - pip_c), unit(tip - dip_c)
            nm = ("Index", "Middle", "Ring", "Little")[f - 2]
            for (jn, par, seg, c, ua, ub, key, lab) in (("mcp", "hand_" + s, "f%d_p_%s" % (f, s), mcp_c, d_mc, d_pp, "finger_mcp", "MCP"),
                                                        ("pip", "f%d_p_%s" % (f, s), "f%d_m_%s" % (f, s), pip_c, d_pp, d_mp, "finger_pip", "PIP"),
                                                        ("dip", "f%d_m_%s" % (f, s), "f%d_d_%s" % (f, s), dip_c, d_mp, d_dp, "finger_dip", "DIP")):
                a = axis_for(ua, p, orth(r, ua))                           # flexion moves the distal segment toward the palm, axis along the radio-ulnar direction
                q0 = signed_angle(ua, ub, a)
                self.add_joint("f%d_%s_%s" % (f, jn, s), "%s finger %s" % (nm, lab), "Fingers", s, seg, par, c, [dict(k="flex", a=a, q0=q0, **self._r(key))])
            info.append(f)
        self.info["fingers_" + s] = "chains for fingers %s" % info

    # ------------------------------------------------------------ leg
    def _leg(self, s):
        K, L = self.K, self.Lw
        R_, U_, A_ = self.R_, self.U_, self.A_
        fem = self.seg("fem_" + s, "pelvis", "Femur " + s.upper(), s)
        pat = self.seg("pat_" + s, "fem_" + s, "Patella " + s.upper(), s)
        tib = self.seg("tib_" + s, "fem_" + s, "Tibia + fibula " + s.upper(), s)
        tal = self.seg("tal_" + s, "tib_" + s, "Talus " + s.upper(), s)
        foot = self.seg("foot_" + s, "tal_" + s, "Foot (calcaneus, midfoot, metatarsals) " + s.upper(), s)
        Pm = self.pelvis_m(s)
        rp, up_p, ap = Pm[:, 0], Pm[:, 1], Pm[:, 2]
        # hip
        up_f = unit(L["hip"] - L["knee"])
        lat_f = orth(L["knee_axis"], up_f)
        fk_ = signed_angle(-up_f, unit(L["ankle"] - L["knee"]), axis_for(-up_f, -np.cross(lat_f, up_f), lat_f))
        if fk_ < -15.0:
            lat_f = -lat_f
            self.info["knee_lat_flipped_" + s] = True
        ant_f = unit(np.cross(lat_f, up_f))
        F = np.c_[lat_f, up_f, ant_f]
        D0 = F @ Pm.T
        a_fl = axis_for(-up_p, ap, rp); a_ab = axis_for(-up_p, rp, ap); a_ro = axis_for(rp, ap, up_p)
        q, err = solve_euler([a_fl, a_ab, a_ro], D0)
        self.info["hip_fit_rms_%s" % s] = err
        self.add_joint("hip_" + s, "Hip", "Hip", s, "fem_" + s, "pelvis", L["hip"],
                       [dict(k="flex", a=a_fl, q0=q[0], **self._r("hip_flex")), dict(k="abd", a=a_ab, q0=q[1], **self._r("hip_abd")), dict(k="rot", a=a_ro, q0=q[2], **self._r("hip_rot"))],
                       note="flexion, then abduction, then rotation about the femoral axis (intrinsic order); angles relative to the pelvis frame (hip centres, sacrum, hip bones)")
        # knee
        a_k = axis_for(-up_f, -ant_f, lat_f)
        q0 = signed_angle(-up_f, unit(L["ankle"] - L["knee"]), a_k)
        self.add_joint("knee_" + s, "Knee", "Knee", s, "tib_" + s, "fem_" + s, L["knee"], [dict(k="flex", a=a_k, q0=q0, **self._r("knee_flex"))],
                       note="hinge about the transepicondylar axis (no tibial rotation / screw-home in this preview)")
        self.add_joint("patella_" + s, "Patella (coupled)", "Knee", s, "pat_" + s, "fem_" + s, L["knee"], [dict(k="flex", a=a_k, q0=0.0, lo=0, hi=0, label="driven by the knee", drv=dict(src="knee_" + s, k=0.6))],
                       driven="coupled", note="patella follows 60% of the knee flexion angle about the same axis (ASSUMPTION, Hehne 1990-type ratio)")
        # ankle: foot frame (sole plane: heel + forefoot points) relative to the tibia frame (lateral = knee axis made perpendicular to the shank) -> dorsiflexion / inversion / foot rotation
        up_t = -L["tib_u"]
        lat_t = orth(lat_f, up_t)
        ant_t = unit(np.cross(lat_t, up_t))
        fwd = L["foot_fwd"]
        dors = L["foot_n"]
        lat_foot = orth(L["mt_lat"] - L["mt_med"], fwd)
        if lat_foot @ lat_t < 0: lat_foot = -lat_foot
        Ft = np.c_[lat_t, up_t, ant_t]
        Ff = np.c_[lat_foot, dors, fwd]
        a_dp = axis_for(ant_t, up_t, lat_t)
        a_inv = axis_for(up_t, lat_t, ant_t)
        a_rt = axis_for(ant_t, lat_t, up_t)
        qa, errf = solve_euler([a_dp, a_inv, a_rt], Ff @ Ft.T)
        self.info["ankle_fit_rms_%s" % s] = errf
        self.info["foot_rotation_%s" % s] = float(qa[2])
        self.add_joint("ankle_" + s, "Ankle", "Ankle / foot", s, "tal_" + s, "tib_" + s, L["ankle"], [dict(k="dp", a=a_dp, q0=qa[0], **self._r("ankle_dp"))],
                       note="talocrural hinge through the malleolar tips")
        # subtalar (inversion / eversion), Inman axis in the foot frame
        medial = -R_
        f_h = orth(fwd, dors)
        ax = unit(np.cos(np.radians(42)) * (np.cos(np.radians(23)) * f_h + np.sin(np.radians(23)) * medial) + np.sin(np.radians(42)) * dors)
        a_inv_j = axis_for(dors, R_, ax)
        q0i = qa[1]
        subc = cen(self.K.V("talus", s)[self.K.V("talus", s)[:, 1] < np.percentile(self.K.V("talus", s)[:, 1], 40)])
        self.add_joint("subtalar_" + s, "Ankle (subtalar)", "Ankle / foot", s, "foot_" + s, "tal_" + s, subc, [dict(k="inv", a=a_inv_j, q0=q0i, **self._r("ankle_inv"))],
                       note="subtalar axis after Inman (1976): 42 deg above the horizontal, 23 deg medial to the foot axis, through the inferior talus (literature axis, not fitted)")
        self.foot_frame = dict(fwd=fwd, dors=dors, lat=lat_foot)
        self._toes(s)

    def _toes(self, s):
        L = self.Lw
        fb = L["foot_bones"]
        if not any(fb[f].get("prox") is not None for f in range(1, 6)):
            self.info["toes_" + s] = "not available: toe bones are merged into one mesh on this page (foot moves as one rigid segment)"
            return
        ff = self.foot_frame
        dors, lat = ff["dors"], ff["lat"]
        info = []
        for f in range(1, 6):
            b = fb[f]
            if b.get("mt") is None or b.get("prox") is None:
                continue
            mt, pp, mp, dp = b["mt"], b["prox"], b.get("mid"), b.get("dist")
            u_mt = self._bone_u(mt, L["calcaneus"])
            mt_base = self.K.region(mt, u_mt, "prox", 0.10)[0].mean(0)
            mtp_c = self._head_center(mt, u_mt, 5, 14)
            u_pp0 = self._bone_u(pp, mtp_c)
            cs = [mtp_c]
            if f == 1 and dp is not None:
                ipc = self._head_center(pp, u_pp0, 5, 14); u_dp0 = self._bone_u(dp, ipc)
                cs += [ipc, self._tip(dp, u_dp0)]
                spec = [("mtp", "toe1_mtp", "MTP", "foot_" + s, "t1_p_%s" % s), ("ip", "toe1_ip", "IP", "t1_p_%s" % s, "t1_d_%s" % s)]
            elif mp is not None and dp is not None:
                pc = self._head_center(pp, u_pp0, 4, 12); u_mp0 = self._bone_u(mp, pc)
                dc = self._head_center(mp, u_mp0, 3, 10); u_dp0 = self._bone_u(dp, dc)
                cs += [pc, dc, self._tip(dp, u_dp0)]
                spec = [("mtp", "toe_mtp", "MTP", "foot_" + s, "t%d_p_%s" % (f, s)), ("pip", "toe_pip", "PIP", "t%d_p_%s" % (f, s), "t%d_m_%s" % (f, s)), ("dip", "toe_dip", "DIP", "t%d_m_%s" % (f, s), "t%d_d_%s" % (f, s))]
            else:
                continue
            ds = [unit(mtp_c - mt_base)] + [unit(cs[i + 1] - cs[i]) for i in range(len(cs) - 1)]
            for i, (jn, key, lab, par, sg) in enumerate(spec):
                self.seg(sg, par, "Toe %d %s %s" % (f, lab, s.upper()), s)
                ua, ub = ds[i], ds[i + 1]
                a = axis_for(ua, -dors, orth(lat, ua))              # flexion curls the toe toward the sole
                q0 = signed_angle(ua, ub, a)
                self.add_joint("t%d_%s_%s" % (f, jn, s), "Toe %d %s" % (f, lab), "Toes", s, sg, par, cs[i], [dict(k="flex", a=a, q0=q0, **self._r(key))])
            info.append(f)
        self.info["toes_" + s] = "chains for toes %s" % info

    # ------------------------------------------------------------ bones -> segments
    def _assign_bones(self):
        K = self.K
        B = K.B
        bs = {}
        vert_seg = {v["key"]: "v" + v["label"] for v in K.spine}
        thor = "v" + self._thorax_vert()
        for k in B:
            sd = k[-1] if k.endswith(("_l", "_r")) else None
            if k in vert_seg:
                bs[k] = vert_seg[k]; continue
            if k in ("sacrum", "coccyx") or k.startswith("hip_bone"):
                bs[k] = "pelvis"; continue
            if k in ("sternum", "xiphoid_process"):
                bs[k] = thor; continue
            if k.startswith(("rib_", "ribs_")):
                self.soft_bones.add(k); continue
            if k.startswith("clavicle"):
                bs[k] = "clav_" + sd; continue
            if k.startswith("scapula"):
                bs[k] = "scap_" + sd; continue
            if sd is None:
                if k == "hyoid":
                    bs[k] = "v" + min([v for v in K.spine if v["region"] == "cervical"], key=lambda v: abs(v["c"][1] - cen(K.bv("hyoid"))[1]))["label"] if "hyoid" in B else "head"
                else:
                    bs[k] = "head" if k in ("mandible", "cranium", "frontal", "occipital", "sphenoid", "ethmoid", "vomer") or k.startswith("head_misc") else None
                continue
            nm = k[:-2]
            if nm == "humerus": bs[k] = "hum_" + sd
            elif nm == "ulna": bs[k] = "uln_" + sd
            elif nm == "radius": bs[k] = "rad_" + sd
            elif nm.startswith("carpal") or nm.startswith("metacarpal") or nm == "phalanges_hand": bs[k] = "hand_" + sd
            elif re.match(r"mc_[2-5]$", nm): bs[k] = "hand_" + sd
            elif nm == "mc_1": bs[k] = ("th_mc_" + sd) if ("th_mc_" + sd) in self.sid else "hand_" + sd
            elif re.match(r"ph_hand_(\d)_(prox|midd|dist)$", nm):
                f, sg = re.match(r"ph_hand_(\d)_(prox|midd|dist)$", nm).groups()
                if f == "1":
                    t = "th_p_" if sg == "prox" else "th_d_"
                else:
                    t = "f%s_%s_" % (f, {"prox": "p", "midd": "m", "dist": "d"}[sg])
                bs[k] = t + sd if (t + sd) in self.sid else "hand_" + sd
            elif nm == "femur": bs[k] = "fem_" + sd
            elif nm == "patella": bs[k] = "pat_" + sd
            elif nm in ("tibia", "fibula"): bs[k] = "tib_" + sd
            elif nm == "talus": bs[k] = "tal_" + sd
            elif re.match(r"ph_foot_(\d)_(prox|midd|dist)$", nm):
                f, sg = re.match(r"ph_foot_(\d)_(prox|midd|dist)$", nm).groups()
                t = "t%s_%s_" % (f, {"prox": "p", "midd": "m", "dist": "d"}[sg])
                bs[k] = t + sd if (t + sd) in self.sid else "foot_" + sd
            elif nm in ("calcaneus", "navicular", "cuboid", "metatarsals", "phalanges_foot") or nm.startswith(("cuneiform", "mt_", "sesamoid")): bs[k] = "foot_" + sd
            elif nm in ("temporal", "zygomatic", "maxilla", "parietal", "nasal", "lacrimal", "palatine", "inferior_nasal_concha") or nm.startswith("head_misc"): bs[k] = "head"
            else: bs[k] = None
        self.bone_seg = bs

    def export(self):
        return dict(segments=self.segs, joints=self.joints, regions=self.regions)


if __name__ == "__main__":
    import sys, json
    M = MD.Model(sys.argv[1])
    RB = RigBuilder(M)
    rig = RB.build()
    print(len(rig["segments"]), "segments", len(rig["joints"]), "joints", len(rig["regions"]), "regions")
    for j in rig["joints"]:
        if j["side"] in ("r",) or j["side"] == "m":
            print(j["id"], [(d["k"], round(d["q0"], 1), d["lo"], d["hi"]) for d in j["dof"]])
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in RB.info.items()})
    unm = [k for k in RB.K.B if k not in RB.bone_seg and k not in RB.soft_bones]
    print("unmapped", unm)
    print("none-mapped", [k for k, v in RB.bone_seg.items() if v is None][:50])
