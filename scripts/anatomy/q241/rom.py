"""Q241 / Q245 normal range of motion (degrees) used as the HARD bounds of the Pose-panel sliders.

Q245 re-checked every value against the published literature (see docs/pose_rom_table.md for the full table, the rule and the references).  The rule used for every bound:
  HARD bound = mean + 1 SD of the best adult sample whose mean AND SD were actually read (full text or abstract), rounded to a whole degree;
               when only a mean was read: that mean (of the larger / multi-sex sample when sources differ);
               when nothing could be read: the earlier AAOS-style value, kept and labelled 'abstract only' (number NOT verified);
  SOFT ('extended') limit = mean + 2 SD, only where an SD was read (stored in ROM_EVID / the rig 'rom_meta', not used by the viewer).
Passive end-of-range values are preferred (the sliders pose a body, not a muscle contraction).  The bounds are therefore 'upper normal' values of the sources' (mostly young adult) samples:
a healthy adult beyond the soft limit exists, and a person aged 60+ is well inside them.

Public API (unchanged since Q241): ROM[key] = (lo, hi, label, src) with lo..hi the allowed range of the displayed value, spine_weights().
New in Q245: ROM_EVID (per end: old value, status, data, soft limit, sources), SOURCES, COUPLED, STATUS, status_text(), changed(), rom_meta()."""

import math

# status codes of one end of one range
STATUS = {
    "V_FT": "verified from source (full text)",         # the number was read in the full text / table of a primary paper
    "V_AB": "verified from source (abstract)",          # the number was read in the PubMed abstract of a primary paper
    "SEC": "secondary snippet only",                    # number seen only in a search-engine summary of a source page (primary table not opened)
    "AO": "abstract only (number not verified)",        # paper found and abstract read but the abstract has no number: the earlier AAOS-style value is kept, UNVERIFIED
    "AS": "assumption",                                 # modelling choice, no standard value
    "DEF": "definition (neutral = 0)",                  # the end is the anatomical zero of the displayed value
}

