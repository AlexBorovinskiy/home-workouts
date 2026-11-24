"""Restore neutral leg orientation via native hip coordinates, not mesh offsets.
Keep the v0.7 pelvis/sacrum weld and all native joint definitions. The target
is the v0.6 leg posture, not an independently validated physiological stance.
"""
import argparse,json,pathlib,xml.etree.ElementTree as ET
import numpy as np
import opensim as osim
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

def main():
    p=argparse.ArgumentParser();p.add_argument('model',type=pathlib.Path);p.add_argument('reference',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    reference=json.loads(a.reference.read_text());f=reference['sequences'][0]['frames'][0]
    ref={n:np.array(f['rotations'][i]) for i,n in enumerate(reference['bodyNames'])}
    m=osim.Model(str(a.model));initial=m.initSystem();m.assemble(initial);m.realizePosition(initial)
    cs=m.getCoordinateSet();bs=m.getBodySet()
    def tr(s,n):
        t=bs.get(n).getTransformInGround(s);return np.array([t.p()[i] for i in range(3)]),np.array([[t.R().get(i,j) for j in range(3)] for i in range(3)])
    def angle(s,side):
        h=tr(s,'femur_'+side)[0];ankle=tr(s,'talus_'+side)[0];d=h-ankle
        return float(np.degrees(np.arctan2(d[0],d[1])))
    before={side:angle(initial,side) for side in ('r','l')}
    # Preserve neutral knee and ankle articulation if the hip alone suffices.
    names=[f'hip_{q}_{side}' for side in ('r','l') for q in ('flexion','adduction','rotation')]
    coords=[cs.get(n) for n in names];x0=np.array([q.getValue(initial) for q in coords])
    assert all(not q.getLocked(initial) for q in coords)
    def state(x):
        s=osim.State(initial)
        for q,v in zip(coords,x):q.setValue(s,float(v),False)
        m.assemble(s);m.realizePosition(s)
        assert max(abs(q.getValue(s)-v) for q,v in zip(coords,x))<1e-6
        return s
    def residual(x):
        s=state(x)
        return np.concatenate([Rotation.from_matrix(ref[n].T@tr(s,n)[1]).as_rotvec() for n in ('femur_r','femur_l','calcn_r','calcn_l')])
    # The two exported models differ by a pure sagittal rotation at the weld.
    # Start from that measured rotation, not a near-zero finite difference
    # (OpenSim assembly can suppress infinitesimal perturbations).
    guess=x0.copy()
    for i,side in enumerate(('r','l')):
        delta=Rotation.from_matrix(ref['femur_'+side]@tr(initial,'femur_'+side)[1].T).as_rotvec()
        guess[3*i]+=delta[2]
    def jac(x):
        h=1e-4
        return np.column_stack([(residual(x+np.eye(len(x))[i]*h)-residual(x-np.eye(len(x))[i]*h))/(2*h) for i in range(len(x))])
    print('STANCE_INITIAL_RESIDUAL',residual(guess).tolist(),flush=True)
    fit=least_squares(residual,guess,jac=jac,bounds=([q.getRangeMin() for q in coords],[q.getRangeMax() for q in coords]),xtol=1e-10,ftol=1e-10,gtol=1e-10,max_nfev=60)
    s=state(fit.x);assert np.max(abs(residual(fit.x)))<1e-5,(fit.x.tolist(),residual(fit.x).tolist(),fit.message)
    tree=ET.parse(a.model);model=tree.getroot().find('Model')
    for n,v in zip(names,fit.x):
        q=next(q for q in model.findall('./JointSet/objects/*/coordinates/Coordinate') if q.get('name')==n)
        q.find('default_value').text=f'{v:.16g}'
    out=a.out/'candidate.osim';tree.write(out,encoding='utf-8',xml_declaration=True)
    for n in ['pelvis','sacrum','lumbar5']:
        assert np.linalg.norm(tr(s,n)[0]-tr(initial,n)[0])<1e-9
        assert np.max(abs(tr(s,n)[1]-tr(initial,n)[1]))<1e-9
    hips=[tr(s,'femur_'+side)[0] for side in ('r','l')]
    oldhips=[tr(initial,'femur_'+side)[0] for side in ('r','l')]
    assert max(np.linalg.norm(a-b) for a,b in zip(hips,oldhips))<1e-9
    after={side:angle(s,side) for side in ('r','l')}
    assert max(abs(v) for v in after.values())<2
    report={'status':'neutral kinematic correction against v0.6, not anatomical standing validation','beforeSagittalDeg':before,'afterSagittalDeg':after,'hipDefaultDeg':{n:float(np.degrees(v)) for n,v in zip(names,fit.x)},'hipCenterSeparationMm':float(np.linalg.norm(hips[0]-hips[1])*1000),'maxOrientationResidualRad':float(np.max(abs(residual(fit.x)))),'pelvisSacrumLumbarUnchanged':True,'limitations':['No endplate contact measurement','No ground contact or balance solve','No anthropometric scaling']}
    (a.out/'stance-report.json').write_text(json.dumps(report,indent=2))
    print('STANCE_QA',json.dumps(report))
if __name__=='__main__':main()
