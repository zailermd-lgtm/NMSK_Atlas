"""Colour classes for the VH FEMALE cryosections (RGB uint8, blue gelatin background). Same classes as the male's
cryo_classes.py (1 tissue, 2 fat, 3 muscle, 4 pale connective, 5 white cortex) with thresholds retuned on her
photographs (2026-09-12): her frozen muscle is darker and browner than his (median value 97 vs the male rule's
60-170 window; r-g median 41 but a long tail under 15), so tissue starts at value 30 (not 60) and muscle needs
only r > g+10; measured: 20 % of her in-body pixels at thorax level were left unclassified by the male's rule,
median value 49, r-g 20, r-b 27 -- muscle and organ, not gelatin (gelatin has r-b <= 0). Fat / pale / white unchanged."""
import numpy as np
def classify(im):
    im=im.astype(np.float32); r,g,b=im[...,0],im[...,1],im[...,2]; v=im.max(-1); mn=im.min(-1); sat=(v-mn)/(v+1e-3)
    tissue=(r>b+12)&(v>30)
    white=tissue&(v>200)&(sat<0.30)
    fat=tissue&(v>140)&(sat>=0.30)&(g>0.72*r)&~white
    pale=tissue&(v>150)&(sat<0.30)&~white
    muscle=tissue&(r>g+10)&(v<170)&~fat&~pale
    out=np.zeros(im.shape[:2],np.uint8); out[tissue]=1; out[fat]=2; out[muscle]=3; out[pale]=4; out[white]=5
    return out
PAL=np.array([[0,0,0],[90,90,90],[240,220,120],[190,50,40],[200,200,255],[255,255,255]],np.uint8)
