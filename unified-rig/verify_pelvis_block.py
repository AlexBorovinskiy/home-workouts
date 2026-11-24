"""Independent OpenSim replay against rigid lower-body subtree prediction."""
import json,sys,pathlib,numpy as np
old,new,report=map(pathlib.Path,sys.argv[1:])
a,b,r=[json.loads(x.read_text()) for x in [old,new,report]]
assert a['jointNames']==b['jointNames'] and a['bodyNames']==b['bodyNames']
bi={n:i for i,n in enumerate(a['bodyNames'])};ji={n:i for i,n in enumerate(a['jointNames'])}
ix=[bi[n] for n in r['pelvisSubtreeBodies']];jx=[ji[n] for n in r['pelvisSubtreeJoints']]
R=np.array(r['surfaceFit']['rotation']);t=np.array(r['surfaceFit']['translationM'])
worst=0;angle=0;count=0
for x in a['sequences']:
    y=next(s for s in b['sequences'] if s['id']==x['id'])
    assert len(x['frames'])==len(y['frames'])
    for f,g in zip(x['frames'],y['frames']):
        B=np.array(f['bodies']);J=np.array(f['points']);RR=np.array(f['rotations'])
        q=RR[bi['sacrum']]@R@RR[bi['pelvis']].T
        shift=B[bi['sacrum']]+RR[bi['sacrum']]@t-q@B[bi['pelvis']]
        B[ix]=B[ix]@q.T+shift;J[jx]=J[jx]@q.T+shift;RR[ix]=q@RR[ix]
        worst=max(worst,float(np.max(np.linalg.norm(B-np.array(g['bodies']),axis=-1))),float(np.max(np.linalg.norm(J-np.array(g['points']),axis=-1))))
        angle=max(angle,float(np.max(abs(RR-np.array(g['rotations'])))))
        count+=1
assert worst<1e-5 and angle<1e-5,(worst,angle)
r['nativeReplayQA']={'frames':count,'maxPositionResidualM':worst,'maxRotationMatrixResidual':angle,'allOriginalMotionsPreserved':True}
report.write_text(json.dumps(r,indent=2))
print('NATIVE_PELVIS_REPLAY',r['nativeReplayQA'])
