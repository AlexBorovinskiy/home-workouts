"""Separate calibration candidate. Do not overwrite baseline native rig.
FHS joint anchors define neck and bilateral sternoclavicular interfaces.
Hip registration is intentionally audit-only unless identical pelvis geometry
and consistent local mesh scale can be established.
"""
import argparse, pathlib, json, copy, xml.etree.ElementTree as ET
import numpy as np
import opensim as osim
from scipy.spatial.transform import Rotation
from scipy.spatial import cKDTree
import zipfile, urllib.request

def arr(x): return np.asarray(x,float)
def frame(f,s):
    t=f.getTransformInGround(s)
    return arr([t.p()[i] for i in range(3)]),arr([[t.R().get(i,k) for k in range(3)] for i in range(3)])
def put(e,key,v):
    e.find(key).text=' '.join(f'{x:.16g}' for x in v)
def main():
    p=argparse.ArgumentParser();p.add_argument('inventory',type=pathlib.Path);p.add_argument('fhs_zip',type=pathlib.Path);p.add_argument('legs',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    fhs=json.loads((a.inventory/'fhs.json').read_text());top=json.loads((a.inventory/'topology.json').read_text())
    b={e['name']:e['world'] for e in fhs['bodies']};j={e['child']:e for e in fhs['joints']}
    src=a.inventory/'candidate/candidate.osim';tree=ET.parse(src);m=tree.getroot().find('Model');joints={e.get('name'):e for e in m.findall('./JointSet/objects/*')}
    baseline=osim.Model(str(src));s0=baseline.initSystem();baseline.assemble(s0);baseline.realizePosition(s0)
    records=[]
    def set_interface(name,parent,anchor,orientation,label):
        node=joints[name];f=next(e for e in node.findall('./frames/PhysicalOffsetFrame') if e.findtext('socket_parent')=='/bodyset/'+parent)
        pb,Rb=arr(b[parent]['p']),arr(b[parent]['R'])
        local=Rb.T@(arr(anchor)-pb);rot=Rb.T@arr(orientation)
        oldp,oldR=frame(baseline.getJointSet().get(name).getParentFrame(),s0)
        put(f,'translation',local);put(f,'orientation',Rotation.from_matrix(rot).as_euler('XYZ'))
        records.append({'joint':name,'parent':parent,'reference':label,'targetP':list(anchor),'targetR':arr(orientation).tolist(),'beforeResidualMm':float(np.linalg.norm(oldp-arr(anchor))*1000),'beforeOrientationDeg':float(Rotation.from_matrix(arr(orientation).T@oldR).magnitude()*180/np.pi)})
    set_interface('auxt1jnt','thoracic1',j['head_neck']['parent_world']['p'],j['head_neck']['parent_world']['R'],'FHS original T1–head_neck parent frame')
    for side,prefix in [('R','RA'),('L','LA')]:
        set_interface(prefix+'_sternoclavicular','sternum',j['clavicle_'+side]['parent_world']['p'],np.eye(3),'FHS sternoclavicular center; donor AAH neutral thorax axes aligned to FHS ground')
    # Compare actual unscaled donor pelvis surface vertices with FHS local vertices.
    # No scaling of legs: only hip socket placement is transferred if both pelvic
    # surfaces are demonstrably the same in local coordinates.
    hip={'status':'audit only','reason':'pelvic surface equivalence not demonstrated'}
    try:
        lm=ET.parse(a.legs).getroot().find('Model')
        donor=next(e for e in lm.findall('./BodySet/objects/Body') if e.get('name')=='pelvis')
        manifest=json.loads(pathlib.Path('opensim-lab/assets/fhs-original-frames.json').read_text())
        defs=manifest['anatomyMeshes']['pelvis']
        def vertices(raw):
            e=ET.fromstring(raw).find('./PolyData/Piece/Points/DataArray')
            assert e is not None and e.get('format')=='ascii'
            return np.fromstring(e.text,sep=' ').reshape(-1,3)
        df=[]
        for mesh in donor.findall('./attached_geometry/Mesh'):
            assert (mesh.findtext('socket_frame') or '..').strip()=='..'
            file=mesh.findtext('mesh_file').strip()
            if 'sacrum' in file.lower():continue
            scale=arr((mesh.findtext('scale_factors') or '1 1 1').split())
            url='https://raw.githubusercontent.com/opensim-org/opensim-models/master/Geometry/'+file
            df.append(vertices(urllib.request.urlopen(url,timeout=30).read())*scale)
        assert len(df)==2, 'expected two donor pelvic surfaces'
        with zipfile.ZipFile(a.fhs_zip) as z:
            path=manifest['archiveRelativeOsimPath'];prefix=path[:path.rindex('/Male/')]+ '/Geometry/'
            tf=[vertices(z.read(prefix+d['file']))*arr(d['scaleFactors']) for d in defs]
        source=np.concatenate(df);target=np.concatenate(tf)
        # Fit uniform scale using centered bounding boxes, then validate bidirectional
        # nearest-vertex errors against the independent original surfaces.
        ss=source.max(0)-source.min(0);ts=target.max(0)-target.min(0)
        scale=float(np.dot(ss,ts)/np.dot(ss,ss));translation=(target.max(0)+target.min(0)-scale*(source.max(0)+source.min(0)))/2
        transformed=source*scale+translation
        distances=np.concatenate([cKDTree(target).query(transformed)[0],cKDTree(transformed).query(target)[0]])
        hip.update({'scale':scale,'translationM':translation.tolist(),'p95Mm':float(np.percentile(distances,95)*1000),'maxMm':float(distances.max()*1000),'sourceVertices':len(source),'targetVertices':len(target)})
        if hip['p95Mm']<1 and hip['maxMm']<3 and .6<scale<1.4:
            for side in ('r','l'):
                name='hip_'+side;f=next(e for e in joints[name].findall('./frames/PhysicalOffsetFrame') if e.findtext('socket_parent')=='/bodyset/pelvis')
                old=arr(f.findtext('translation').split());new=old*scale+translation
                pb,Rb=arr(b['pelvis']['p']),arr(b['pelvis']['R'])
                oldp,oldR=frame(baseline.getJointSet().get(name).getParentFrame(),s0)
                set_interface(name,'pelvis',pb+Rb@new,oldR,'verified local pelvic surface similarity; socket transfer only')
            hip.update(status='socket centers transferred',reason='bidirectional surface similarity gate passed; femoral size and joint contact still unvalidated')
    except Exception as e:hip['reason']=str(e)
    out=a.out/'candidate.osim';tree.write(out,encoding='utf-8',xml_declaration=True)
    model=osim.Model(str(out));s=model.initSystem();model.assemble(s);model.realizePosition(s)
    assert model.getJointSet().getSize()==top['counts']['joints']
    for r in records:
        p,R=frame(model.getJointSet().get(r['joint']).getParentFrame(),s)
        r['afterResidualMm']=float(np.linalg.norm(p-arr(r['targetP']))*1000)
        r['afterOrientationDeg']=float(Rotation.from_matrix(arr(r['targetR']).T@R).magnitude()*180/np.pi)
        assert r['afterResidualMm']<.01 and r['afterOrientationDeg']<.01,r
    def landmarks(m,s):
        names=['skull','cerv7','thoracic1','sternum','pelvis','RA1H','LA1H','RA2U','LA2U','RA3L','LA3L','femur_r','femur_l','tibia_r','tibia_l','calcn_r','calcn_l','toes_r','toes_l']
        return {n:frame(m.getBodySet().get(n),s)[0].tolist() for n in names}
    report={'status':'interface reference registration, not anatomical validation','interfaces':records,'hip':hip,'baselineLandmarksM':landmarks(baseline,s0),'calibratedLandmarksM':landmarks(model,s),'targetHeightCalibrated':False}
    (a.out/'calibration.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print('INTERFACE_QA',json.dumps(report,separators=(',',':')))
if __name__=='__main__':main()
