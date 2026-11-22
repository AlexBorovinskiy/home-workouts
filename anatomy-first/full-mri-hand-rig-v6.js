// Anatomy First v6: palm-anchored reference grip with mesh collision constraints, using original MRI-derived bone surfaces.
// 19 metacarpals + phalanges (5+14), seven provisionally named carpals.
// Missing separate pisiform is NEVER invented. Approximate joint midpoints are
// used as temporary 3-DOF scene pivots, NOT clinical bone kinematics.
import {createMRIThumbRig} from './thumb-mri-rig.js';

const ids={
  index:{metacarpal:1,prox:9,mid:20,dist:27},
  middle:{metacarpal:2,prox:8,mid:16,dist:25},
  ring:{metacarpal:4,prox:7,mid:17,dist:26},
  little:{metacarpal:5,prox:11,mid:24,dist:28}
};
const text={index:'Указательный',middle:'Средний',ring:'Безымянный',little:'Мизинец'};
const color={index:0x9ecce1,middle:0x9ecdad,ring:0xc9b6e6,little:0xe4c8a0};
// Experimental grip angle targets (degrees). Fitted to MRI joint-chain positions
// for a 22 mm handle; NOT clinically validated limits or motion-capture data.
// The MCP must not close as fast as PIP, or fingertips pass below the shaft.
const digitAngles={index:[60,108,45],middle:[58,110,45],ring:[60,110,48],little:[63,112,50]};

