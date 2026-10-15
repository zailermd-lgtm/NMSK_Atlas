"""Q241 quick pose previews (matplotlib, orthographic point clouds of bones + a few soft tissue classes) for the python rig; development aid."""
import sys, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import model as MD, rig as RG, skin as SK, fk as FK


def setq(rig, pose, jid, k, val):
    for j in rig["joints"]:
        if j["id"] == jid:
            for n, d in enumerate(j["dof"]):
                if d["k"] == k:
                    pose["joints"][jid][n] = val
            return
    for r in rig["regions"]:
        if r["id"] == jid:
            for n, d in enumerate(r["dof"]):
                if d["k"] == k:
                    pose["regions"][jid][n] = val
            return
    raise KeyError(jid)


def render(M, rig, out, poses, fn, layers=("bone", "muscle", "skin", "vessel", "nerve"), views=("front", "side")):
    fig, axs = plt.subplots(len(poses), len(views), figsize=(5 * len(views), 8 * len(poses)), squeeze=False)
    col = dict(bone="#e8e0c8", muscle="#b04040", skin="#d8a080", vessel="#3050c0", nerve="#d0b020", viscera="#60a060", cartilage="#80c0c0")
    for r, (title, pose) in enumerate(poses):
        Ms = FK.fk(rig, pose)
        pv = SK.apply_pose(M.S, out, Ms)
        for c, vw in enumerate(views):
            ax = axs[r][c]
            for sysn in layers:
                P = np.vstack([pv[x["idx"]][::max(1, len(x["v"]) // (60 if sysn != "bone" else 120))] for x in M.S if x["sys"] == sysn]) if any(x["sys"] == sysn for x in M.S) else None
                if P is None: continue
                a = (P[:, 0], P[:, 1]) if vw == "front" else (P[:, 2], P[:, 1])
                ax.scatter(*a, s=0.3, c=col.get(sysn, "gray"), alpha=0.5 if sysn == "skin" else 0.9, linewidths=0)
            ax.set_aspect("equal"); ax.set_title(title + " " + vw); ax.axis("off")
    plt.tight_layout(); plt.savefig(fn, dpi=60); plt.close()


if __name__ == "__main__":
    key = sys.argv[1]
    M = MD.Model(key); RB = RG.RigBuilder(M); rig = RB.build()
    out, st = SK.compute(M, RB)
    base = FK.default_pose(rig)
    poses = [("rest", base)]
    import copy
    p = copy.deepcopy(base); setq(rig, p, "elbow_r", "flex", 90); setq(rig, p, "shoulder_l", "abd", 90); setq(rig, p, "hip_r", "flex", 90); setq(rig, p, "knee_r", "flex", 90); setq(rig, p, "knee_l", "flex", 90)
    poses.append(("elbowR90 shoulderL abd90 hipR90 kneeL/R90", p))
    render(M, rig, out, poses, sys.argv[2], layers=("bone", "muscle"))
