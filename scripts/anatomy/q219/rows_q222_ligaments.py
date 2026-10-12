"""Q222 rows, part 4: ligaments (PubMed-verified on 2026-10-12)."""
from rows_common import P, S

# ------------------------------------------------------------------ iliolumbar ligament
S("iliolumbar_ligament.bands", "iliolumbar_ligament", "ligament_component", "Iliolumbar ligament: number of bands / parts", [
    (2, "hanson1994", "anterior and posterior part, both from the L5 transverse process (autopsy / dissection)"),
    (2, "rucco1996", "anterior and posterior band, MR of 30 ligaments in 15 volunteers"),
    (1, "dabrowski2023", "single band in 44 of 60 ligaments (73 %); double band in 13 (22 %); other 3"),
    (3, "hanson1994", "lower end of 'three to five parts' described in the earlier literature quoted by the Hanson abstract (original sources not retrieved)"),
    (5, "hanson1994", "upper end of the same quoted range")],
  note="Counts disagree: older literature 3-5 parts; Hanson 1994 and Rucco 1996 two (anterior / posterior); Dabrowski 2023 one band as the typical form and two as the most common variant. Dabrowski found no convincing insertion on the L4 vertebra (Hanson: none on the L4 transverse process).")
P("iliolumbar_ligament", "anterior_band", "ligament_component", "Anterior band (L5 transverse process to the anterior iliac tuberosity)", "Broad and flat; two varieties: type 1 from the anterior aspect of the inferolateral L5 transverse process, type 2 from its anterior, lateral and posterior aspects; fans out to the anterior iliac tuberosity.", ["rucco1996", "hanson1994"], cls="ligament",
  ev="MR, 15 volunteers; autopsy / dissection", anchor=dict(bone="hip_bone", landmark="iliac tuberosity (upper part, anterior)"), setid="iliolumbar_ligament.bands")
P("iliolumbar_ligament", "posterior_band", "ligament_component", "Posterior band (apex of the L5 transverse process to the iliac crest)", "Fusiform, from the apex of the L5 transverse process; widens like a small cone before inserting on the anterior margin and apex of the iliac crest; thinner than the anterior band with a smaller iliac base.", ["rucco1996", "hanson1994"], cls="ligament",
  ev="MR, 15 volunteers; autopsy / dissection", anchor=dict(bone="hip_bone", landmark="iliac crest, anterior margin / apex (MR) or upper iliac tuberosity (Hanson)"), setid="iliolumbar_ligament.bands",
  note="Rucco places the posterior band on the iliac crest, Hanson on the upper part of the iliac tuberosity below the crest: a recorded disagreement on the iliac footprint.")
P("iliolumbar_ligament", "accessory_short_bands_costal_process", "ligament_component", "Short ligamentous bands from the L5 costal process to the iliac plate", "Present in 24 of 60 ligaments (about 40 %); a fibrous membrane connected to the ligament was found in 38 (63 %).", ["dabrowski2023"], cls="ligament",
  ev="cadaver, 60 ligaments of 30 cadavers", var="40 % / 63 %")

# ------------------------------------------------------------------ popliteofibular ligament
S("popliteofibular_ligament.types", "popliteofibular_ligament", "ligament_component", "Popliteofibular ligament: forms", [
    (1, "olewnik2022pfl", "type I single ligament to the apex of the fibular head, 72.3 % of 137 limbs"),
    (2, "olewnik2022pfl", "type II bifurcated, 8.7 %"), (2, "olewnik2022pfl", "type III double PFL, 7.3 %"),
    (0, "olewnik2022pfl", "absent in 11.7 % (present in 88.3 %)")])
P("popliteofibular_ligament", "type_i_single_apex", "ligament_component", "Type I: single band to the apex of the fibular head", "Most common form (72.3 %).", ["olewnik2022pfl"], cls="ligament",
  ev="cadaver n=137 limbs", var="72.3 %", anchor=dict(bone="fibula", landmark="apex of the head of the fibula"), setid="popliteofibular_ligament.types")
P("popliteofibular_ligament", "type_ii_bifurcated", "ligament_component", "Type II: bifurcated (anterior slope + posterior surface of the fibular styloid)", "Dominant band to the anterior slope of the styloid process of the fibula, smaller band to its posterior surface.", ["olewnik2022pfl"], cls="ligament",
  ev="cadaver n=137 limbs", var="8.7 %", anchor=dict(bone="fibula", landmark="styloid process, anterior slope and posterior surface"), setid="popliteofibular_ligament.types")
P("popliteofibular_ligament", "type_iii_double", "ligament_component", "Type III: double ligament (from popliteus tendon and from popliteus musculotendinous junction)", "Main band from the popliteus tendon to the anterior slope of the styloid process; second band from the musculotendinous junction of popliteus to the posterior surface of the styloid process.", ["olewnik2022pfl"], cls="ligament",
  ev="cadaver n=137 limbs", var="7.3 %", anchor=dict(bone="fibula", landmark="styloid process, anterior slope and posterior surface"), setid="popliteofibular_ligament.types", related=["popliteus"])

# ------------------------------------------------------------------ annular ligament
S("annular_ligament.bands", "annular_ligament", "ligament_component", "Annular ligament: oblique bands", [
    (2, "barnes2018", "superior oblique band 15/19 and inferior oblique band 13/19"), (3, "barnes2018", "plus an anterior oblique band in 8/19")])
P("annular_ligament", "superior_oblique_band", "ligament_component", "Superior oblique band (SOB)", "Present in 15 of 19 elbows; 3.9 +/- 1.0 mm wide x 10.5 +/- 3.8 mm long; part of the deeper layer of the lateral elbow ligaments.", ["barnes2018"], cls="ligament",
  ev="cadaver n=19 elbows", var="15/19", setid="annular_ligament.bands")
P("annular_ligament", "inferior_oblique_band", "ligament_component", "Inferior oblique band (IOB)", "Present in 13 of 19; 3.6 +/- 1.1 x 11.4 +/- 4.2 mm; inserts onto the anterior proximal ulna rather than the supinator crest.", ["barnes2018"], cls="ligament",
  ev="cadaver n=19 elbows", var="13/19", anchor=dict(bone="ulna", landmark="anterior proximal ulna (medial to the supinator crest)"), setid="annular_ligament.bands")
P("annular_ligament", "anterior_oblique_band", "ligament_component", "Anterior oblique band", "Present in 8 of 19; 3.8 +/- 1.7 mm wide.", ["barnes2018"], cls="ligament", ev="cadaver n=19 elbows", var="8/19", setid="annular_ligament.bands")
P("annular_ligament", "accessory_lateral_collateral_thickening", "ligament_component", "Accessory lateral collateral ligament (localised thickening, supinator insertion)", "The described 'accessory LCL' is a localised thickening of the lateral complex arising from the supinator insertion independently of the IOB, attaching to the annular ligament and to the anterior proximal ulna at the bicipital fossa floor.", ["barnes2018"], cls="ligament",
  ev="cadaver n=19 elbows", anchor=dict(bone="ulna", landmark="bicipital fossa floor, medial to the supinator crest"), related=["supinator"])
