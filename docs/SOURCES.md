# NMSK Atlas — Sources & Citation Policy

## Policy

Every entity in `data/` carries a `source` (or, for reference tables, a
top-level `sources`) field. `tests/test_source_coverage.py` enforces this
mechanically — no entity may ship without one. Two honesty notes that apply
throughout the dataset, stated once here rather than repeated on every file:

1. **Representative vs. exact values.** Numeric biomechanical parameters
   (fascicle length, pennation angle, PCSA, joint ROM) are given as
   representative typical values consistent with the architecture
   classification and magnitude reported in the cited literature — not
   exact digitized transcriptions from one specimen. This is stated
   explicitly because published cadaver/imaging studies themselves disagree
   by 20–40% (normal biological + measurement variation between studies),
   so a bare "measured" number would overstate precision the field itself
   doesn't have. Where a formula is used to derive a value (e.g.
   `max_isometric_force = PCSA × specific_tension`), the formula and its
   literature-based constant are shown, not just the result.
2. **Skeletal coordinates.** Bone landmark `position_local_mm` values are
   placed consistently with documented average adult long-bone lengths and
   standard descriptive landmark locations — not digitized from a scanned
   specimen (no such source was available in this session; see
   docs/ROADMAP.md Stage 5 for the real path to genuine scan-derived
   geometry). They are geometrically self-consistent (correct relative
   position, correct bone length) and sufficient to drive the rig/generator
   pipeline correctly, but are an engineering approximation, not a
   measurement.

## Primary references used

**General gross anatomy / nomenclature**
- Drake RL, Vogl AW, Mitchell AWM. *Gray's Anatomy for Students*, 4th ed. Elsevier, 2019.
- Terminologia Anatomica (FICAT/IFAA 1998) — official anatomical nomenclature standard.
- Moore KL, Dalley AF, Agur AMR. *Clinically Oriented Anatomy*, 8th ed. Wolters Kluwer.

**Joint kinematics / coordinate systems**
- Wu G et al. (2002) "ISB recommendation on definitions of joint coordinate systems of various joints for the reporting of human joint motion — part I: ankle, hip, and spine." *J Biomech* 35:543–548.
- Wu G et al. (2005) "ISB recommendation on definitions of joint coordinate systems of various joints for the reporting of human joint motion — part II: shoulder, elbow, wrist and hand." *J Biomech* 38:981–992.
- American Academy of Orthopaedic Surgeons. *Joint Motion: Method of Measuring and Recording* (1965) — standard clinical ROM norms.
- Delp SL et al. (1990) "An interactive graphics-based model of the lower extremity to study orthopaedic surgical procedures." *IEEE Trans Biomed Eng* 37:757–767 — source of the ankle-complex (talocrural+subtalar combined) simplification convention adopted here.

**Muscle architecture**
- Holzbaur KR, Murray WM, Delp SL (2005) "A model of the upper extremity for simulating musculoskeletal surgery and analyzing neuromuscular control." *Ann Biomed Eng* 33(6):829–840.
- Lieber RL, Fridén J (2000) "Functional and clinical significance of skeletal muscle architecture." *Muscle Nerve* 23:1647–1666.
- Ward SR, Eng CM, Smallwood LH, Lieber RL (2009) "Are current measurements of lower extremity muscle architecture accurate?" *Clin Orthop Relat Res* 467:1074–1082 — primary source for lower-limb fascicle length/PCSA representative values.
- Fridén J, Lieber RL (2003) "Spec ific tension of human skeletal muscle" — representative in-vivo specific-tension estimate used to compute illustrative `max_isometric_force_N`.

