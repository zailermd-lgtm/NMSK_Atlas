"""Q259: the vagus nerve's single most clinically important absent branch -- the RECURRENT LARYNGEAL NERVE (RLN) --
on the four Z-family pages, which already carry a real cervical+upper-thoracic vagus trunk mesh (`zan_vagus_nerve_x_{l,r}`,
Q247: 'X vagus n. (cervical trunk)' = Y) to branch it from, plus real subclavian artery, aortic arch, trachea and
cricoid-cartilage meshes to anchor its textbook hook-and-ascend course against (all confirmed present before writing
this module, not assumed).

The OWN pages (Imaging F/M) are investigated too, honestly: they ship NO vagus nerve mesh at all -- not even the
cervical trunk the brief said was already present (that "Y" is true only for the four Z pages; Q247's own table
lists the own-page cells for this row as '-'). A recurrent laryngeal branch cannot be built off a trunk that does
not exist on the page: this round does NOT invent a vagus trunk to hang an RLN off, which would be exactly the kind
of guess the brief asks to avoid. Left absent on both own pages, queued precisely in docs/OPEN_ITEMS_FOR_OWNER.md
for whichever future round builds the vagus trunk itself there first (the own pages DO have the needed landmarks --
common/internal carotid arteries, subclavian artery, trachea, oesophagus -- so a rule-based vagus trunk is feasible,
just out of THIS round's scope, which is branches of an EXISTING trunk).

Course (Gray's Anatomy for Students, 4th ed., ch.8; Moore, Dalley, Agur, Clinically Oriented Anatomy, 8th ed.;
Terminologia Anatomica): the right RLN leaves the vagus where it crosses the right subclavian artery, hooks under it
and ascends in the tracheo-oesophageal groove to enter the larynx just below the inferior constrictor, at the
cricothyroid joint. The left RLN leaves the vagus where it crosses the arch of the aorta (just lateral to the
ligamentum arteriosum), hooks under the arch and ascends the SAME groove on the left -- a considerably longer course,
real anatomy this page's own landmarks reproduce directly (the aortic arch sits well below the subclavian artery on
every one of these pages, measured, not assumed). Superior laryngeal nerve, cardiac / pharyngeal branches and the
abdominal vagal trunks are NOT attempted this round -- stated plainly as still open, see docs/OPEN_ITEMS_FOR_OWNER.md.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import lmk                     # noqa: E402
from rulenerve import Builder  # noqa: E402

ROOT_DEFAULT = "build/q258"
SG = {"l": -1.0, "r": 1.0}
SOURCE = "Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.8; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, 8th ed.; Terminologia Anatomica (FICAT 1998)."
ERR = 12.0
ERR_TEXT = "landmark-rule allowance for the RLN's hook-and-ascend course (no page-specific calibre study; the tracheo-oesophageal groove itself is not separately shipped, so the ascending waypoints are approximated from the trachea's own posterolateral surface)"


def groove_point(E, s, xm, y, trachea_id):
    v = E[trachea_id]["v"]
    band = v[np.abs(v[:, 1] - y) < 8.0]
    if len(band) < 6:
        band = v
    relx = (band[:, 0] - xm) * SG[s]
    # posterolateral aspect on this side: a moderately lateral band (not the most lateral, not the midline), biased
    # toward the posterior (low-z) surface, matching the groove between the trachea and the oesophagus (posterior
    # to the trachea, slightly left of the midline in the neck -- the real reason the left groove is the more
    # reliable surgical plane, Moore & Dalley).
    lo, hi = np.percentile(relx, 55), np.percentile(relx, 90)
    sel = band[(relx >= lo) & (relx <= hi)]
    if len(sel) < 4:
        sel = band
    return sel[np.argmin(sel[:, 2])]


def build(key, root=ROOT_DEFAULT):
    S = lmk.Spine(key, root=root)
    if not S.z:
        return [], dict(reason="own pages ship no vagus trunk mesh at all (not just no branches): RLN not attempted, see module docstring")
    B = Builder(S)
    E = S.E
    xm = S.xm
    trachea_id = S.find("zan_trachea")
    cricoid_id = S.find("zan_cricoid_cartilage")
    for s in "lr":
        sw = "left" if s == "l" else "right"
        lat = "sinister" if s == "l" else "dexter"
        vagus_id = S.find(f"zan_vagus_nerve_x_{s}")
        if vagus_id is None or trachea_id is None or cricoid_id is None:
            B.hold(f"vagus_n_recurrent_laryngeal_branch_{s}", "Recurrent laryngeal nerve", "vagus trunk / trachea / cricoid cartilage not all available on this page", side=s)
            continue
        vagus_C = S.centerline(vagus_id, n=60)
        if s == "r":
            hook_id = S.find("zan_right_subclavian_artery")
        else:
            hook_id = S.find("aortic_arch_and_great_vessels")
        if hook_id is None or vagus_C is None:
            B.hold(f"vagus_n_recurrent_laryngeal_branch_{s}", "Recurrent laryngeal nerve", "subclavian artery / aortic arch mesh or vagus centreline not available on this page", side=s)
            continue
        hv = E[hook_id]["v"]
        y_hook = float(hv[:, 1].min())                 # the vessel's own inferior-most point: where the nerve hooks under it
        j = int(np.argmin(np.abs(vagus_C[:, 1] - y_hook)))
        origin = vagus_C[j]
        band = hv[np.abs(hv[:, 1] - y_hook) < 6.0]
        hook_pt = (band.mean(0) if len(band) else hv[np.argmin(hv[:, 1])]) + np.array([0.0, -2.0, 0.0])
        cric_v = E[cricoid_id]["v"]
        y_top = float(np.percentile(cric_v[:, 1], 40))
        n_groove = 4
        ys = np.linspace(y_hook + 4.0, y_top, n_groove)
        groove = [groove_point(E, s, xm, y, trachea_id) for y in ys]
        end = groove[-1] + np.array([0.0, 2.0, 2.0])
        anchors = [origin, hook_pt, *groove, end]
        e = B.mk(f"vagus_n_recurrent_laryngeal_branch_{s}", f"Recurrent laryngeal nerve ({sw})", f"Nervus laryngeus recurrens {lat}", s, anchors, 1.3, region="neck",
                 course=(f"branches from the vagus nerve where it crosses {'the right subclavian artery' if s == 'r' else 'the arch of the aorta'} (this page's own {hook_id}, measured inferior-most point), hooks under it "
                         f"and ascends in the tracheo-oesophageal groove (approximated from this page's own {trachea_id} posterolateral surface, the real groove itself not being separately shipped) to enter the larynx "
                         f"just below the inferior constrictor, near the cricothyroid joint (this page's own {cricoid_id})."),
                 calibre="no published adult diameter found for the isolated RLN; 1.3 mm = ASSUMPTION (a named cervical/thoracic nerve of intermediate calibre, between the ansa cervicalis twigs 1.0 mm and the vagus trunk "
                         "itself, which this atlas ships at 1.0-1.6 mm, Q240 calibre table)", calibre_kind="assumption", source=SOURCE, err_mm=ERR, err_text=ERR_TEXT, len_range=(30, 260), min_skin=None,
                 softpush=((trachea_id, 0.5),))
    return B.out, S.notes
