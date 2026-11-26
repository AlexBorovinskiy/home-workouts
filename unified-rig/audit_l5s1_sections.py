"""L5/S1 sectional audit. No automatic anatomy or rig changes.
Export only derived measurements and plots, not the FHS source meshes."""
import argparse,json,pathlib,zipfile,urllib.request
import numpy as np
from audit_hip_surfaces import mesh
from audit_endplates import rays,plane
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

def main():
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('poses');p.add_argument('out');a=p.parse_args()
    out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    d=json.loads(pathlib.Path(a.poses).read_text());f=d['sequences'][0]['frames'][0];bi={n:i for i,n in enumerate(d['bodyNames'])};ji={n:i for i,n in enumerate(d['jointNames'])}
    origin=np.array(f['points'][ji['L5_S1_IVDjnt']])
    # Orient analysis frame along L5 local axes, not global vertical.
    R=np.array(f['rotations'][bi['lumbar5']])
    manifest=json.loads(pathlib.Path('opensim-lab/assets/fhs-original-frames.json').read_text())
    prefix=manifest['archiveRelativeOsimPath'].split('/Male/')[0]+'/Geometry/'
    def transform(m,b):
        i=bi[b];m.vertices=(m.vertices@np.array(f['rotations'][i]).T+np.array(f['bodies'][i])-origin)@R
        return m
    with zipfile.ZipFile(a.archive) as z:
        meshes={}
        for b in ['lumbar5','sacrum']:
            q=manifest['anatomyMeshes'][b][0];assert q['socket']=='..'
            meshes[b]=transform(mesh(z.read(prefix+q['file']),q['scaleFactors']),b)
    url='https://raw.githubusercontent.com/opensim-org/opensim-models/master/Models/Rajagopal/Geometry/sacrum.vtp'
    meshes['native_sacrum']=transform(mesh(urllib.request.urlopen(url,timeout=30).read(),[1,1,1]),'pelvis')
    # All intersections within a generous anterior body ROI; choose surfaces
    # facing the joint only after looking at the sectional contours.
    x=np.arange(-.035,.051,.001);z=np.arange(-.021,.022,.002)
    grid=np.array([(xx,zz) for xx in x for zz in z]);raw={}
    for b,m in meshes.items():
        hits=rays(m.triangles,grid);raw[b]=[[round(float(v)*1000,4) for v in sorted(h)] for h in hits]
    (out/'ray-grid.json').write_text(json.dumps({'frame':'L5 axes, origin L5/S1 child joint','xMm':(x*1000).tolist(),'zMm':(z*1000).tolist(),'gridOrder':'x outer, z inner','worldOriginM':origin.tolist(),'frameBasis':R.tolist(),'intersectionsYMm':raw},separators=(',',':')))
    colors={'lumbar5':'#23589b','sacrum':'#8895a5','native_sacrum':'#bc5036'}
    def section(ax,b,axis,offset):
        n=np.eye(3)[axis];s=meshes[b].section(plane_origin=n*offset,plane_normal=n)
        if s is None:return
        dims=[k for k in range(3) if k!=axis]
        for poly in s.discrete:ax.plot(poly[:,dims[0]]*1000,poly[:,dims[1]]*1000,color=colors[b],lw=1.4)
    fig,axs=plt.subplots(2,3,figsize=(15,10))
    for ax,zz in zip(axs[0],[0,.008,.016]):
        for b in meshes:section(ax,b,2,zz)
        ax.set_title(f'Sagittal z={zz*1000:.0f} mm');ax.set_xlabel('Anterior local x (mm)');ax.set_ylabel('Local y (mm)');ax.scatter(0,0,c='black',s=15)
    for ax,xx in zip(axs[1],[-.008,.006,.020]):
        # section helper returns local y then z; swap for coronal plot.
        for b in meshes:
            s=meshes[b].section(plane_origin=[xx,0,0],plane_normal=[1,0,0])
            if s:
                for poly in s.discrete:ax.plot(poly[:,2]*1000,poly[:,1]*1000,color=colors[b],lw=1.4)
        ax.set_title(f'Coronal x={xx*1000:.0f} mm');ax.set_xlabel('Lateral z (mm)');ax.set_ylabel('Local y (mm)')
    for ax in axs.flat:ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_ylim(-65,45)
    fig.legend([plt.Line2D([0],[0],color=colors[b]) for b in meshes],list(meshes),loc='upper center',ncol=3);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(out/'sections.png',dpi=160);plt.close(fig)
    # Plot envelope heights and clearance maps without assigning endplate labels.
    surfaces={}
    for b,hits in raw.items():
        surfaces[b]=np.array([(min(h) if b=='lumbar5' else max(h)) if h else np.nan for h in hits]).reshape(len(x),len(z))
    fig,axs=plt.subplots(1,3,figsize=(15,5))
    for ax,b in zip(axs,meshes):
        a=surfaces[b];im=ax.imshow(a.T,origin='lower',extent=[x[0]*1000,x[-1]*1000,z[0]*1000,z[-1]*1000],aspect='equal',cmap='viridis');fig.colorbar(im,ax=ax,label='local y (mm)');ax.set_title(b+' facing envelope');ax.set_xlabel('local x (mm)');ax.set_ylabel('local z (mm)')
    fig.tight_layout();fig.savefig(out/'envelopes.png',dpi=150);plt.close(fig)
    report={'frame':'L5 local axes','bodyVertexCounts':{b:len(m.vertices) for b,m in meshes.items()},'boundsMm':{b:(m.bounds*1000).tolist() for b,m in meshes.items()},'gridSamples':len(grid),'modelModified':False}
    (out/'report.json').write_text(json.dumps(report,indent=2));print('L5S1_SECTION_QA',json.dumps(report))
if __name__=='__main__':main()