**Intramuscular functional compartmentalization**
- Wickham JB, Brown JM (1998) "Muscles within muscles: a mechanomyographic analysis of muscle segment contractile properties within human deltoid." *Eur J Appl Physiol* 78:6–17.
- Brown JM et al. (2007) "Muscles within muscles: coordination of 19 muscle segments within three shoulder muscles during isometric motor tasks." *J Electromyogr Kinesiol* 17:57–73.
- Fabrizio PA, Clemente FR (2011) "Anatomic compartmentalization of infraspinatus." *J Anat* 219(3):303–310.
- von Schroeder HP, Botte MJ (1993) "Anatomy of the extensor tendons of the fingers: variations and multiplicity." *J Hand Surg Am* 18(1):16–20 (FDP/extensor compartment anatomy).
- Gottschalk F, Kourosh S, Leveau B (1989) "The functional anatomy of tensor fasciae latae and gluteus medius and minimus." *J Anat* 166:179–189 — describes gluteus medius's three functionally-graded parts (anterior/middle/posterior).
- Selkowitz DM, Beneck GJ, Powers CM (2016) "Comparison of Electromyographic Activity of the Superior and Inferior Portions of the Gluteus Maximus Muscle During Common Therapeutic Exercises." *J Orthop Sports Phys Ther* 46(9):794–799 — fine-wire EMG confirming gluteus maximus's superior/inferior functional segments (corrects an earlier draft's misattribution of this claim to Gottschalk et al. 1989, which is actually about gluteus medius/minimus — caught by adversarial fact-check, see docs/VERIFICATION.md).
- Lieb FJ, Perry J (1968) "Quadriceps function: an anatomical and mechanical study using amputated limbs." *J Bone Joint Surg Am* 50(8):1535–1548 — original description dividing vastus medialis into proximal VML and distal VMO.
- Castanov V et al. (2019) "Muscle architecture of vastus medialis obliquus and longus and its functional implications: A three-dimensional investigation." *Clin Anat* 32(4):515–523 — quantitative pennation-angle confirmation of the VML/VMO distinction (corrects an earlier draft's citation of Lieber, Loren & Fridén 1994, which is actually about wrist extensor sarcomere length, unrelated to the knee — caught by adversarial fact-check).
- Takizawa M et al. (2013) "The adductor part of the adductor magnus is innervated by both obturator and sciatic nerves." *Clin Anat* 27(5):778–782 — refines/confirms adductor magnus's dual-innervation adductor+hamstring parts.
- Kellis E et al. (2011) "In vivo and in vitro examination of the tendinous inscription of the human semitendinosus muscle." *Cells Tissues Organs* 195(4):365–376.
- Bogduk N, Macintosh JE, Pearcy MJ (1992) "A universal model of the lumbar back muscles in the upright position." *Spine* 17(8):897–913 — quantitative architecture/moment-arm model of lumbar erector spinae (iliocostalis, longissimus) and multifidus.
- Ward SR, Kim CW, Eng CM, Gottschalk LJ 4th, Tomiya A, Garfin SR, Lieber RL (2009) "Architectural analysis and intraoperative measurements demonstrate the unique design of the multifidus muscle for lumbar spine stability." *J Bone Joint Surg Am* 91(1):176–185 — multifidus's unusually short fascicle length relative to its large PCSA, an architecture built for stiffness/force rather than excursion.
- Phillips S, Mercer S, Bogduk N (2008) "Anatomy and biomechanics of quadratus lumborum." *Proc Inst Mech Eng H* 222(2):151–159 — describes quadratus lumborum's three fiber-bundle layers (anterior/iliocostal, middle/lumbocostal, posterior/iliolumbar) (corrects an earlier draft's citation of Bogduk, Macintosh & Pearcy 1992 for this claim — that paper covers lumbar erector spinae/multifidus but not quadratus lumborum — caught by adversarial fact-check, see docs/VERIFICATION.md).
- Hodges PW, Richardson CA (1996) "Inefficient muscular stabilization of the lumbar spine associated with low back pain." *Spine* 21(22):2640–2650 — transversus abdominis's feedforward (anticipatory) activation preceding limb movement, its role as the abdominal wall's primary intrinsic spinal stabilizer.
- De Troyer A, Kirkwood PA, Wilson TA (2005) "Respiratory action of the intercostal muscles." *Physiol Rev* 85(2):717–756 — documents that the internal intercostal's interosseous part (expiratory) and interchondral/parasternal part (inspiratory) have opposite mechanical actions despite being one named muscle.
- Kearney R, Sawhney R, DeLancey JOL (2004) "Levator ani muscle anatomy evaluated by origin-insertion pairs." *Obstet Gynecol* 104(1):168–173 — origin-insertion analysis of levator ani (used here alongside Gray's for the traditional puborectalis/pubococcygeus/iliococcygeus 3-part teaching division; note that paper's own conclusion favors a finer 5-way subdivision — puboperineal/pubovaginal/puboanal/puborectal/iliococcygeal — flagged by adversarial fact-check, see docs/VERIFICATION.md).
- van Eijden TM, Korfage JA, Brugman P (1997) "Architecture of the human jaw-closing and jaw-opening muscles." *Anat Rec* 248(3):464–474 — cadaveric fascicle length/pennation/PCSA data for masseter's superficial/deep heads, temporalis's anterior/posterior parts, and medial/lateral pterygoid's heads; an architecture-only study, not a source for muscle activity timing (see the Murray et al. entry below for that).
- Murray GM, Phanachet I, Uchida S, Whittle T (2004) "The human lateral pterygoid muscle: a review of some experimental aspects and possible clinical relevance." *Aust Dent J* 49(1):2–8 — the classical reciprocal-activity model (lateral pterygoid's superior head active during jaw closing, inferior head during opening), together with the caveat that later EMG-with-imaging studies found this reciprocal pattern less clear-cut than the classical model suggests (corrects an earlier draft's attribution of this functional/activity-timing claim to van Eijden et al. 1997, an architecture-only study that does not address activity timing — caught by adversarial fact-check, see docs/VERIFICATION.md).

