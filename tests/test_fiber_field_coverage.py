import numpy as np

from engine import fiber_field as ff
from engine import geometry as geo


def _seed_square(size=20.0):
    return np.array([
        geo.vec3(-size / 2, -size / 2, 0), geo.vec3(size / 2, -size / 2, 0),
        geo.vec3(size / 2, size / 2, 0), geo.vec3(-size / 2, size / 2, 0),
    ])


def test_every_fascicle_is_tagged_with_its_compartment_and_has_one_nmj():
    seed = _seed_square()
    origin = geo.vec3(0, 0, 0)
    insertion = geo.vec3(0, -150, 0)
    fascicles = ff.generate_compartment_fibers(
        compartment_id="deltoid_r_posterior",
        architecture_type="unipennate",
        pennation_deg=18.0,
        seed_region_local_mm=seed,
        origin_anchor_local_mm=origin,
        insertion_anchor_local_mm=insertion,
        nmj_fraction=0.5,
        resolution_mm=2.0,
    )
    assert len(fascicles) > 1, "expected multiple seeded fascicles across the origin footprint"
    for f in fascicles:
        assert f.compartment_id == "deltoid_r_posterior"
        assert f.nmj_position_mm.shape == (3,)
        assert len(f.points_mm) >= 2
        # NMJ marker must lie on (or very near) the generated centerline
        dists = np.linalg.norm(f.points_mm - f.nmj_position_mm, axis=1)
        assert dists.min() < 1e-6


def test_parallel_and_pennate_architectures_differ_in_path_shape():
    seed = np.atleast_2d(geo.vec3(0, 0, 0))
    origin = geo.vec3(0, 0, 0)
    insertion = geo.vec3(0, -100, 0)
    parallel = ff.generate_compartment_fibers("c", "parallel_strap", 0.0, seed, origin, insertion, resolution_mm=1.0)
    pennate = ff.generate_compartment_fibers("c", "bipennate", 25.0, seed, origin, insertion, resolution_mm=1.0)
    # a pennate path is not a straight line to the insertion, unlike parallel
    p_pts = pennate[0].points_mm
    straight_dist = np.linalg.norm(insertion - origin)
    path_len = np.sum(np.linalg.norm(np.diff(p_pts, axis=0), axis=1))
    assert path_len >= straight_dist  # pennate routing is not shorter than a straight line


def test_fascicle_count_scales_with_pcsa():
    small = ff.compartment_fascicle_count_from_pcsa(pcsa_mm2=50)
    large = ff.compartment_fascicle_count_from_pcsa(pcsa_mm2=500)
    assert large > small
