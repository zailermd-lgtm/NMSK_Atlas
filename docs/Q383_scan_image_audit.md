# Q383 — scan simulation: image audit (2026-11-19)

Owner, after testing Base · Male v103: "the simulation is still at a very low level". Six standard views were rendered on the
page (linear probe, the frame the page itself computes) and compared with the documented normal appearance. Views are seated
from the page's own meshes by `scripts/anatomy/q383/verify_image_q383.py`; the measures are in
`scripts/anatomy/q383/image_metrics_q383.py`. Before / after pictures: scratchpad `q383/shots/`.

## Appearance used as the target (sources)

| Tissue | Documented appearance | Source |
|---|---|---|
| Muscle | Dark, with bright connective tissue: short marks across the fibres, lines along them; bright epimysium | Pillen & van Alfen 2011, PMID 22196753; Peetrons 2002, PMID 11868072 (abstracts read; the normal-appearance text is the reviews' body, recalled) |
| Epimysium, perimysium | Every muscle is enveloped by epimysium, continuous with its tendons; the perimysium is a continuous network of sheets dividing the muscle into fascicles; its collagen lies 20–80° to the fibre axis | Schleip (ed.), *Fascia in Sport and Movement* 2015, ch. 2, PDF p. 40, 42 (owner's copy) |
| Deep fascia | A thin layer (fascia lata / lumbar fascia < 2 mm); its thickness is measured with ultrasound | same book, ch. 1 PDF p. 24; ch. 24 PDF p. 411 (quoting Stecco 2014, PMID 23975091). The book does not describe echogenicity |
| Nerve | Dark fascicles between bright bands (honeycomb) | Silvestri 1995, PMID 7568840 (abstract read) |
| Tendon | Bright, fibrillar, anisotropic | Fornage 1987, PMID 3546718 (record found, not read) |
| Bone, vessels, attenuation, speckle | Bright cortex line with a shadow; anechoic lumen with enhancement behind; loss with depth and frequency | textbook acoustics as already cited in `clinical/data/ultrasound_tissues.json` |

## Audit: what was wrong, and why in the code

| View(s) | What was wrong | Why (in `clinical/ultrasound_tool.js` / the table) | Done |
|---|---|---|---|
| all | Every interface outside the focal zone was a horizontal band; skin and fat a white smear | `latFw()` modelled a fixed-focus single element: 8 mm wide at the skin, 1.6 mm 5 mm off the focus at 10 MHz | Array beam (dynamic receive focus), `global.beam` |
| thigh, calf, forearm | Neighbouring muscles merged into one dark area: no epimysium, no septa | An echo was made only where the tissue CLASS changes; two muscle meshes are one class | Sheath interface at every structure boundary of a muscle / nerve / vessel, `interfaces.sheath` (rule) |
| thigh, calf | Muscle black below 2–3 cm; nothing of the femur | Fixed TGC 0.6 dB/cm/MHz against muscle 1.0 and a fascia sheet of 4.7: 8 dB lost per cm at 10 MHz | Gain follows the tissue, `global.tgc` (convention), capped at 90 dB |
| forearm, carpal, shoulder | The bone cortex repeated as two white bands inside its own shadow | Reverberation for any reflector with R ≥ 0.4; muscle–bone is 0.41 | `artefacts.reverb.r_min` 0.5: gas only |
| transverse views | Muscle texture a closed polygon net, hardly visible | Worley cell walls drawn at one brightness whatever their direction | Walls are specular sheets (bright facing the probe), a share of them bright, the rest faint; darker fascicles |
| all | Steep borders showed as chains of beads (once the smear was gone) | Interface floor 0.2–0.35 at any angle; the impedance gradient vanishes in a thin layer, so the angle was unknown there | `global.soft_diffuse_scale`; direction from the raster window for thin layers |
| all | Fat a flat grey | No texture for the class | Fat lobules with thin septa, `textures.fat` (assumption) |

Measured before → after on Base · Male (page frames): see the hand-back of the round and
`q383/shots/q383_<page>_{before,after}_metrics.json`.

## Still far from a real scan

- Lines are too clean and too uniform: a real fascia is grainy, layered and varies in thickness; here every sheath is one
  smooth line of the same strength. The carpal tunnel and forearm views read as outlines of many small structures.
- Tendons are not yet bright fibrillar ovals in short axis, and the median nerve's honeycomb is not resolved at the
  0.1–0.19 mm raster pixel (the image is 233–350 px wide, then magnified on screen).
- Speckle is a synthetic pattern multiplied onto the tissue level, not the interference of scatterers; its grain is finer and
  flatter than on a scanner. No refraction, edge shadow, side lobes, slice thickness, compression or motion (as before).
- The position of every single septum and fat lobule is a rule. Only the mesh boundaries, the fibre direction and the
  pennation come from the page's geometry and the cited architecture table.
- The star matrix (nine images) is still the workspace's default view; the eight side images are computed at the lower tier.
- The owner's reference picture had not arrived when this was written: the fascia look follows the literature above, not his
  example.