**Fascia**
- Stecco C. *Functional Atlas of the Human Fascial System*. Churchill Livingstone/Elsevier, 2015.
- Vleeming A, Pool-Goudzwaard AL, Stoeckart R, van Wingerden JP, Snijders CJ (1995) "The posterior layer of the thoracolumbar fascia: its function in load transfer from spine to legs." *Spine* 20(7):753–758 — the posterior layer's myofascial coupling of contralateral latissimus dorsi and gluteus maximus across the lumbosacral junction.

**Nerve root maps**
- ASIA (American Spinal Injury Association) International Standards for Neurological Classification of Spinal Cord Injury — standard myotome/dermatome charts.

## Sources considered but not reachable this session

An automated multi-agent PubMed/web literature research pass (12 parallel
research agents covering ROM, muscle architecture, plexus trees, vasculature,
fascia and joint kinematics) was attempted to independently ground every
number against live-searched literature. It failed entirely — every agent
hit a tool-level structured-output error after multiple retries, a systemic
issue rather than a content problem (see the workflow run for
`nmsk-atlas-research`, all 12/12 agents errored identically). Rather than
retry at similar cost, the data in this pass was authored directly from the
well-established references above (the same standard I used successfully
for the skeleton, joints, and nerve-root map), and then spot-verified by a
second, smaller round of adversarial fact-check agents — see
docs/VERIFICATION.md for what they checked and found.

## Data sources for future full-body scale-up (not used in this pass)

- NIH Visible Human Project — public domain, ~15GB of 1mm axial cryosection/CT/MRI data. https://www.nlm.nih.gov/research/visible/visible_human.html
- AIST BodyParts3D / Anatomography — CC BY-SA segmented 3D anatomy meshes. https://lifesciencedb.jp/bp3d/
- OpenSim (Stanford) musculoskeletal models — BSD-licensed, published moment-arm/muscle-path data usable for Stage 6 validation. https://opensim.stanford.edu
