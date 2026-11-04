import json,sys
f=sys.argv[1]; side=sys.argv[2] if len(sys.argv)>2 else 'l'; jn=sys.argv[3] if len(sys.argv)>3 else 'elbow'
r=json.load(open(f))
for j in r['junctions']:
    if j['side']!=side or j['name']!=jn: continue
    print(r['model'],j['name'],j['side'],'centre',j['centre_mm'])
    print(' bones',j['bones']); print(' angles',{k:v for k,v in (j.get('elbow_angles') or {}).items() if 'axis' not in k}); print(' skin',j['skin'])
    if 'chains' in j: print(' chains',[(c['parent'][-18:],c['child'][-18:],c.get('end_to_end_mm'),c.get('min_surface_vertex_mm')) for c in j['chains']])
    for s in j['soft']:
        if 'error' in s: print('ERR',s); continue
        att={k:(v.get('min_expected_bone_mm',v['min_any_bone_mm'])) for k,v in s.get('attach_ends_in_zone',{}).items()}
        print(f"  {s['id'][:34]:34s} {str(s.get('cls'))[:6]:6s}{str(s.get('src'))[:22]:22s} isl={s['islands']:2d} igap={s['max_island_gap_mm']:5.1f} open={s['open_edge_frac']:.3f} flat={[ (x['dist_to_joint_mm'],x['extent_mm']) for x in s['flat_cut_loops']]} caps={[(x['axis'],x['plane_mm'],x['area_mm2'],x['dist_to_joint_mm']) for x in s.get('flat_caps',[])]} axgap={s['max_axial_gap_mm']:.1f} X={int(s['crosses_joint'])} out%={s['outside_skin_pct']} inb%={s['inside_bone_pct']}/{s['inside_bone_max_mm']} att={att}")
    for s in j['tubes']:
        if 'error' in s: print('ERR',s); continue
        if not s['near_zone']: continue
        print(f"  T {s['id'][:34]:34s} isl={s['islands']} igap={s['max_island_gap_mm']} jump={s.get('max_level_jump_mm')} turn={s.get('max_turn_deg')} out%={s['outside_skin_pct']} inb%={s['inside_bone_pct']}")
