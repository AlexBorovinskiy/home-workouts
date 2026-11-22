// Thumb Lab v2: actual MRI thumb + full articulated index finger, shared anatomical joints.
// The index finger is added because the user's open vs closed reference photographs
// show BOTH digits moving. Bones remain unchanged; only rigid transformations are applied.
// Geometry-derived joint midpoints are approximate; no physiological validation is claimed.
import {createMRIThumbRig} from './thumb-mri-rig.js';
export function createReferenceGripRig(THREE,gltf,landmarks){
 const base=createMRIThumbRig(THREE,gltf,landmarks);
 const root=base.root;
 // This is a joint study, not a dumbbell product render: weight plates obstruct
 // the bones in mobile side-view. Keep only the handle as a passive reference.
 for(const part of base.handle.children.slice(1))part.visible=false;
 const all=new Map();
 root.traverse(o=>{if(o.isMesh&&o.name.startsWith('segment_'))all.set(o.name,o)});
 const names={
   metacarpal:'segment_01_unlabeled',
   prox:'segment_09_unlabeled',
   mid:'segment_20_unlabeled',
   dist:'segment_27_unlabeled'
 };
 for(const [k,id] of Object.entries(names))if(!all.has(id))throw Error('Отсутствует костный сегмент указательного пальца: '+id);
 const index=Object.fromEntries(Object.entries(names).map(([k,id])=>[k,all.get(id)]));
 const surface=new THREE.MeshStandardMaterial({color:0x9ecce1,roughness:.76,side:THREE.DoubleSide});
 for(const mesh of Object.values(index)){mesh.visible=true;mesh.material=surface.clone()}
 // Actual neighboring bone-surface midpoints, in GLB metres (not clinically measured joint centers).
 const mcp=new THREE.Vector3(.02060,.00542,.01168);
 const pip=new THREE.Vector3(.02858,.00766,.05286);
 const dip=new THREE.Vector3(.03121,.00804,.07640);
 const pivot=(name,parent,local)=>{const node=new THREE.Group();node.name=name;node.position.copy(local);parent.add(node);return node};
 const mcpNode=pivot('Index MCP approximate pivot',root,mcp);
 root.updateMatrixWorld(true);mcpNode.attach(index.prox);
 const pipNode=pivot('Index PIP approximate pivot',mcpNode,pip.clone().sub(mcp));
 root.updateMatrixWorld(true);pipNode.attach(index.mid);
 const dipNode=pivot('Index DIP approximate pivot',pipNode,dip.clone().sub(pip));
 root.updateMatrixWorld(true);dipNode.attach(index.dist);
 root.updateMatrixWorld(true);
 const attr=index.dist.geometry.attributes.position;
 const p=new THREE.Vector3(),world=new THREE.Vector3(),localTip=new THREE.Vector3();
 let maxZ=-Infinity;
 for(let i=0;i<attr.count;i++){
   p.fromBufferAttribute(attr,i);
   world.copy(p).applyMatrix4(index.dist.matrixWorld);
   if(world.z>maxZ){maxZ=world.z;localTip.copy(p)}
 }
 const tip=new THREE.Object3D();tip.position.copy(localTip);tip.name='Index bone distal landmark';
 index.dist.add(tip);
 const DEG=Math.PI/180;
 const indexPivotMarkers=[];
 for(const [n,position] of [['MCP',mcp],['PIP',pip],['DIP',dip]]){
   const marker=new THREE.Mesh(new THREE.SphereGeometry(.0016,10,8),
     new THREE.MeshBasicMaterial({color:0x8ee3f6,depthTest:false}));
   marker.name='index '+n+' surface midpoint';marker.position.copy(position);
   marker.visible=false;root.add(marker);indexPivotMarkers.push(marker);
 }
 // Choice of the palmar direction is made from the photographed end-effector relation:
 // test both signs in the MRI coordinate frame rather than assuming +/-X is palmar.
 let flexSign=1,idxCurl=0;
 function setIndex(c,sign=flexSign){
   idxCurl=Math.min(1,Math.max(0,c));
   mcpNode.rotation.x=sign*65*DEG*idxCurl;
   pipNode.rotation.x=sign*92*DEG*idxCurl;
   dipNode.rotation.x=sign*35*DEG*idxCurl;
   root.updateMatrixWorld(true);
 }
 function boneTipDistances(){
   root.updateMatrixWorld(true);
   const idx=tip.getWorldPosition(new THREE.Vector3());
   const thumb=base.tipMarker.getWorldPosition(new THREE.Vector3());
   return {
     indexTip:idx.toArray(),
     thumbTip:thumb.toArray(),
     boneTipDistanceMm:Number(idx.distanceTo(thumb)*1000).toFixed(2)
   };
 }
 // The reference with a curled index finger is less like an open hand;
 // choose bend sign that brings the index toward, not away from, the thumb.
 base.pose(base.PRESETS.oppose);
 let best=Infinity;
 for(const sign of [1,-1]){
   setIndex(.9,sign);
   const val=Number(boneTipDistances().boneTipDistanceMm);
   if(val<best){best=val;flexSign=sign}
 }
 setIndex(0);
 base.pose(base.PRESETS.neutral);
 const referencePresets={
   open:{thumb:{...base.PRESETS.neutral},indexCurl:0},
   oppose:{thumb:{...base.PRESETS.oppose},indexCurl:.72},
   grasp:{thumb:{...base.PRESETS.grasp},indexCurl:.95}
 };
 let preset='open';
 function pose(name){
   if(!(name in referencePresets))throw Error('Неизвестная поза '+name);
   const state=referencePresets[name];
   base.pose(state.thumb);setIndex(state.indexCurl);
   preset=name;
   return metrics();
 }
 function setIndexCurl(value){setIndex(value);preset='custom';return metrics()}
 function metrics(){
   const thumb=base.metrics();
   const tips=boneTipDistances();
   return {...thumb,...tips,
      indexCurl:Number((idxCurl*100).toFixed(1)),
      indexFlexSign:flexSign,
      boneSurfacesFromMRI:8,
      referencePose:preset,
      opponentRelationValidated:false,
      note:'Distance between index and thumb BONE tips, not fleshy finger pads'
   };
 }
 function showIndex(visible){for(const mesh of Object.values(index))mesh.visible=visible;}
 const origPivots=base.showPivots;
 base.showPivots=(visible)=>{origPivots(visible);indexPivotMarkers.forEach(m=>m.visible=visible)};
 base.showContext=(visible)=>showIndex(visible);
 pose('open');
 return {...base,index,indexJoints:{mcpNode,pipNode,dipNode},indexTip:tip,
   poseReference:pose,setIndexCurl,metrics,referencePresets,getIndexSign:()=>flexSign,
   showIndex,referenceStudy:'open hand vs closed index/contralateral thumb'}
}
