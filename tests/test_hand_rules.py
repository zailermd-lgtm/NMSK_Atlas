"""The pure rule functions of scripts/cryo/vhf_hand_muscles_from_cryo.py on synthetic metacarpal discs whose answer
is known by construction: naming the five discs, the metacarpal frame (e ulnar -> radial, n palmar = the MC1 side),
the compartment layering (dorsal / palmar interossei, adductor band, thenar, hypothenar, palm), the rule seeds
(mm from the disc surface) and the segment bounds / CT-to-photo shift helpers."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_hand_muscles_from_cryo as hm  # noqa: E402

# a synthetic right hand in (row, col) px: MC2..MC5 on row 100, 30 px = 10 mm apart, MC1 palmar-radial of MC2.
# photo rows increase palmar-ward here, so n = (+1, 0); cols increase radially, so e = (0, +1).
P = {"mc1": (130.0, 215.0), "mc2": (100.0, 190.0), "mc3": (100.0, 160.0), "mc4": (100.0, 130.0), "mc5": (100.0, 100.0)}
R = {b: 12.0 for b in hm.MC}                       # 12 px = 4 mm disc radius
E, N = np.array([0.0, 1.0]), np.array([1.0, 0.0])
SHAPE = (220, 300)


def test_name_metacarpals_finds_the_thumb_and_orders_the_rest_from_it():
    scrambled = [P["mc3"], P["mc5"], P["mc1"], P["mc2"], P["mc4"]]
    named = hm.name_metacarpals(scrambled)
    for b in hm.MC:
        assert np.allclose(named[b], P[b]), b
    with pytest.raises(ValueError):
        hm.name_metacarpals(scrambled[:4])


def test_hand_frame_runs_ulnar_to_radial_with_the_palmar_normal_on_the_mc1_side():
    e, n, m = hm.hand_frame(P)
    assert np.allclose(e, E) and np.allclose(n, N)
    assert np.allclose(m, (100.0, 145.0))
    flipped = {**P, "mc1": (70.0, 215.0)}                      # thumb on the other side -> n flips with it
    assert np.allclose(hm.hand_frame(flipped)[1], -N)
    no_thumb = {**P, "mc1": None}                              # no thumb: keep the previous level's orientation
    assert np.allclose(hm.hand_frame(no_thumb, n_prev=N)[1], N)
    assert np.allclose(hm.hand_frame(no_thumb, n_prev=-N)[1], -N)
    with pytest.raises(ValueError):
        hm.hand_frame(no_thumb)


def test_compartments_layer_dorsal_to_palmar_between_the_metacarpals():
    comp = hm.compartments(SHAPE, P, R, E, N)
    C = hm.COMP_ID
    assert comp[80, 175] == C["dorsal_interossei_hand"]        # dorsal of the MC2-MC3 line
    assert comp[110, 175] == C["palmar_interossei"]            # palmar of it, within the disc + 3 mm cap
    assert comp[135, 175] == C["adductor_pollicis"]            # beyond the cap, radial of the MC3 centre
    assert comp[175, 175] == C["thenar"]                       # beyond the 8 mm adductor band
    assert comp[135, 145] == C["palmar_flexor_tendon_compartment"]   # palm, between the MC3 and MC4 centres
    assert comp[135, 115] == C["hypothenar"]                   # palmar, ulnar of the MC4 centre
    assert comp[100, 80] == C["hypothenar"]                    # ulnar of the MC5 centre plane


def test_compartments_around_the_thumb_need_mc1():
    comp = hm.compartments(SHAPE, P, R, E, N)
    C = hm.COMP_ID
    assert comp[110, 205] == C["dorsal_interossei_hand"]       # first web, dorsal of the MC1-MC2 line: 1st DI
    assert comp[130, 205] == C["adductor_pollicis"]            # first web, palmar of that line
    assert comp[150, 240] == C["thenar"]                       # radial of MC1
    no_thumb = hm.compartments(SHAPE, {**P, "mc1": None}, R, E, N)
    assert no_thumb[80, 205] == 0                              # without MC1 nothing radial of MC2 is a web space
    assert no_thumb[110, 205] == C["adductor_pollicis"]         # only the palmar layering from the MC2 surface is left
    assert no_thumb[175, 205] == C["thenar"]


def test_compartments_give_no_interosseous_space_to_a_carried_metacarpal():
    comp = hm.compartments(SHAPE, P, R, E, N, real={"mc2", "mc3", "mc1"})
    assert comp[80, 175] == hm.COMP_ID["dorsal_interossei_hand"]     # MC2-MC3: both photographed
    assert comp[80, 115] == 0                                        # MC4-MC5: carried, no interossei
    assert comp[135, 115] == hm.COMP_ID["hypothenar"]                # the palmar layering still applies


def test_marker_positions_offset_from_the_disc_surface_on_the_right_sides():
    seeds = hm.marker_positions(P, R, E, N)
    assert set(seeds) == set(hm.MARKER_RULES)
    el = np.array(P["mc1"]) - np.array(P["mc2"]); el = el / np.hypot(*el)       # thenar: the MC2 -> MC1 direction
    anc, em, nm, grp = hm.MARKER_RULES["abductor_pollicis_brevis"]
    exp = np.array(P["mc1"]) + el * (em / hm.PX + np.sign(em) * R["mc1"]) + N * (nm / hm.PX + np.sign(nm) * R["mc1"])
    assert np.allclose(seeds["abductor_pollicis_brevis"], exp)
    for nm_ in ("abductor_pollicis_brevis", "flexor_pollicis_brevis", "opponens_pollicis"):
        assert np.dot(np.array(seeds[nm_]) - np.array(P["mc1"]), N) > 0          # thenar seeds are palmar of MC1
    apb, fpb, op = (np.array(seeds[k]) for k in ("abductor_pollicis_brevis", "flexor_pollicis_brevis", "opponens_pollicis"))
    assert np.dot(apb - op, N) > np.dot(fpb - op, N) > 0                         # APB most superficial, OP deepest
    for nm_ in ("abductor_digiti_minimi_hand", "flexor_digiti_minimi_brevis_hand", "opponens_digiti_minimi"):
        assert np.dot(np.array(seeds[nm_]) - np.array(P["mc5"]), E) < 0          # hypothenar seeds are ulnar of MC5
    adm, fdmb, odm = (np.array(seeds[k]) for k in ("abductor_digiti_minimi_hand", "flexor_digiti_minimi_brevis_hand", "opponens_digiti_minimi"))
    assert np.dot(adm - np.array(P["mc5"]), E) < np.dot(fdmb - np.array(P["mc5"]), E)   # ADM the most ulnar
    assert np.dot(fdmb - odm, N) > 0                                             # FDMB palmar of ODM
    assert hm.marker_positions({**P, "mc1": None}, R, E, N).keys() == {n for n, r in hm.MARKER_RULES.items() if r[0] != "mc1"}


def _track_level(cols, found=hm.MC[1:], sep=30.0):
    t = {"found": {b: False for b in hm.MC}}
    for b in hm.MC:
        t[b] = None
    for k, b in enumerate(hm.MC[1:]):
        if b in found:
            t[b] = (100.0, cols + k * sep, 12.0, None); t["found"][b] = True
    return t


def test_segment_bounds_takes_the_longest_run_of_four_separated_discs():
    track = {}
    for j in range(0, 2):
        track[j] = _track_level(100.0, found=("mc2", "mc3", "mc4"))      # MC5 missing
    for j in range(2, 7):
        track[j] = _track_level(100.0)                                   # 10 mm apart: good
    for j in range(7, 10):
        track[j] = _track_level(100.0, sep=9.0)                          # 3 mm apart: the discs have merged
    assert hm.segment_bounds(track) == (2, 6)
    assert hm.segment_bounds({j: _track_level(100.0, sep=9.0) for j in range(4)}) == (None, None)


def test_match_shift_recovers_a_known_translation():
    ct = [(100.0, 100.0), (100.0, 130.0), (100.0, 160.0), (100.0, 190.0)]
    true = np.array([12.0, -7.0])
    peaks = [tuple(np.array(c) + true) for c in ct]
    sh, assign = hm.match_shift(ct, peaks, max_mm=6.0)
    assert np.allclose(sh, true)
    assert assign == [0, 1, 2, 3]
    far = hm.match_shift(ct, [tuple(np.array(ct[0]) + true)], max_mm=6.0)[1]
    assert far[0] == 0 and far[1:] == [None, None, None]
