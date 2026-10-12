"""Q222 additional references for data/anatomy/structure_parts.json (same rules as refs.py).

Every journal entry was read in its PubMed record (title, authors, journal, year, volume, pages, DOI, PMID, abstract) on 2026-10-12 through the PubMed
connector; the `basis` string says what the abstract supports.  Nothing is invented; when PubMed has no DOI the field is None.
"""
import refs
from refs import J, REFS

V2 = "pubmed-2026-10-12"


def J2(key, authors, title, journal, year, vol, pages, doi, pmid, basis):
    k, d = J(key, authors, title, journal, year, vol, pages, doi, pmid, basis)
    d["verified"] = V2
    REFS[k] = d


# ---- shoulder girdle / back / arm
J2("umatani2026", "Umatani N, Arai R, Kuriyama S, Matsuda S.", "Anatomical variations in pectoralis minor muscle attachment to the coracoid process relevant to muscle transfer: A cadaveric study.", "J Orthop Sci", 2026, "31(4)", "783-788",
   "10.1016/j.jos.2026.01.008", "41720692", "abstract: 22 cadaver shoulders; PMiM tendon on the medial surface of the coracoid in 11 (50 %), on the superior or medial-to-superior surface in the other 11")
J2("ogut2024pmi", "Ogut E, Bagci S, Aslan GK, Turkoglu P, Falay M, Barut C.", "A case report of bilateral atypical origin of pectoralis minor.", "Surg Radiol Anat", 2024, "46(8)", "1373-1378",
   "10.1007/s00276-024-03407-9", "38858313", "abstract: case report; right PMi bifid with medial and lateral fibres, left PMi from superolateral margins of ribs 4-6 to the anterosuperior surface of the coracoid")
J2("kwon2025ld", "Kwon S, Choi CH, Kim H, Hur MS.", "Morphological Analysis of the Latissimus Dorsi Tendon Insertion: Implications for Optimizing Tendon Transfer Surgeries in Rotator Cuff Repair.", "Clin Anat", 2025, "39(5)", "572-578",
   "10.1002/ca.24285", "40366331", "abstract: 32 LD tendons in 16 Korean cadavers; three insertion patterns fully combined (40.6 %) / partially combined (34.4 %) / fully separated (25.0 %) with the teres major; slips to triceps tendon, brachial fascia, coracoid, anterior capsule in 9 specimens")
J2("bustami1986", "Bustami FM.", "A new description of the lumbar erector spinae muscle in man.", "J Anat", 1986, "144", "81-91",
   None, "3693050", "abstract: lumbar erector spinae = superficial (costal) part from the erector spinae aponeurosis to the lower ten ribs + deep (vertebral) part into upper four lumbar and lower eight thoracic vertebrae")
J2("alraddadi2017", "Alraddadi A, Alashkham A, Lamb C, Soames R.", "Variability in attachment of the coracoacromial ligament in relation with its morphology.", "Surg Radiol Anat", 2017, "39(12)", "1323-1330",
   "10.1007/s00276-017-1900-5", "28735412", "abstract: 220 shoulders; CAL single band 16 %, two bands 38 %, three or more bands 46 %; shapes broadband / quadrangular / Y-shaped / multiple-banded; medial acromial and coracoid attachments")
J2("alraddadi2021", "Alraddadi A, Alashkham A, Lamb C, Soames R.", "The association between coracoacromial ligament morphology and rotator cuff tears: A cadaveric study.", "Clin Anat", 2021, "35(4)", "461-468",
   "10.1002/ca.23814", "34851534", "abstract: 172 shoulders; CAL one band 18 %, two bands 36 %, three or more bands 46 % (155 shoulders); more than one band associated with rotator cuff tear")
