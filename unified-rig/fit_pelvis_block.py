"""Fit the native Rajagopal pelvis/sacrum block to the FHS sacrum.
Experimental registration only: never overwrite v0.6. Preserve all native
pelvis-to-leg geometry and mechanisms. No uniform or segment scaling.
"""
import argparse,json,pathlib,zipfile,urllib.request,xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from scipy.spatial import cKDTree
from audit_hip_surfaces import mesh,distances,summary

def main():
    p=argparse.ArgumentParser();p.add_argument('inventory',type=pathlib.Path);p.add_argument('archive',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    f=json.loads((a.inventory/'fhs.json').read_text());l=json.loads((a.inventory/'legs.json').read_text());top=json.loads((a.inventory/'topology.json').read_text())
    fbody={x['name']:x['world'] for x in f['bodies']};lbody={x['name']:x['world'] for x in l['bodies']}
    fjoint={x['name']:x for x in f['joints']};ljoint={x['name']:x for x in l['joints']}
    S=fbody['sacrum'];sr=np.array(S['R']);sp=np.array(S['p']);P=fbody['pelvis'];pr=np.array(P['R']);pp=np.array(P['p'])
    nativeP=lbody['pelvis'];back=np.array(nativeP['R']).T@(np.array(ljoint['back']['parent_world']['p'])-np.array(nativeP['p']))
    disc=sr.T@(np.array(fjoint['L5_S1_IVDjnt']['parent_world']['p'])-sp)
    oldR=sr.T@pr;oldP=sr.T@(pp-sp)
    manifest=json.loads(pathlib.Path('opensim-lab/assets/fhs-original-frames.json').read_text())
    desc=manifest['anatomyMeshes']['sacrum'][0];prefix=manifest['archiveRelativeOsimPath'].split('/Male/')[0]+'/Geometry/'
    with zipfile.ZipFile(a.archive) as z: target=mesh(z.read(prefix+desc['file']),desc['scaleFactors'])
    url='https://raw.githubusercontent.com/opensim-org/opensim-models/master/Models/Rajagopal/Geometry/sacrum.vtp'
    donor=mesh(urllib.request.urlopen(url,timeout=40).read(),[1,1,1])
    def samples(m,n=5000):
        rng=np.random.default_rng(123)
        tri=m.triangles;area=m.area_faces;idx=rng.choice(len(tri),n,p=area/area.sum());u=rng.random((n,2));flip=u.sum(axis=1)>1;u[flip]=1-u[flip]
        q=tri[idx];return np.concatenate([m.vertices,q[:,0]+u[:,0,None]*(q[:,1]-q[:,0])+u[:,1,None]*(q[:,2]-q[:,0])])
    A=samples(donor);B=samples(target);bt=cKDTree(B)
    # Symmetry-preserving 2D sagittal rigid registration; z fixed at 0.
    def pose(x):return np.array([x[0],x[1],0.]),Rotation.from_rotvec([0,0,x[2]]).as_matrix()
    def err(x):
        t,R=pose(x);C=A@R.T+t
        return np.r_[bt.query(C)[0],cKDTree(C).query(B)[0]]
    def score(t,R):
        transformed=donor.copy();transformed.vertices=donor.vertices@R.T+t
        e1=distances(target,transformed.vertices);e2=distances(transformed,target.vertices)
        return {'donorToFHS':summary(e1),'fhsToDonor':summary(e2),'discPivotResidualMm':float(np.linalg.norm(t+R@back-disc)*1000),'translationM':t.tolist(),'rotation':R.tolist()}
    pivot=disc-oldR@back
    initial=[np.r_[oldP[:2],Rotation.from_matrix(oldR).as_rotvec()[2]],np.r_[pivot[:2],Rotation.from_matrix(oldR).as_rotvec()[2]],np.r_[(B.mean(0)-A.mean(0))[:2],0.]]
    fits=[least_squares(err,x,bounds=([-0.15,-0.15,-.6],[.15,.15,.6]),loss='soft_l1',f_scale=.005,max_nfev=100,diff_step=.0001) for x in initial]
    best=min(fits,key=lambda x:x.cost);t,R=pose(best.x)
    result={'status':'experimental rigid sacrum registration; anatomical contact unverified','baseline':score(oldP,oldR),'pivotOnly':score(pivot,oldR),'surfaceFit':score(t,R),'donorBackPivotLocalM':back.tolist(),'fhsDiscPivotLocalM':disc.tolist(),'pelvisSubtreeBodies':['pelvis']+[j['child'] for j in top['joints'] if j['source']=='legs'],'pelvisSubtreeJoints':['pelvis_sacrum']+[j['joint'] for j in top['joints'] if j['source']=='legs'],'scale':1,'meshSource':url,'fitRotationDeg':float(np.degrees(best.x[2])),'fitMultiStartCosts':[float(x.cost) for x in fits]}
    # Native XML patch: weld pelvis to FHS sacrum frame. Preserve all hip/leg
    # definitions byte-for-byte; FHS sacrum remains the virtual root body.
    src=a.inventory/'calibrated/candidate.osim';tree=ET.parse(src);m=tree.getroot().find('Model');w=m.find('./JointSet/objects/WeldJoint[@name="pelvis_sacrum"]')
    parent=next(e for e in w.findall('./frames/PhysicalOffsetFrame') if e.findtext('socket_parent')=='/bodyset/sacrum')
    child=next(e for e in w.findall('./frames/PhysicalOffsetFrame') if e.findtext('socket_parent')=='/bodyset/pelvis')
    assert np.linalg.norm(np.fromstring(child.findtext('translation'),sep=' '))<1e-9
    assert np.linalg.norm(np.fromstring(child.findtext('orientation'),sep=' '))<1e-9
    parent.find('translation').text=' '.join(map(str,t))
    parent.find('orientation').text=' '.join(map(str,Rotation.from_matrix(R).as_euler('XYZ')))
    tree.write(a.out/'candidate.osim',encoding='utf-8',xml_declaration=True)
    # Check the exact rigid subtree prediction against all existing native frames.
    poses=json.loads((a.inventory/'calibrated/sequences-calibrated.json').read_text());bi={n:i for i,n in enumerate(poses['bodyNames'])};ji={n:i for i,n in enumerate(poses['jointNames'])}
    ix=[bi[n] for n in result['pelvisSubtreeBodies']];jx=[ji[n] for n in result['pelvisSubtreeJoints']]
    worst=0.;framecount=0;mirror=0.
    for seq in poses['sequences']:
        for frame in seq['frames']:
            B0=np.array(frame['bodies']);RR=np.array(frame['rotations']);J0=np.array(frame['points'])
            Q=RR[bi['sacrum']]@R@RR[bi['pelvis']].T;newP=B0[bi['sacrum']]+RR[bi['sacrum']]@t;shift=newP-Q@B0[bi['pelvis']]
            X=B0[ix]@Q.T+shift
            worst=max(worst,float(np.max(abs(np.linalg.norm(X[:,None]-X[None,:],axis=-1)-np.linalg.norm(B0[ix,None]-B0[None,ix],axis=-1)))))
            if not framecount:
                for side in ['r','l']:
                    h=ljoint['hip_'+side]['parent_world']['p'];local=np.array(nativeP['R']).T@(np.array(h)-np.array(nativeP['p']))
                    hip=Q@J0[ji['hip_'+side]]+shift
                    assert np.linalg.norm(hip-(newP+RR[bi['sacrum']]@R@local))<2e-6
            framecount+=1
    assert worst<1e-10
    result['rigidReplayQA']={'frames':framecount,'maxInternalDistanceDriftM':worst,'nativeHipCentersPreserved':True}
    result['anatomicallyValidated']=False
    (a.out/'pelvis-block.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    print('PELVIS_BLOCK_QA',json.dumps(result))
if __name__=='__main__':main()
