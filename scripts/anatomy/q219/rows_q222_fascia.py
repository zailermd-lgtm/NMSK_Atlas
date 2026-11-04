"""Q222 rows, part 5: fascia, retinacula, aponeuroses with documented parts or perforation points (PubMed-verified on 2026-10-12)."""
from rows_common import P, S

# ------------------------------------------------------------------ palmar aponeurosis
S("palmar_fascial_complex.components", "palmar_aponeurosis", "ligament_component", "Palmar fascial complex: components", [
    (5, "rayan1999", "radial aponeurosis, ulnar aponeurosis, central (palmar) aponeurosis, palmo-digital fascia, digital fascia")])
for slug, nm, ds in [("radial_aponeurosis", "Radial aponeurosis", "Named component of the palmar fascial complex; the abstract lists it without describing its extent."),
                     ("ulnar_aponeurosis", "Ulnar aponeurosis", "Named component of the palmar fascial complex; the abstract lists it without describing its extent."),
                     ("central_aponeurosis", "Central (palmar) aponeurosis", "Named component (Rayan 1999). Thickened bands overlying the flexor tendons in the palm, linked by the transverse palmar fascia, are described in the Dupuytren pathologic anatomy (Watson 1991)."),
                     ("palmo_digital_fascia", "Palmo-digital fascia", "Named component of the palmar fascial complex; the abstract lists it without describing its extent."),
                     ("digital_fascia", "Digital fascia", "Named component of the palmar fascial complex; the abstract lists it without describing its extent.")]:
    P("palmar_aponeurosis", slug, "ligament_component", nm, ds, ["rayan1999"] + (["watson1991"] if slug == "central_aponeurosis" else []), cls="fascia",
      ev="gross + microdissection (Rayan 1999); Dupuytren pathologic anatomy (Watson 1991)", setid="palmar_fascial_complex.components",
      note="Component list from Rayan 1999 only; which sub-structure (natatory ligaments, Grayson's ligaments, spiral bands) belongs to which component is not stated in the retrieved abstracts and is not assigned here.")
P("palmar_aponeurosis", "pulley_transverse_fibres_vertical_septa", "ligament_component", "Palmar aponeurosis pulley: transverse fibres + vertical septa to the transverse metacarpal ligament", "Transverse fibres attached by vertical septa to the underlying transverse metacarpal ligament form a pulley over the flexor tendons; constant and substantial, overlying the synovial sheath.", ["doyle1990"], cls="fascia",
  ev="anatomic study (J Hand Surg 1990)", related=["flexor_tendon_pulley_system_hand"])
P("palmar_aponeurosis", "vertical_septa_tendon_neurovascular_passages", "fascial_passage", "Vertical septa between the flexor tendons and the neurovascular tunnels", "Vertical septa fix the longitudinal bands to the deep fascia and the transverse metacarpal ligaments and pass deep between the tendon and the neurovascular tunnel.", ["watson1991"], cls="fascia",
  ev="Dupuytren pathologic anatomy review", passes=dict(kind="tendon/neurovascular bundle", traversing=[], traversing_text="flexor tendons (central) and digital neurovascular bundles (either side)", through="vertical septa of the palmar aponeurosis"))
P("palmar_aponeurosis", "central_band_bifurcation_pip", "ligament_component", "Central band: bifurcation just distal to the PIP joint", "A central band continues into the finger, forks and dissipates just distal to the PIP joint; the two bundles pass deep to the neurovascular bundle and attach to the flexor sheath of the middle phalanx.", ["watson1991"], cls="fascia",
  ev="Dupuytren pathologic anatomy review", note="Description of the pathologic (Dupuytren) cord; the normal counterpart is not distinguished in the abstract.")

