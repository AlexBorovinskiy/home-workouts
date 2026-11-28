"""Independent numerical QA of exported native poses. No anatomical certification."""
import argparse,json,pathlib
import numpy as np

def angle(a,b):
    relative = a.T @ b
    skew = relative - relative.T
    sine = np.linalg.norm([skew[2, 1], skew[0, 2], skew[1, 0]]) / 2
    cosine = (np.trace(relative) - 1) / 2
    return float(np.degrees(np.arctan2(sine, cosine)))

def sternoclavicular_anchors(reference):
    if 'joints' in reference:
        points = {j['child']: j['parent_world']['p'] for j in reference['joints']}
        return {side: points['clavicle_'+side] for side in ('R', 'L')}
    if 'interfaces' in reference:
        points = {j['joint']: j['targetP'] for j in reference['interfaces']}
        return {side: points[side+'A_sternoclavicular'] for side in ('R', 'L')}
    raise ValueError('Expected a native FHS joint inventory or the interface calibration report')

def arm_rotation_diagnostics(rotations, body_indices, side):
    # AAH body names: humerus 1H, ulna 2U, radius 2R, trapezium 3T,
    # first metacarpal 4M1, proximal thumb phalanx 5P1 and distal 6D1.
    links = {
        'humeroulnar': ('1H', '2U'),
        'radioulnar': ('2U', '2R'),
        'thumbCmc': ('3T', '4M1'),
        'thumbMcp': ('4M1', '5P1'),
        'thumbIp': ('5P1', '6D1'),
    }
    result = {}
    for joint, (parent, child) in links.items():
        parent_rotation = rotations[:, body_indices[side+parent]]
        child_rotation = rotations[:, body_indices[side+child]]
        relative = parent_rotation.swapaxes(-1, -2) @ child_rotation
        changes = [angle(relative[0], rotation) for rotation in relative]
        result[joint] = {'endChangeDeg': changes[-1], 'maxChangeDeg': max(changes)}
    return result

def audit(path, fhs_path):
    d=json.loads(path.read_text());fhs=json.loads(fhs_path.read_text())
    bi={n:i for i,n in enumerate(d['bodyNames'])};ji={n:i for i,n in enumerate(d['jointNames'])}
    base=np.array(d['sequences'][0]['frames'][0]['points']);out={}
    references={}
    anchors=sternoclavicular_anchors(fhs)
    for side,prefix in [('R','RA'),('L','LA')]:
        anchor=anchors[side]
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
        if s['id'] in ('pronation', 'curl', 'grip'):
            q['relativeArmRotations'] = {}
        for side in ['RA','LA']:
            elbow=ji[side+'1H_'+side+'2U'];shoulder=ji[side+'_shoulder2']
            lengths=np.linalg.norm(P[:,elbow]-P[:,shoulder],axis=1)
            q[side+'_humerusLengthMm']=float(lengths[0]*1000)
            q[side+'_humerusLengthDriftMm']=float(np.ptp(lengths)*1000)
            assert q[side+'_humerusLengthDriftMm']<.1
            if 'relativeArmRotations' in q:
                q['relativeArmRotations'][side] = arm_rotation_diagnostics(R, bi, side)
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
    p=argparse.ArgumentParser();p.add_argument('sequences',type=pathlib.Path);p.add_argument('fhs',type=pathlib.Path,help='Native FHS joint inventory or interface calibration report');p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    result=audit(a.sequences,a.fhs);a.out.write_text(json.dumps(result,indent=2));print('INDEPENDENT_POSE_QA',json.dumps(result))
