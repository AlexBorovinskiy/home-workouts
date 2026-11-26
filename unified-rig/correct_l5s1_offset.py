"""Experimental L5/S1 base-offset correction; no modification of native joint DOFs.
Translate spinal subtree along L5 neutral local y by the minimum donor-informed
distance, preserving pelvis and legs. The fit is neutral-only, not a clinical disc.
"""
import argparse,json,pathlib,xml.etree.ElementTree as ET
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('model');p.add_argument('grid');p.add_argument('out');a=p.parse_args()
    out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    d=json.loads(pathlib.Path(a.grid).read_text());x=np.array(d['xMm']);z=np.array(d['zMm'])
    H=d['intersectionsYMm']
    def heights(k):
        return np.array([(min(h) if k=='lumbar5' else max(h)) if h else np.nan for h in H[k]]).reshape(len(x),len(z))
    orig=heights('lumbar5')-heights('sacrum');now=heights('lumbar5')-heights('native_sacrum')
    valid=np.isfinite(orig)&np.isfinite(now);assert valid.sum()>500
    roi=(x[:,None]>=-1e-8)&(x[:,None]<=10+1e-8)&(abs(z[None,:])<=10+1e-8)&valid
    delta=max(float(np.nanmin(orig)-np.nanmin(now)),float(np.median((orig-now)[roi])))
    assert 0<delta<10
    shift=np.array(d['frameBasis'])[:,1]*delta/1000
    tree=ET.parse(a.model);m=tree.getroot().find('Model');joint=m.find('./JointSet/objects/CustomJoint[@name="L5_S1_IVDjnt"]')
    parent=next(e for e in joint.findall('./frames/PhysicalOffsetFrame') if e.findtext('socket_parent')=='/bodyset/sacrum')
    # The FHS sacrum is identity-oriented in this exact neutral export.
    old=np.fromstring(parent.findtext('translation'),sep=' ')
    parent.find('translation').text=' '.join(f'{v:.16g}' for v in old+shift)
    tree.write(out/'candidate.osim',encoding='utf-8',xml_declaration=True)
    def stat(v):return {'minMm':float(np.min(v)),'medianMm':float(np.median(v)),'maxMm':float(np.max(v))}
    report={'status':'experimental geometric neutral correction','shiftAlongL5LocalYmm':delta,'worldShiftM':shift.tolist(),'sampledCommonRays':int(valid.sum()),'donorMinClearanceMm':float(np.nanmin(orig)),'v08MinClearanceMm':float(np.nanmin(now)),'predictedMinClearanceMm':float(np.nanmin(now+delta)),'v08NegativeRays':int(np.sum(now<-.1)),'predictedNegativeRays':int(np.sum(now+delta<-.1)),'coreRoiMm':{'x':[0,10],'absZMax':10},'donorCoreClearance':stat(orig[roi]),'v08CoreClearance':stat(now[roi]),'predictedCoreClearance':stat((now+delta)[roi]),'modelModifiedOnly':'L5_S1_IVDjnt parent translation','anatomicallyValidated':False}
    (out/'correction.json').write_text(json.dumps(report,indent=2));print('L5S1_OFFSET',json.dumps(report))
if __name__=='__main__':main()
