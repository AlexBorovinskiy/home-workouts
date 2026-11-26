"""Experimental head/neck proportion correction using the FHS donor scale.
All nine MASI bodies and all their local joint translations scale together.
T1 interface parent remains fixed. No alteration to angular mechanisms.
"""
import argparse, pathlib, json, zipfile, urllib.request, xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import cKDTree
from audit_hip_surfaces import mesh
import opensim as osim

def pose(model):
    s=model.initSystem();model.assemble(s);model.realizePosition(s);return s

def tr(frame,s):
    t=frame.getTransformInGround(s)
    return np.array([t.p()[i] for i in range(3)]),np.array([[t.R().get(i,j) for j in range(3)] for i in range(3)])

def main():
    p=argparse.ArgumentParser();p.add_argument('model',type=pathlib.Path);p.add_argument('archive',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    fhs=json.loads(pathlib.Path('opensim-lab/assets/fhs-original-frames.json').read_text())
    masi=json.loads(pathlib.Path('opensim-lab/assets/masi-neck-native.json').read_text())
    top=json.loads(pathlib.Path('unified-rig/topology.json').read_text())
    neck={j['child'] for j in top['joints'] if j['source']=='masi'}
    assert neck=={f'cerv{i}' for i in range(1,8)}|{'skull','jaw'}
    defs={d['file']:d for d in fhs['anatomyMeshes']['head_neck']}
    scales={tuple(d['scaleFactors']) for d in defs.values()};assert len(scales)==1
    scale=next(iter(scales))[0];assert all(abs(x-scale)<1e-10 for x in next(iter(scales)))
    assert .7<scale<1.2
    prefix=fhs['archiveRelativeOsimPath'].split('/Male/')[0]+'/Geometry/'
    raw={};fhsraw={};comparisons={}
    base='https://raw.githubusercontent.com/MyoHub/myoconverter/main/models/osim/Neck6D/Geometry/'
    with zipfile.ZipFile(a.archive) as z:
        for b in sorted(neck):
            filename=masi['bodyFrames'][b]['file'] if b!='jaw' else 'jaw.vtp'
            src=mesh(urllib.request.urlopen(base+filename,timeout=35).read(),[1,1,1]).vertices
            dst=mesh(z.read(prefix+filename),[scale]*3).vertices
            raw[b]=src;fhsraw[b]=dst
            # Compare corresponding vertex arrays only when a similarity fit
            # actually establishes correspondence; never assume from filenames.
            if len(src)!=len(dst):
                comparisons[b]={'sourceVertices':len(src),'fhsVertices':len(dst),'equivalent':False};continue
            X=src-src.mean(0);Y=dst-dst.mean(0)
            U,S,Vt=np.linalg.svd(X.T@Y);Q=U@Vt
            if np.linalg.det(Q)<0:U[:,-1]*=-1;Q=U@Vt
            err=np.linalg.norm(scale*X@Q-Y,axis=1)
            comparisons[b]={'sourceVertices':len(src),'fhsVertices':len(dst),'maxCorrespondingResidualMm':float(err.max()*1000),'rmsMm':float(np.sqrt(np.mean(err**2))*1000),'equivalent':bool(err.max()<.001)}
    assert comparisons['skull']['equivalent'] and comparisons['jaw']['equivalent'],comparisons
    assert sum(x['equivalent'] for x in comparisons.values())>=7,comparisons
    tree=ET.parse(a.model);m=tree.getroot().find('Model');changed=[]
    for j in m.findall('./JointSet/objects/*'):
        if j.get('name') not in {j['joint'] for j in top['joints'] if j['source']=='masi'}:continue
        for f in j.findall('./frames/PhysicalOffsetFrame'):
            if f.findtext('socket_parent').split('/')[-1] in neck:
                t=f.find('translation');old=np.fromstring(t.text,sep=' ');assert len(old)==3
                t.text=' '.join(f'{x:.16g}' for x in old*scale);changed.append(j.get('name')+'/'+f.get('name'))
        for ax in j.findall('./SpatialTransform/TransformAxis'):
            if ax.get('name').startswith('translation'):
                val=ax.find('./Constant/value');assert val is not None and float(val.text)==0,ET.tostring(ax)
    out=a.out/'candidate.osim';tree.write(out,encoding='utf-8',xml_declaration=True)
    old=osim.Model(str(a.model));new=osim.Model(str(out));s=pose(old);t=pose(new)
    pivot=tr(old.getJointSet().get('auxt1jnt').getParentFrame(),s)[0]
    assert np.linalg.norm(tr(new.getJointSet().get('auxt1jnt').getParentFrame(),t)[0]-pivot)<1e-9
    assert old.getJointSet().getSize()==new.getJointSet().getSize()
    for i in range(old.getBodySet().getSize()):
        b=old.getBodySet().get(i);n=b.getName();x,R=tr(b,s);y,S=tr(new.getBodySet().get(n),t)
        expected=pivot+scale*(x-pivot) if n in neck else x
        assert np.linalg.norm(y-expected)<2e-6,(n,y,expected)
        assert np.max(abs(R-S))<1e-6
    def world(model,s,b,sc):
        x,R=tr(model.getBodySet().get(b),s);return raw[b]*sc@R.T+x
    def metrics(model,s,sc,includejaw):
        skull=world(model,s,'skull',sc);head=np.r_[skull,world(model,s,'jaw',sc)] if includejaw else skull
        joint=tr(model.getJointSet().get('aux1jnt').getChildFrame(),s)[0]
        return {'headHeightMm':float(np.ptp(head[:,1])*1000),'headWidthMm':float(np.ptp(head[:,2])*1000),'headDepthMm':float(np.ptp(head[:,0])*1000),'baseToOccipitalJointMm':float(np.linalg.norm(joint-pivot)*1000),'baseToHeadTopMm':float((head[:,1].max()-pivot[1])*1000),'jawRendered':includejaw}
    result={'status':'FHS donor-matched geometric scale experiment; not anthropometric certification','scale':scale,'sourceMeshComparisons':comparisons,'beforeDisplayed':metrics(old,s,1,False),'beforeWithJaw':metrics(old,s,1,True),'afterWithJaw':metrics(new,t,scale,True),'changedFrames':changed,'anchorM':pivot.tolist(),'neckBodies':sorted(neck),'limitations':['FHS donor scale is not a personalized head-size measurement','Jaw remains welded in the original MASI model','Dynamic loads and contact unvalidated']}
    # Sample actual neck motions through the native coupled controls.
    cs=new.getCoordinateSet();bs=new.getBodySet();js=new.getJointSet()
    names=[js.get(i).getName() for i in range(js.getSize())];bodies=[bs.get(i).getName() for i in range(bs.getSize())]
    def snap(state):
        return {'points':[tr(js.get(i).getChildFrame(),state)[0].round(6).tolist() for i in range(js.getSize())],'bodies':[tr(bs.get(i),state)[0].round(6).tolist() for i in range(bs.getSize())],'rotations':[tr(bs.get(i),state)[1].round(7).tolist() for i in range(bs.getSize())]}
    plans=[('neck_flex','Сгибание шеи',{'pitch1':-12,'pitch2':-25}),('neck_extend','Разгибание шеи',{'pitch1':18,'pitch2':30}),('neck_turn','Поворот головы',{'yaw1':30,'yaw2':20}),('neck_side','Наклон головы',{'roll1':4,'roll2':20})]
    sequences=[]
    for ident,label,targets in plans:
        qs={n:cs.get(n) for n in targets};start={n:float(q.getValue(t)) for n,q in qs.items()};goal={n:float(np.clip(np.radians(v),qs[n].getRangeMin(),qs[n].getRangeMax())) for n,v in targets.items()}
        frames=[]
        for i in range(31):
            u=(1-np.cos(np.pi*i/30))/2;state=osim.State(t)
            for n,q in qs.items():q.setValue(state,start[n]+(goal[n]-start[n])*u,False)
            new.assemble(state);new.realizePosition(state)
            err=max(abs(q.getValue(state)-(start[n]+(goal[n]-start[n])*u)) for n,q in qs.items());assert err<1e-4
            f=snap(state);f.update(u=float(u),errorRad=float(err));frames.append(f)
        change=np.linalg.norm(np.array(frames[0]['rotations'][bodies.index('skull')])-np.array(frames[-1]['rotations'][bodies.index('skull')]))
        assert change>.05,(ident,change)
        sequences.append({'id':ident,'label':label,'targets':{n:{'start':start[n],'end':goal[n]} for n in qs},'frames':frames})
    result['neckMotionQA']={'sequences':len(sequences),'frames':sum(len(x['frames']) for x in sequences)}
    (a.out/'neck-motion.json').write_text(json.dumps({'jointNames':names,'bodyNames':bodies,'sequences':sequences},separators=(',',':'),ensure_ascii=False))
    (a.out/'head-neck-report.json').write_text(json.dumps(result,indent=2));print('HEAD_NECK_QA',json.dumps(result))
if __name__=='__main__':main()
