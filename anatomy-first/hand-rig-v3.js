// Home Workouts · anatomy-first hand rig prototype v0.3 (individual carpal shape and CMC articulation layout)
// Original procedural geometry. Units: meters, +Y distal, +Z dorsal, -Z palmar.
// This is a teaching/engineering proxy, not a certified anatomical dataset.
export function createAnatomicalRig(THREE) {
  const root=new THREE.Group();root.name='anatomy-first-right-hand';
  const bones=[], controllers={};
  const matBone=new THREE.MeshStandardMaterial({color:0xe5d8bf,roughness:.72});
  const matCarpal=new THREE.MeshStandardMaterial({color:0xe9c9a0,roughness:.75});
  const matJoint=new THREE.MeshStandardMaterial({color:0x5ba8ab,roughness:.72,transparent:true,opacity:.7});
  const matHandle=new THREE.MeshStandardMaterial({color:0x354553,metalness:.5,roughness:.42});
  const matThumbPad=new THREE.MeshStandardMaterial({color:0xe07e72,roughness:.85});
  const V=(x,y,z)=>new THREE.Vector3(x,y,z),axisY=V(0,1,0);
  const rad=d=>THREE.MathUtils.degToRad(d),clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
  function pivot(parent,name,position=V(0,0,0)) {
    const p=new THREE.Group();p.name=name;p.position.copy(position);parent.add(p);controllers[name]=p;return p;
  }
  function sphere(parent,pos,r,color=matJoint) {
    // Joint centres are controls, not independent bone marbles.
    // They remain in the scene for developer inspection but are hidden by default.
    const obj=new THREE.Mesh(new THREE.SphereGeometry(r,10,8),color);
    obj.position.copy(pos);obj.visible=false;obj.userData.jointMarker=true;parent.add(obj);return obj;
  }
  function bone(name,parent,a,b,r,material=matBone) {
    const direction=b.clone().sub(a),len=direction.length();
    if(len<=.0001)throw Error('Bone length invalid: '+name);
    // Controlled 9-section loft: epiphyses expand while shaft narrows.
    // This is deliberately a stylised bone proxy, NOT a scanned anatomical bone.
    const stations=[
      [0,.99],[.055,1.24],[.13,1.13],[.25,.73],[.43,.64],
      [.62,.69],[.78,.85],[.9,1.21],[.963,1.3],[1,.94]
    ];
    const verts=[],inds=[],u=16;
    for(const [t,f] of stations){
      const theta=t*Math.PI;
      const curve=.11*r*Math.sin(theta);
      for(let k=0;k<u;k++){
        const ang=2*Math.PI*k/u;
        const rough=1+.034*Math.cos(3*ang+name.length*.4)*Math.sin(Math.PI*t);
        const rx=r*f*rough*(.97+.05*Math.sin(ang*2));
        const rz=r*f*rough*.82;
        verts.push(Math.cos(ang)*rx+curve,(t-.5)*len,Math.sin(ang)*rz);
      }
    }
    for(let j=0;j<stations.length-1;j++)for(let k=0;k<u;k++){
      const a=j*u+k,b=j*u+(k+1)%u,c=(j+1)*u+k,d=(j+1)*u+(k+1)%u;
      inds.push(a,c,b,b,c,d);
    }
    const lower=verts.length/3;verts.push(0,-len/2,0);
    const upper=verts.length/3;verts.push(0,len/2,0);
    for(let k=0;k<u;k++){
      inds.push(lower,k,(k+1)%u);
      inds.push(upper,(stations.length-1)*u+(k+1)%u,(stations.length-1)*u+k);
    }
    const geo=new THREE.BufferGeometry();
    geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));
    geo.setIndex(inds);
    geo.computeVertexNormals();
    const obj=new THREE.Mesh(geo,material);
    obj.position.copy(a).add(b).multiplyScalar(.5);
    obj.quaternion.setFromUnitVectors(axisY,direction.normalize());
    obj.name=name;obj.userData.anatomicalBone=name;parent.add(obj);
    bones.push({name,mesh:obj,length:len});
    return obj;
  }
  // 8 intentionally distinct bones, sculpted with hand-authored parametric surfaces.
  // Arrangement (radial/thumb x<0 to ulnar x>0) follows proximal/distal rows.
  // Pisiform is on the volar/palmar face of triquetrum, NOT a fourth coplanar pebble.
  // Stylized osteological proxies; NOT segmented CT scans.
  const carpalByName={};
  const carpalShapes={
    scaphoid:{center:[-.026,.013,-.002],scale:[.012,.016,.010],turn:-.20},
    lunate:{center:[-.005,.011,.004],scale:[.012,.011,.011],turn:.07},
    triquetrum:{center:[.017,.012,.004],scale:[.010,.011,.010],turn:.12},
    pisiform:{center:[.027,.012,-.010],scale:[.0062,.0066,.006],turn:.20},
    trapezium:{center:[-.041,.037,-.011],scale:[.011,.012,.010],turn:-.27},
    trapezoid:{center:[-.019,.036,.000],scale:[.010,.012,.009],turn:.07},
    capitate:{center:[.004,.037,.003],scale:[.014,.015,.011],turn:.03},
    hamate:{center:[.030,.035,.000],scale:[.013,.013,.011],turn:.18}
  };
  function carpal(name,data){
    const g=new THREE.SphereGeometry(1,30,22);
    const a=g.getAttribute('position');
    for(let i=0;i<a.count;i++){
      const x=a.getX(i),y=a.getY(i),z=a.getZ(i);
      const rough=1+.024*Math.sin(5*x+name.length*.7)*Math.cos(4*y-3*z);
      let X=x,Y=y,Z=z;
      if(name==='scaphoid'){
        X+=-.20*y;
        Y*=1.02+.08*x;
        Z+=-.18*x*y;
      }else if(name==='lunate'){
        // Concave distal crown: scapholunate facet and the capitate-facing cup.
        Y-=.20*Math.exp(-x*x*7)*Math.max(0,y);
        Z+=.12*(x*x-.35)*Math.max(0,y);
      }else if(name==='triquetrum'){
        X+=.20*y*y-.08;
        Z+=.13*x*y;
      }else if(name==='pisiform'){
        Y+=.10*x;
      }else if(name==='trapezium'){
        // Opposed saddle contours for the first metacarpal.
        Y+=.11*x*x*Math.max(0,y);
        Z+=.20*(x*x-z*z)*Math.max(0,y);
        X+=-.11*y;
      }else if(name==='trapezoid'){
        X*=1+.23*y;
        Y-=.08*x*x;
      }else if(name==='capitate'){
        X*=1-.17*Math.max(0,-y);
        Y+=.08*Math.cos(2*x);
      }else if(name==='hamate'){
        X*=1+.12*y;
        Z+=-.08*x*y;
      }
      a.setXYZ(i,X*rough,Y*rough,Z*rough);
    }
    g.computeVertexNormals();
    const mesh=new THREE.Mesh(g,matCarpal.clone());
    mesh.name=name+'_r';
    mesh.userData.anatomicalBone=mesh.name;
    mesh.userData.carpalRow=['scaphoid','lunate','triquetrum','pisiform'].includes(name)?'proximal':'distal';
    mesh.userData.morphology='procedural approximation';
    mesh.position.set(...data.center);
    mesh.rotation.z=data.turn;
    mesh.scale.set(...data.scale);
    root.add(mesh);
    carpalByName[name]=mesh;
    bones.push({name:mesh.name,mesh,length:data.scale[1]*2});
    if(name==='hamate'){
      // Palmar hook (hamulus) is part of hamate, NOT an additional bone.
      const curve=new THREE.CatmullRomCurve3([
        V(.50,.25,-.65),V(.70,.33,-.95),V(.78,.45,-1.10),V(.59,.57,-1.15)
      ]);
      const hook=new THREE.Mesh(new THREE.TubeGeometry(curve,12,.12,7,false),mesh.material);
      hook.name='hamate-hook-process';mesh.add(hook);
    }
    if(name==='scaphoid'||name==='trapezium'){
      const t=new THREE.Mesh(new THREE.SphereGeometry(.17,12,8),mesh.material);
      t.position.set(name==='scaphoid'?-0.48:0.15,.48,-.83);
      t.scale.set(.95,1.1,.78);
      t.name=name+'-volar-tubercle';
      mesh.add(t);
    }
  }
  // Forearm and upper arm are still proxies; the distal radius faces the
  // scaphoid/lunate. The distal ulna does not directly articulate with carpals.
  bone('humerus_r',root,V(-.016,-.48,.005),V(-.016,-.242,.005),.015);
  bone('radius_r',root,V(-.022,-.235,-.002),V(-.019,-.005,-.003),.009);
  bone('ulna_r',root,V(.018,-.235,.006),V(.019,-.010,.006),.008);
  for(const [name,data] of Object.entries(carpalShapes))carpal(name,data);
  const fingerDefs={
    index:{base:[-.023,.035,0],mcp:[-.024,.096,-.002],lengths:[.041,.026,.019],r:.0055,curl:[56,68,31]},
    middle:{base:[-.005,.035,.004],mcp:[-.005,.105,.001],lengths:[.046,.030,.020],r:.006,curl:[58,71,35]},
    ring:{base:[.016,.033,.004],mcp:[.018,.098,.001],lengths:[.044,.027,.019],r:.0056,curl:[55,68,32]},
    little:{base:[.035,.029,-.001],mcp:[.042,.084,-.002],lengths:[.033,.022,.016],r:.0047,curl:[53,67,32]}
  };
  const joints={};
  for(const [name,f] of Object.entries(fingerDefs)){
    const base=new THREE.Vector3(...f.base),mcp=new THREE.Vector3(...f.mcp);
    const id={index:2,middle:3,ring:4,little:5}[name];
    bone('metacarpal_'+id+'_r',root,base,mcp,f.r*1.18);
    const knuckle=pivot(root,name+'_mcp_r',mcp);
    sphere(knuckle,V(0,0,0),f.r*1.14);
    const proximalEnd=V(0,f.lengths[0],0);
    bone(name+'_proximal_phalanx_r',knuckle,V(0,0,0),proximalEnd,f.r);
    const pip=pivot(knuckle,name+'_pip_r',proximalEnd);
    sphere(pip,V(0,0,0),f.r*.9);
    const middleEnd=V(0,f.lengths[1],0);
    bone(name+'_middle_phalanx_r',pip,V(0,0,0),middleEnd,f.r*.83);
    const dip=pivot(pip,name+'_dip_r',middleEnd);
    sphere(dip,V(0,0,0),f.r*.75);
    bone(name+'_distal_phalanx_r',dip,V(0,0,0),V(0,f.lengths[2],0),f.r*.68);
    joints[name]={knuckle,pip,dip,angles:f.curl};
  }
  // Thumb's 1st metacarpal pivots at the trapezium (CMC); not at a finger knuckle.
  // Opposition couples palmar abduction, CMC flexion, and axial metacarpal rotation.
  const cmcOrigin=V(-.043,.040,-.013); // dorsal/radial saddle facing MC1; anchored to trapezium
  const abduction=pivot(root,'thumb_cmc_abduction_r',cmcOrigin);
  const cmcFlex=pivot(abduction,'thumb_cmc_flexion_r');
  const cmcAxial=pivot(cmcFlex,'thumb_cmc_axial_rotation_r');
  sphere(cmcAxial,V(0,0,0),.007);
  const thumbMetaEnd=V(-.028,.029,-.010);
  bone('metacarpal_1_r',cmcAxial,V(0,0,0),thumbMetaEnd,.0065);
  const thumbMcp=pivot(cmcAxial,'thumb_mcp_r',thumbMetaEnd);
  sphere(thumbMcp,V(0,0,0),.006);
  const thumbProxEnd=V(-.011,.027,-.003);
  bone('thumb_proximal_phalanx_r',thumbMcp,V(0,0,0),thumbProxEnd,.0055);
  const thumbIp=pivot(thumbMcp,'thumb_ip_r',thumbProxEnd);
  sphere(thumbIp,V(0,0,0),.0048);
  const thumbDistEnd=V(-.005,.020,-.003);
  bone('thumb_distal_phalanx_r',thumbIp,V(0,0,0),thumbDistEnd,.0046);
  const pad=pivot(thumbIp,'thumb_pad_marker',thumbDistEnd.clone().multiplyScalar(.88));
  const marker=new THREE.Mesh(new THREE.SphereGeometry(.0042,14,12),matThumbPad);
  marker.scale.set(.72,.9,.46);marker.position.set(0,0,-.004);pad.add(marker);
  // Cylinder across the palm, shown as an experimental target, not automatically held.
  const bar=new THREE.Group();bar.name='dumbbell-handle-target';bar.position.set(0,.092,-.036);root.add(bar);
  const shaft=new THREE.Mesh(new THREE.CylinderGeometry(.011,.011,.196,32),matHandle);
  shaft.rotation.z=Math.PI/2;shaft.name='shaft';bar.add(shaft);
  const plateMat=new THREE.MeshStandardMaterial({color:0x7c91a0,metalness:.7,roughness:.36});
  for(const x of [-.081,.081]){
    const disc=new THREE.Mesh(new THREE.CylinderGeometry(.035,.035,.018,28),plateMat);
    disc.rotation.z=Math.PI/2;disc.position.x=x;bar.add(disc);
  }
  // Tested marker pose only: near shaft, not an anatomically validated skin grip.
  const calibration={cmcAbduction:-45,cmcFlexion:-35,cmcAxial:-40,thumbMcpFlex:-45,thumbIpFlex:-26};
  let currentPose={opposition:0,grip:0};
  function pose({opposition=0,grip=0}={}) {
    const o=clamp(opposition,0,1),g=clamp(grip,0,1);
    currentPose={opposition:o,grip:g};
    // Calibration proxies: each axis is explicitly named and bounded.
    abduction.rotation.y=rad(calibration.cmcAbduction*o);       // palmar abduction
    cmcFlex.rotation.z=rad(calibration.cmcFlexion*o);          // sweep toward the other digits
    cmcAxial.quaternion.setFromAxisAngle(thumbMetaEnd.clone().normalize(),rad(calibration.cmcAxial*o));
    thumbMcp.rotation.x=rad(calibration.thumbMcpFlex*o-11*g);
    thumbIp.rotation.x=rad(calibration.thumbIpFlex*o-12*g);
    for(const entry of Object.values(joints)){
      entry.knuckle.rotation.x=rad(-entry.angles[0]*g);
      entry.pip.rotation.x=rad(-entry.angles[1]*g);
      entry.dip.rotation.x=rad(-entry.angles[2]*g);
    }
    root.updateMatrixWorld(true);
    return getMetrics();
  }
  function getMetrics() {
    root.updateMatrixWorld(true);
    const thumbPad=pad.getWorldPosition(new THREE.Vector3());
    const c=bar.getWorldPosition(new THREE.Vector3());
    const target=V(clamp(thumbPad.x,c.x-.075,c.x+.075),c.y,c.z);
    const indexTip=joints.index.dip.localToWorld(V(0,.019,0));
    const distIndex=thumbPad.distanceTo(indexTip);
    const radial=thumbPad.clone().sub(target).length();
    const padNormal=V(0,0,-1).transformDirection(pad.matrixWorld).normalize();
    const towards=target.clone().sub(thumbPad).normalize();
    const cmc=abduction.getWorldPosition(new THREE.Vector3());
    return {
      bones:bones.length,
      thumbPad:[thumbPad.x,thumbPad.y,thumbPad.z],
      thumbTipToHandleMeters:radial-.011,
      thumbPadFacingDot:padNormal.dot(towards),
      thumbToIndexTipMeters:distIndex,
      cmcOrigin:[cmc.x,cmc.y,cmc.z],
      gripIsAnatomicallyValidated:false
    };
  }
  if(bones.length!==30)throw Error('Expected 30 named anatomical proxies, found '+bones.length);
  const nodes=new Set(bones.map(b=>b.name));
  if(nodes.size!==bones.length)throw Error('Duplicate named anatomical proxy');
  pose();
  function getCarpalMetrics(){
    const positions=Object.fromEntries(Object.entries(carpalByName).map(([name,m])=>[name,m.position.toArray()]));
    const trapezium=carpalByName.trapezium.position;
    const cmcToTrapezium=abduction.position.distanceTo(trapezium);
    return {count:Object.keys(carpalByName).length,positions,
      proximal:['scaphoid','lunate','triquetrum','pisiform'],
      distal:['trapezium','trapezoid','capitate','hamate'],
      cmcToTrapeziumMeters:cmcToTrapezium,
      morphology:'stylized individual carpal contours, not CT validated'};
  }
  return {root,bones,controllers,joints,bar,pad,pose,getMetrics,getCarpalMetrics,
    setThumbCalibration:(next)=>{for(const [k,v] of Object.entries(next))if(k in calibration&&Number.isFinite(v))calibration[k]=v;return pose(currentPose)},
    getThumbCalibration:()=>({...calibration}),
    carpalByName,THREE,version:'0.3-carpal-morphology'};
}