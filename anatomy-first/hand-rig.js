// Home Workouts · anatomy-first hand rig prototype v0.1
// Original procedural geometry. Units: meters, +Y distal, +Z dorsal, -Z palmar.
// This is a teaching/engineering proxy, not a certified anatomical dataset.
export function createAnatomicalRig(THREE) {
  const root=new THREE.Group();root.name='anatomy-first-right-hand';
  const bones=[], controllers={};
  const matBone=new THREE.MeshStandardMaterial({color:0xe5d8bf,roughness:.72});
  const matCarpal=new THREE.MeshStandardMaterial({color:0xe9c9a0,roughness:.75});
  const matJoint=new THREE.MeshStandardMaterial({color:0x5ba8ab,roughness:.72,transparent:true,opacity:.8});
  const matHandle=new THREE.MeshStandardMaterial({color:0x354553,metalness:.5,roughness:.42});
  const matThumbPad=new THREE.MeshStandardMaterial({color:0xe07e72,roughness:.85});
  const V=(x,y,z)=>new THREE.Vector3(x,y,z),axisY=V(0,1,0);
  const rad=d=>THREE.MathUtils.degToRad(d),clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
  function pivot(parent,name,position=V(0,0,0)) {
    const p=new THREE.Group();p.name=name;p.position.copy(position);parent.add(p);controllers[name]=p;return p;
  }
  function sphere(parent,pos,r,color=matJoint) {
    const obj=new THREE.Mesh(new THREE.SphereGeometry(r,12,8),color);obj.position.copy(pos);parent.add(obj);return obj;
  }
  function bone(name,parent,a,b,r,material=matBone) {
    const direction=b.clone().sub(a),len=direction.length();
    if(len<=.0001)throw Error('Bone length invalid: '+name);
    const geo=new THREE.CylinderGeometry(r*.82,r,len,12,1);
    const obj=new THREE.Mesh(geo,material);
    obj.position.copy(a).add(b).multiplyScalar(.5);
    obj.quaternion.setFromUnitVectors(axisY,direction.normalize());
    obj.name=name;obj.userData.anatomicalBone=name;parent.add(obj);
    bones.push({name,mesh:obj,length:len});
    return obj;
  }
  function carpal(name,x,y,z,scale) {
    const o=new THREE.Mesh(new THREE.SphereGeometry(1,16,12),matCarpal);
    o.name=name+'_r';o.userData.anatomicalBone=o.name;
    o.position.set(x,y,z);o.scale.set(...scale);root.add(o);bones.push({name:o.name,mesh:o,length:scale[1]*2});
  }
  // Forearm and upper arm: bone volumes for orientation only, not joint surfaces.
  bone('humerus_r',root,V(-.016,-.48,.005),V(-.016,-.242,.005),.015);
  bone('radius_r',root,V(-.022,-.235,-.002),V(-.019,-.008,-.003),.009);
  bone('ulna_r',root,V(.018,-.235,.006),V(.019,-.005,.005),.008);
  const carpals=[
    ['scaphoid',-.025,.007,-.002,[.010,.012,.009]],
    ['lunate',-.007,.009,.003,[.010,.009,.009]],
    ['triquetrum',.012,.009,.004,[.009,.009,.009]],
    ['pisiform',.029,.003,-.010,[.007,.008,.007]],
    ['trapezium',-.035,.028,-.010,[.010,.010,.009]],
    ['trapezoid',-.017,.030,.001,[.009,.010,.009]],
    ['capitate',.004,.028,.006,[.012,.014,.011]],
    ['hamate',.027,.026,.003,[.013,.011,.011]]
  ];
  carpals.forEach(([n,x,y,z,s])=>carpal(n,x,y,z,s));
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
  const cmcOrigin=V(-.038,.032,-.009);
  const abduction=pivot(root,'thumb_cmc_abduction_r',cmcOrigin);
  const cmcFlex=pivot(abduction,'thumb_cmc_flexion_r');
  const cmcAxial=pivot(cmcFlex,'thumb_cmc_axial_rotation_r');
  sphere(cmcAxial,V(0,0,0),.007);
  const thumbMetaEnd=V(-.031,.027,-.009);
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
  function pose({opposition=0,grip=0}={}) {
    const o=clamp(opposition,0,1),g=clamp(grip,0,1);
    // Calibration proxies: each axis is explicitly named and bounded.
    abduction.rotation.y=rad(-34*o);       // palmar abduction
    cmcFlex.rotation.z=rad(-29*o);          // sweep toward the other digits
    cmcAxial.quaternion.setFromAxisAngle(thumbMetaEnd.clone().normalize(),rad(-40*o));
    thumbMcp.rotation.x=rad(-26*o-11*g);
    thumbIp.rotation.x=rad(-24*o-12*g);
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
    const target=V(clamp(thumbPad.x,c.x-.096,c.x+.096),c.y,c.z);
    const radial=thumbPad.clone().sub(target).length();
    const padNormal=V(0,0,-1).transformDirection(pad.matrixWorld).normalize();
    const towards=target.clone().sub(thumbPad).normalize();
    const cmc=abduction.getWorldPosition(new THREE.Vector3());
    return {
      bones:bones.length,
      thumbPad:[thumbPad.x,thumbPad.y,thumbPad.z],
      thumbTipToHandleMeters:radial-.011,
      thumbPadFacingDot:padNormal.dot(towards),
      cmcOrigin:[cmc.x,cmc.y,cmc.z],
      gripIsAnatomicallyValidated:false
    };
  }
  if(bones.length!==30)throw Error('Expected 30 named anatomical proxies, found '+bones.length);
  const nodes=new Set(bones.map(b=>b.name));
  if(nodes.size!==bones.length)throw Error('Duplicate named anatomical proxy');
  pose();
  return {root,bones,controllers,joints,bar,pad,pose,getMetrics,THREE};
}