# ------------------------------------------------------------------ Guyon's canal
S("guyons_canal.zones", "guyons_canal", "fascial_passage", "Guyon's canal: zones", [
    (3, "posner2000", "three zones: zone 1 proximal (single nerve), zones 2 and 3 distal (nerve divided into motor and sensory branches)"),
    (3, "murata2003", "three zones of compression; 31 patients"), (3, "saran2025", "three zones, each containing distinct neural structures (review)")])
P("guyons_canal", "zone_1", "fascial_passage", "Zone 1: most proximal part (undivided ulnar nerve)", "In zone 1 the ulnar nerve is still a single structure with motor and sensory fascicles; compression here was found in 28 of 31 cases of ulnar tunnel syndrome.", ["posner2000", "murata2003"], cls="fascia",
  ev="review; retrospective series n=31", passes=dict(kind="nerve", traversing=["ulnar_nerve"], through="Guyon's canal (ulnar tunnel), zone 1"), setid="guyons_canal.zones")
P("guyons_canal", "zone_2", "fascial_passage", "Zone 2 (distal; nerve divided into motor and sensory branches)", "Distal part where the nerve has divided; compression in 6 of 31 cases. Which of zones 2 / 3 carries the deep motor branch is not stated in the cited abstracts.", ["posner2000", "murata2003"], cls="fascia",
  ev="review; retrospective series n=31", passes=dict(kind="nerve", traversing=["ulnar_nerve"], through="Guyon's canal, zone 2"), setid="guyons_canal.zones")
P("guyons_canal", "zone_3", "fascial_passage", "Zone 3 (distal; nerve divided into motor and sensory branches)", "Distal part where the nerve has divided; compression in 19 of 31 cases; 17 cases (55 %) had compression in more than one zone.", ["posner2000", "murata2003"], cls="fascia",
  ev="review; retrospective series n=31", passes=dict(kind="nerve", traversing=["ulnar_nerve"], through="Guyon's canal, zone 3"), setid="guyons_canal.zones")
P("guyons_canal", "aberrant_hypothenar_muscle", "fascial_passage", "Aberrant hypothenar muscle crossing the canal (variant)", "Anomalous (accessory) abductor digiti minimi can compress the ulnar nerve within Guyon's canal.", ["claassen2013", "bouredoucen2026"], cls="fascia",
  ev="reviews", var="variant", passes=dict(kind="nerve", traversing=["ulnar_nerve"], through="Guyon's canal with an accessory ADM"), related=["abductor_digiti_minimi_hand"])

# ------------------------------------------------------------------ bicipital aponeurosis (lacertus fibrosus)
P("bicipital_aponeurosis", "superficial_part", "ligament_component", "Superficial part of the lacertus fibrosus", "Released first in the two-step release (R); after superficial and deep release the biceps lever arm drops 28 % in flexion and 50 % in supination.", ["snoeck2021"], cls="fascia",
  ev="biomechanics, 7 fresh-frozen limbs")
P("bicipital_aponeurosis", "deep_part", "ligament_component", "Deep part of the lacertus fibrosus", "Released second (R2).", ["snoeck2021"], cls="fascia", ev="biomechanics, 7 fresh-frozen limbs")
P("bicipital_aponeurosis", "median_nerve_passage_beneath", "fascial_passage", "Median nerve beneath the lacertus fibrosus", "The lacertus fibrosus is a potential site of proximal median neuropathy; maximal perineural pressure at its level fell from 669 to 77 mmHg after release during elbow flexion.", ["archambault2023"], cls="fascia",
  ev="cadaver, 7 limbs of 4 cadavers", passes=dict(kind="nerve", traversing=["median_nerve"], through="lacertus fibrosus (bicipital aponeurosis) at the elbow"), related=["biceps_brachii"])

# ------------------------------------------------------------------ thoracolumbar fascia components, latissimus aponeurosis, sacrotuberous attachment
P("latissimus_dorsi_aponeurosis", "superficial_lamina_posterior_layer_tlf", "ligament_component", "Superficial lamina of the posterior layer of the TLF (aponeuroses of latissimus dorsi and serratus posterior inferior)", "The superficial lamina of the posterior layer is dominated by the aponeuroses of the latissimus dorsi and the serratus posterior inferior.", ["willard2012"], cls="fascia",
  ev="anatomical review (J Anat 2012)", related=["posterior_layer_tlf", "latissimus_dorsi"])
