"""Independent numerical QA of exported native poses. No anatomical certification."""
import argparse,json,pathlib
import numpy as np

def angle(a,b):
    return float(np.degrees(np.arccos(np.clip((np.trace(a.T@b)-1)/2,-1,1))))
def audit(path, fhs_path):
    d=json.loads(path.read_text());fhs=json.loads(fhs_path.read_text())
    bi={n:i for i,n in enumerate(d['bodyNames'])};ji={n:i for i,n in enumerate(d['jointNames'])}
    base=np.array(d['sequences'][0]['frames'][0]['points']);out={}
    references={}
    for side,prefix in [('R','RA'),('L','LA')]:
        anchor=next(j for j in fhs['joints'] if j['child']=='clavicle_'+side)['parent_world']['p']
        references[side]=float(np.linalg.norm(base[ji[prefix+'_sternoclavicular']]-anchor)*1000)
    for s in d['sequences']:
        P=np.array([f['points'] for f in s['frames']]);B=np.array([f['bodies'] for f in s['frames']]);R=np.array([f['rotations'] for f in s['frames']])
        assert P.shape[1:]==(len(ji),3) and B.shape[1:]==(len(bi),3)
        assert np.isfinite(P).all() and np.isfinite(B).all() and np.isfinite(R).all()
        orth=float(np.max(abs(R@R.swapaxes(-1,-2)-np.eye(3))))
        det=float(np.max(abs(np.linalg.det(R)-1)))
        err=max(f['errorRad'] for f in s['frames'])
        assert orth<1e-5 and det<1e-5 and err<1e-4
        q={'frames':len(P),'coordinateResidualRad':err,'rotationOrthogonalityError':orth,'rotationDeterminantError':det,'maxNeutralDifferenceMm':float(np.max(np.linalg.norm(P[0]-base,axis=1))*1000)}
        assert q['maxNeutralDifferenceMm']<.1
        for side in ['RA','LA']:
            elbow=ji[side+'1H_'+side+'2U'];shoulder=ji[side+'_shoulder2']
            lengths=np.linalg.norm(P[:,elbow]-P[:,shoulder],axis=1)
            q[side+'_humerusLengthMm']=float(lengths[0]*1000)
            q[side+'_humerusLengthDriftMm']=float(np.ptp(lengths)*1000)
            assert q[side+'_humerusLengthDriftMm']<.1
        if s['id']=='pronation':
            for side in ['RA','LA']:
                u,v=bi[side+'2U'],bi[side+'2R'];rel=R[:,u].swapaxes(-1,-2)@R[:,v]
                q[side+'_radiusRelativeRotationDeg']=angle(rel[0],rel[-1])
                assert q[side+'_radiusRelativeRotationDeg']>45
        if s['id']=='arms':
            for side in ['RA','LA']:
                for suffix in ['_clavicle','_scapula','1H']:
                    k=bi[side+suffix];q[side+suffix+'_totalRotationDeg']=angle(R[0,k],R[-1,k])
                assert q[side+'_scapula_totalRotationDeg']>5
        out[s['id']]=q
    return {'status':'numerical pose audit only','sourceSternoclavicularResidualMm':references,'sequences':out,'totalFrames':sum(x['frames'] for x in out.values()),'unvalidated':['anatomical joint surface contact','scapulothoracic contact and anatomically defined rotation components','hip geometry fit','neck movement','spinal movement','measured exercise trajectories','stature','balance and loads']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('sequences',type=pathlib.Path);p.add_argument('fhs',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    result=audit(a.sequences,a.fhs);a.out.write_text(json.dumps(result,indent=2));print('INDEPENDENT_POSE_QA',json.dumps(result))
