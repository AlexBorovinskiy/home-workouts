// Laboratory-only organic extension of the CC0 glove.
// Samples the wrist directly from the actual skinned vertices in the glove's
// own root coordinates; generates a smooth multi-ring forearm surface.
// This is a visual prototype, NOT a topologically welded Blender mesh.
export function createForearmExtension({THREE,mesh,root,material,scene}){
  scene.updateMatrixWorld(true);
  const geom=mesh.geometry,attr=geom.getAttribute('position');
  const toLocal=new THREE.Matrix4().copy(root.matrixWorld).invert();
  const p=new THREE.Vector3(),samples=[];
  for(let i=0;i<attr.count;i++){
    p.fromBufferAttribute(attr,i);
    mesh.applyBoneTransform(i,p);
    mesh.localToWorld(p);p.applyMatrix4(toLocal);
    // Proximal wrist only: avoids thumb and finger web.
    if(p.y>.007&&p.y<.015&&p.x>-.05&&p.x<.045)samples.push([p.x,p.z]);
  }
  if(samples.length<35)throw Error('Недостаточно вершин для построения сечения запястья: '+samples.length);
  const percentile=(a,f)=>{const i=(a.length-1)*f,l=Math.floor(i),h=Math.ceil(i);return a[l]+(a[h]-a[l])*(i-l)};
  const xs=samples.map(a=>a[0]).sort((a,b)=>a-b),zs=samples.map(a=>a[1]).sort((a,b)=>a-b);
  const xmin=percentile(xs,.045),xmax=percentile(xs,.955),zmin=percentile(zs,.045),zmax=percentile(zs,.955);
  const cx=(xmin+xmax)/2,cz=(zmin+zmax)/2;
  const rx=(xmax-xmin)/2,rz=(zmax-zmin)/2;
  if(rx<.009||rx>.045||rz<.007||rz>.045)throw Error('Неожиданное сечение запястья');
  const sectors=64,rings=30,pts=[],uv=[],tri=[];
  // The first ring is buried slightly within the glove at y=.013,
  // then transitions through the visible wrist into a tapered forearm.
  for(let j=0;j<=rings;j++){
    const t=j/rings,e=t*t*(3-2*t);
    const y=.013-.169*t;
    const xcenter=cx-.004*e, zcenter=cz-.001*e;
    const scaleX=.955+.48*e,scaleZ=.965+.43*e;
    for(let i=0;i<=sectors;i++){
      const a=i/sectors*Math.PI*2,cs=Math.cos(a),sn=Math.sin(a);
      // Gentle ellipsoidal contour; keep wrist slightly flattened.
      const muscle=1+.045*Math.sin(Math.PI*t)*Math.cos(2*a-.3);
      pts.push(xcenter+rx*scaleX*cs*muscle,y,zcenter+rz*scaleZ*sn*muscle);
      uv.push(i/sectors,t);
    }
  }
  for(let j=0;j<rings;j++)for(let i=0;i<sectors;i++){
    const a=j*(sectors+1)+i,b=a+sectors+1;
    tri.push(a,b,a+1,b,b+1,a+1);
  }
  // End cap is located beyond the camera focus, not at the wrist.
  const cap=pts.length/3;
  pts.push(cx-.004,-.156,cz-.001);uv.push(.5,1);
  for(let i=0;i<sectors;i++)tri.push(cap,rings*(sectors+1)+i,rings*(sectors+1)+i+1);
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(pts,3));
  g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));
  g.setIndex(tri);g.computeVertexNormals();
  const sleeve=new THREE.Mesh(g,material);sleeve.name='wrist-derived-organic-forearm';
  sleeve.frustumCulled=false;
  root.add(sleeve);
  return {mesh:sleeve,wrist:{vertices:samples.length,center:[cx,cz],radii:[rx,rz],rangeY:[.007,.015]},length:.169,welded:false};
}
