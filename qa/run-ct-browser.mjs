import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import http from 'node:http';

const output = path.resolve('qa-results');
await fs.mkdir(output,{recursive:true});
const logs=[];
const log=(...x)=>{const s=x.map(v=>typeof v==='string'?v:JSON.stringify(v)).join(' ');logs.push(new Date().toISOString()+' '+s);console.log(s)};
const server=spawn('python3',['-m','http.server','8765','--bind','127.0.0.1'],{stdio:'ignore'});
let browser,page,monitor;
const origin='http://127.0.0.1:8765';
const statuses=['status','ctStatus','cacheInfo','fhsStorage','thoraxStatus','pelvisStatus','femurStatus','lowerStatus','skullStatus','shoulderStatus','armFitStatus','rigStatus','axisStatus','depthStatus','depthBatchStatus','reportStatus'];
async function snapshot(){return page.evaluate(ids=>Object.fromEntries(ids.map(id=>[id,document.getElementById(id)?.textContent?.trim()||''])),statuses)}
async function waitServer(){
 for(let i=0;i<60;i++){
  const ok=await new Promise(resolve=>{
   const req=http.get(origin+'/',{agent:false},res=>{res.on('error',()=>resolve(false));res.on('end',()=>resolve(res.statusCode===200));res.resume()});
   req.on('error',()=>resolve(false));req.setTimeout(3000,()=>req.destroy());
  });
  if(ok)return;
  await new Promise(r=>setTimeout(r,500));
 }
 throw Error('Local HTTP server failed');
}
try{
 await waitServer();
 browser=await chromium.launch({headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1100,height:900},acceptDownloads:true});
 page=await context.newPage();
 page.on('pageerror',e=>log('PAGE ERROR',e.message));
 page.on('console',m=>{if(['error','warning'].includes(m.type()))log('CONSOLE',m.type(),m.text().slice(0,800))});
 page.on('requestfailed',r=>log('REQUEST FAILED',r.url(),r.failure()?.errorText));
 page.on('crash',()=>log('PAGE CRASHED'));
 // Seed the same IndexedDB key used by the app, before any model initialization.
 await page.route(origin+'/__qa_bootstrap',r=>r.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>QA bootstrap</title>'}));
 await page.goto(origin+'/__qa_bootstrap',{waitUntil:'domcontentloaded',timeout:60000});
 await page.evaluate(async()=>{
  const response=await fetch('/.qa-cache/fhs.zip');if(!response.ok)throw Error('FHS HTTP '+response.status);
  const blob=await response.blob();if(blob.size<1000)throw Error('Empty FHS');
  await new Promise((resolve,reject)=>{
   const req=indexedDB.open('home-workouts-fhs-data',1);
   req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('archive'))req.result.createObjectStore('archive')};
   req.onerror=()=>reject(req.error);
   req.onsuccess=()=>{const db=req.result,tx=db.transaction('archive','readwrite');tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('IDB aborted'));tx.objectStore('archive').put({blob,name:'FHS_dataset_4.x.zip'},'fhs-2026-scientific-zip')};
  });
 });
 log('FHS seeded');
 const auditSource="\nwindow.__hipCenterComparison=async()=>{\n const model=rigModel,fitModel=axisModel,ref=headData.sequences.find(s=>s.id===model.reference).frames[0];\n if(!model||!fitModel||!$(\"#kneeAxis\").checked||!$(\"#hipCenterFix\").checked)throw Error(\"Integrated fixes inactive\");\n const {MeshBVH}=await import(\"https://cdn.jsdelivr.net/npm/three-mesh-bvh@0.9.5/build/index.module.js\");collisionSelfTest(MeshBVH);depthSelfTest(MeshBVH);\n const rad=Math.PI/180,quant=(v,q)=>{const a=v.slice().sort((x,y)=>x-y);return a[Math.floor((a.length-1)*q)]};\n const matrixError=(a,b)=>Math.max(...a.elements.map((v,i)=>Math.abs(v-b.elements[i])));\n const refOld=rigDeltaModel(model,ref,false,true),refNew=rigDeltaModel(model,ref,false,false);\n const neutralError=Math.max(...[...refOld.moves].map(([b,m])=>matrixError(m,refNew.moves.get(b))));\n if(neutralError>1e-6)throw Error(\"Reference pose changed\");\n const poses=headData.sequences.flatMap(s=>s.frames.map((f,i)=>({f,sequence:s.id,frame:i+1,old:rigDeltaModel(model,f,false,true),candidate:rigDeltaModel(model,f,false,false)})));\n const sides={},pictures=[],oldKnee={};\n function relative(r,parent,child){return r.moves.get(parent).clone().invert().multiply(r.moves.get(child))}\n function sampled(g,n){const seen=new Set();return ctPoints(g,n).filter(p=>{const k=p.toArray().map(x=>Math.round(x*4000)).join(\",\");if(seen.has(k))return false;seen.add(k);return true})}\n function distances(points,tree,src,dst){const m=dst.clone().invert().multiply(src),d=points.map(p=>{const q=p.clone().applyMatrix4(m),v=tree.closestPointToPoint(q,{});if(!v||!Number.isFinite(v.distance))throw Error(\"Nearest surface failed\");return q.applyMatrix4(dst).distanceTo(v.point.clone().applyMatrix4(dst))*1000});return {sampleMin:Math.min(...d),near05:quant(d,.05),median:quant(d,.5),near95:quant(d,.95)}}\n for(const side of [\"r\",\"l\"]){\n  const po=collisionMesh(\"pelvis\",side.toUpperCase()),fo=collisionMesh(\"femur_\"+side),to=collisionMesh(\"tibia_\"+side,null,\"TIBIA_\"),ko=collisionMesh(\"patella_\"+side);\n  let pg=null,fg=null,tg=null,kg=null;\n  try{\n   pg=collisionTree(po,MeshBVH);fg=collisionTree(fo,MeshBVH);tg=collisionTree(to,MeshBVH);kg=collisionTree(ko,MeshBVH);\n   const pw0=collisionWorld(po,ref,ref,refOld),fw0=collisionWorld(fo,ref,ref,refOld);\n   const center=vec(hipCenterProfile[side]),radius=side===\"r\"?.025595593633801908:.02564221290754893;\n   const fem=sampled(fg,18000),head=fem.filter(p=>{const d=p.clone().applyMatrix4(fw0).distanceTo(center);return d>=radius-.004&&d<=radius+.003});\n   if(head.length<30)throw Error(\"Too few head surface samples\");\n   const joint=model.order.find(j=>j.child===\"femur_\"+side),anchor=model.anchors.get(joint.joint);\n   const patch=head.map(p=>({p,d:distances([p],pg.boundsTree,fw0,pw0).sampleMin})).sort((a,b)=>a.d-b.d).slice(0,Math.min(160,Math.max(30,Math.ceil(head.length*.15)))).map(x=>x.p);\n   function measure(x,r){\n    const pw=collisionWorld(po,ref,x.f,r),fw=collisionWorld(fo,ref,x.f,r),rel=relative(r,\"pelvis\",\"femur_\"+side);\n    const q=new THREE.Quaternion().setFromRotationMatrix(rel).normalize();\n    return {headDriftMm:center.clone().applyMatrix4(rel).distanceTo(center)*1000,relativeRotationDeg:2*Math.acos(Math.min(1,Math.abs(q.w)))/rad,headGap:distances(head,pg.boundsTree,fw,pw),fixedPatchGap:distances(patch,pg.boundsTree,fw,pw),hit:collisionHit(pg,fg,pw,fw)};\n   }\n   const series=[];let maxRotationError=0,maxKneeError=0,kneeHits=0,maxKneeProxyError=0;\n   const lm=tetherProfile[side],tub=vec(lm.tub),inf=vec(lm.inf),len=tub.distanceTo(inf)*1000;\n   for(const x of poses){\n    const a=measure(x,x.old),b=measure(x,x.candidate);\n    maxRotationError=Math.max(maxRotationError,matrixError(new THREE.Matrix4().extractRotation(relative(x.old,\"pelvis\",\"femur_\"+side)),new THREE.Matrix4().extractRotation(relative(x.candidate,\"pelvis\",\"femur_\"+side))));\n    for(const child of [\"tibia_\",\"patella_\",\"talus_\",\"calcn_\",\"toes_\"])maxKneeError=Math.max(maxKneeError,matrixError(relative(x.old,\"femur_\"+side,child+side),relative(x.candidate,\"femur_\"+side,child+side)));\n    const fw=collisionWorld(fo,ref,x.f,x.candidate),tw=collisionWorld(to,ref,x.f,x.candidate),kw=collisionWorld(ko,ref,x.f,x.candidate);\n    kneeHits+=+(collisionHit(fg,tg,fw,tw)||collisionHit(fg,kg,fw,kw)||collisionHit(tg,kg,tw,kw));\n    const proxy=inf.clone().applyMatrix4(x.candidate.moves.get(\"patella_\"+side)).distanceTo(tub.clone().applyMatrix4(x.candidate.moves.get(\"tibia_\"+side)))*1000;\n    maxKneeProxyError=Math.max(maxKneeProxyError,Math.abs(proxy-len));\n    series.push({sequence:x.sequence,frame:x.frame,old:a,candidate:b});\n    if(series.length%20===0)await new Promise(r=>setTimeout(r,0));\n   }\n   function summary(key){const rows=series.map(x=>x[key]);return {frames:rows.length,intersectionFrames:rows.filter(x=>x.hit).length,maxHeadDriftMm:Math.max(...rows.map(x=>x.headDriftMm)),maxRelativeRotationDeg:Math.max(...rows.map(x=>x.relativeRotationDeg)),maxHeadNear05Mm:Math.max(...rows.map(x=>x.headGap.near05)),maxFixedPatchMedianMm:Math.max(...rows.map(x=>x.fixedPatchGap.median))}}\n   const before=summary(\"old\"),after=summary(\"candidate\");\n   // Rank collision burden using exact surface triangle-pair counts at every sampled pose.\n   // For selected worst frames, use the same local parity depth estimator as run 9.\n   const burden=[];\n   for(const x of poses){\n    const row={sequence:x.sequence,frame:x.frame};\n    for(const key of [\"old\",\"candidate\"]){\n     const r=x[key],pw=collisionWorld(po,ref,x.f,r),fw=collisionWorld(fo,ref,x.f,r);\n     const lines=depthLines(pg,fg,pw.clone().invert().multiply(fw),pw);\n     row[key]={triangleHits:lines.hits,truncated:lines.truncated};\n    }\n    burden.push(row);if(burden.length%20===0)await new Promise(r=>setTimeout(r,0));\n   }\n   const worst=(key)=>burden.reduce((a,b)=>b[key].triangleHits>a[key].triangleHits?b:a,burden[0]);\n   const worstDrift=series.reduce((a,b)=>b.old.headDriftMm>a.old.headDriftMm?b:a,series[0]);\n   const selections=[{type:\"neutral\",sequence:model.reference,frame:1},{type:\"old-drift\",...worstDrift},{type:\"old-burden\",...worst(\"old\")},{type:\"new-burden\",...worst(\"candidate\")}];\n   const details=[];\n   for(const s of selections){\n    const x=poses.find(p=>p.sequence===s.sequence&&p.frame===s.frame);\n    if(!x)throw Error(\"Missing selected pose\");\n    const detail={type:s.type,sequence:s.sequence,frame:s.frame};\n    for(const key of [\"old\",\"candidate\"]){\n     const r=x[key],pw=collisionWorld(po,ref,x.f,r),fw=collisionWorld(fo,ref,x.f,r),lines=depthLines(pg,fg,pw.clone().invert().multiply(fw),pw);\n     let estimates=null;\n     if(lines.segments.length){\n      const box=new THREE.Box3().setFromPoints(lines.segments).expandByScalar(.012),guard=()=>{};\n      const a=await depthSample(pg,fg,pw,fw,box,guard),b=await depthSample(fg,pg,fw,pw,box,guard);\n      const compact=({inside,maxPoint,...v})=>({...v,insideCount:inside.length});\n      estimates={pelvis:compact(a),femur:compact(b)};\n     }\n     detail[key]={...measure(x,r),triangleHits:lines.hits,truncated:lines.truncated,estimates};\n     if(s.type===\"neutral\"||s.type===\"old-drift\"||s.type===\"new-burden\"){\n      $(\"#hipCenterFix\").checked=key===\"candidate\";$(\"#region\").value=\"hips\";$(\"#sequence\").value=s.sequence;choose();visibility();apply(s.frame-1);\n      const c=center.clone().applyMatrix4(r.moves.get(\"femur_\"+side));orbit.target.copy(c);camera.position.copy(c).add(new THREE.Vector3(.34,.10,side===\"r\"?.28:-.28));orbit.update();\n      let overlay=null;\n      try{if(lines.segments.length){overlay=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(lines.segments),new THREE.LineBasicMaterial({color:0xff4d55,depthTest:false}));overlay.renderOrder=20;scene.add(overlay)}pictures.push(reportImage(\"hip-center-\"+side+\"-\"+s.type+\"-\"+key+\".jpg\"))}\n      finally{if(overlay){scene.remove(overlay);overlay.geometry.dispose();overlay.material.dispose()}}\n     }\n    }\n    details.push(detail);\n   }\n   $(\"#hipCenterFix\").checked=true;visibility();fit();\n   const kneeRegression={frames:poses.length,hits:kneeHits,maxRelativeMatrixError:maxKneeError,maxProxyErrorMm:maxKneeProxyError,accepted:kneeHits===0&&maxKneeError<1e-6&&maxKneeProxyError<.01};\n   const driftAccepted=after.maxHeadDriftMm<.001&&maxRotationError<1e-6&&neutralError<1e-6;\n   sides[side]={joint:joint.joint,oldCenter:anchor.a.toArray(),newCenter:center.toArray(),offsetMm:center.distanceTo(anchor.a)*1000,before,after,maxRotationError,driftAccepted,kneeRegression,headSamples:head.length,burden:{oldTotal:burden.reduce((s,x)=>s+x.old.triangleHits,0),newTotal:burden.reduce((s,x)=>s+x.candidate.triangleHits,0),oldMax:worst(\"old\"),newMax:worst(\"candidate\"),truncated:burden.some(x=>x.old.truncated||x.candidate.truncated)},details,series,burdenSeries:burden};\n  }finally{for(const g of [pg,fg,tg,kg])if(g){g.boundsTree=null;g.dispose()}}\n }\n return {method:\"Same CT neutral pose and original 3D relative hip rotations, pivot moved to run-9 sphere center; source hip translation suppressed. Exact triangle intersections; unsigned sampled distances and local parity depth estimates, not validated clinical penetration. Knee transforms compared in femur coordinates.\",neutralError,sides,pictures};\n};\n";
 await page.route(origin+'/unified-rig/hip-center-ct.html',async route=>{const response=await route.fetch();const html=await response.text();if(!html.includes('</script></body></html>'))throw Error('Audit injection target missing');await route.fulfill({response,body:html.replace('</script></body></html>',auditSource+'\n</script></body></html>')})});
 await page.goto(origin+'/unified-rig/hip-center-ct.html',{waitUntil:'domcontentloaded',timeout:120000});
 let previous='';
 monitor=setInterval(async()=>{try{const s=JSON.stringify(await snapshot());if(s!==previous){previous=s;log('PROGRESS',s)}}catch{}},20000);
 await page.waitForFunction(()=>{const b=document.getElementById('depthBatch');return !!window.__unifiedSurfaceQA?.rigReport&&b&&!b.disabled},{},{timeout:20*60*1000,polling:2000});
 log('RIG READY',await snapshot());
 await page.locator('#depthBatch').click({timeout:60000});
 await page.waitForFunction(()=>{const b=document.getElementById('depthBatchStop');const s=document.getElementById('depthBatchStatus')?.textContent||'';return b?.disabled&&(/Сравнение:|Серия:/.test(s));},{},{timeout:25*60*1000,polling:2000});
 const report=await page.locator('#reportPreview').inputValue();
 await fs.writeFile(path.join(output,'report.json'),report);
 const parsed=JSON.parse(report);
 // Export the app's ZIP without invoking OS-level sharing.
 if(await page.locator('#reportShare').isDisabled()) await page.locator('#reportPrepare').click();
 await page.waitForFunction(()=>!document.getElementById('reportShare').disabled,{},{timeout:120000});
 await page.evaluate(()=>{Object.defineProperty(navigator,'share',{value:undefined,configurable:true})});
 const [download]=await Promise.all([page.waitForEvent('download',{timeout:120000}),page.locator('#reportShare').click()]);
 await download.saveAs(path.join(output,'unified-rig-qa-1.8.2.zip'));
 const comparison=parsed.tests?.['knee-depth-comparison']?.result;
 const axis=parsed.tests?.['axis-candidate']?.result;
 const cases=parsed.cases||[];
 const summary={complete:comparison?.complete===true,caseCount:cases.length,validation:axis?.validation,acceptedForPreview:axis?.acceptedForPreview,error:comparison?.error,load:parsed.load};
 await fs.writeFile(path.join(output,'summary.json'),JSON.stringify(summary,null,2));
 log('QA SUMMARY',summary);
 if(!summary.complete||cases.length!==12||axis?.validation?.length!==6)throw Error('Incomplete comparison; artifacts preserved');


 log('HIP CENTER COMPARISON START');
 const audit=await page.evaluate(()=>window.__hipCenterComparison());
 const {pictures,...reportData}=audit;
 await fs.writeFile(path.join(output,'hip-center-comparison.json'),JSON.stringify(reportData,null,2));
 for(const p of pictures)await fs.writeFile(path.join(output,p.name),Buffer.from(p.data,'base64'));
 log('HIP CENTER SUMMARY',{neutralError:reportData.neutralError,sides:Object.fromEntries(Object.entries(reportData.sides).map(([k,{series,burdenSeries,...x}])=>[k,x]))});
 if(Object.keys(reportData.sides).length!==2||pictures.length!==12)throw Error('Incomplete hip center comparison');
 if(!Object.values(reportData.sides).every(x=>x.driftAccepted&&x.kneeRegression.accepted))throw Error('Hip center or knee regression failed; reports preserved');
}catch(e){log('FAIL',e.stack||String(e));process.exitCode=1}
finally{
 clearInterval(monitor);
 if(page){try{await fs.writeFile(path.join(output,'status.json'),JSON.stringify(await snapshot(),null,2));await page.screenshot({path:path.join(output,'final-page.png'),fullPage:false,timeout:20000})}catch(e){log('Final snapshot failed',String(e))}}
 await fs.writeFile(path.join(output,'browser.log'),logs.join('\n'));
 await browser?.close();server.kill();
}