J2("fealy2005", "Fealy S, April EW, Khazzam M, Armengol-Barallat J, Bigliani LU.", "The coracoacromial ligament: morphology and study of acromial enthesopathy.", "J Shoulder Elbow Surg", 2005, "14(5)", "542-548",
   "10.1016/j.jse.2005.02.006", "16194749", "abstract: 56 shoulders; most common configuration two bands, anterolateral band (ALB) and posteromedial band (PMB); ALB may end in the coracoacromial falx; spurs in the ALB")
J2("stine2009", "Stine IA, Vangsness CT.", "Analysis of the capsule and ligament insertions about the acromioclavicular joint: a cadaveric study.", "Arthroscopy", 2009, "25(9)", "968-974",
   "10.1016/j.arthro.2009.04.072", "19732634", "abstract: 28 shoulders; AC capsular insertions measured on anterior, posterior, superior, inferior edges; trapezoid begins 14.7 mm and conoid 32.1 mm from the lateral clavicle")
J2("morell2016", "Morell DJ, Thyagarajan DS.", "Sternoclavicular joint dislocation and its management: A review of the literature.", "World J Orthop", 2016, "7(4)", "244-250",
   "10.5312/wjo.v7.i4.244", "27114931", "abstract: SC joint stability from costoclavicular, interclavicular and capsular ligaments; the posterior capsule is the most important restraint")
# ---- forearm / hand
J2("thomas2000", "Thomas SJ, Yakin DE, Parry BR, Lubahn JD.", "The anatomical relationship between the posterior interosseous nerve and the supinator muscle.", "J Hand Surg Am", 2000, "25(5)", "936-941",
   "10.1053/jhsu.2000.16360", "11040309", "abstract: 31 specimens of 16 cadavers; supinator one semicircular head/layer in 71 %, two distinct heads/layers in 29 % (superficial to the lateral epicondyle, deep to the ulna below the radial notch); arcade of Frohse membranous 68 %, tendinous 32 %")
J2("kacena2025", "Kacena-Merrell C, Ngo S, Chow I.", "Mapping Origins of Tendons on the Lateral Epicondyle.", "J Hand Surg Am", 2025, "51(4)", "426.e1-426.e7",
   "10.1016/j.jhsa.2025.05.016", "40622317", "abstract: 6 cadaveric arms; ECRB origin 8.3 +/- 0.8 mm proximal-distal x 7.6 +/- 0.3 mm anterior-posterior and 0 mm from the joint capsule; EDC origin touches the proximal edge of the LCL")
J2("inserra1986", "Inserra S, Spinner M.", "An anatomic factor significant in transposition of the ulnar nerve.", "J Hand Surg Am", 1986, "11(1)", "80-82",
   "10.1016/s0363-5023(86)80109-5", "3944450", "abstract: cadaver dissection of the flexor-pronator origin; common aponeurosis between flexor digitorum superficialis of the ring finger and the humeral head of flexor carpi ulnaris must be released for ulnar nerve transposition")
J2("rein2025", "Rein S, Hagert E.", "Nerve transfer of the median flexor pollicis brevis branch to the deep branch of the ulnar nerve for ulnar nerve palsy: a cadaveric feasibility study.", "Hand Surg Rehabil", 2025, "44(2)", "102083",
   "10.1016/j.hansur.2025.102083", "39805349", "abstract: 6 cadaveric hands; separate median branch to the superficial head of FPB (sFPB) 8.3 +/- 5.3 mm distal to the thenar branch; the deep head of FPB is reinnervated via the deep branch of the ulnar nerve")
J2("loss2020", "Loss J, Li ZM.", "Biometry of thenar muscle origins on the flexor retinaculum.", "Clin Anat", 2020, "33(8)", "1176-1180",
   "10.1002/ca.23558", "31894884", "abstract: 10 cadaveric specimens; origin areas APB 105.8, sFPB 64.6, OPP 245.9 mm2 (TCL 386.2 mm2); APB in the proximal-radial quadrant of the TCL, sFPB on the distal aponeurosis outside the TCL, OPP around the ridge of the trapezium")