# id -> (citation, doi, pmid, how it was read in Q245)
SOURCES = {
    "Vairo2012": ("Vairo GL et al., Clinical descriptive measures of shoulder range of motion for a healthy, young and physically active cohort. Sports Med Arthrosc Rehabil Ther Technol 2012;4:33", "10.1186/1758-2555-4-33", "22964130", "full text (PMC3475119), tables 2-5"),
    "Zwerus2019": ("Zwerus EL et al., Normative values and affecting factors for the elbow range of motion. Shoulder Elbow 2019;11:215-224 (online 2017)", "10.1177/1758573217728711", "31210794", "abstract (full text not returned)"),
    "Kim2014": ("Kim TS et al., A study on the measurement of wrist motion range using the iPhone 4 gyroscope application. Ann Plast Surg 2014;73:215-218", "10.1097/SAP.0b013e31826eabfe", "24322647", "abstract (goniometer values, n = 52)"),
    "Baumbach2014": ("Baumbach SF et al., The influence of knee position on ankle dorsiflexion - a biometric study. BMC Musculoskelet Disord 2014;15:246", "10.1186/1471-2474-15-246", "25053374", "full text (PMC4118219), table 2"),
    "Kouyoumdjian2012": ("Kouyoumdjian P et al., Clinical evaluation of hip joint rotation range of motion in adults. Orthop Traumatol Surg Res 2012;98:17-23", "10.1016/j.otsr.2011.08.015", "22227606", "abstract"),
    "Soucie2011": ("Soucie JM et al., Range of motion measurements: reference values and a database for comparison studies. Haemophilia 2011;17:500-507", "10.1111/j.1365-2516.2010.02399.x", "21070485", "abstract; adult rows (hip, knee, ages 20-44) only via a search-engine summary of the CDC archive table (archive.cdc.gov/www_cdc_gov/ncbddd/jointrom), paper itself not opened"),
    "Roaas1982": ("Roaas A, Andersson GBJ, Normal range of motion of the hip, knee and ankle joints in male subjects, 30-40 years of age. Acta Orthop Scand 1982;53:205-208", "10.3109/17453678208992202", "7136564", "abstract; hip means via a search-engine summary of the full text (actaorthop.org), table not opened"),
    "Boone1979": ("Boone DC, Azen SP, Normal range of motion of joints in male subjects. J Bone Joint Surg Am 1979;61:756-759", "", "457719", "abstract only (no table values seen)"),
    "Roach1991": ("Roach KE, Miles TP, Normal hip and knee active range of motion: the relationship to age. Phys Ther 1991;71:656-665", "10.1093/ptj/71.9.656", "1881956", "abstract only (no table values seen)"),
    "Walker1984": ("Walker JM et al., Active mobility of the extremities in older subjects. Phys Ther 1984;64:919-923", "10.1093/ptj/64.6.919", "6728913", "abstract only (60-84 years, outside the 20-59 default)"),
    "Barnes2001": ("Barnes CJ, Van Steyn SJ, Fischer RA, The effects of age, sex, and shoulder dominance on range of motion of the shoulder. J Shoulder Elbow Surg 2001;10:242-246", "10.1067/mse.2001.115270", "11408905", "abstract only (no values)"),
    "Ellenbecker1996": ("Ellenbecker TS et al., Glenohumeral joint internal and external rotation range of motion in elite junior tennis players. J Orthop Sports Phys Ther 1996;24:336-341", "10.2519/jospt.1996.24.6.336", "8938599", "abstract only (no values; NOT Am J Sports Med as sometimes cited)"),
    "Conte2009": ("Conte ALF et al., Handedness influences passive shoulder range of motion in nonathlete adult women. J Manipulative Physiol Ther 2009;32:149-153", "10.1016/j.jmpt.2008.12.006", "19243727", "abstract"),
    "Macedo2008": ("Macedo LG, Magee DJ, Differences in range of motion between dominant and nondominant sides of upper and lower extremities. J Manipulative Physiol Ther 2008;31:577-582", "10.1016/j.jmpt.2008.09.003", "18984240", "abstract"),
    "Macedo2009": ("Macedo LG, Magee DJ, Effects of age on passive range of motion of selected peripheral joints in healthy adult females. Physiother Theory Pract 2009;25:145-164", "10.1080/09593980802686870", "19212902", "abstract (no table values)"),
    "Gunal1996": ("Gunal I et al., Normal range of motion of the joints of the upper extremity in male subjects, with special reference to side. J Bone Joint Surg Am 1996;78:1401-1404", "10.2106/00004623-199609000-00017", "8816658", "abstract (n = 1000 men 18-22 y; right smaller than left, no values)"),
    "Allander1974": ("Allander E et al., Normal range of joint movements in shoulder, hip, wrist and thumb with special reference to side. Int J Epidemiol 1974;3:253-261", "10.1093/ije/3.3.253", "4414846", "citation only (no abstract in PubMed)"),
    "McKay2017": ("McKay MJ et al., Normative reference values for strength and flexibility of 1,000 children and adults. Neurology 2017;88:36-43", "10.1212/WNL.0000000000003466", "27881628", "abstract (no values; full text not returned)"),
    "Morrey1981": ("Morrey BF, Askew LJ, Chao EY, A biomechanical study of normal functional elbow motion. J Bone Joint Surg Am 1981;63:872-877", "", "7240327", "abstract (functional arc 30-130 flexion, 50 pronation + 50 supination: needs of daily living, not the limit)"),
    "Ryu1991": ("Ryu JY et al., Functional ranges of motion of the wrist joint. J Hand Surg Am 1991;16:409-419", "10.1016/0363-5023(91)90006-w", "1861019", "abstract (functional need: 60 ext, 54 flex, 40 ulnar, 17 radial)"),
    "Palmer1985": ("Palmer AK et al., Functional wrist motion: a biomechanical study. J Hand Surg Am 1985;10:39-46", "10.1016/s0363-5023(85)80246-x", "3968403", "abstract (functional need: 5 flex, 30 ext, 10 radial, 15 ulnar)"),
    "Hume1990": ("Hume MC et al., Functional range of motion of the joints of the hand. J Hand Surg Am 1990;15:240-243", "10.1016/0363-5023(90)90102-w", "2324451", "abstract (functional flexion postures MCP 61, PIP 60, DIP 39; thumb MCP 21, IP 18)"),
    "Mallon1991": ("Mallon WJ, Brown HR, Nunley JA, Digital ranges of motion: normal values in young adults. J Hand Surg Am 1991;16:882-887", "10.1016/s0363-5023(10)80155-8", "1940169", "abstract only (no values; women more MCP extension)"),
    "Cooney1981": ("Cooney WP et al., The kinesiology of the thumb trapeziometacarpal joint. J Bone Joint Surg Am 1981;63:1371-1381", "", "7320028", "abstract (total CMC motion 53 flexion-extension, 42 abduction-adduction, 17 axial rotation; n = 19, 26 y)"),
    "Mossberg1983": ("Mossberg KA, Smith LK, Axial rotation of the knee in women. J Orthop Sports Phys Ther 1983;4:236-240", "10.2519/jospt.1983.4.4.236", "18806440", "abstract (total tibial rotation 35 / 40 / 44 at 70 / 90 / 110 deg knee flexion; ER about twice IR)"),
    "Nawoczenski1999": ("Nawoczenski DA, Baumhauer JF, Umberger BR, Relationship between clinical measurements and motion of the first metatarsophalangeal joint during gait. J Bone Joint Surg Am 1999;81:370-376", "10.2106/00004623-199903000-00009", "10199275", "abstract (active weight-bearing dorsiflexion 44, heel rise 58, gait 42)"),
    "Hopson1995": ("Hopson MM, McPoil TG, Cornwall MW, Motion of the first metatarsophalangeal joint. Reliability and validity of four measurement techniques. J Am Podiatr Med Assoc 1995;85:198-204", "10.7547/87507315-85-4-198", "7738816", "abstract (about 65 deg extension needed for walking; static techniques exceed it)"),
    "Lindsjo1985": ("Lindsjo U, Danckwardt-Lillieström G, Sahlstedt B, Measurement of the motion range in the loaded ankle. Clin Orthop Relat Res 1985;199:68-71", "", "4042498", "abstract (loaded dorsiflexion 32.5 deg on radiographs, n = 66)"),
    "Lundberg1989a": ("Lundberg A et al., The axis of rotation of the ankle joint. J Bone Joint Surg Br 1989;71:94-99", "10.1302/0301-620X.71B1.2915016", "2915016", "abstract (axis changes through the arc, near the mid-malleolar point)"),
    "Lundberg1989b": ("Lundberg A et al., Kinematics of the ankle/foot complex - Part 2: pronation and supination. Foot Ankle 1989;9:248-253", "10.1177/107110078900900508", "2731838", "abstract (talonavicular > talocalcaneal motion)"),
    "Elveru1988": ("Elveru RA, Rothstein JM, Lamb RL, Goniometric reliability in a clinical setting. Subtalar and ankle joint measurements. Phys Ther 1988;68:672-677", "10.1093/ptj/68.5.672", "3362980", "abstract (inter-tester ICC 0.17-0.72: goniometric foot values are poorly reproducible)"),
    "Apti2023": ("Apti A et al., Normative values for cervical and lumbar range of motion in healthy young adults. Journal of Turkish Spinal Surgery 2023 (n = 300, 18-29 y, two-arm goniometer; DOI not returned by the search tool)", "", "", "abstract (Consensus record)"),
    "Youdas1992": ("Youdas JW et al., Normal range of motion of the cervical spine: an initial goniometric study. Phys Ther 1992;72:770-780", "10.1093/ptj/72.11.770", "1409874", "abstract only (no values; n = 337, 11-97 y, females more except flexion, all decrease with age)"),
    "Lind1989": ("Lind B et al., Normal range of motion of the cervical spine. Arch Phys Med Rehabil 1989;70:692-695", "", "2774888", "abstract only (no values; no sex difference, linear decrease with age)"),
    "Bible2010c": ("Bible JE et al., Normal functional range of motion of the cervical spine during 15 activities of daily living. J Spinal Disord Tech 2010;23:15-21", "10.1097/BSD.0b013e3181981632", "20051924", "abstract (functional needs 13-32 flex/ext, 9-21 lateral, 13-57 rotation)"),
    "Bible2010l": ("Bible JE et al., Normal functional range of motion of the lumbar spine during 15 activities of daily living. J Spinal Disord Tech 2010;23:106-112", "10.1097/BSD.0b013e3181981823", "20065869", "abstract (functional needs 3-49 flex/ext, 2-11 lateral, 2-7 rotation)"),
    "Ishii2004": ("Ishii T et al., Kinematics of the upper cervical spine in rotation: in vivo three-dimensional analysis. Spine 2004;29:E139-E144", "10.1097/01.brs.0000116998.55056.3c", "15087810", "abstract (Oc-C1 1.7 +- 1.5, C1-C2 36.2 +- 4.5 deg axial rotation to each side)"),
    "Pearcy1984a": ("Pearcy M, Portek I, Shepherd J, Three-dimensional x-ray analysis of normal movement in the lumbar spine. Spine 1984;9:294-297", "", "6374922", "abstract (via Consensus; about 14 deg flexion + extension per level)"),
    "Pearcy1984b": ("Pearcy MJ, Tibrewal SB, Axial rotation and lateral bending in the normal lumbar spine measured by three-dimensional radiography. Spine 1984;9:582-587", "", "6495028", "abstract (via Consensus; about 2 deg axial rotation per level, lateral bending 10/10/10/6/3 deg L1-S1; one-sided vs total not stated)"),
    "Edmondston2012": ("Edmondston SJ et al., Clinical and radiological investigation of thoracic spine extension motion during bilateral arm elevation. J Orthop Sports Phys Ther 2012;42:861-869", "10.2519/jospt.2012.4164", "22523094", "abstract (extension with arm elevation 12.8 +- 7.6 deg radiographic, n = 21 men; not a maximal-extension test)"),
    "McClure2001": ("McClure PW et al., Direct 3-dimensional measurement of scapular kinematics during dynamic movements in vivo. J Shoulder Elbow Surg 2001;10:269-277", "10.1067/mse.2001.112954", "11408911", "abstract (glenohumeral : scapulothoracic = 1.7 : 1, bone pins, n = 8)"),
    "Ludewig2009": ("Ludewig PM et al., Motion of the shoulder complex during multiplanar humeral elevation. J Bone Joint Surg Am 2009;91:378-389", "10.2106/JBJS.G.01483", "19181982", "abstract (n = 12, bone pins; SC posterior rotation 31, AC posterior tilt 19 deg)"),
    "Wu2002": ("Wu G et al. (ISB), ISB recommendation on definitions of joint coordinate system of various joints - Part I: ankle, hip, and spine. J Biomech 2002;35:543-548", "10.1016/s0021-9290(01)00222-6", "11934426", "abstract only (recommendation text not fetched; deviations in the doc are from the author's knowledge of it)"),
    "Wu2005": ("Wu G et al. (ISB), ISB recommendation on definitions of joint coordinate systems of various joints - Part II: shoulder, elbow, wrist and hand. J Biomech 2005;38:981-992", "10.1016/j.jbiomech.2004.05.042", "15844264", "abstract only (recommendation text not fetched; deviations in the doc are from the author's knowledge of it)"),
    "Sadeghi2000": ("Sadeghi H et al., Symmetry and limb dominance in able-bodied gait: a review. Gait Posture 2000;12:34-45", "10.1016/s0966-6362(00)00070-9", "10996295", "abstract (gait, not joint ROM)"),
    "Herzog1989": ("Herzog W et al., Asymmetries in ground reaction force patterns in normal human gait. Med Sci Sports Exerc 1989;21:110-114", "10.1249/00005768-198902000-00020", "2927295", "abstract (force-plate symmetry index; gives NO joint-angle tolerance)"),
    "Knutson2005": ("Knutson GA, Anatomic and functional leg-length inequality ... Part I. Chiropr Osteopat 2005;13:11", "10.1186/1746-1340-13-11", "16026625", "abstract (anatomic leg-length inequality 5.2 +- 4.1 mm)"),
    "Biaggi2021": ("Biaggi K et al., Shoulder strength and range of motion in healthy collegiate softball players. J Athl Train 2021;56:1086-1093", "10.4085/301-20", "33481015", "abstract (dominant arm 12 deg more ER, 12 deg less IR: overhead athletes)"),
    "Myers2024": ("Myers NL et al., Upper extremity musculoskeletal profiles in tennis players: a systematic review. Sports Health 2024;16:931-937", "10.1177/19417381231223540", "38361439", "abstract (ER gain 1.8-8.8, IR loss 3.0-15.3 deg in men's tennis dominant arm)"),
    "Greene1994": ("Greene WB, Heckman JD (eds), The Clinical Measurement of Joint Motion. AAOS 1994 (also AAOS, Joint Motion: Method of Measuring and Recording, 1965; AMA Guides 5th/6th ed.; Norkin & White 5th ed. 2016; Kapandji; White & Panjabi 2nd ed. 1990)", "", "", "NOT read in Q241 or Q245 (books, no access); values quoted from memory and, for some, from web tables that reproduce them; kept only as the 'old' value"),
}


