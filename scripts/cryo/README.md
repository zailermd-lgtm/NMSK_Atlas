# Visible Human male cryosections (colour) -- pipeline

Source: NLM Visible Human Project, male, "Fullcolor - direct digital"
cryosection series on the IDC mirror (`gs://idc-open-data/4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385/`),
1878 axial RGB photographs, 2048 x 1216 px at 0.33 mm, 1 mm apart, vertex
(z = -1001 mm in the DICOM frame) to the soles (z = -2878). Public domain.

1. `stream_vhm_cryosections.py` -- streams every DICOM (7.5 MB each, 14 GB
   in all) and keeps only a 3x3-averaged copy (~1 mm) in `cryo_1mm.npy`
   (1878 x 405 x 682 x 3, 1.6 GB); nothing is written to disk at full size.
   `cryo_index.json` maps array index -> object -> z.
2. `cryo_classes.py` / `classify_cryo_volume.py` -- per-pixel colour
   classes: 1 tissue, 2 fat (pale cream/yellow), 3 muscle (red-brown),
   4 pale connective (tendon, fascia, nerve, cartilage), 5 white (cortical
   bone). The blue gelatin is the background. These are colour thresholds
   read off the photographs, not a trained model; bone marrow and cortex
   are cream, close to fat, so bone is best taken from the CT wherever the
   CT has it and from the photographs only where the CT field of view
   clips the arms.
3. `register_cryo_to_ct.py` -- the photographs were taken block by block
   and some blocks are flipped relative to the CT (the abdomen block has
   the spine at the top of the frame, the thorax block at the bottom).
   For CT anchor slices it searches the cryo index and the four flips,
   aligning silhouettes by phase correlation, and writes `anchors.json`.
   The cryo volume is placed in the atlas frame through the CT (same
   torso-frame origin), never on its own.

What the photographs are used for, and not: bone where the CT is clipped
(elbow region, hands); muscle compartments where fascial planes are
visible. Individual muscle naming from the photographs needs review slice
by slice and is not automatic; what ships from them is labelled as such.
