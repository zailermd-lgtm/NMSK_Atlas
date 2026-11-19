# Recovered male viewer bundle (Version 25)

`bundle.json` + `bundle.bin` are the decimated, 0.25 mm-quantised meshes of every structure in the
male viewer as published (artifact c5d01522, Version 25, 2026-09-11), read back from the published
HTML with `scripts/transfer/bundle_io.py`. Kept in the repository because the male's source meshes
cannot be rebuilt after a container reset (the DU lower-limb STL hosts are denied by the network
policy and his cryosection skin is not stored), while the female's are. `scripts/transfer/
bundle_to_subjects.py` unpacks it into `build/vh/<subject>/` for `scripts/export_viewer_bundle.py`;
`scripts/transfer/cross_subject_transfer.py` reads it as the source of the male-to-female transfer.

Attribution travels with it (see `attribution` in bundle.json): NLM Visible Human Project imagery;
lower-extremity geometry from Andreassen et al. 2023 (Sci Data 10:34, CC BY 4.0).
