"""Endplate candidate audit from actual bone mesh ray intersections.
Not automated anatomical segmentation. Never changes model or pose.
"""
import argparse,json,pathlib,zipfile,urllib.request
import numpy as np
from audit_hip_surfaces import mesh

def plane(points):
    X=np.c_[points[:,0],points[:,2],np.ones(len(points))]
    coef=np.linalg.lstsq(X,points[:,1],rcond=None)[0]
    residual=points[:,1]-X@coef
    return {'slopeDeg':float(np.degrees(np.arctan(coef[0]))),'coronalSlopeDeg':float(np.degrees(np.arctan(coef[1]))),'rmsMm':float(np.sqrt(np.mean(residual**2))*1000),'centerM':points.mean(0).tolist(),'planeYFromXZ':coef.tolist()}

def rays(tri,xz):
    # Vertical intersections, independent of mesh winding.
    A=tri[:,0];U=tri[:,1]-A;V=tri[:,2]-A
    den=U[:,0]*V[:,2]-U[:,2]*V[:,0];valid=abs(den)>1e-14
    A,U,V,den=A[valid],U[valid],V[valid],den[valid]
    result=[]
    for x,z in xz:
        dx=x-A[:,0];dz=z-A[:,2]
        u=(dx*V[:,2]-dz*V[:,0])/den;v=(U[:,0]*dz-U[:,2]*dx)/den
        keep=(u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)
        result.append(A[keep,1]+u[keep]*U[keep,1]+v[keep]*V[keep,1])
    return result

def patch(tri,seed,upper,radius):
    grid=np.linspace(-radius,radius,9)
    xz=np.array([[seed[0]+x,seed[2]+z] for x in grid for z in grid if x*x+z*z<=radius*radius+1e-12])
    intersections=rays(tri,xz);pts=[]
    for (x,z),ys in zip(xz,intersections):
        if len(ys):pts.append([x,float(max(ys) if upper else min(ys)),z])
    if len(pts)<12:return {'coverage':len(pts)/len(xz),'valid':False},np.array(pts)
    points=np.array(pts);p=plane(points);p['coverage']=len(pts)/len(xz);p['valid']=True
    p['centerToJointMm']=float(np.linalg.norm(points.mean(0)-seed)*1000)
    return p,points

