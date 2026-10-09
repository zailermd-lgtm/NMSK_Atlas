"""Colour classes for the VH male cryosections (RGB uint8, blue gelatin background).
tissue: not gelatin/black. bone: white cortex (value>200, saturation<0.30), holes filled per slice.
fat: pale cream/yellow. muscle: red-brown. pale: whitish connective tissue (tendon, fascia, nerve, cartilage)."""
import numpy as np
from scipy import ndimage as ndi
def classify(im):
    im=im.astype(np.float32); r,g,b=im[...,0],im[...,1],im[...,2]; v=im.max(-1); mn=im.min(-1); sat=(v-mn)/(v+1e-3)
    tissue=(r>b+15)&(v>60)
    white=tissue&(v>200)&(sat<0.30)
    fat=tissue&(v>140)&(sat>=0.30)&(g>0.72*r)&~white
    muscle=tissue&(r>g+15)&(v<170)&~fat
    pale=tissue&(v>150)&(sat<0.30)&~white
    out=np.zeros(im.shape[:2],np.uint8); out[tissue]=1; out[fat]=2; out[muscle]=3; out[pale]=4; out[white]=5
    return out
PAL=np.array([[0,0,0],[90,90,90],[240,220,120],[190,50,40],[200,200,255],[255,255,255]],np.uint8)