def _r(x):
    return int(math.floor(x + 0.5))


def E(old, new, st, data, refs=(), soft=None, n=0):
    """one end of a range: old (Q241) value, new (Q245) value, status code, the data behind it, sources, soft ('extended', mean + 2 SD) limit, number of independent sources whose number was read"""
    return dict(old=old, new=new, st=st, data=data, refs=tuple(refs), soft=soft, n=n)


# key -> (label, short src string for the viewer, lo end, hi end)
_DEF = {
    "shoulder_flex": ("Flexion (+) / extension (-)",
        "Q245: flexion = passive mean + 1 SD, Vairo 2012 (170.2 +- 8.6, n 622, 18 y; AAOS 180); extension AAOS 60, abstract only (not verified) - shoulder complex, scapula included",
        E(-60, -60, "AO", "AAOS extension 0-60 (book not re-read). Barnes 2001 measured extension (abstract: non-dominant larger, no values); Greene/AAOS 60", ["Greene1994", "Barnes2001"]),
        E(180, 179, "V_FT", "Vairo 2012 passive flexion 170.6 +- 7.7 (dominant) / 169.8 +- 9.4 (non-dominant); men 170.2 +- 7.5 / women 172.9 +- 8.5 (dominant); n = 548 men + 74 women, 18-19 y, supine goniometer. Pooled mean 170.2, SD 8.6; mean + 1 SD = 179, + 2 SD = 187 (95th percentile 185). Barnes 2001: no dominant / non-dominant difference in forward elevation. AAOS 180", ["Vairo2012", "Barnes2001", "Greene1994"], soft=187, n=1)),
    "shoulder_abd": ("Abduction (+) / adduction (-)",
        "AAOS abduction 0-180 (abstract only, not verified); adduction in the frontal plane -30 = ASSUMPTION (AAOS/AMA cross-body adduction 30-50 is horizontal adduction)",
        E(-30, -30, "AS", "adduction limit in the frontal plane: ASSUMPTION (AAOS adduction 0-30, AMA 5th 50 = cross-body). Vairo 2012 cross-body adduction 20-25 cm (a distance, not an angle)", ["Vairo2012", "Greene1994"]),
        E(180, 180, "AO", "AAOS abduction 0-180 (book not re-read). Barnes 2001: abduction measured, no dominant / non-dominant difference, no values in the abstract", ["Barnes2001", "Greene1994"])),
    "shoulder_rot": ("Internal rotation (+) / external rotation (-)",
        "Q245: Vairo 2012 passive mean + 1 SD: ER 81.4 +- 12.0 (arm at side, elbow 90), IR 60.7 +- 13.4 (arm at 90 abduction); ER reaches 103-105 at 90 abduction (AAOS 90 / 70)",
        E(-90, -93, "V_FT", "Vairo 2012 passive ER with the arm adducted, elbow 90: 82.3 +- 12.3 (dominant) / 80.5 +- 11.7 (non-dominant): mean 81.4, SD 12.0, + 1 SD = 93, + 2 SD = 105. With the arm at 90 abduction ER is larger: 104.6 +- 10.8 / 100.6 +- 9.8 (+ 1 SD 113). The single slider must be valid in every arm position, so the arm-at-side value is used. AAOS 90 is defined at 90 abduction", ["Vairo2012", "Barnes2001", "Ellenbecker1996"], soft=-105, n=1),
        E(70, 74, "V_FT", "Vairo 2012 passive IR at 90 abduction, elbow 90: 58.9 +- 14.0 (dominant) / 62.4 +- 12.8 (non-dominant): mean 60.7, SD 13.4, + 1 SD = 74, + 2 SD = 88. IR with the arm at the side was not measured. AAOS 70", ["Vairo2012", "Greene1994"], soft=88, n=1)),
    "elbow_flex": ("Flexion (+) / extension (0)",
        "Q245: Zwerus 2019 active flexion 146, passive 3-5 larger = about 150 (AAOS 150, AMA 140); extension 0 (Zwerus: active -2)",
        E(0, 0, "V_AB", "Zwerus 2019 active extension -2 deg (dominant hand; sign convention not in the abstract, a few degrees of hyperextension); the model allows none", ["Zwerus2019"], n=1),
        E(150, 150, "V_AB", "Zwerus 2019 (n = 352 adults, goniometer): active flexion 146 (dominant), passive 3-5 deg larger = about 150; males less than females; dominant vs non-dominant < 1 deg. SD not in the abstract. AAOS 150, AMA 140. Morrey 1981 functional arc 30-130 is the need of daily living, not the limit", ["Zwerus2019", "Morrey1981", "Greene1994"], n=1)),
    "forearm_sup": ("Supination (+) / pronation (-)",
        "Q245: Zwerus 2019 active pronation 80 / supination 87 + passive 3-5 = pronation 84 / supination 91 (AAOS 80 / 80)",
        E(-80, -84, "V_AB", "Zwerus 2019 active pronation 80 (dominant), passive 3-5 larger (midpoint 4) = 84 (derived). Soucie 2011 (children 2-8 y, secondary snippet) 80-85. AAOS 80", ["Zwerus2019", "Soucie2011", "Greene1994"], n=1),
        E(80, 91, "V_AB", "Zwerus 2019 active supination 87 (dominant), passive + 4 = 91 (derived). Soucie 2011 (children, secondary snippet) 86-94. AAOS 80. Females more than males (Soucie: most obvious sex difference)", ["Zwerus2019", "Soucie2011", "Greene1994"], n=1)),
    "wrist_flex": ("Flexion (+) / extension (-)",
        "Q245: Kim 2014 goniometer n 52: extension 71.1 +- 4.9, flexion 74.2 +- 5.1 (+ 1 SD 76 / 79); AAOS 70 / 80; single study",
        E(-70, -76, "V_AB", "Kim 2014 (n = 52 healthy adults, universal goniometer): extension 71.1 +- 4.9 -> + 1 SD = 76, + 2 SD = 81. Functional need of daily living: 60 (Ryu 1991), 30 (Palmer 1985). AAOS 70", ["Kim2014", "Ryu1991", "Palmer1985", "Greene1994"], soft=-81, n=1),
        E(80, 79, "V_AB", "Kim 2014: flexion 74.2 +- 5.1 -> + 1 SD = 79, + 2 SD = 84. Functional need 54 (Ryu), 5 (Palmer). AAOS 80", ["Kim2014", "Ryu1991", "Palmer1985", "Greene1994"], soft=84, n=1)),
    "wrist_dev": ("Radial deviation (+) / ulnar deviation (-)",
        "Q245: Kim 2014 goniometer n 52: radial 19.7 +- 3.0, ulnar 34.0 +- 3.7 (+ 1 SD 23 / 38); AAOS 20 / 30; single study",
        E(-30, -38, "V_AB", "Kim 2014: ulnar deviation 34.0 +- 3.7 -> + 1 SD = 38, + 2 SD = 41. Functional need 40 (Ryu), 15 (Palmer). AAOS 30", ["Kim2014", "Ryu1991", "Palmer1985", "Greene1994"], soft=-41, n=1),
        E(20, 23, "V_AB", "Kim 2014: radial deviation 19.7 +- 3.0 -> + 1 SD = 23, + 2 SD = 26. Functional need 17 (Ryu), 10 (Palmer). AAOS 20", ["Kim2014", "Ryu1991", "Palmer1985", "Greene1994"], soft=26, n=1)),
    "thumb_cmc_flex": ("CMC flexion (+) / extension (-)",
        "AAOS thumb flexion 15 / extension 20 (abstract only, not verified); Cooney 1981 in vivo total CMC flexion-extension 53 (split not in the abstract) - unchanged",
        E(-20, -20, "AO", "Cooney 1981 (n = 19, 26 y, skin markers): total trapeziometacarpal flexion-extension 53 deg versus 35 (15 + 20) in the model; the split between flexion and extension is not in the abstract, so unchanged. Note: the as-built thumbs of the six pages already lie at CMC flexion -41 .. -1.5", ["Cooney1981", "Greene1994"]),
        E(15, 15, "AO", "see extension; AAOS 15", ["Cooney1981", "Greene1994"])),
    "thumb_cmc_abd": ("CMC palmar abduction (+)",
        "Q245: Cooney 1981 in vivo total CMC abduction-adduction 42 (AAOS thumb abduction 70 includes the first web and MCP, not the CMC alone); single source",
        E(0, 0, "DEF", "neutral = thumb metacarpal against the index metacarpal", []),
        E(70, 42, "V_AB", "Cooney 1981 (n = 19): total trapeziometacarpal abduction-adduction 42 deg, axial rotation 17 (not modelled). AAOS 70 = radial + palmar abduction of the whole thumb. The model assigns all abduction to the CMC joint", ["Cooney1981", "Greene1994"], n=1)),
    "thumb_mcp": ("MCP flexion (+)",
        "AAOS thumb MCP flexion 0-50 (abstract only, not verified; Hume 1990 functional posture 21)",
        E(-5, -5, "AS", "small hyperextension: ASSUMPTION (AAOS lists 0)", ["Greene1994"]),
        E(50, 50, "AO", "AAOS 50; Hume 1990: functional flexion posture mean 21 deg, 32% of the available flexion (so the active range is about 65, abstract)", ["Hume1990", "Greene1994"])),
    "thumb_ip": ("IP flexion (+) / extension (-)",
        "AAOS thumb IP flexion 0-80, extension 0-20 (abstract only, not verified; Hume 1990 functional 18)",
        E(-20, -20, "AO", "AAOS extension 20 (hyperextension)", ["Greene1994"]),
        E(80, 80, "AO", "AAOS 80; Hume 1990 functional posture 18 deg", ["Hume1990", "Greene1994"])),
    "finger_mcp": ("MCP flexion (+) / extension (-)",
        "AAOS MCP flexion 0-90, hyperextension 0-45 (abstract only, not verified; Mallon 1991 no values in the abstract; Hume 1990 functional 61)",
        E(-45, -45, "AO", "AAOS hyperextension 45; Mallon 1991: women have more MCP extension (active and passive), no numbers in the abstract", ["Mallon1991", "Greene1994"]),
        E(90, 90, "AO", "AAOS 90; Hume 1990 functional flexion posture 61; Mallon: MCP flexion increases linearly from index to little finger (no numbers)", ["Hume1990", "Mallon1991", "Greene1994"])),
    "finger_pip": ("PIP flexion (+)",
        "AAOS PIP flexion 0-100 (abstract only, not verified; Hume 1990 functional 60)",
        E(0, 0, "DEF", "full extension", []),
        E(100, 100, "AO", "AAOS 100; Hume 1990 functional flexion posture 60", ["Hume1990", "Greene1994"])),
    "finger_dip": ("DIP flexion (+)",
        "AAOS DIP flexion 0-70/90, 80 used = ASSUMPTION (Hume 1990 functional 39; Mallon 1991: tenodesis effect at the DIP)",
        E(0, 0, "DEF", "full extension", []),
        E(80, 80, "AS", "AAOS 70-90: mid value, ASSUMPTION. Hume 1990 functional 39; Mallon 1991 describes a tenodesis effect at the DIP (no numbers)", ["Hume1990", "Mallon1991", "Greene1994"])),
    "hip_flex": ("Flexion (+) / extension (-)",
        "Q245: Soucie 2011 passive, ages 20-44 (CDC table, snippet): flexion F 133.8 / M 130.4 -> 132; extension F 18.1 / M 17.4 -> 18 (Roaas 1982: 120 / 9.5; AAOS 120 / 30)",
        E(-30, -18, "SEC", "Soucie 2011 (CDC table, ages 20-44, passive): hip extension F 18.1 (95% CI 17.0-19.2), M 17.4 (16.3-18.5) -> 18. Roaas & Andersson 1982 (men 30-40, passive): mean 9.5 (range 0-35). Roach & Miles 1991 (NHANES): extension is the motion that declines most with age (no values in the abstract). AAOS 30. Chosen: Soucie (larger, both sexes)", ["Soucie2011", "Roaas1982", "Roach1991", "Greene1994"], n=2),
        E(120, 132, "SEC", "Soucie 2011 (CDC table, ages 20-44, passive): hip flexion F 133.8 (132.5-135.1), M 130.4 (129.0-131.8) -> 132. Roaas & Andersson 1982 (men 30-40): mean 120 (range 90-150). AAOS 120. Chosen: Soucie (n = 674 all ages, both sexes); the protocols differ (knee flexed vs not)", ["Soucie2011", "Roaas1982", "Greene1994"], n=2)),
    "hip_abd": ("Abduction (+) / adduction (-)",
        "Q245: Roaas 1982 (men 30-40, passive): abduction 38.5, adduction 30.5 (AAOS 45 / 30); one source, via a snippet",
        E(-30, -30, "SEC", "Roaas & Andersson 1982: adduction mean 30.5 (range 15-45) -> 30. A secondary table of AAOS 'normative' values lists adduction 13.8 +- 6.3 (conflicting; protocol unknown). AAOS 30", ["Roaas1982", "Greene1994"], n=1),
        E(45, 39, "SEC", "Roaas & Andersson 1982: abduction mean 38.5 (range 15-55) -> 39. A secondary table of AAOS values lists 33.0 +- 4.8. AAOS 45. Allander 1974 and Macedo 2009 give side/age effects (no values retrieved)", ["Roaas1982", "Allander1974", "Macedo2009", "Greene1994"], n=1)),
    "hip_rot": ("Internal rotation (+) / external rotation (-)",
        "Q245: Kouyoumdjian 2012 (n 120, 20-60 y): ER 38.5-41.8, IR 29.6-37.9 depending on position (mean ER 40, IR 34); AAOS 45 / 45",
        E(-45, -40, "V_AB", "Kouyoumdjian 2012 external rotation: supine 38.5, prone (hip extended) 41.8, seated (hip flexed 90) 40.6 (derived: total 78.5 - IR 37.9; the abstract prints ER = 78.5 by a typo) -> mean 40. Men 4.7 deg less, decreasing with age, SD not in the abstract. AAOS 45", ["Kouyoumdjian2012", "Greene1994"], n=1),
        E(45, 34, "V_AB", "Kouyoumdjian 2012 internal rotation: supine 29.6, prone 35.2, seated 37.9 -> mean 34. Totals 68.1 / 77.1 / 78.5 (authors: no significant difference between positions). AAOS 45", ["Kouyoumdjian2012", "Greene1994"], n=1)),
    "knee_flex": ("Flexion (+) / extension (0)",
        "Q245: Soucie 2011 passive, ages 20-44 (CDC table, snippet): F 141.9 / M 137.7 -> 140 (AAOS 135 active, AMA 140)",
        E(0, 0, "DEF", "full extension; the as-built knees of the pages lie at -0.4 .. -2.7 (slight hyperextension) and are shown as they are. Soucie reports knee extension (lack of extension in children 1.6-5.4); adult rows not read", ["Soucie2011"]),
        E(135, 140, "SEC", "Soucie 2011 (CDC table, ages 20-44, passive): knee flexion F 141.9 (140.9-142.9), M 137.7 (136.5-138.9) -> 140. AAOS 135 (active), AMA 140. Roach & Miles 1991 NHANES (active) differs from textbooks by up to 18 deg (abstract)", ["Soucie2011", "Roach1991", "Greene1994"], n=1)),
    "ankle_dp": ("Dorsiflexion (+) / plantarflexion (-)",
        "Q245: dorsiflexion non-weight-bearing, knee flexed, Baumbach 2014: 20 +- 9 (+ 1 SD 29; weight-bearing 39 +- 7); with the KNEE EXTENDED only 4 +- 7 (AAOS 20); plantarflexion AAOS 50, abstract only",
        E(-50, -50, "AO", "AAOS plantarflexion 50 (book not re-read). Soucie 2011 children 2-8 y (snippet) 56-67; a later review quotes goniometric PF from < 30 to about 60 (Roaas 1982). Adult values not read", ["Soucie2011", "Roaas1982", "Greene1994"]),
        E(20, 29, "V_FT", "Baumbach 2014 (n = 20, 18-40 y, goniometer, pooled sides): non-weight-bearing knee 20-75 flexed 20-21 +- 9 -> + 1 SD = 29, + 2 SD = 38; knee extended 4 +- 7 (95% CI 1-8; + 1 SD 11, + 2 SD 18); weight-bearing knee flexed 39 +- 7, knee extended 25 +- 6. Lindsjo 1985 loaded 32.5 (radiographs, n = 66). No sex or side difference. AAOS 20 (= the flexed-knee mean)", ["Baumbach2014", "Lindsjo1985", "Greene1994"], soft=38, n=2)),
    "ankle_inv": ("Inversion (+) / eversion (-)",
        "AAOS inversion 0-35, eversion 0-15 = foot (subtalar + transverse tarsal), all given to the subtalar joint here = ASSUMPTION (abstract only, not verified)",
        E(-15, -15, "AS", "AAOS eversion 15 describes the foot complex; the model gives it all to the subtalar joint: ASSUMPTION. Lundberg 1989 (stereophotogrammetry): the talonavicular joint moves most in pronation/supination; Elveru 1988: goniometric subtalar values are poorly reproducible between testers (ICC 0.17-0.32). Subtalar-only normal values were not retrieved", ["Lundberg1989b", "Elveru1988", "Greene1994"]),
        E(35, 35, "AS", "AAOS inversion 35, same remark; the subtalar-only range is probably smaller (not quantified from a source read in Q245)", ["Lundberg1989b", "Elveru1988", "Greene1994"])),
    "toe_mtp": ("MTP flexion (+) / extension (-)",
        "ASSUMPTION: lesser toes ~ +40 / -40 (no standard value found)",
        E(-40, -40, "AS", "lesser-toe MTP extension: ASSUMPTION (no normative series found)", []),
        E(40, 40, "AS", "lesser-toe MTP flexion: ASSUMPTION", [])),
    "toe1_mtp": ("Great toe MTP flexion (+) / extension (-)",
        "AAOS great toe MTP flexion 0-45, extension 0-70 (abstract only, not verified; Nawoczenski 1999 active weight-bearing extension 44, Hopson 1995 about 65 needed for walking)",
        E(-70, -70, "AO", "AAOS extension 70. Nawoczenski 1999 (n = 33): active weight-bearing dorsiflexion 44, heel rise 58, gait 42; Hopson 1995 (n = 20): static techniques exceed the about 65 needed in walking, i.e. 70 passive non-weight-bearing is consistent but was not measured in an abstract", ["Nawoczenski1999", "Hopson1995", "Greene1994"]),
        E(45, 45, "AO", "AAOS flexion 45; no series read", ["Greene1994"])),
    "toe_pip": ("PIP flexion (+)",
        "ASSUMPTION: lesser toes PIP flexion ~35 (few standard values)",
        E(0, 0, "DEF", "full extension", []),
        E(35, 35, "AS", "ASSUMPTION", [])),
    "toe_dip": ("DIP flexion (+)",
        "ASSUMPTION: lesser toes DIP flexion ~60 (few standard values)",
        E(0, 0, "DEF", "full extension", []),
        E(60, 60, "AS", "ASSUMPTION", [])),
    "toe1_ip": ("Great toe IP flexion (+)",
        "AAOS great toe IP flexion 0-90 (abstract only, not verified; no series read)",
        E(-5, -5, "AS", "small hyperextension: ASSUMPTION", []),
        E(90, 90, "AO", "AAOS 90; no measured series found in Q245", ["Greene1994"])),
    "cerv_flex": ("Flexion (+) / extension (-)",
        "Q245: Apti 2023 goniometer n 300 (18-29 y): flexion 57.7 +- 8.2, extension 59.1 +- 10.2 (+ 1 SD 66 / 69); head + neck (occiput included); AAOS 45 / 45, AMA 50 / 60",
        E(-45, -69, "V_AB", "Apti 2023 (n = 300, 18-29 y, 198 F): extension 59.1 +- 10.2 -> + 1 SD = 69, + 2 SD = 80; no sex difference. Young sample: older adults are lower (Youdas 1992, Lind 1989: all motions fall with age, no values in the abstracts). AAOS 45, AMA 5th 60", ["Apti2023", "Youdas1992", "Lind1989", "Greene1994"], soft=-80, n=1),
        E(45, 66, "V_AB", "Apti 2023: flexion 57.7 +- 8.2 -> + 1 SD = 66, + 2 SD = 74. Bible 2010: daily living needs 13-32 deg of flexion/extension. AAOS 45, AMA 5th 50", ["Apti2023", "Bible2010c", "Greene1994"], soft=74, n=1)),
    "cerv_lat": ("Lateral bend right (+) / left (-)",
        "Q245: Apti 2023 (n 300, 18-29 y): right 42.1 +- 7.9, left 41.4 +- 7.7 (+ 1 SD 50); AAOS 45",
        E(-45, -50, "V_AB", "Apti 2023: left lateral flexion 41.4 +- 7.7; mean of the two sides 41.8 +- 7.8 -> + 1 SD = 50, + 2 SD = 57. AAOS 45. Bible 2010: daily living needs 9-21 deg", ["Apti2023", "Bible2010c", "Greene1994"], soft=-57, n=1),
        E(45, 50, "V_AB", "Apti 2023: right lateral flexion 42.1 +- 7.9 (see left)", ["Apti2023", "Greene1994"], soft=57, n=1)),
    "cerv_rot": ("Rotation right (+) / left (-)",
        "Q245: Apti 2023 (n 300, 18-29 y): right 71.1 +- 10.5, left 70.2 +- 9.7 (+ 1 SD 81); AAOS 60, AMA 80; C1/C2 carries 36.2 per side (Ishii 2004)",
        E(-60, -81, "V_AB", "Apti 2023: left rotation 70.2 +- 9.7, mean of both sides 70.7 +- 10.1 -> + 1 SD = 81, + 2 SD = 91. Ishii 2004 (3D MRI, n = 15): C1-C2 36.2 +- 4.5 and occiput-C1 1.7 +- 1.5 deg to each side, i.e. C1/C2 = about 50% of the rotation (model share 0.5, occiput 0): consistent. AAOS 60, AMA 80", ["Apti2023", "Ishii2004", "Greene1994"], soft=-91, n=1),
        E(60, 81, "V_AB", "Apti 2023: right rotation 71.1 +- 10.5 (see left). Bible 2010: daily living needs 13-57 deg (backing a car 57 = 92% of the active range)", ["Apti2023", "Ishii2004", "Bible2010c", "Greene1994"], soft=91, n=1)),
    "thor_flex": ("Flexion (+) / extension (-)",
        "White & Panjabi thoracic flexion ~20-40, extension ~15-25 (not re-read); extension 20 consistent with Edmondston 2012 (12.8 +- 7.6 with arm elevation); flexion 30 = ASSUMPTION",
        E(-20, -20, "V_AB", "Edmondston 2012 (n = 21 men): thoracic extension with end-range bilateral arm elevation 12.8 +- 7.6 radiographic (10.5 +- 4.4 photographic) -> + 1 SD = 20, + 2 SD = 28: consistent with 20 but this is not a maximal-extension test. White & Panjabi extension 15-25 (book, not read)", ["Edmondston2012", "Greene1994"], soft=-28, n=1),
        E(30, 30, "AS", "thoracic flexion ASSUMPTION (White & Panjabi 20-40, book not read)", ["Greene1994"])),
    "thor_lat": ("Lateral bend right (+) / left (-)",
        "White & Panjabi ~25 each side (book, not re-read) - ASSUMPTION",
        E(-25, -25, "AS", "ASSUMPTION (White & Panjabi, from memory); no in vivo series read", ["Greene1994"]),
        E(25, 25, "AS", "ASSUMPTION", ["Greene1994"])),
    "thor_rot": ("Rotation right (+) / left (-)",
        "AAOS thoracolumbar rotation 0-45 each side, mostly thoracic = ASSUMPTION 35 (no in vivo series read)",
        E(-35, -35, "AS", "ASSUMPTION; Apti 2023 goniometric lumbar rotation 38 each side is trunk (thoracic + lumbar + pelvis) rotation, not thoracic alone", ["Apti2023"]),
        E(35, 35, "AS", "ASSUMPTION", ["Apti2023"])),
    "lumb_flex": ("Flexion (+) / extension (-)",
        "AAOS lumbar flexion 0-60, extension 0-25 (abstract only, not verified); Pearcy 1984 about 14 per level (= 70 over 5 levels, vs 85 here)",
        E(-25, -25, "AO", "AAOS extension 25. Pearcy 1984: flexion + extension about 14 deg per level, i.e. about 70 over L1-S1 (the model: 85). Apti 2023 goniometric extension 40.0 +- 10.2 is a surface measure that includes hip and pelvis, not vertebral rotation", ["Pearcy1984a", "Apti2023", "Greene1994"]),
        E(60, 60, "AO", "AAOS flexion 60; Pearcy 1984 as above; Apti 2023 surface flexion 69.9 +- 14.5 (includes the hips). Bible 2010: daily living needs 3-49 deg", ["Pearcy1984a", "Apti2023", "Bible2010l", "Greene1994"])),
    "lumb_lat": ("Lateral bend right (+) / left (-)",
        "AAOS lumbar lateral flexion 0-25 each side (abstract only, not verified); Pearcy 1984 10 / 10 / 10 / 6 / 3 per level (one-sided vs total not stated)",
        E(-25, -25, "AO", "AAOS 25. Pearcy & Tibrewal 1984: lateral bending 10 deg at L1-L4 and 6 / 3 at L4-5 / L5-S1 (if one-sided: 39 over L1-S1, if total: 20); the abstract does not say which", ["Pearcy1984b", "Greene1994"]),
        E(25, 25, "AO", "AAOS 25; see left", ["Pearcy1984b", "Greene1994"])),
    "lumb_rot": ("Rotation right (+) / left (-)",
        "White & Panjabi lumbar axial rotation ~5 each side (book, not re-read); Pearcy 1984 about 2 per level (if one-sided: 10 over 5 levels)",
        E(-5, -5, "AO", "White & Panjabi ~5 (book not read). Pearcy & Tibrewal 1984: about 2 deg axial rotation at each lumbar level (one-sided vs total not stated; one-sided would give about 10 over L1-S1, i.e. the model may be too small)", ["Pearcy1984b"]),
        E(5, 5, "AO", "see left", ["Pearcy1984b"])),
}

