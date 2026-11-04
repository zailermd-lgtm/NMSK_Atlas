"""Q241 forward kinematics of a rig dict (see rig.py header); the viewer (pose.js) implements the same maths."""
from __future__ import annotations
import numpy as np
from geom import rot, about, T4, unit


def joint_R(j, q):
    """R(q) = Rot(a1,q1) Rot(a2,q2) Rot(a3,q3)"""
    R = np.eye(3)
    for d, v in zip(j["dof"], q):
        R = R @ rot(d["a"], v)
    return R


def default_pose(rig):
    return {"joints": {j["id"]: [d["q0"] for d in j["dof"]] for j in rig["joints"]},
            "regions": {r["id"]: [0.0 for _ in r["dof"]] for r in rig["regions"]}}


def anatomical_pose(rig):
    """every displayed value = 0 (clamped to its range; driven joints follow)"""
    P = default_pose(rig)
    for j in rig["joints"]:
        P["joints"][j["id"]] = [min(max(0.0, d["lo"]), d["hi"]) if not d.get("drv") else d["q0"] for d in j["dof"]]
    return P


def elevation(rig, jid_vals, j):
    """humeral elevation e (deg) of a shoulder joint for displayed values: angle between R(q)(down) and down; down = -dof axis geometry is not stored, so use the humerus axis stored as the first dof's frame:
    the shoulder carries 'down' in j['down'] (model space unit vector of the anatomical arm direction)."""
    R = joint_R(j, jid_vals)
    dn = np.array(j["down"])
    v = R @ dn
    return float(np.degrees(np.arccos(np.clip(v @ dn, -1, 1))))


def fk(rig, pose):
    segs, joints, regions = rig["segments"], rig["joints"], rig["regions"]
    byseg = {j["seg"]: j for j in joints}
    lev = {}
    for r in regions:
        for k, L in enumerate(r["levels"]):
            lev[L["seg"]] = (r, k, L)
    Jid = {j["id"]: j for j in joints}
    M = [np.eye(4) for _ in segs]
    for i in range(1, len(segs)):
        par = segs[i]["par"]
        if i in lev:
            r, k, L = lev[i]
            th = pose["regions"][r["id"]]
            R = np.eye(3)
            for d, t in zip(r["dof"], th):
                R = R @ rot(d["a"], t * d["w"][k])
            M[i] = M[par] @ about(R, np.array(L["c"]))
            continue
        j = byseg.get(i)
        if j is None:
            M[i] = M[par].copy(); continue
        q = pose["joints"][j["id"]]
        c = np.array(j["c"])
        if j.get("driven"):
            d = j["dof"][0]; src = Jid[d["drv"]["src"]]
            sq = pose["joints"][src["id"]]
            if src["id"].startswith("shoulder"):
                ang = d["drv"]["k"] * (elevation(rig, sq, src) - elevation(rig, [dd["q0"] for dd in src["dof"]], src))
            else:
                ang = d["drv"]["k"] * (sq[0] - src["dof"][0]["q0"])
            dR = rot(d["a"], ang)
        else:
            dR = joint_R(j, q) @ joint_R(j, [d["q0"] for d in j["dof"]]).T
        if j["ref"] >= 0:
            Rref = M[j["ref"]][:3, :3]
            Rt = Rref @ dR
            pos = M[par][:3, :3] @ c + M[par][:3, 3]
            Mi = np.eye(4); Mi[:3, :3] = Rt; Mi[:3, 3] = pos - Rt @ c
            M[i] = Mi
        else:
            M[i] = M[par] @ about(dR, c)
    return M
