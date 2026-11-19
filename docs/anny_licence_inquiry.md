# Anny licence inquiry (draft, not sent)

Status: draft prepared 2026-10-14. Nothing has been sent or posted. The owner sends it.

## Where to send it

1. GitHub issue (public): https://github.com/naver/anny/issues/new
   Checked 2026-10-14: 24 issues listed, none about licensing (titles only).
2. Email (private): `romain.bregier@naverlabs.com`
   Found in `pyproject.toml` of naver/anny, line 13: `{ name = "Romain Brégier", email = "romain.bregier@naverlabs.com" }`.
   The same address is the commit author of 84 of the commits. No other contact address exists in the repository.
   The arXiv paper (2511.03589) and the NAVER LABS Europe pages could not be opened from the drafting sandbox, so check them for a corresponding-author address before sending. Do not guess addresses.

## Evidence behind the questions (naver/anny, main, 135 commits)

- `README.md`, "License": "The code of Anny, Copyright (c) 2025 NAVER Corp., is licensed under the Apache License, Version 2.0".
- `README.md`: "**data/mpfb2**: *Anny* relies on MakeHuman assets adapted from MPFB2 that are licensed under the CC0 1.0 Universal License." (The folder is actually `src/anny/data/mpfb2/`; it holds `LICENSE.md` with the CC0 text.)
- `README.md`: faceunits01 (Mika Suominen) CC0; `data/soma` Apache-2.0 (from NVlabs SOMA-X); "smplx" topology "for non-commercial use only", downloaded from `noncommercial.zip` (LICENSE.txt and NOTICE.txt inside; not readable from the sandbox).
- `pyproject.toml` line 17: `license-files = ["LICENSE", "LICENSE_THINGS"]`. No file named `LICENSE_THINGS` exists at HEAD; `git log --all -S'LICENSE_THINGS'` finds only the first commit `cf47015` "Public release". It was never added to the history.
- Per-file statements inside `src/anny/data/mpfb2`: `3dobjs/base.obj` header says "This asset was explicitly released as CC0 in september 2020", with copyright holders Data Collection AB, Joel Palmius, Jonas Hauquier. `rigs/**/weights.*.json` carry `"license": "CC0"`; `weights.default.json` also has `"copyright": "Copyright (C) 2025 NAVER Corp."`.
- The 1,260 `.target.gz` files, the 10 `.jpg` and 186 `.png` files under `mpfb2` carry no per-file licence text.
- No licence statement at all for `cached/*.pth`, `keypoints/coco.pth`, `segmentation/*`, `shape_calibration/*.pth`, `topology/*.obj`, `template_mesh_internal_cavities.pth`.
- Upstream MPFB2 `LICENSE.md` (section C) lists as CC0: "The base mesh and proxies", "Targets and modifiers", "Textures", "Clothes (any MHCLO-based asset)", "Rigs, poses and expressions", "JSON data with mesh information". Its code is GPLv3.

## Message (English, ready to paste)

Subject: Licence of Anny data files (LICENSE_THINGS, mpfb2 targets/textures) - question about use in an open anatomy atlas

Dear Dr Brégier and the Anny team,

Thank you for releasing Anny. I maintain NMSK Atlas, a non-commercial, open 3D anatomy atlas whose text and models are released under CC BY-SA. I would like to use Anny only as an optional, clearly labelled external body-envelope reference (skin surface, approximate and not anatomical), with full attribution. Before I do, I would like to be sure about the licensing, and I have three specific questions.

1. `pyproject.toml` lists `license-files = ["LICENSE", "LICENSE_THINGS"]`, but I cannot find a `LICENSE_THINGS` file in the repository or its history. Is there a file or a list of third-party licences that was meant to be published, and if so, could it be added? If it exists, which assets does it cover?

2. The README says the `mpfb2` data (`src/anny/data/mpfb2`) is CC0 1.0. Can you confirm that this applies to everything in that folder, including the blend-shape targets (`targets/**/*.target.gz`), the textures (`textures/*.jpg`, `sss.png`), rigs, weights and mesh metadata, and that none of these files comes from a source with a different licence (for example non-commercial or share-alike data)? Can you also confirm the licence of the other data folders that the README does not mention: `cached`, `keypoints`, `segmentation`, `shape_calibration` and `topology` (Apache-2.0 like the code, or something else)?

3. Is it permitted to use the CC0 and Apache-2.0 parts, with attribution (NAVER Corp. for Anny; MakeHuman / MPFB2 for the assets), as a reference in a non-commercial open atlas published under CC BY-SA 4.0, including showing meshes generated from Anny parameters? I understand the "smplx" non-commercial download is separate and I will not use it.

A short reply here, or by email, is enough. If there is a preferred attribution or citation text, I will use it.

Thank you very much,
[Name], NMSK Atlas
[contact email or repository URL]

## Notes for the sender

- Fill the two placeholders at the end. Send either the GitHub issue (public, answer is citable) or the email, not necessarily both.
- Until NAVER answers, treat only the CC0 base mesh header and the upstream MPFB2 asset statement as established; targets and textures are covered by upstream MPFB2 CC0 but Anny's own copy has no per-file notice.