J2("may2020", "May CA.", "Long Abductor Digiti Minimi Muscle: Variation of the Hypothenar Muscles and Clinical Consequences.", "Clin Anat", 2020, "33(5)", "643-645",
   "10.1002/ca.23472", "31573103", "abstract: both hands of 38 donors; opponens digiti minimi and abductor digiti minimi constant; flexor digiti minimi one belly 58 %, two bellies 21 %, missing 21 %; supernumerary muscles 2.5 %")
J2("claassen2013", "Claassen H, Schmitt O, Schulze M, Wree A.", "Variation in the hypothenar muscles and its impact on ulnar tunnel syndrome.", "Surg Radiol Anat", 2013, "35(10)", "893-899",
   "10.1007/s00276-013-1113-5", "23558800", "abstract: review; abductor digiti minimi one to three bellies, additional heads from flexor retinaculum, palmaris longus tendon, pronator quadratus tendon or antebrachial fascia; flexor digiti minimi accessory heads; opponens mostly without variation")
J2("torun2022", "Torun BI, Balaban M.", "Prevalence and clinical implications of the Gantzer's muscle.", "Surg Radiol Anat", 2022, "44(9)", "1297-1303",
   "10.1007/s00276-022-03006-6", "35974186", "abstract: 473 limbs by MRI and US; Gantzer's muscle 20.3 %, all from the coronoid process, 79.1 % attached to FPL and 20.9 % to FDS (US); AIN posterior to it")
J2("asghar2022", "Asghar A, Jha RK, Patra A, Chaudhary B, Singh B.", "The prevalence and distribution of the variants of Gantzer's muscle: a meta-analysis of cadaveric studies.", "Anat Cell Biol", 2022, "55(1)", "3-13",
   "10.5115/acb.21.141", "34785621", "abstract: meta-analysis; accessory head of FPL 48 % (59 studies, 5903 limbs), accessory head of FDP 17 % (14 studies, 1627 limbs); Gantzer's muscle in about 2/3 of limbs")
J2("barker2007", "Barker PJ, Urquhart DM, Story IH, Fahrer M, Briggs CA.", "The middle layer of lumbar fascia and attachments to lumbar transverse processes: implications for segmental control and fracture.", "Eur Spine J", 2007, "16(12)", "2232-2237",
   "10.1007/s00586-007-0502-z", "17924150", "abstract: 18 embalmed cadavers; psoas attaches to the anteromedial surface of each lumbar transverse process, quadratus lumborum and transversus abdominis to its lateral border (QL at the upper and lower corners, TrA via the middle layer to the tip)")
J2("sugiura2025", "Sugiura S, Nimura A, Hishiyama J, Fujishiro H, Sasaki T, Muro S, Yoshii T, Akita K.", "The Trapezius Aponeurosis Insertion on the Acromion: An Anatomical Study with a Possible Implication for Dynamic Stabilization of the Acromioclavicular Joint.", "J Bone Joint Surg Am", 2026, "108(6)", "450-456",
   "10.2106/JBJS.25.01007", "41460933", "abstract: 21 shoulder girdles; trapezius aponeurosis inserts on the medial edge of the acromion, the posterior end of the AC joint and the posterior edge of the lateral clavicle; lengths 28.9 / 20.3 / 7.2 mm; fibrocartilaginous insertion only at the acromial insertion; contiguous with the deltoid origin and the superior AC capsule")
J2("gaydarski2023", "Gaydarski LL, Georgiev GP, Olewnik L, Karauda P, Landzhov B.", "A Rare Variation of the Levator Scapulae Muscle: A Case Report and Review of Literature.", "Cureus", 2023, "15(7)", "e42355",
   "10.7759/cureus.42355", "37621798", "abstract: case report; accessory slip from the distal third of levator scapulae inserting onto the superior nuchal line, passing above the superficial branch of the transverse cervical vessels")
