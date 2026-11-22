// Experimental: bind both CC0 skinned glove meshes to the SAME body skeleton.
// Preview only. The teaching lesson remains unchanged.
const URI='./assets/skin-hand-right.cc0.glb';
export async function createSkinHandPreview({THREE,GLTFLoader,scene,rig,rest,bodyMesh}){
  const pose=Object.entries(rig).map(([name,b])=>[b,b.quaternion.clone(),b.position.clone()]);
  const overlays=[];
  let covered=0,uniform={value:1};
  try{
    for(const [name,b] of Object.entries(rig)){b.quaternion.copy(rest[name].quat);b.position.copy(rest[name].pos)}
    scene.updateMatrixWorld(true);
    const gltf=await new GLTFLoader().loadAsync(URI),source=gltf.scene;
    source.updateMatrixWorld(true);
    let donor=null;source.traverse(o=>{if(o.isSkinnedMesh)donor=o});
    const srcHand=source.getObjectByName('hand_r');
    if(!donor||!srcHand||!donor.skeleton)throw Error('No source glove skeleton');
    const sourceBones=donor.skeleton.bones;
    const bodyIndex=new Map(bodyMesh.skeleton.bones.map((b,i)=>[b,i]));
    const srcHandInv=srcHand.matrixWorld.clone().invert();
    const meshInv=bodyMesh.matrixWorld.clone().invert();
    const sourcePositions=donor.geometry.getAttribute('position');
    const sourceIndices=donor.geometry.getAttribute('skinIndex');
    const sourceWeights=donor.geometry.getAttribute('skinWeight');
    if(!sourcePositions||!sourceIndices||!sourceWeights)throw Error('Missing source skinning attributes');
    for(const side of ['L','R']){
      const hand=rig['hand.'+side],handInv=hand.matrixWorld.clone().invert();
      const scale=new THREE.Matrix4().makeScale(side==='L'?-.87:.87,.87,.87);
      const targetBones=sourceBones.map(b=>rig[b.name==='hand_r'?'hand.'+side:b.name.replace(/_r$/,'.'+side)]);
      if(targetBones.some(b=>!b))throw Error('Missing target finger bone: '+side);
      const maps=sourceBones.map((b,j)=>{
        const from=scale.clone().multiply(srcHandInv).multiply(b.matrixWorld);
        const to=handInv.clone().multiply(targetBones[j].matrixWorld);
        return to.multiply(from.invert());
      });
      const geo=donor.geometry.clone();
      const positions=new Float32Array(sourcePositions.count*3),indices=new Uint16Array(sourcePositions.count*4);
      const p=new THREE.Vector3(),v=new THREE.Vector3(),sum=new THREE.Vector3();
      for(let i=0;i<sourcePositions.count;i++){
        p.fromBufferAttribute(sourcePositions,i);
        donor.applyBoneTransform(i,p);
        donor.localToWorld(p);
        p.applyMatrix4(srcHandInv).applyMatrix4(scale);
        sum.set(0,0,0);
        for(let j=0;j<4;j++){
          const originalIndex=sourceIndices.getComponent(i,j),weight=sourceWeights.getComponent(i,j);
          if(!weight)continue;
          v.copy(p).applyMatrix4(maps[originalIndex]).multiplyScalar(weight);
          sum.add(v);
          const targetIndex=bodyIndex.get(targetBones[originalIndex]);
          if(targetIndex===undefined)throw Error('Target joint index not found');
          indices[i*4+j]=targetIndex;
        }
        // Heatsy body positions are unnormalized 1e-4m KHR_mesh_quantization units.
        sum.applyMatrix4(hand.matrixWorld).applyMatrix4(meshInv).multiplyScalar(10000);
        const k=i*3;positions[k]=sum.x;positions[k+1]=sum.y;positions[k+2]=sum.z;
      }
      geo.setAttribute('position',new THREE.BufferAttribute(positions,3));
      geo.setAttribute('skinIndex',new THREE.BufferAttribute(indices,4));
      geo.computeVertexNormals();geo.computeBoundingSphere();
      const glove=new THREE.SkinnedMesh(geo,new THREE.MeshStandardMaterial({color:0xd6aba0,roughness:.87,metalness:0,side:THREE.DoubleSide}));
      glove.bindMode=bodyMesh.bindMode;
      glove.bind(bodyMesh.skeleton,bodyMesh.bindMatrix);
      glove.frustumCulled=false;glove.name='unified-glove-'+side;
      bodyMesh.add(glove);overlays.push(glove);
    }
    const originalIndices=bodyMesh.geometry.getAttribute('skinIndex');
    const originalWeights=bodyMesh.geometry.getAttribute('skinWeight');
    const bodySkeleton=bodyMesh.skeleton.bones;
    const fingerSet=new Set(bodySkeleton.map((b,i)=>/^(hand|index_|middle_|ring_|pinky_|thumb_)/.test(b.name)?i:-1).filter(i=>i>=0));
    const mask=new Float32Array(bodyMesh.geometry.getAttribute('position').count);
    for(let i=0;i<mask.length;i++){
      let weight=0;
      for(let j=0;j<4;j++)if(fingerSet.has(originalIndices.getComponent(i,j)))weight+=originalWeights.getComponent(i,j);
      mask[i]=Math.min(1,Math.max(0,weight));
      if(mask[i]>.5)covered++;
    }
    bodyMesh.geometry.setAttribute('aSkinnedHandMask',new THREE.BufferAttribute(mask,1));
    const mat=bodyMesh.material,oldCompile=mat.onBeforeCompile?.bind(mat);
    mat.onBeforeCompile=(shader,renderer)=>{
      if(oldCompile)oldCompile(shader,renderer);
      shader.uniforms.uSkinHandCover=uniform;
      shader.vertexShader='attribute float aSkinnedHandMask; varying float vSkinnedHandMask;\n'+shader.vertexShader.replace('void main() {','void main() {\n vSkinnedHandMask=aSkinnedHandMask;');
      shader.fragmentShader='varying float vSkinnedHandMask; uniform float uSkinHandCover;\n'+shader.fragmentShader.replace('void main() {','void main() {\n if (uSkinHandCover > 0.5 && vSkinnedHandMask > 0.51) discard;');
    };mat.needsUpdate=true;
  }finally{
    for(const [bone,q,p] of pose){bone.quaternion.copy(q);bone.position.copy(p)}
    scene.updateMatrixWorld(true);
  }
  if(overlays.length!==2)throw Error('Could not generate both body-rigged gloves');
  let enabled=true;
  return {update(){},setEnabled(flag){enabled=!!flag;uniform.value=enabled?1:0;overlays.forEach(o=>o.visible=enabled)},
    isEnabled:()=>enabled,maskedVertices:covered,overlays};
}
