import numpy as np, sys
sys.path.insert(0,"/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo"); from cryo_classes import classify
vol=np.load("cryo_1mm.npy",mmap_mode="r"); Z=vol.shape[0]
out=np.lib.format.open_memmap("cryo_1mm_classes.npy",mode="w+",dtype=np.uint8,shape=vol.shape[:3])
for z in range(Z):
    out[z]=classify(np.asarray(vol[z]))
    if z%200==0: print(z,flush=True)
out.flush(); print("CLASS_DONE",flush=True)