def main():
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('poses');p.add_argument('out');a=p.parse_args()
    out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    pose=json.loads(pathlib.Path(a.poses).read_text());f=pose['sequences'][0]['frames'][0];bi={n:i for i,n in enumerate(pose['bodyNames'])};ji={n:i for i,n in enumerate(pose['jointNames'])}
    top=json.loads(pathlib.Path('unified-rig/topology.json').read_text())
    manifest=json.loads(pathlib.Path('opensim-lab/assets/fhs-original-frames.json').read_text())
    masi=json.loads(pathlib.Path('opensim-lab/assets/masi-neck-native.json').read_text())
    pre=manifest['archiveRelativeOsimPath'].split('/Male/')[0]+'/Geometry/'
    bodies={};failures={}
    def add(body,raw,scale,frame=None):
        m=mesh(raw,scale);i=bi[frame or body];m.vertices=m.vertices@np.array(f['rotations'][i]).T+np.array(f['bodies'][i]);bodies[body]=m
    with zipfile.ZipFile(a.archive) as z:
        for b,ds in manifest['anatomyMeshes'].items():
            if not b.startswith(('lumbar','thoracic')) and b!='sacrum':continue
            try:
                d=ds[0];assert d['socket']=='..';add(b,z.read(pre+d['file']),d['scaleFactors'])
            except Exception as e:failures[b]=str(e)
    for b,d in masi['bodyFrames'].items():
        if not b.startswith('cerv'):continue
        try:add(b,urllib.request.urlopen('https://raw.githubusercontent.com/MyoHub/myoconverter/main/models/osim/Neck6D/Geometry/'+d['file'],timeout=30).read(),d['scale'])
        except Exception as e:failures[b]=str(e)
    add('native_sacrum',urllib.request.urlopen('https://raw.githubusercontent.com/opensim-org/opensim-models/master/Models/Rajagopal/Geometry/sacrum.vtp',timeout=30).read(),[1,1,1],'pelvis')
    records={};planes={};plotdata=[]
    for j in top['joints']:
        child=j['child'];parent=j['parent']
        if child=='cerv1' or not child.startswith(('lumbar','thoracic','cerv')):continue
        if parent not in bodies or child not in bodies:continue
        # T12/L1 joint is reversed in the source hierarchy.
        lower,upper=sorted([parent,child],key=lambda n:bodies[n].vertices[:,1].mean())
        seed=np.array(f['points'][ji[j['joint']]])
        for b,high in [(lower,True),(upper,False)]:
            if b=='sacrum':b='native_sacrum'
            key=b+(':superior' if high else ':inferior')
            radii=[.003,.005,.007] if b.startswith('cerv') else [.006,.009,.012]
            samples=[];points=[]
            for rad in radii:
                q,pts=patch(bodies[b].triangles,seed,high,rad);q['radiusMm']=rad*1000;samples.append(q);points.append(pts)
            valid=[x for x in samples if x['valid'] and x['coverage']>=.8 and x['rmsMm']<=1.5 and x['centerToJointMm']<=25]
            stable=len(valid)==3 and np.ptp([x['slopeDeg'] for x in valid])<=5
            planes[key]={'joint':j['joint'],'candidateOnly':True,'stable':bool(stable),'samples':samples}
            if stable:planes[key]['selected']=valid[1]
            if len(points[1]):plotdata.append((key,points[1],stable,seed))
        akey=('native_sacrum' if lower=='sacrum' else lower)+':superior';bkey=upper+':inferior'
        A=planes[akey];B=planes[bkey];rec={'joint':j['joint'],'lower':akey,'upper':bkey,'bothStable':A['stable'] and B['stable']}
        if rec['bothStable']:
            ca=np.array(A['selected']['planeYFromXZ']);cb=np.array(B['selected']['planeYFromXZ']);x=np.array([seed[0],seed[2],1]);rec['centralVerticalClearanceMm']=float((cb-ca)@x*1000)
            rec['interpretation']='plane extrapolation at joint center; not contact or cartilage thickness'
        records[j['joint']]=rec
    def cobb(a,b):
        if a not in planes or b not in planes or not planes[a]['stable'] or not planes[b]['stable']:return None
        return abs(planes[a]['selected']['slopeDeg']-planes[b]['selected']['slopeDeg'])
    # T1 superior and C7 inferior are measured at the cervical/thoracic joint.
    measures={'lumbarL1S1CandidateDeg':cobb('lumbar1:superior','native_sacrum:superior'),'thoracicT1T12CandidateDeg':cobb('thoracic1:superior','thoracic12:inferior'),'cervicalC2C7CandidateDeg':cobb('cerv2:inferior','cerv7:inferior')}
    report={'status':'exploratory surface patches, not anatomically certified endplates','geometrySources':{'trunk':'original FHS archive','neck':'MyoHub surrogate used by viewer','sacrum':'native Rajagopal'},'meshFailures':failures,'bodyCount':len(bodies),'planes':planes,'interfaces':records,'candidateAngles':measures,'modelModified':False,'limitations':['Joint-seeded vertical rays may hit posterior elements or non-endplate surfaces; visual review required.','All angles withheld when coverage, plane residual or ROI stability gates fail.','No inference of physical contact from plane clearance.']}
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    fig,ax=plt.subplots(figsize=(9,15))
    for b,m in bodies.items():
        if b=='sacrum':continue
        ax.add_collection(PolyCollection(m.triangles[:,:,:2],facecolors='#dae2eb',edgecolors='none',alpha=.16))
    for key,pts,ok,seed in plotdata:
        ax.scatter(pts[:,0],pts[:,1],s=3,c='#168343' if ok else '#d97706')
        ax.scatter(seed[0],seed[1],s=8,c='#325c9e')
        ax.annotate(key,(pts[:,0].mean(),pts[:,1].mean()),fontsize=5,xytext=(4,0),textcoords='offset points')
    ax.autoscale();ax.set_aspect('equal');ax.set_title('v0.8 | Endplate candidate patches (green = geometric stability only)');ax.set_xlabel('Anterior x (m)');ax.set_ylabel('Superior y (m)');fig.savefig(out/'sagittal.png',dpi=170);plt.close(fig)
    print('ENDPLATE_QA',json.dumps({'bodyCount':len(bodies),'failures':failures,'stable':sum(x['stable'] for x in planes.values()),'total':len(planes),'angles':measures,'l5s1':records.get('L5_S1_IVDjnt')}))
if __name__=='__main__':main()
