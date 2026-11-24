"""Audit pelvis registration using point-to-triangle distances, not vertex density.
No joint modifications. Sphere candidates are diagnostic, not segmented acetabula.
"""
import argparse,json,pathlib,zipfile,urllib.request,xml.etree.ElementTree as ET
import numpy as np
import trimesh
from scipy.optimize import least_squares

def mesh(raw,scale):
    piece=ET.fromstring(raw).find('./PolyData/Piece')
    pts=piece.find('./Points/DataArray')
    assert pts.get('format')=='ascii'
    v=np.fromstring(pts.text,sep=' ').reshape(-1,3)*np.array(scale)
    a={e.get('Name'):e for e in piece.findall('./Polys/DataArray')}
    ix=np.fromstring(a['connectivity'].text,sep=' ',dtype=int)
    ends=np.fromstring(a['offsets'].text,sep=' ',dtype=int)
    triangles=[];start=0
    for end in ends:
        triangles.extend([ix[start],ix[i],ix[i+1]] for i in range(start+1,end-1));start=end
    assert len(triangles)>0
    return trimesh.Trimesh(vertices=v,faces=triangles,process=False)
def distances(m,points):
    return np.concatenate([trimesh.proximity.closest_point_naive(m,x)[1] for x in np.array_split(points,max(1,int(np.ceil(len(points)/32))))])
def summary(x):
    return {'medianMm':float(np.median(x)*1000),'p95Mm':float(np.percentile(x,95)*1000),'maxMm':float(np.max(x)*1000)}
def sphere_candidates(m,seed):
    # Explore sensitivity to ROI choice: no assumption that these vertices are
    # the anatomical lunate surface. Reject unstable estimates, do not apply.
    v=m.vertices;out=[]
    for radius in [.04,.05,.06]:
        p=v[np.linalg.norm(v-seed,axis=1)<radius]
        if len(p)<12:continue
        fit=least_squares(lambda x:np.linalg.norm(p-x[:3],axis=1)-x[3],np.r_[seed,.025],bounds=(np.r_[seed-.035,.012],np.r_[seed+.035,.045]),loss='soft_l1',f_scale=.003)
        c=fit.x[:3];r=fit.x[3]
        out.append({'roiRadiusMm':radius*1000,'vertices':len(p),'centerM':c.tolist(),'radiusMm':float(r*1000),'radialResidual':summary(abs(np.linalg.norm(p-c,axis=1)-r))})
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('donor');p.add_argument('out');a=p.parse_args()
    manifest=json.loads(pathlib.Path('opensim-lab/assets/fhs-original-frames.json').read_text())
    pre=manifest['archiveRelativeOsimPath'].split('/Male/')[0]+'/Geometry/'
    fhs={}
    with zipfile.ZipFile(a.archive) as z:
        for d in manifest['anatomyMeshes']['pelvis']:
            fhs['r' if '_r' in d['file'] else 'l']=mesh(z.read(pre+d['file']),d['scaleFactors'])
    model=ET.parse(a.donor).getroot().find('Model')
    body=next(e for e in model.findall('./BodySet/objects/Body') if e.get('name')=='pelvis')
    donor={}
    for e in body.findall('./attached_geometry/Mesh'):
        name=e.findtext('mesh_file').strip()
        if 'sacrum' in name.lower():continue
        assert (e.findtext('socket_frame') or '..').strip()=='..'
        side='r' if '_r' in name or name.startswith('r_') else 'l'
        assert side not in donor,name
        donor[side]=mesh(urllib.request.urlopen('https://raw.githubusercontent.com/opensim-org/opensim-models/master/Geometry/'+name,timeout=40).read(),np.fromstring(e.findtext('scale_factors') or '1 1 1',sep=' '))
    assert set(fhs)==set(donor)=={'r','l'}
    src=np.concatenate([x.vertices for x in donor.values()]);dst=np.concatenate([x.vertices for x in fhs.values()])
    ss=np.ptp(src,axis=0);ts=np.ptp(dst,axis=0);scale=float(ss@ts/(ss@ss));shift=(dst.max(0)+dst.min(0)-scale*(src.max(0)+src.min(0)))/2
    result={'method':'bidirectional vertex-to-triangle distance; exploratory robust sphere fits in unsegmented ROIs','scale':scale,'translationM':shift.tolist(),'sides':{},'jointChangesApplied':False}
    for side in ('r','l'):
        m=donor[side].copy();m.vertices=m.vertices*scale+shift
        n=fhs[side]
        joint=next(e for e in model.findall('./JointSet/objects/*') if e.get('name')=='hip_'+side)
        pf=next(e for e in joint.findall('./frames/PhysicalOffsetFrame') if e.findtext('socket_parent')=='/bodyset/pelvis')
        origin=np.fromstring(pf.findtext('translation'),sep=' ')
        seed=origin*scale+shift
        result['sides'][side]={'donorVertices':len(m.vertices),'fhsVertices':len(n.vertices),'donorToFhs':summary(distances(n,m.vertices)),'fhsToDonor':summary(distances(m,n.vertices)),'originalHipM':origin.tolist(),'transferredHypothesisM':seed.tolist(),'sphereSensitivity':sphere_candidates(n,seed)}
    pathlib.Path(a.out).write_text(json.dumps(result,indent=2,allow_nan=False))
    print('HIP_SURFACE_AUDIT',json.dumps(result))
if __name__=='__main__':main()
