"""Sample independent coordinates on the assembled model, one at a time.
All displayed poses are actually assembled by OpenSim. No browser FK approximation.
"""
import argparse,json,pathlib,math,xml.etree.ElementTree as ET
import opensim as osim
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('model',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    model=osim.Model(str(a.model));initial=model.initSystem();model.assemble(initial);model.realizePosition(initial)
    joints=model.getJointSet();cs=model.getCoordinateSet()
    names=[joints.get(i).getName() for i in range(joints.getSize())]
    def snapshot(s):
        frames=[]
        for i in range(joints.getSize()):
            j=joints.get(i)
            t=j.getChildFrame().getTransformInGround(s)
            frames.append([round(float(t.p()[k]),6) for k in range(3)])
        return frames
    def axes(s,i):
        t=joints.get(i).getParentFrame().getTransformInGround(s)
        return [[round(float(t.p()[k]),6) for k in range(3)]]+[[round(float(t.R().get(k,col)),6) for k in range(3)] for col in range(3)]
    root=ET.parse(a.model).getroot().find('Model')
    dependent={e.text.strip() for e in root.findall('./ConstraintSet/objects/*/dependent_coordinate_name') if e.text}
    owners={q.get('name'):j.get('name') for j in root.findall('./JointSet/objects/*') for q in j.findall('./coordinates/Coordinate')}
    base=snapshot(initial); controls=[]; skipped=[]
    for i in range(cs.getSize()):
        q=cs.get(i);name=q.getName()
        if name not in owners: continue
        ji=names.index(owners[name])
        default=float(q.getValue(initial));lo=float(q.getRangeMin());hi=float(q.getRangeMax())
        if q.getLocked(initial) or name in dependent or not all(map(math.isfinite,[lo,hi,default])) or hi-lo<1e-8:
            skipped.append({'name':name,'reason':'locked, dependent or invalid range'});continue
        motion=int(q.getMotionType())
        # OpenSim enum: rotational=1, translational=2, coupled=3; coupled coordinates stay in native units.
        step=.03 if motion==2 else math.pi/4
        low=max(lo,default-step);high=min(hi,default+step)
        targets=sorted(set([default]+[low+(high-low)*k/6 for k in range(7)]))
        samples=[]; errors=[]
        for v in targets:
            try:
                s=osim.State(initial)
                q.setValue(s,v,False);model.assemble(s);model.realizePosition(s)
                actual=float(q.getValue(s))
                if abs(actual-v)>1e-4: raise ValueError('assembly did not retain requested coordinate')
                xyz=snapshot(s)
                if not np.isfinite(xyz).all(): raise ValueError('non-finite pose')
                samples.append({'value':round(actual,7),'points':xyz,'axes':axes(s,ji)})
            except Exception as e: errors.append({'target':v,'reason':str(e)[:200]})
        displacement=max((float(np.max(np.linalg.norm(np.array(s['points'])-np.array(base),axis=1))) for s in samples),default=0)
        if len(samples)<2 or displacement<1e-5:
            skipped.append({'name':name,'reason':'no verified positional motion','errors':errors});continue
        controls.append({'name':name,'joint':owners[name],'index':ji,'motionType':motion,'default':default,'range':[lo,hi],'samples':samples,'maxDisplacementM':displacement,'rejectedSamples':len(errors)})
    assert len(controls)>10, 'insufficient native movement samples'
    result={'schema':'native-single-coordinate-samples-v1','jointNames':names,'neutralPoints':base,'neutralAxes':[axes(initial,i) for i in range(len(names))],'controls':controls,'skipped':skipped,'limits':'One coordinate at a time; not a multi-coordinate solver. Axes are parent joint frame axes, not necessarily instantaneous rotation axes.'}
    a.out.write_text(json.dumps(result,separators=(',',':'),allow_nan=False))
    print('NATIVE_MOTION_QA',len(controls),'controls',sum(len(c['samples']) for c in controls),'assembled poses',len(skipped),'skipped')
if __name__=='__main__':main()