ROM = {k: (v[2]["new"], v[3]["new"], v[0], v[1]) for k, v in _DEF.items()}
ROM_EVID = {k: dict(label=v[0], lo=v[2], hi=v[3]) for k, v in _DEF.items()}

# coupled motions: (what, data, sources, modelled in the Pose panel?)
COUPLED = [
    ("Ankle dorsiflexion depends on the KNEE angle (gastrocnemius)", "Baumbach 2014: non-weight-bearing dorsiflexion 4 +- 7 with the knee extended, 20 +- 9 with the knee flexed; no further gain beyond 20 deg knee flexion (a 15 deg step from 0 to 20 deg); weight-bearing 25 +- 6 -> 39 +- 7. The slider range is the flexed-knee value (29); with an extended knee the normal limit is 11 (+ 2 SD 18).", ["Baumbach2014"], False),
    ("Shoulder abduction needs scapulothoracic motion (scapulohumeral rhythm)", "Overall glenohumeral : scapulothoracic = 1.7 : 1 (McClure 2001, bone pins, n = 8; scapular upward rotation 50 +- 4.8, posterior tilt 30 +- 13, external rotation 24 +- 12.8 at full elevation). The model uses a fixed 2 : 1 (scapula + clavicle = 1/3 of the humeral elevation; literature share 37%) and upward rotation only; Ludewig 2009 (n = 12): sternoclavicular posterior rotation 31, acromioclavicular posterior tilt 19, glenohumeral plane of elevation differs up to 46 between flexion and abduction.", ["McClure2001", "Ludewig2009"], True),
    ("Shoulder rotation limit depends on arm elevation", "Vairo 2012 passive ER: 81.4 +- 12.0 with the arm at the side, 102.6 +- 10.3 at 90 abduction (+ 1 SD 93 vs 113); IR only measured at 90 abduction (60.7 +- 13.4). The slider uses the arm-at-side ER limit in every position.", ["Vairo2012"], False),
    ("Hip rotation vs hip flexion", "Kouyoumdjian 2012: total rotation 68.1 supine (hip 0), 77.1 prone (hip extended), 78.5 seated (hip flexed 90); authors report no significant difference between the three positions. Not modelled (no coupling needed on this evidence).", ["Kouyoumdjian2012"], False),
    ("Knee rotation vs knee flexion", "Mossberg 1983 (85 women): total tibial rotation 35 / 40 / 44 at 70 / 90 / 110 deg flexion, external rotation about twice internal; the Pose panel has no tibial rotation DOF.", ["Mossberg1983"], False),
    ("Forearm rotation vs elbow position", "Clinical forearm rotation is measured with the elbow flexed 90 (AAOS / Norkin protocol, from memory); no source on elbow-position dependence of the maximal range was retrieved. Morrey 1981: daily living needs 50 pronation + 50 supination at 30-130 elbow flexion.", ["Morrey1981"], False),
    ("Cervical rotation is coupled with extension and lateral bending; C1/C2 carries half", "Ishii 2004: C1-C2 36.2 +- 4.5 deg axial rotation to each side with 3.8 +- 3.0 lateral bending (opposite side) and 6.9 +- 3.0 extension; occiput-C1 1.7 deg rotation with 4.1 lateral bending and 13.3 +- 4.9 extension. The regional slider keeps C1 at 50% of the rotation (matches) but does not couple the extension / bending.", ["Ishii2004"], False),
    ("Lumbar axial rotation / lateral bending coupling", "Pearcy & Tibrewal 1984: upper lumbar axial rotation to the right goes with lateral bending to the left; at L5-S1 both go in the same direction; no simple mechanical coupling. Not modelled.", ["Pearcy1984b"], False),
    ("Thumb CMC axial rotation", "Cooney 1981: 17 deg of axial rotation (pronation-supination) accompanies thumb motion; the Pose panel has no CMC rotation DOF.", ["Cooney1981"], False),
]


