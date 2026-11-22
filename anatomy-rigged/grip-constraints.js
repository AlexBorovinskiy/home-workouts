// Home Workouts — reusable dumbbell hand-grip fitting (experimental).
// Fits the skinned rig's finger-bone endpoints around actual cylinder geometry.
// No hand/finger poses are assumed anatomically certified. Fallback is the source pose.
const DIGITS=['index','middle','ring','pinky'];
const BOUNDS_FINGER=[[-120,-35],[-125,-20],[-100,5],[-35,35]];
const BOUNDS_THUMB=[[-50,35],[-90,-30],[0,90],[-45,70]];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const clone=(obj)=>JSON.parse(JSON.stringify(obj));
const round=v=>Math.round(v*10)/10;

export async function fitDumbbellGrip({THREE,rig,dumbbells,initialPose,applyPose,onProgress}){
  if(!rig||!Array.isArray(dumbbells)||!dumbbells.length||typeof applyPose!=='function')
    return {ok:false,patch:{},measurements:[],reason:'Не найден скелет или рукоятки'};
  const oldPose=clone(initialPose),patch={},measurements=[];
  const sceneV=new THREE.Vector3(),localV=new THREE.Vector3();
  const v3=(obj)=>obj.clone();
  // Independent hand-local cylinder origins: each dumbbell is parented to its hand.
  function bonePoint(name,hand){const b=rig[name];if(!b)return null;
    b.getWorldPosition(sceneV);localV.copy(sceneV);return hand.worldToLocal(v3(localV));
  }
  function boneTip(name,hand){const b=rig[name];if(!b)return null;
    b.localToWorld(localV.set(0,.021,0));return hand.worldToLocal(v3(localV));
  }
  function scoreDigit(side,name,vals,center,base){
    const sample={...base};
    sample[name+'_01.'+side]=[vals[0],0,vals[3]]; // MCP abduction/adduction, not just flexion
    sample[name+'_02.'+side]=[vals[1],0,0];
    sample[name+'_03.'+side]=[vals[2],0,0];
    applyPose(sample);
    const hand=rig['hand.'+side],points=[];
    for(let i=1;i<=3;i++){
      const p=bonePoint(name+'_0'+i+'.'+side,hand);if(!p)return {cost:Infinity,gap:Infinity};
      points.push(p);
    }
    const tip=boneTip(name+'_03.'+side,hand);
    if(!tip)return {cost:Infinity,gap:Infinity};
    points.push(tip);
    const radial=p=>Math.hypot(p.y-center.y,p.z-center.z);
    const gap=Math.abs(radial(tip)-.012);
    // The resting digit roots are spaced ~2 cm apart across the handle.
    // Prevent the finger tips from fanning several centimetres away from their own roots.
    const goalX=points[0].x+(side==='L'?-0.004:0.004);
    const lateral=Math.abs(tip.x-goalX);
    let cost=330*Math.pow(tip.y-(center.y-.010),2)+210*Math.pow(tip.z-(center.z+.006),2);
    cost+=1100*Math.pow(tip.x-goalX,2)+280*Math.pow(points[2].x-goalX,2);
    cost+=600*Math.pow(radial(tip)-.012,2);
    // Avoid finger phalanges passing inside the 10 mm-radius handle.
    for(let i=0;i<3;i++){
      for(const t of [.25,.5,.75]){
        const p=v3(points[i]).lerp(points[i+1],t);
        const inner=Math.max(0,.0105-radial(p));
        cost+=950*inner*inner;
      }
    }
    // The middle phalanges should wrap over the outside, not hang below the bar.
    cost+=65*Math.pow(Math.max(0,center.z+.013-points[1].z),2);
    // Suppress over-extension / unnatural joint extremes.
    cost+=.00008*vals.reduce((sum,v,i)=>sum+Math.pow((v-[-85,-90,-40,0][i])/35,2),0);
    return {cost,gap,lateral,radius:radial(tip),tip:[tip.x,tip.y,tip.z]};
  }
  function scoreThumb(side,vals,center,base){
    const sample={...base};
    sample['thumb_01.'+side]=[vals[0],0,(side==='L'?1:-1)*vals[1]];
    sample['thumb_02.'+side]=[vals[2],0,0];
    sample['thumb_03.'+side]=[vals[3],0,0];
    applyPose(sample);
    const hand=rig['hand.'+side],points=[];
    for(let i=1;i<=3;i++){const p=bonePoint('thumb_0'+i+'.'+side,hand);if(!p)return {cost:Infinity,gap:Infinity};points.push(p)}
    const tip=boneTip('thumb_03.'+side,hand);if(!tip)return {cost:Infinity,gap:Infinity};
    points.push(tip);
    const radial=p=>Math.hypot(p.y-center.y,p.z-center.z);
    const gap=Math.abs(radial(tip)-.012);
    let cost=350*Math.pow(tip.y-(center.y+.008),2)+260*Math.pow(tip.z-(center.z-.008),2);
    cost+=700*Math.pow(radial(tip)-.012,2);
    // Keep opposition over the handle, inside the grippable region, with no deep penetration.
    cost+=100*Math.pow(Math.max(0,Math.abs(tip.x)-.060),2);
    for(let i=0;i<3;i++)for(const t of [.3,.6,.85]){
      const p=v3(points[i]).lerp(points[i+1],t),inside=Math.max(0,.0105-radial(p));
      cost+=900*inside*inside;
    }
    cost+=.00015*(Math.pow((vals[0]+15)/30,2)+Math.pow((vals[1]+70)/30,2)+Math.pow((vals[2]-42)/40,2)+Math.pow(vals[3]/50,2));
    return {cost,gap,radius:radial(tip),tip:[tip.x,tip.y,tip.z]};
  }
  function optimize(initial,bounds,evaluate){
    let best=initial.map((v,i)=>clamp(v,bounds[i][0],bounds[i][1]));
    let score=evaluate(best);
    for(const step of [18,8,3]){
      for(let pass=0;pass<2;pass++){
        let changed=false;
        for(let i=0;i<best.length;i++){
          let bestV=best[i],bestResult=score;
          for(const sign of [-1,1]){
            const v=clamp(best[i]+sign*step,bounds[i][0],bounds[i][1]);if(v===best[i])continue;
            const t=[...best];t[i]=v;const r=evaluate(t);
            if(r.cost<bestResult.cost){bestResult=r;bestV=v}
          }
          if(bestV!==best[i]){best[i]=bestV;score=bestResult;changed=true}
        }
        if(!changed)break;
      }
    }
    return {angles:best.map(round),score};
  }
  try{
    for(const side of ['L','R']){
      const hand=rig['hand.'+side],handle=dumbbells.find(g=>g.name==='training-dumbbell-'+side)||dumbbells[side==='L'?0:1];
      if(!hand||!handle)throw Error('Отсутствует кисть или гантель: '+side);
      const center=handle.position.clone();
      for(const finger of DIGITS){
        const base={...oldPose,...patch};
        const initial=[1,2,3].map(i=>base[finger+'_0'+i+'.'+side]?.[0]??[-85,-90,-40][i-1]);
        initial.push(base[finger+'_01.'+side]?.[2]??0);
        const solved=optimize(initial,BOUNDS_FINGER,vals=>scoreDigit(side,finger,vals,center,base));
        const valid=Number.isFinite(solved.score.cost)&&solved.score.gap<.016&&solved.score.lateral<.018;
        measurements.push({joint:finger+'.'+side,gap:round(solved.score.gap*1000),lateral:round(solved.score.lateral*1000),valid});
        if(valid){
          patch[finger+'_01.'+side]=[solved.angles[0],0,solved.angles[3]];
          patch[finger+'_02.'+side]=[solved.angles[1],0,0];
          patch[finger+'_03.'+side]=[solved.angles[2],0,0];
        }
        if(onProgress)onProgress(finger+'.'+side);
      }
      const base={...oldPose,...patch},initial=[
        base['thumb_01.'+side]?.[0]??-15,
        (base['thumb_01.'+side]?.[2]??(side==='L'?-70:70))*(side==='L'?1:-1),
        base['thumb_02.'+side]?.[0]??42,
        base['thumb_03.'+side]?.[0]??0
      ];
      const solved=optimize(initial,BOUNDS_THUMB,vals=>scoreThumb(side,vals,center,base));
      const valid=Number.isFinite(solved.score.cost)&&solved.score.gap<.016;
      measurements.push({joint:'thumb.'+side,gap:round(solved.score.gap*1000),valid});
      if(valid){
        patch['thumb_01.'+side]=[solved.angles[0],0,(side==='L'?1:-1)*solved.angles[1]];
        patch['thumb_02.'+side]=[solved.angles[2],0,0];
        patch['thumb_03.'+side]=[solved.angles[3],0,0];
      }
      if(onProgress)onProgress('thumb.'+side);
      // Give Safari a chance to repaint between hands.
      await new Promise(resolve=>requestAnimationFrame(resolve));
    }
    const good=measurements.filter(x=>x.valid).length;
    applyPose(oldPose);
    return {ok:good===measurements.length,patch,measurements,
      reason:good===measurements.length?'Подгонка пальцев к рукояткам выполнена':
      'Некоторые пальцы не удалось надёжно подогнать; оставлены исходные положения'};
  }catch(error){
    applyPose(oldPose);
    return {ok:false,patch:{},measurements,reason:String(error.message||error)};
  }
}