export function createFullMRIHandRigV6(THREE,gltf,landmarks,jointData){
  const rig=createMRIThumbRig(THREE,gltf,landmarks);
  const root=rig.root;
  // Reference video: transverse handle lies over the distal palm, not at fingertips.
  rig.handle.position.set(.010,-.022,.005);
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
  // Provisional palmar normal inferred from experimental thumb opposition; not MRI-validated.
  const palmNormal=new THREE.Vector3(0,-1,0);
  const hinge=(start,end)=>new THREE.Vector3().crossVectors(end.clone().sub(start),palmNormal).normalize();
  for(const name of ['index','middle','ring','little']){
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
    fingers[name]={parts,mcpNode,pipNode,dipNode,tip,curl:0,
      axes:{mcp:hinge(mcp,pip),pip:hinge(pip,dip),dip:hinge(pip,dip)}};
  }
  const wristIds=[13,14,15,18,21,22,23],wrist=[];
  for(const n of wristIds){
    const mesh=meshMap.get(key(n));if(!mesh)throw Error('Отсутствует кандидат на кость запястья '+key(n));
    mesh.visible=true;
    if(n!==18)mesh.material=new THREE.MeshStandardMaterial({color:0xb8c6b8,roughness:.89,side:THREE.DoubleSide});
    wrist.push(mesh);
  }
  // All four fingers use one model. Each hinge follows that finger's MRI bone direction
  // instead of rotating every joint around a universal world-X axis.
  const D=Math.PI/180;
  function setFinger(name,fraction){
    const f=fingers[name];
    if(!f)throw Error('Unknown finger '+name);
    f.curl=Math.max(0,Math.min(1,Number(fraction)||0));
    const a=digitAngles[name];
    f.mcpNode.quaternion.setFromAxisAngle(f.axes.mcp,f.curl*a[0]*D);
    f.pipNode.quaternion.setFromAxisAngle(f.axes.pip,f.curl*a[1]*D);
    f.dipNode.quaternion.setFromAxisAngle(f.axes.dip,f.curl*a[2]*D);
  }

  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  function setFingerAngles(name,angles){
    const f=fingers[name],a=angles.map(Number);
    f.angles=a.slice();
    f.mcpNode.quaternion.setFromAxisAngle(f.axes.mcp,a[0]*D);
    f.pipNode.quaternion.setFromAxisAngle(f.axes.pip,a[1]*D);
    f.dipNode.quaternion.setFromAxisAngle(f.axes.dip,a[2]*D);
    root.updateMatrixWorld(true);
  }
  // A real grip must keep the whole bone surface OUTSIDE the shaft,
  // with several mm for soft tissue. Fitting only fingertips produced false positives.
  function meshClearancePenalty(meshes){
    const h=rig.handle.position,v=new THREE.Vector3();
    let penalty=0;
    for(const mesh of meshes){
      const a=mesh.geometry.attributes.position;
      for(let i=0;i<a.count;i+=Math.max(1,Math.ceil(a.count/95))){
        v.fromBufferAttribute(a,i).applyMatrix4(mesh.matrixWorld);
        if(Math.abs(v.x-h.x)>.079)continue;
        const radial=Math.hypot(v.y-h.y,v.z-h.z);
        const deficiency=Math.max(0,(.014-radial)*1000);
        penalty+=deficiency*deficiency*.13;
      }
    }
    return penalty;
  }
  const targets={
    index:{y:-.030,z:-.004},middle:{y:-.031,z:-.004},
    ring:{y:-.029,z:-.005},little:{y:-.027,z:-.006}
  };
  // Offline-fitted IK joint angles from mobile visual + bone-surface QA.
  // Do NOT rerun a multi-second optimizer on the user's iPhone.
  let fitted={
    fingers:{
      index:{angles:[69.4,88.4,68],residualMm:4.28},
      middle:{angles:[59,110,45],residualMm:3.15},
      ring:{angles:[54.4,110,49.8],residualMm:4.21},
      little:{angles:[35,88.4,56.6],residualMm:25.07}
    },
    thumb:{pose:{abduct:-16,cmcFlex:41,cmcRotate:18,mcpFlex:30,ipFlex:45},residualMm:13.42}
  };
  function fitDigit(name){
    const f=fingers[name],expected=digitAngles[name],goal=targets[name];
    const bounds=[[35,78],[88,128],[25,68]];
    let a=expected.slice();
    const tip=new THREE.Vector3();
    function cost(v){
      setFingerAngles(name,v);
      f.tip.getWorldPosition(tip);
      const dz=(tip.z-goal.z)*1000,dy=(tip.y-goal.y)*1000;
      const balance=.035*Math.hypot(v[0]-expected[0],v[1]-expected[1],v[2]-expected[2]);
      return Math.hypot(dz,dy)+balance+meshClearancePenalty([f.parts.prox,f.parts.mid,f.parts.dist]);
    }
    let best=cost(a);
    for(const step of [20,10,5,2,1,.4]){
      let improved=true,tries=0;
      while(improved&&tries++<8){
        improved=false;
        for(let j=0;j<3;j++)for(const sign of [-1,1]){
          const b=a.slice();
          b[j]=clamp(b[j]+sign*step,...bounds[j]);
          const score=cost(b);
          if(score<best-1e-6){best=score;a=b;improved=true;}
        }
      }
    }
    setFingerAngles(name,a);
    return {angles:a,residualMm:Number(best.toFixed(2))};
  }
  function fitThumb(){
    const keys=['abduct','cmcFlex','cmcRotate','mcpFlex','ipFlex'];
    const bounds=[[-25,35],[-15,55],[-45,45],[-15,45],[-15,45]];
    const goal=new THREE.Vector3(.020,-.033,.023);
    const seeds=[
      [8,20,10,8,8],[18,35,22,30,25],[20,45,-20,35,25],
      [-15,35,25,35,25],[15,50,35,45,40],[0,40,-35,60,55],
      [25,25,-25,50,35],[-20,50,-15,60,60]
    ];
    let best=Infinity,answer=null;
    const target=()=>rig.tipMarker.getWorldPosition(new THREE.Vector3());
    function measure(a){
      rig.pose(Object.fromEntries(keys.map((k,i)=>[k,a[i]])));
      const t=target();
      const mm=t.distanceTo(goal)*1000;
      // Prefer anatomically moderate control magnitudes when positions agree.
      return mm+.015*Math.hypot(a[0],a[1],a[2],a[3],a[4])+
        meshClearancePenalty([rig.bone.mc1,rig.bone.prox,rig.bone.distal]);
    }
    for(const seed of seeds){
      let a=seed.map((val,i)=>clamp(val,...bounds[i])),v=measure(a);
      for(const step of [22,11,5,2,1]){
        let keep=true,n=0;
        while(keep&&n++<7){
          keep=false;
          for(let k=0;k<5;k++)for(const sign of [-1,1]){
            const b=a.slice();b[k]=clamp(b[k]+sign*step,...bounds[k]);
            const candidate=measure(b);
            if(candidate<v-.00001){a=b;v=candidate;keep=true;}
          }
        }
      }
      if(v<best){best=v;answer=a.slice();}
    }
    const pose=Object.fromEntries(keys.map((k,i)=>[k,answer[i]]));
    rig.pose(pose);
    return {pose,residualMm:Number(best.toFixed(2))};
  }
  function fitAll(){
    const result={fingers:{},thumb:null};
    for(const name of ['index','middle','ring','little']){
      result.fingers[name]=fitDigit(name);
    }
    result.thumb=fitThumb();
    return result;
  }
  function digitCurls(){
    return Object.fromEntries(Object.entries(fingers).map(([name,f])=>[name,f.curl]));
  }
  let active='open';
  const presets={
    open:{fraction:0,handle:true},
    oppose:{fraction:.33,handle:true},
    grasp:{fraction:1,handle:true}
  };
  const origShowPivots=rig.showPivots;
  rig.showPivots=(on)=>{origShowPivots(on);pivotMarkers.forEach(p=>p.visible=on)};
  function pose(name){
    const p=presets[name];if(!p)throw Error('Unknown preset '+name);
    if(name==='open'){
      for(const digit of ['index','middle','ring','little']){setFingerAngles(digit,[0,0,0]);fingers[digit].curl=0;}
      rig.pose(rig.PRESETS.neutral);
    }else{
      if(!fitted)fitted=fitAll();
      for(const digit of ['index','middle','ring','little']){
        const angles=fitted.fingers[digit].angles.map(deg=>deg*p.fraction);
        setFingerAngles(digit,angles);
        fingers[digit].curl=p.fraction;
      }
      const thumb=Object.fromEntries(
        Object.entries(fitted.thumb.pose).map(([key,val])=>[key,val*p.fraction]));
      rig.pose(thumb);
    }
    rig.handle.visible=true;
    root.updateMatrixWorld(true);active=name;
    return metrics();
  }
  function updateFinger(name,value){setFinger(name,value);active='custom';root.updateMatrixWorld(true);return metrics()}
  function setAllCurl(value){for(const name of ['index','middle','ring','little'])setFinger(name,value);root.updateMatrixWorld(true);active='custom';return metrics()}
  function showFingers(on){
    for(const finger of Object.values(fingers))
      for(const mesh of Object.values(finger.parts))mesh.visible=on;
    rig.bone.trapezium.visible=true;
  }
  function showWrist(on){wrist.forEach(w=>w.visible=on)}
  const showContext=(on)=>{showFingers(on);showWrist(on)};
  function metrics(){
    root.updateMatrixWorld(true);
    const base=rig.metrics();
    const points=Object.fromEntries(Object.entries(fingers).map(([name,f])=>[name,f.tip.getWorldPosition(new THREE.Vector3()).toArray()]));
    const thumb=rig.tipMarker.getWorldPosition(new THREE.Vector3());
    const index=new THREE.Vector3(...points.index);
    return {...base,indexTip:points.index,thumbTip:thumb.toArray(),
      boneTipDistanceMm:Number((thumb.distanceTo(index)*1000).toFixed(2)),
      indexCurl:Number((fingers.index.curl*100).toFixed(1)),
      digitCurls:digitCurls(),fingerTipPositions:points,pose:active,
      digitCount:5,actualHandBones:19,carpalMeshesDisplayed:wrist.length,
      sourceGeometryUnmodified:true,calibratedJointAxes:false,
      fittedGrip:fitted,
      fingerAxes:Object.fromEntries(Object.entries(fingers).map(([name,f])=>[name,Object.fromEntries(Object.entries(f.axes).map(([joint,v])=>[joint,v.toArray()]))])),
      note:'Reference-video-inspired IK hand: numerical fit to distal palm shaft, with provisional joints; skin collision not simulated.'};
  }
  pose('open');
  showWrist(true);
  return {...rig,poseFull:pose,updateFinger,setAllCurl,setFingerAngles,fitAll,metrics,showFingers,showWrist,showContext,
    handPresets:presets,fingers,wrist,getIndexSign:()=>1,fingerNames:text,
    actualHandBones:19};
}
