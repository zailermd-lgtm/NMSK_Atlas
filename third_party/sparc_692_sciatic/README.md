# SPARC dataset 692: a real measured human sciatic nerve, used as a calibre reference (Q304)

This directory holds the licence, the attribution and the change statement for the only use this project makes
of SPARC dataset 692: **the calibre of a real human sciatic nerve, as numbers**. No geometry from the dataset is
vendored, shipped or displayed. See `NOTICE` for the full attribution, the subject description and the required
citation, and `LICENSE` for the CC BY 4.0 legal code.

## Why only numbers

The dataset is 369.7 GB of microCT at 11.4 um. Q302 established that it cannot supply shape: its six samples are
~9 cm segments that were **excised and laid straight in the scanner**, so a traced centreline is a straight line
in scan space and carries no in-body trajectory. Its five annotated branches are all tibial-division hamstring
branches; it contains no common fibular (peroneal) nerve. What it does carry, and what no other reachable source
carries, is a **measured cross-sectional size of a human sciatic nerve at named bone-referenced levels**.

## What was downloaded

`scripts/anatomy/q304/sparc304.py fetch` downloads 23 files, about 9.0 MB in total, from the dataset's own public
object store into an empty directory under `/dev/shm`, and records every file's size and sha256 in
`data/derived/Q304_sparc692_calibre.json` (`files`). Nothing is kept on disk but the derived numbers.

| what | files | bytes |
|---|---|---|
| `NerveMorphology.csv` per sample (per-slice area, perimeter, equivalent diameter, centre, axes, angle) | 6 | 6,116,717 |
| `sciatic_levels.csv` per sample (the slice index of each named anatomical level) | 6 | 1,403 |
| the sciatic trunk's own traced centreline per sample (read only to re-check Q302's "laid straight" finding) | 6 | 2,757,707 |
| `README.md`, `dataset_description.xlsx`, `samples.xlsx`, `subjects.xlsx`, `manifest.json` | 5 | 86,376 |

## The measurement, and what it is compared against

`sparc304.py measure` converts the morphology columns from voxels to millimetres (0.0114 mm per voxel -- the
columns are in voxels, which is the one trap in this dataset) and reads the equivalent diameter at each named
level over a +-2 mm window of slices. `sparc304.py ours` measures the same quantity on each of this project's six
pages: the equivalent diameter of a cross-section cut **perpendicular to our own nerve's local axis**, at the
same five levels placed on that page's own femur and sacrum by one geometric rule used identically on all six
pages. `sparc304.py compare` writes the differences to `data/derived/Q304_sparc692_comparison.json`.

## What was decided, and why no mesh changed

Our sciatic nerve matches the measured calibre within about a quarter in the mid and distal thigh and is 1.4 to
2.3 times too thick at the two proximal levels. The geometry was **not** changed: the SPARC specimen is embalmed,
PTA-stained and excised, so it is a lower bound on a living nerve and rescaling to it would swap one bias for
another; and it is one subject, while the rescale would have to run along the whole course of our mesh, which is
a sculpting operation rather than a measurement. The discrepancy is written on the sciatic nerve's card on every
one of the six pages instead, with this DOI.
