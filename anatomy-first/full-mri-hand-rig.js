// Anatomy First: five-digit hand using unmodified MRI-derived triangle meshes.
// 19 metacarpals + phalanges (5+14), seven provisionally named carpals.
// Missing separate pisiform is NEVER invented. Approximate joint midpoints are
// used as temporary 3-DOF scene pivots, NOT clinical bone kinematics.
import {createReferenceGripRig} from './reference-grip-rig.js';

const ids={
  middle:{metacarpal:2,prox:8,mid:16,dist:25},
  ring:{metacarpal:4,prox:7,mid:17,dist:26},
  little:{metacarpal:5,prox:11,mid:24,dist:28}
};
const text={middle:'Средний',ring:'Безымянный',little:'Мизинец'};
const color={middle:0x9ecdad,ring:0xc9b6e6,little:0xe4c8a0};
const digitAngles={middle:[63,85,34],ring:[65,88,36],little:[67,92,38]};

export function createFullMRIHandRig(THREE,gltf,landmarks,jointData){
  const rig=createReferenceGripRig(THREE,gltf,landmarks);
  const root=rig.root;
  root.updateMatrixWorld(true);
  const meshMap=new Map();
  root.traverse(obj=>{if(obj.isMesh&&/^segment_\d+_unlabeled$/.test(obj.name))meshMap.set(obj.name,obj)});
  const key=n=>'segment_'+String(n).padStart(2,'0')+'_unlabeled';
  const joints=new Map(jointData.joints.map(j=>[j.joint,j]));
  const pivot=(name,parent,local)=>{
    const g=new THREE.Group();g.name=name;g.position.copy(local);parent.add(g);return g;
  };
  const readPoint=(finger,joint)=>{
    const j=joints.get(finger+'_'+joint);
    if(!j||j.verifiedJointCentre!==false)throw Error('Нет проверяемого приближённого ориентира '+finger+'_'+joint);
    return new THREE.Vector3(...j.approx_near_surface_midpoint_mm).multiplyScalar(.001);
  };
  const fingers={},pivotMarkers=[];
  const sign=rig.getIndexSign();
  for(const name of ['middle','ring','little']){
    const parts=Object.fromEntries(Object.entries(ids[name]).map(([type,n])=>{
      const mesh=meshMap.get(key(n));if(!mesh)throw Error('Отсутствует МРТ-кость: '+key(n));
      mesh.visible=true;
      mesh.material=new THREE.MeshStandardMaterial({color:color[name],roughness:.8,side:THREE.DoubleSide});
      return [type,mesh];
    }));
    const mcp=readPoint(name,'mcp'),pip=readPoint(name,'pip'),dip=readPoint(name,'dip');
    const mcpNode=pivot(name+' MCP approximate',root,mcp);
    root.updateMatrixWorld(true);mcpNode.attach(parts.prox);
    const pipNode=pivot(name+' PIP approximate',mcpNode,pip.clone().sub(mcp));
    root.updateMatrixWorld(true);pipNode.attach(parts.mid);
    const dipNode=pivot(name+' DIP approximate',pipNode,dip.clone().sub(pip));
    root.updateMatrixWorld(true);dipNode.attach(parts.dist);
    root.updateMatrixWorld(true);
    const g=parts.dist.geometry,attr=g.attributes.position;
    const local=new THREE.Vector3(),world=new THREE.Vector3(),tipLocal=new THREE.Vector3();
    let furthest=-Infinity;
    for(let i=0;i<attr.count;i++){
      local.fromBufferAttribute(attr,i);
      world.copy(local).applyMatrix4(parts.dist.matrixWorld);
      if(world.z>furthest){furthest=world.z;tipLocal.copy(local)}
    }
    const tip=new THREE.Object3D();tip.name=name+' distal bone landmark';tip.position.copy(tipLocal);parts.dist.add(tip);
    for(const [j,p] of [['MCP',mcp],['PIP',pip],['DIP',dip]]){
      const marker=new THREE.Mesh(new THREE.SphereGeometry(.0015,10,8),new THREE.MeshBasicMaterial({color:color[name],depthTest:false}));
      marker.name=name+' approximate '+j;marker.position.copy(p);marker.visible=false;root.add(marker);pivotMarkers.push(marker);
    }
    fingers[name]={parts,mcpNode,pipNode,dipNode,tip,curl:0};
  }
  const wristIds=[13,14,15,18,21,22,23],wrist=[];
  for(const n of wristIds){
    const mesh=meshMap.get(key(n));if(!mesh)throw Error('Отсутствует кандидат на кость запястья '+key(n));
    mesh.visible=true;
    if(n!==18)mesh.material=new THREE.MeshStandardMaterial({color:0xb8c6b8,roughness:.89,side:THREE.DoubleSide});
    wrist.push(mesh);
  }
  // All four MCP/PIP/DIP chains share the exact same transform calculation.
  // The sign is taken from the already-screened index direction; joint axes
  // remain engineering estimates rather than author-provided MRI joint axes.
  const D=Math.PI/180;
  function setFinger(name,fraction){
    if(name==='index'){rig.setIndexCurl(fraction);return}
    const finger=fingers[name];if(!finger)throw Error('Unknown finger '+name);
    finger.curl=Math.max(0,Math.min(1,fraction));
    const a=digitAngles[name],x=sign*finger.curl*D;
    finger.mcpNode.rotation.x=x*a[0];
    finger.pipNode.rotation.x=x*a[1];
    finger.dipNode.rotation.x=x*a[2];
  }
  function digitCurls(){
    return {index:rig.metrics().indexCurl/100,
      middle:fingers.middle.curl,ring:fingers.ring.curl,little:fingers.little.curl};
  }
  let active='open';
  const presets={
    open:{thumb:'open',curls:{index:0,middle:0,ring:0,little:0},handle:false},
    oppose:{thumb:'oppose',curls:{index:.72,middle:.71,ring:.69,little:.65},handle:false},
    grasp:{thumb:'grasp',curls:{index:.88,middle:.88,ring:.84,little:.80},handle:true}
  };
  const origShowPivots=rig.showPivots;
  rig.showPivots=(on)=>{origShowPivots(on);pivotMarkers.forEach(p=>p.visible=on)};
  function pose(name){
    const p=presets[name];if(!p)throw Error('Unknown preset '+name);
    rig.poseReference(p.thumb);
    for(const [finger,level] of Object.entries(p.curls))setFinger(finger,level);
    rig.handle.visible=p.handle;
    root.updateMatrixWorld(true);active=name;
    return metrics();
  }
  function updateFinger(name,value){setFinger(name,value);active='custom';root.updateMatrixWorld(true);return metrics()}
  function setAllCurl(value){for(const name of ['index','middle','ring','little'])setFinger(name,value);root.updateMatrixWorld(true);active='custom';return metrics()}
  function showFingers(on){
    for(const mesh of Object.values(rig.index))mesh.visible=on;
    for(const finger of Object.values(fingers))
      for(const mesh of Object.values(finger.parts))mesh.visible=on;
    rig.bone.trapezium.visible=true;
  }
  function showWrist(on){wrist.forEach(w=>w.visible=on)}
  const showContext=(on)=>{showFingers(on);showWrist(on)};
  function metrics(){
    root.updateMatrixWorld(true);
    const base=rig.metrics();
    const points={index:base.indexTip};
    for(const [name,obj] of Object.entries(fingers))points[name]=obj.tip.getWorldPosition(new THREE.Vector3()).toArray();
    const c=digitCurls();
    return {...base,digitCurls:c,fingerTipPositions:points,pose:active,
      digitCount:5,actualHandBones:19,carpalMeshesDisplayed:wrist.length,
      sourceGeometryUnmodified:true,
      calibratedJointAxes:false,
      note:'Finger MCP/PIP/DIP pivots are approximate bone-surface points; no skin or collision dynamics'};
  }
  pose('open');
  showWrist(true);
  return {...rig,poseFull:pose,updateFinger,setAllCurl,metrics,showFingers,showWrist,showContext,
    handPresets:presets,fingers,wrist,fingerNames:{index:'Указательный',...text},
    actualHandBones:19};
}
