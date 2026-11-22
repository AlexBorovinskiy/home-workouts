// Optional CC0 smooth hand overlays for the anatomical exercise viewer.
// Imported 16-bone Innerscene/MakeHuman skinned hand; aligned to the existing
// Heatsy hand rig. Source: HAND-CC0-NOTICE.txt. Experimental, not training-approved.
const DIGITS=['index','middle','ring','pinky','thumb'];
const SEGMENTS=['01','02','03'];
const SKIN_URL='./assets/skin-hand-right.cc0.glb';
const copyQ=(THREE,array)=>new THREE.Quaternion().fromArray(array).normalize();

export async function createSkinHandPreview({THREE,GLTFLoader,scene,rig,rest,bodyMesh}){
  if(!rig['hand.L']||!rig['hand.R']||!bodyMesh?.isSkinnedMesh)throw Error('No skinned hands or anatomical body');
  const overlayItems=[];
  const sourceLoader=new GLTFLoader();
  for(const side of ['R','L']){
    const gltf=await sourceLoader.loadAsync(SKIN_URL);
    const source=gltf.scene;
    source.updateMatrixWorld(true);
    const srcHand=source.getObjectByName('hand_r');
    if(!srcHand||!srcHand.isBone)throw Error('CC0 asset has no 16-bone hand_r rig');
    const srcHandRestInRoot=source.matrixWorld.clone().invert().multiply(srcHand.matrixWorld);
    const inverseSourceHandRest=srcHandRestInRoot.clone().invert();
    const fingers=[];
    const srcRestRelative={hand_r:new THREE.Quaternion()};
    const srcCurrentRelative={};
    const srcRestLocal={};
    for(const finger of DIGITS){
      for(const seg of SEGMENTS){
        const name=finger+'_'+seg+'_r';
        const b=source.getObjectByName(name);
        const target=rig[finger+'_'+seg+'.'+side];
        if(!b?.isBone||!target)throw Error('Missing bone '+name+' / '+finger+'_'+seg+'.'+side);
        const parentRest=srcRestRelative[b.parent.name]||new THREE.Quaternion();
        const localRest=b.quaternion.clone();
        srcRestLocal[name]=localRest;
        srcRestRelative[name]=parentRest.clone().multiply(localRest);
        fingers.push({src:b,targetName:finger+'_'+seg+'.'+side,name,parentName:b.parent.name});
      }
    }
    source.traverse(o=>{
      if(o.isSkinnedMesh){
        const materials=Array.isArray(o.material)?o.material:[o.material];
        o.material=materials.map(()=>new THREE.MeshStandardMaterial({
          color:0xd6aba0,roughness:.87,metalness:0,side:THREE.DoubleSide
        }));
        if(o.material.length===1)o.material=o.material[0];
        o.frustumCulled=false;
      }
    });
    const handTransformScale=new THREE.Matrix4().makeScale(side==='L'?-.87:.87,.87,.87);
    source.matrixAutoUpdate=false;
    scene.add(source);
    overlayItems.push({side,source,srcHand,inverseSourceHandRest,handTransformScale,fingers,srcRestRelative,srcCurrentRelative,srcRestLocal});
  }
  // Remove exposed source phalanges only when the skin overlay is visible.
  // Mask is calculated from the actual skinning weights, not from vertex height.
  const geom=bodyMesh.geometry,skinIndices=geom.getAttribute('skinIndex'),skinWeights=geom.getAttribute('skinWeight');
  const sourceBones=bodyMesh.skeleton.bones;
  if(!skinIndices||!skinWeights||!sourceBones)throw Error('Missing original anatomical skin weights');
  const fingerSet=new Set(sourceBones.map((b,i)=>i).filter(i=>/^(hand|index_|middle_|ring_|pinky_|thumb_)/i.test(sourceBones[i].name)));
  const mask=new Float32Array(geom.getAttribute('position').count);
  for(let i=0;i<mask.length;i++){
    let w=0;
    for(let j=0;j<4;j++){
      const idx=skinIndices.getComponent(i,j);
      if(fingerSet.has(idx))w+=skinWeights.getComponent(i,j);
    }
    mask[i]=Math.min(1,Math.max(0,w));
  }
  geom.setAttribute('aSkinnedHandMask',new THREE.BufferAttribute(mask,1));
  const uniform={value:1};
  const material=bodyMesh.material;
  const oldCompile=material.onBeforeCompile?.bind(material);
  material.onBeforeCompile=(shader,renderer)=>{
    if(oldCompile)oldCompile(shader,renderer);
    shader.uniforms.uSkinHandCover=uniform;
    shader.vertexShader='attribute float aSkinnedHandMask; varying float vSkinnedHandMask;\n'
      +shader.vertexShader.replace('void main() {','void main() {\n vSkinnedHandMask=aSkinnedHandMask;');
    shader.fragmentShader='varying float vSkinnedHandMask; uniform float uSkinHandCover;\n'
      +shader.fragmentShader.replace('void main() {','void main() {\n if (uSkinHandCover > 0.5 && vSkinnedHandMask > 0.51) discard;');
  };
  material.needsUpdate=true;
  const inverse=new THREE.Quaternion();
  const qTargetHand=new THREE.Quaternion(),qTargetBone=new THREE.Quaternion();
  const qRestHand={},qRestBone={},qDelta=new THREE.Quaternion(),qDesired=new THREE.Quaternion();
  for(const side of ['L','R']){
    const hand=rest['hand.'+side];
    qRestHand[side]=hand.parentWorldQ.clone().multiply(hand.quat);
    for(const item of overlayItems.find(v=>v.side===side).fingers){
      const j=rest[item.targetName];
      qRestBone[item.targetName]=j.parentWorldQ.clone().multiply(j.quat);
    }
  }
  let enabled=true;
  const update=()=>{
    if(!enabled)return;
    scene.updateMatrixWorld(true);
    for(const hand of overlayItems){
      const {side,source,inverseSourceHandRest,handTransformScale,fingers,srcRestRelative,srcCurrentRelative}=hand;
      const targetHand=rig['hand.'+side];
      const currentTargetHand=targetHand.getWorldQuaternion(qTargetHand).clone();
      const inverseCurrentHand=currentTargetHand.clone().invert();
      const inverseRestHand=qRestHand[side].clone().invert();
      for(const joint of fingers){
        const target=rig[joint.targetName];
        const targetRelNow=inverseCurrentHand.clone().multiply(target.getWorldQuaternion(qTargetBone));
        const targetRelRest=inverseRestHand.clone().multiply(qRestBone[joint.targetName]);
        qDelta.copy(targetRelNow).multiply(targetRelRest.invert()).normalize();
        if(side==='L'){qDelta.y*=-1;qDelta.z*=-1;} // reflect axial rotation across local X
        qDesired.copy(qDelta).multiply(srcRestRelative[joint.name]).normalize();
        const parentRel=joint.parentName==='hand_r'?new THREE.Quaternion():srcCurrentRelative[joint.parentName];
        if(!parentRel)throw Error('Source finger hierarchy missing '+joint.parentName);
        joint.src.quaternion.copy(parentRel).invert().multiply(qDesired).normalize();
        srcCurrentRelative[joint.name]=qDesired.clone();
      }
      source.matrix.copy(targetHand.matrixWorld).multiply(handTransformScale).multiply(inverseSourceHandRest);
      source.updateMatrixWorld(true);
    }
  };
  function setEnabled(flag){
    enabled=!!flag;uniform.value=enabled?1:0;
    for(const item of overlayItems)item.source.visible=enabled;
    if(enabled)update();
  }
  update();
  return {update,setEnabled,isEnabled:()=>enabled,maskedVertices:mask.filter(x=>x>.5).length,overlays:overlayItems};
}