P("sacrotuberous_ligament", "attachment_thoracolumbar_composite", "ligament_component", "Attachment of the thoracolumbar composite", "The sacrotuberous ligament is one of the two firm attachments (with the PSIS) of the caudal thoracolumbar composite.", ["willard2012"], cls="ligament",
  ev="anatomical review", related=["posterior_layer_tlf"], note="Only this attachment is stated in the abstract; the ligament's own ischial / sacral attachments are not recorded by this reference.")

# ================================================================== batch 2: Scarpa / Colles, ankle extensor retinaculum
P("scarpas_fascia", "oval_sac_each_side", "ligament_component", "Membranous layer confined to an oval area on each side of the abdominal wall", "Scarpa's fascia is limited to an oval area each side; by its attachment to the deep fascia it encloses an obliquely directed oval sac; medially it blends with the fundiform ligament; its inferior margin forms the groin crease by attachment to the fascia lata.", ["martin1984"], cls="fascia",
  ev="dissection (J Anat 1984)", related=["fascia_lata", "colles_fascia"])
S("colles_fascia.pockets", "colles_fascia", "ligament_component", "Colles' fascia: pockets of the abdomino-perineal sac", [(3, "martin1984", "lateral, intermediate and medial pocket-like diverticulae")])
P("colles_fascia", "lateral_pocket_superficial_perineal_pouch", "ligament_component", "Lateral pocket (continues into the superficial perineal pouch)", "Lateral of the three pockets arising from the Scarpa sac; it continues into the superficial perineal pouch.", ["martin1984"], cls="fascia", ev="dissection", setid="colles_fascia.pockets")
P("colles_fascia", "intermediate_pocket_spermatic_cord", "ligament_component", "Intermediate pocket (with the spermatic cord / round ligament)", "Associated with the spermatic cord or the round ligament of the uterus, blending with their coverings posteriorly; in the male it ends just above the testis.", ["martin1984"], cls="fascia", ev="dissection", setid="colles_fascia.pockets", related=["cremaster"])
P("colles_fascia", "medial_pocket_scrotum_labium", "ligament_component", "Medial pocket (with the intermediate pocket occupies the scrotum or labium majus)", "The medial pocket together with the intermediate one occupies the scrotum or labium majus; the pockets of the two sides do not communicate with each other.", ["martin1984"], cls="fascia", ev="dissection", setid="colles_fascia.pockets")
S("extensor_retinaculum_ankle.parts", "extensor_retinaculum_ankle", "ligament_component", "Inferior extensor retinaculum: parts", [
    (2, "dalmau2016", "main retinaculum + a non-constant oblique supero-lateral band"), (1, "rougereau2022", "main part = the frondiform ligament")])
P("extensor_retinaculum_ankle", "frondiform_ligament_main_part", "ligament_component", "Frondiform ligament (main part of the inferior extensor retinaculum)", "The main part of the IER; becomes taut in the valgus position (shear-wave speed 4.1 m/s at 20 degrees valgus in 20 healthy adults).", ["rougereau2022"], cls="fascia",
  ev="shear-wave elastography, 20 healthy adults", setid="extensor_retinaculum_ankle.parts")
P("extensor_retinaculum_ankle", "oblique_superolateral_band", "ligament_component", "Non-constant oblique supero-lateral band", "The inferior extensor retinaculum is an aponeurotic structure continuous with the anterior sural fascia; the non-constant oblique supero-lateral band defines whether true IER or only anterior sural fascia is present.", ["dalmau2016"], cls="fascia",
  ev="pictorial essay (anatomical)", var="non-constant", setid="extensor_retinaculum_ankle.parts", related=["crural_fascia"])
