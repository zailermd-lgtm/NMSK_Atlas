# Open Anatomy Project / SPL atlas geometry (Q296)

This directory holds the licence and attributions for the only Open Anatomy geometry this project
ships: four structures of the **SPL Inner Ear Atlas**. No atlas file is vendored here -- the
geometry is fetched on demand by `scripts/anatomy/q296/ear296.py fetch` and the registered,
decimated result is written into the six viewer pages' own mesh blobs.

## What is used

| Our structure id | Atlas structure | Atlas model file |
|---|---|---|
| `oa_labyrinth_{l,r}` | Labyrinth | `models/Model_10_Labyrinth.vtk` |
| `oa_spiral_lamina_{l,r}` | Osseous Spiral Lamina | `models/Model_23_Osseous_Spiral_Lamina.vtk` |
| `oa_fenestra_cochleae_{l,r}` | Fenestra Rotunda | `models/Model_12_Fenestra_Rotunda.vtk` |
| `oa_stapedius_{l,r}` | Stapedius Muscle | `models/Model_28_Stapedius_Muscle.vtk` |

Base URL: `https://www.openanatomy.org/atlases/nac/inner-ear-2018-02/models/`.
`scripts/anatomy/q296/ear296.py` records each file's size and sha256 in its report.

The atlas's **Malleus, Incus and Stapes Bone** models are downloaded as well but are *not*
shipped: they are only the registration landmarks (see below).

## What we changed -- marked as such, per Part B paragraph 1(d)

These are **modified versions** of the atlas models. They are not the original Software and must
not be taken for it. Every modification:

1. **One similarity transform per page and side** (uniform scale, rotation, translation) from the
   bone-point registration in `scripts/anatomy/q296/reg296.py`: the atlas's malleus, incus and
   stapes are registered by per-structure nearest-point similarity ICP onto the page's own three
   ossicles, and the four imported structures ride on the same transform. No per-structure
   adjustment, no warp.
2. **The atlas's own model coordinates are uniformly about 3.15x life size** (its label maps were
   meshed with the scanner's nominal spacing, not the 140 um flat-panel voxel). The registration's
   scale term recovers this; the fitted scale comes out identical to five decimals on every page
   and side, which is the evidence that the factor is a single global scale and not a distortion.
3. **Quadric decimation to 40 % of the atlas triangle count** (`fast_simplification`, agg=5), to
   fit the viewers' triangle budget. Volume changes by less than 0.5 %.
4. **The atlas ear is a right ear.** The left-side copy is the mirror image of it, which the
   registration finds as a reflected fit; it is not an independently segmented left ear.
5. The structures are renamed to this project's naming (Terminologia Anatomica style, e.g.
   "Fenestra Rotunda" -> "Round window (fenestra cochleae)") and carry our own card text.

## What was deliberately NOT imported

* **Tympanic Membrane, Malleus, Incus, Stapes** -- the pages already have these.
* **Tensor Tympani Muscle** -- 51 % of its registered volume falls inside the page's own
  temporomandibular articular disc. Rejected on the non-penetration check.
* **Cochlear / Vestibular / Facial Nerve** -- the pages' own vestibulocochlear nerve stops ~14 mm
  short of the internal auditory canal, so these would be shipped as a visibly detached stub.
* **Internal Carotid Artery, Internal Jugular Vein** -- already present.

The full survey of all seven Open Anatomy atlases, and why nothing else cleared the bar, is in
`docs/research/Q296_openanatomy_survey.md` (Hebrew, with English anatomy terms).

See also `docs/GEOMETRY_SOURCES.md` (the separately licensed components table).
