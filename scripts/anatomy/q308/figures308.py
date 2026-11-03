#!/usr/bin/env python3
"""Q308, the owner's SECOND test: against the FIGURES in the papers, which is not the same test as against the
papers' text.

The brief's own rule is followed exactly: a figure that cannot be scaled is UNUSABLE and is not guessed at.

What was attempted, and what came of it, is recorded here as fact rather than as an impression:

  1. The PubMed MCP full-text channel returns body text with the figure CAPTIONS STRIPPED -- Kosy 2016 came back
     with the literal token "(Fig.)" where each caption and its reference should be. So the captions, which are
     where a scale bar or a stated magnification would be declared, do not arrive through that channel.
  2. Fetching the figures themselves from PubMed Central was attempted and FAILED at the network layer:
     `pmc.ncbi.nlm.nih.gov` does not resolve from this session, because it is outside the session's allowed
     network domains. So neither the images nor their captions are obtainable here at all.
  3. Therefore NO figure of the eight sources was scaled, and no number in this round is taken from a figure.
     Every literature number used is from the text (abstract or, for Kosy 2016, the full body text), and the
     round says so on every card.

This is not the figure test passing. It is the figure test being BLOCKED, reported as blocked.

What WAS possible instead, and what it gave, is the third test (models308.py): HRA / CCF publishes the
anterolateral ligament of the knee as a real closed mesh with its triangle count and its bounding size in
millimetres, on the same two donors as this project's Imaging pages -- a measurable geometric comparison from a
model rather than from a figure.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/derived/Q308_figure_comparison.json"

SOURCES = {
 "khadanovich2023": {"pmid": "38128746", "open_access": False, "pmc": None,
                     "figures_in_paper": "heatmaps of the LACN/SBRN cross-sectional relationship to the cephalic "
                                         "vein, plus dissection photographs (named in the abstract)",
                     "obtainable_here": False,
                     "why_not": "not open access; no PMC id. Only the abstract is reachable.",
                     "scalable": None, "used": False},
 "qawasmi2024": {"pmid": "38934998", "open_access": False, "pmc": None,
                 "figures_in_paper": "cubital-fossa dissection photographs with the measured landmarks",
                 "obtainable_here": False, "why_not": "not open access; no PMC id.",
                 "scalable": None, "used": False},
 "vonschroeder2001": {"pmid": "11210947", "open_access": False, "pmc": None,
                      "figures_in_paper": "scapular morphometry diagrams",
                      "obtainable_here": False, "why_not": "not open access; no PMC id.",
                      "scalable": None, "used": False},
 "hu2009": {"pmid": "20073313", "open_access": False, "pmc": None,
            "figures_in_paper": "CAL morphology and the conjoined-tendon transfer",
            "obtainable_here": False,
            "why_not": "not open access, Chinese-language journal with an English abstract, and no DOI assigned.",
            "scalable": None, "used": False},
 "nicholson1996": {"pmid": "8919436", "open_access": False, "pmc": None,
                   "figures_in_paper": "acromial morphology types I-III and outlet radiographs",
                   "obtainable_here": False, "why_not": "not open access.",
                   "scalable": None, "used": False},
 "raja2026": {"pmid": "42502531", "open_access": True, "pmc": "PMC13400699",
              "figures_in_paper": "dissection photographs of the bilateral and the unilateral psoas minor",
              "obtainable_here": False,
              "why_not": "open access, but `pmc.ncbi.nlm.nih.gov` does not resolve from this session -- the host "
                         "is outside the session's allowed network domains. The full-text channel that does "
                         "work strips captions.",
              "scalable": None, "used": False},
 "kosy2016": {"pmid": "26861760", "open_access": True, "pmc": "PMC5071230",
              "figures_in_paper": "three figures: the isolated ALL with the LCL, GT and fibular head marked; the "
                                  "oblique fibre bundles under internal rotation; the meniscal attachment",
              "obtainable_here": False,
              "why_not": "the full text WAS read in full through the MCP channel and is the source of the "
                         "lateral-femoral-epicondyle rule and the 37-59 mm published range -- but every caption "
                         "came back as the bare token '(Fig.)', and PMC itself does not resolve from this "
                         "session, so the images could not be inspected.",
              "scalable": None, "used": False,
              "note": "this paper's TEXT changed the construction (the femoral origin rule); its FIGURES did not."},
 "rustagi2019": {"pmid": "30905987", "open_access": True, "pmc": "PMC6394189",
                 "figures_in_paper": "ALL dissection photographs with LCL and Gerdy's tubercle",
                 "obtainable_here": False,
                 "why_not": "open access, but PMC does not resolve from this session.",
                 "scalable": None, "used": False},
}

BLOCKED_HOST = "pmc.ncbi.nlm.nih.gov"


def main():
    out = {
      "doc": __doc__.strip().splitlines()[0],
      "rule_followed": "a figure that cannot be scaled is unusable and is not guessed at",
      "blocked_host": BLOCKED_HOST,
      "how_to_unblock": ("the environment's network policy denied the host. It is changed in the environment's "
                         "settings (the cloud environment menu in the session's title bar, then Edit): either a "
                         "broader access level, or " + BLOCKED_HOST + " added under Allowed domains with "
                         "'Allow package managers' left ticked. "
                         "https://code.claude.com/docs/en/cloud-environments#network-access"),
      "sources": SOURCES,
      "n_sources": len(SOURCES),
      "n_figures_obtained": 0,
      "n_figures_scaled": 0,
      "n_numbers_taken_from_a_figure": 0,
      "verdict": ("The figure test could NOT be carried out in this session. Three of the eight sources are not "
                  "open access at all; the other five are, but PubMed Central does not resolve here and the "
                  "full-text channel that does work strips figure captions -- which is exactly where a scale "
                  "bar or a stated magnification would be declared. No figure was scaled and NO number in this "
                  "round comes from a figure. The nearest available substitute was the third test, where HRA / "
                  "CCF publishes the anterolateral ligament of the knee as a real closed mesh with its "
                  "triangle count and millimetre bounding size on the same two donors as the Imaging pages."),
      "what_would_close_it": ("allow " + BLOCKED_HOST + " and re-run; the five open-access sources' figures "
                              "could then be inspected for a scale bar, and the two ALL papers' dissection "
                              "photographs compared against the built ligament's femoral and tibial "
                              "attachment positions."),
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(out["verdict"])
    print("\nwritten", OUT)


if __name__ == "__main__":
    main()
