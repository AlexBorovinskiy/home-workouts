// Anatomy First: motion study using 4 unchanged research MRI bone surfaces.
// This is NOT a validated CMC biomechanical simulator.
// Thumb meshes: segment_18 (probable trapezium), 06 (MC1), 12 (P1), 19 (P2).
const D = Math.PI/180;
export function createMRIThumbRig(THREE, gltf, landmarks) {
  const root = new THREE.Group();
  root.name = 'MRI thumb, original skinless segmented surfaces';
  root.add(gltf.scene);
  root.updateMatrixWorld(true);
  const id = landmarks.meshIds;
  const found = new Map();
  root.traverse(o => { if(o.isMesh){found.set(o.name,o); o.frustumCulled=false;} });
  const required = Object.values(id);
  for(const n of required) if(!found.has(n)) throw new Error('Не найдена исходная МРТ-кость: '+n);
  const bone={
    trapezium:found.get(id.trapezium),
    mc1:found.get(id.metacarpal1),
    prox:found.get(id.proximal),
    distal:found.get(id.distal),
    indexMc:found.get(id.indexMetacarpal),
    indexProx:found.get(id.indexProximal)
  };
  // Existing STL facets are never remeshed or changed.
  for(const [name,mesh] of found){
    mesh.visible=required.includes(name);
    mesh.material=new THREE.MeshStandardMaterial({
      color:name===id.trapezium?0xc3d7c9:
            name===id.metacarpal1?0xe8be87:
            name===id.proximal?0xf0d8b3:
            name===id.distal?0xf0b5a3:0x8fbac4,
      roughness:.76,metalness:0,side:THREE.DoubleSide,
      transparent:[id.indexMetacarpal,id.indexProximal].includes(name),
      opacity:[id.indexMetacarpal,id.indexProximal].includes(name)?.32:1
    });
  }
  const cmc=new THREE.Vector3(...landmarks.landmarks.cmc.xyz);
  const mcp=new THREE.Vector3(...landmarks.landmarks.mcp.xyz);
  const ip =new THREE.Vector3(...landmarks.landmarks.ip.xyz);
  const metacarpalAxis=mcp.clone().sub(cmc).normalize();
  const hinge=new THREE.Vector3(metacarpalAxis.z,0,-metacarpalAxis.x).normalize();
  if(hinge.length()<.9)throw new Error('Некорректная ось большого пальца');
  const pivot=(name,parent,pos)=>{
    const o=new THREE.Group();o.name=name;o.position.copy(pos);parent.add(o);return o;
  };
  const abduction=pivot('CMC: palmar abduction',root,cmc);
  const flexion=pivot('CMC: flexion across palm',abduction,new THREE.Vector3());
  const axial=pivot('CMC: first metacarpal axial roll',flexion,new THREE.Vector3());
  root.updateMatrixWorld(true);
  axial.attach(bone.mc1); // preserve original world transform
  const mcpNode=pivot('MCP: thumb flexion',axial,mcp.clone().sub(cmc));
  root.updateMatrixWorld(true);
  mcpNode.attach(bone.prox);
  const ipNode=pivot('IP: thumb flexion',mcpNode,ip.clone().sub(mcp));
  root.updateMatrixWorld(true);
  ipNode.attach(bone.distal);
  // A surface point towards the distal end, from actual MRI triangle vertices.
  const geo=bone.distal.geometry,attr=geo.attributes.position;
  bone.distal.updateWorldMatrix(true,false);
  geo.computeBoundingBox();
  const centroidLocal=geo.boundingBox.getCenter(new THREE.Vector3());
  const forward=centroidLocal.applyMatrix4(bone.distal.matrixWorld).sub(ip).normalize();
  let best=-Infinity,tipLocal=new THREE.Vector3(),p=new THREE.Vector3(),pworld=new THREE.Vector3();
  for(let i=0;i<attr.count;i++){
    p.fromBufferAttribute(attr,i);
    pworld.copy(p).applyMatrix4(bone.distal.matrixWorld);
    const score=pworld.clone().sub(ip).dot(forward);
    if(score>best){best=score;tipLocal.copy(p);}
  }
  const tipMarker=new THREE.Mesh(new THREE.SphereGeometry(.0019,12,10),
    new THREE.MeshBasicMaterial({color:0x5ee0d0,depthTest:false}));
  tipMarker.position.copy(tipLocal);tipMarker.name='tip landmark on original distal bone';
  bone.distal.add(tipMarker);
  // Show engineering pivots independently of the anatomical geometry.
  const markerMat=new THREE.MeshBasicMaterial({color:0x72e3d1,transparent:true,opacity:.65,depthTest:false});
  const jointPoints=[];
  for(const [name,p] of [['CMC',cmc],['MCP',mcp],['IP',ip]]){
    const mark=new THREE.Mesh(new THREE.SphereGeometry(.0022,12,10),markerMat);
    mark.position.copy(p);mark.name='estimated '+name+' surface midpoint';
    root.add(mark);jointPoints.push(mark);
  }
  const handle=new THREE.Group();handle.name='fixed handle reference';
  handle.position.set(.010,-.011,.028);root.add(handle);
  const metal=new THREE.MeshStandardMaterial({color:0x172c3a,metalness:.57,roughness:.36});
  const shaft=new THREE.Mesh(new THREE.CylinderGeometry(.011,.011,.158,36),metal);
  shaft.rotation.z=Math.PI/2;handle.add(shaft);
  for(const x of [-.073,.073]){
    const disc=new THREE.Mesh(new THREE.CylinderGeometry(.026,.026,.013,40),
      new THREE.MeshStandardMaterial({color:0x60788b,metalness:.7,roughness:.38}));
    disc.position.x=x;disc.rotation.z=Math.PI/2;handle.add(disc);
  }
  const PRESETS={
    neutral:{abduct:0,cmcFlex:0,cmcRotate:0,mcpFlex:0,ipFlex:0},
    oppose:{abduct:4,cmcFlex:14,cmcRotate:8,mcpFlex:4,ipFlex:4},
    grasp:{abduct:8,cmcFlex:20,cmcRotate:10,mcpFlex:4,ipFlex:8}
  };
  const ranges={abduct:[-25,35],cmcFlex:[-15,55],cmcRotate:[-45,45],
    mcpFlex:[-15,65],ipFlex:[-15,75]};
  let current={...PRESETS.neutral};
  function pose(partial){
    current={...current,...partial};
    for(const [key,v] of Object.entries(current)){
      if(!Number.isFinite(v))throw new Error('Invalid '+key);
      current[key]=Math.max(ranges[key][0],Math.min(ranges[key][1],v));
    }
    // Calibrated *control conventions*, not validated physiological axes.
    abduction.quaternion.setFromAxisAngle(hinge,current.abduct*D);
    flexion.quaternion.setFromAxisAngle(new THREE.Vector3(0,-1,0),current.cmcFlex*D);
    axial.quaternion.setFromAxisAngle(metacarpalAxis,current.cmcRotate*D);
    mcpNode.quaternion.setFromAxisAngle(hinge,current.mcpFlex*D);
    ipNode.quaternion.setFromAxisAngle(hinge,current.ipFlex*D);
    root.updateMatrixWorld(true);
    return metrics();
  }
  function metrics(){
    root.updateMatrixWorld(true);
    const tip=tipMarker.getWorldPosition(new THREE.Vector3());
    const pivotCMC=abduction.getWorldPosition(new THREE.Vector3());
    const pivotMCP=mcpNode.getWorldPosition(new THREE.Vector3());
    const pivotIP=ipNode.getWorldPosition(new THREE.Vector3());
    const tipInShaft=handle.worldToLocal(tip.clone());
    const radial=Math.hypot(tipInShaft.y,tipInShaft.z);
    // Closest surface distance of BONE landmark to cylindrical shaft. Not skin.
    const outOfLength=Math.max(0,Math.abs(tipInShaft.x)-.079);
    const clearance=Math.hypot(outOfLength,Math.max(radial-.011,0));
    return {
      pivotCMC:pivotCMC.toArray(),pivotMCP:pivotMCP.toArray(),pivotIP:pivotIP.toArray(),
      distalBoneTip:tip.toArray(),
      tipToShaftMm:Number((clearance*1000).toFixed(2)),
      shaftRadialMm:Number((radial*1000).toFixed(2)),
      tipX:tipInShaft.x,position:{...current},
      bonesFromMRI:4,rigValidated:false
    };
  }
  function showContext(visible) {
    bone.indexMc.visible=visible;bone.indexProx.visible=visible;
  }
  function showPivots(visible){jointPoints.forEach(x=>x.visible=visible);}
  pose(PRESETS.neutral);
  showContext(true);showPivots(false);handle.visible=false;
  return {root,bone,handle,pose,metrics,PRESETS,ranges,showContext,showPivots,
    cmc,mcp,ip,hinge,metacarpalAxis,tipMarker,
    provenance:landmarks.source};
}