# ------------------------------------------------------------------ helpers
def status_text(e):
    t = STATUS[e["st"]]
    if e["st"] in ("V_FT", "V_AB", "SEC") and e["n"] == 1:
        t += "; single source"
    elif e["st"] in ("V_FT", "V_AB", "SEC") and e["n"] > 1:
        t += "; %d sources read" % e["n"]
    return t


def ends():
    """[(key, 'lo'|'hi', end dict)] for every end of every range"""
    return [(k, w, v[w]) for k, v in ROM_EVID.items() for w in ("lo", "hi")]


def changed():
    return [(k, w, e) for k, w, e in ends() if e["old"] != e["new"]]


def rom_meta(keys):
    """compact evidence record embedded in the rig JSON (not read by the viewer): key -> {old: [lo, hi], soft: [lo, hi] (null = no SD read), st: [status codes], n: [sources read]}"""
    out = {}
    for k in keys:
        v = ROM_EVID[k]
        out[k] = dict(old=[v["lo"]["old"], v["hi"]["old"]], soft=[v["lo"]["soft"], v["hi"]["soft"]], st=[v["lo"]["st"], v["hi"]["st"]], n=[v["lo"]["n"], v["hi"]["n"]])
    return out


# spine: share of the REGIONAL total taken by each level joint (child vertebra), per DOF.  ASSUMPTION: equal shares, cervical rotation 50% at C1/C2 (Ishii 2004: 36.2 of ~70 per side = 51%), head (occiput/C1) gets part of the flexion.
def spine_weights(region, labels, dof):
    """labels: child vertebra labels top->bottom of the region (head joint 'OCC' included for cervical).  -> list of weights summing to 1"""
    n = len(labels)
    w = [1.0 / n] * n
    if region == "cervical":
        if dof == "rot" and "C1" in labels:                         # C1/C2 carries ~50% of the cervical rotation
            w = [0.5 if l == "C1" else (0.0 if l == "OCC" else 0.5 / (n - 2)) for l in labels]
        elif dof == "flex" and "OCC" in labels:                     # occiput/C1 ~ 20% of the flexion-extension arc
            w = [0.2 if l == "OCC" else 0.8 / (n - 1) for l in labels]
    return w
