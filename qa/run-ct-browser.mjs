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
 const auditSource="\nwindow.__integratedHipQA=async()=>{\n const model=rigModel,fitModel=axisModel,ref=headData.sequences.find(s=>s.id===model.reference).frames[0];\n if(!model||!fitModel||!$(\"#kneeAxis\").checked)throw Error(\"Integrated knee profile inactive\");\n const {MeshBVH}=await import(\"https://cdn.jsdelivr.net/npm/three-mesh-bvh@0.9.5/build/index.module.js\");collisionSelfTest(MeshBVH);depthSelfTest(MeshBVH);\n const rad=Math.PI/180,quant=(v,q)=>{const a=v.slice().sort((x,y)=>x-y);return a[Math.floor((a.length-1)*q)]};\n function sampled(g,n){const seen=new Set();return ctPoints(g,n).filter(p=>{const k=p.toArray().map(x=>Math.round(x*4000)).join(\",\");if(seen.has(k))return false;seen.add(k);return true})}\n function distances(points,tree,src,dst){\n  const m=dst.clone().invert().multiply(src),d=points.map(p=>{const q=p.clone().applyMatrix4(m),v=tree.closestPointToPoint(q,{});if(!v||!Number.isFinite(v.distance))throw Error(\"Nearest surface failed\");return q.applyMatrix4(dst).distanceTo(v.point.clone().applyMatrix4(dst))*1000});\n  return {sampleMin:Math.min(...d),near05:quant(d,.05),median:quant(d,.5),near95:quant(d,.95)};\n }\n const poses=headData.sequences.flatMap(s=>s.frames.map((f,i)=>({f,sequence:s.id,frame:i+1,r:rigDeltaModel(model,f)})));\n const neutral=rigDeltaModel(model,ref,true),knees={},hips={},pictures=[];\n function hinge(r,side,deg){\n  const a=fitModel.sides[side],f=r.moves.get(\"femur_\"+side),old=r.moves.get(\"tibia_\"+side),t=f.clone().multiply(axisAround(a.geom.center,a.ctAxis,deg*rad)),delta=t.clone().multiply(old.clone().invert());\n  for(const body of [\"tibia_\"+side,\"talus_\"+side,\"calcn_\"+side,\"toes_\"+side]){\n   const m=r.moves.get(body);if(m)m.premultiply(delta);\n   const j=model.order.find(x=>x.child===body);if(j&&r.joints.has(j.joint)){if(body===\"tibia_\"+side)r.joints.set(j.joint,a.geom.center.clone().applyMatrix4(f));else r.joints.get(j.joint).applyMatrix4(delta)}\n  }\n  const body=\"patella_\"+side,p=tetherPatella(side,r,fitModel,deg*rad);r.moves.set(body,p);\n  const j=model.order.find(x=>x.child===body);if(j)r.joints.set(j.joint,a.geom.patCenter.clone().applyMatrix4(p));\n }\n for(const side of [\"r\",\"l\"]){\n  const fo=collisionMesh(\"femur_\"+side),to=collisionMesh(\"tibia_\"+side,null,\"TIBIA_\"),po=collisionMesh(\"patella_\"+side);\n  let fg=null,tg=null,pg=null;\n  try{\n   fg=collisionTree(fo,MeshBVH);tg=collisionTree(to,MeshBVH);pg=collisionTree(po,MeshBVH);\n   const ps=sampled(pg,2500),lm=tetherProfile[side],tub=vec(lm.tub),inf=vec(lm.inf),len=tub.distanceTo(inf)*1000;\n   function measure(r,f){\n    const fw=collisionWorld(fo,ref,f,r),tw=collisionWorld(to,ref,f,r),pw=collisionWorld(po,ref,f,r);\n    const pf=distances(ps,fg.boundsTree,pw,fw);\n    const hits=[collisionHit(fg,tg,fw,tw),collisionHit(fg,pg,fw,pw),collisionHit(tg,pg,tw,pw)];\n    const proxy=inf.clone().applyMatrix4(r.moves.get(\"patella_\"+side)).distanceTo(tub.clone().applyMatrix4(r.moves.get(\"tibia_\"+side)))*1000;\n    return {pf,hits,proxyErrorMm:Math.abs(proxy-len)};\n   }\n   const baseline=measure(neutral,ref),sweep=[],real=[];\n   for(let deg=0;deg<=130;deg++){\n    const r=rigDeltaModel(model,ref,true);hinge(r,side,deg);sweep.push({deg,...measure(r,ref)});if(deg%20===0)await new Promise(r=>setTimeout(r,0));\n   }\n   for(const x of poses){real.push({sequence:x.sequence,frame:x.frame,...measure(x.r,x.f)});if(real.length%30===0)await new Promise(r=>setTimeout(r,0))}\n   function summarize(rows){return {frames:rows.length,hits:rows.filter(x=>x.hits.some(Boolean)).length,maxMin:Math.max(...rows.map(x=>x.pf.sampleMin)),minGap:Math.min(...rows.map(x=>x.pf.sampleMin)),maxNear:Math.max(...rows.map(x=>x.pf.near05)),maxProxyErrorMm:Math.max(...rows.map(x=>x.proxyErrorMm))}}\n   const s=summarize(sweep),a=summarize(real),accepted=[s,a].every(x=>!x.hits&&x.minGap>=.1&&x.maxNear<=baseline.pf.near05+2&&x.maxProxyErrorMm<.01);\n   knees[side]={accepted,baseline,sweepSummary:s,animationSummary:a,sweep,real};\n  }finally{for(const g of [fg,tg,pg])if(g){g.boundsTree=null;g.dispose()}}\n }\n for(const side of [\"r\",\"l\"]){\n  const po=collisionMesh(\"pelvis\",side.toUpperCase()),fo=collisionMesh(\"femur_\"+side);\n  let pg=null,fg=null;\n  try{\n   pg=collisionTree(po,MeshBVH);fg=collisionTree(fo,MeshBVH);\n   const pw0=collisionWorld(po,ref,ref,neutral),fw0=collisionWorld(fo,ref,ref,neutral);\n   const fem=sampled(fg,18000),world=fem.map(p=>p.clone().applyMatrix4(fw0));\n   const top=rigRegion(world,\"y\",true,.20),joint=model.order.find(j=>j.child===\"femur_\"+side),anchor=model.anchors.get(joint.joint);\n   const candidates=[];\n   for(const y of [.12,.16,.20,.24])for(const z of [.35,.42,.48,.55]){\n    const pts=rigRegion(rigRegion(world,\"y\",true,y),\"z\",side===\"l\",z),s=rigSphere(pts);\n    if(!s||s.radius<15||s.radius>40||s.rms>5||s.center.distanceTo(anchor.a)>.05)continue;\n    const inliers=pts.filter(p=>Math.abs(p.distanceTo(s.center)*1000-s.radius)<=2.5),q=rigSphere(inliers);\n    if(q&&q.radius>=15&&q.radius<=40&&q.rms<2.5&&q.center.distanceTo(s.center)<.008)candidates.push({center:q.center.toArray(),radiusMm:q.radius,rmsMm:q.rms,n:inliers.length,sampleN:pts.length,y,z});\n   }\n   candidates.sort((a,b)=>a.rmsMm-b.rmsMm||b.n-a.n);\n   const sphere=candidates[0]||null,center=sphere?vec(sphere.center):anchor.a.clone(),radius=sphere?sphere.radiusMm/1000:.028;\n   const head=fem.filter((p,i)=>world[i].distanceTo(center)<=radius+.003&&world[i].distanceTo(center)>=radius-.004);\n   if(head.length<30)throw Error(\"Too few head surface samples \"+side);\n   const patch=head.map(p=>({p,d:distances([p],pg.boundsTree,fw0,pw0).sampleMin})).sort((a,b)=>a.d-b.d).slice(0,Math.min(160,Math.max(30,Math.ceil(head.length*.15)))).map(x=>x.p);\n   const proximal=rigRegion(world,\"y\",true,.18),distal=rigRegion(world,\"y\",false,.15),shaft=rigCenter(distal).sub(center).normalize();\n   function measure(x){\n    const pw=collisionWorld(po,ref,x.f,x.r),fw=collisionWorld(fo,ref,x.f,x.r),pel=x.r.moves.get(\"pelvis\"),fem=x.r.moves.get(\"femur_\"+side);\n    const relative=pel.clone().invert().multiply(fem),moved=center.clone().applyMatrix4(relative);\n    const q=new THREE.Quaternion().setFromRotationMatrix(relative).normalize();\n    return {sequence:x.sequence,frame:x.frame,headCenterDriftMm:moved.distanceTo(center)*1000,anchorDriftMm:anchor.a.clone().applyMatrix4(relative).distanceTo(anchor.a)*1000,relativeRotationDeg:2*Math.acos(Math.min(1,Math.abs(q.w)))/rad,shaftAngleDeg:shaft.angleTo(shaft.clone().transformDirection(relative))/rad,headGap:distances(head,pg.boundsTree,fw,pw),fixedPatchGap:distances(patch,pg.boundsTree,fw,pw),hit:collisionHit(pg,fg,pw,fw)};\n   }\n   const base={f:ref,r:neutral,sequence:model.reference,frame:1},baseline=measure(base),series=[];\n   for(const x of poses){series.push(measure(x));if(series.length%20===0)await new Promise(r=>setTimeout(r,0))}\n   const worst=(fn)=>series.reduce((a,b)=>fn(b)>fn(a)?b:a,series[0]);\n   const selected=[{type:\"neutral\",...baseline},{type:\"drift\",...worst(x=>x.headCenterDriftMm)},{type:\"separation\",...worst(x=>x.headGap.near05)},{type:\"flex\",...worst(x=>x.shaftAngleDeg)}];\n   const detailed=[];\n   for(const s of selected){\n    const x=s.type===\"neutral\"?base:poses.find(p=>p.sequence===s.sequence&&p.frame===s.frame);\n    const pw=collisionWorld(po,ref,x.f,x.r),fw=collisionWorld(fo,ref,x.f,x.r),lines=depthLines(pg,fg,pw.clone().invert().multiply(fw),pw);\n    let estimates=null;\n    if(lines.segments.length){\n     const box=new THREE.Box3().setFromPoints(lines.segments).expandByScalar(.012),guard=()=>{};\n     const a=await depthSample(pg,fg,pw,fw,box,guard),b=await depthSample(fg,pg,fw,pw,box,guard);\n     const compact=({inside,maxPoint,...v})=>({...v,insideCount:inside.length,maxPoint:maxPoint?.toArray()||null});\n     estimates={pelvis:compact(a),femur:compact(b)};\n    }\n    const worldC=center.clone().applyMatrix4(x.r.moves.get(\"femur_\"+side));\n    const radial=lines.segments.map(p=>p.distanceTo(worldC)*1000);\n    detailed.push({...s,triangleHits:lines.hits,lineSegments:lines.segments.length/2,truncated:lines.truncated,intersectionRadiusMm:radial.length?{min:Math.min(...radial),max:Math.max(...radial),median:quant(radial,.5)}:null,estimates});\n    $(\"#region\").value=\"hips\";$(\"#sequence\").value=s.sequence;choose();visibility();apply(s.frame-1);\n    const c=worldC;orbit.target.copy(c);camera.position.copy(c).add(new THREE.Vector3(.34,.10,side===\"r\"?.28:-.28));orbit.update();\n    let overlay=null;\n    try{if(lines.segments.length){overlay=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(lines.segments),new THREE.LineBasicMaterial({color:0xff4d55,depthTest:false}));overlay.renderOrder=20;scene.add(overlay)}pictures.push(reportImage(\"hip-\"+side+\"-\"+s.type+\".jpg\"))}\n    finally{if(overlay){scene.remove(overlay);overlay.geometry.dispose();overlay.material.dispose()}}\n   }\n   hips[side]={joint:joint.joint,anchor:{kind:anchor.kind,point:anchor.a.toArray(),old:anchor.old.toArray()},sphere,fitCandidates:candidates,headSamples:head.length,patchSamples:patch.length,centerOffsetFromAnchorMm:center.distanceTo(anchor.a)*1000,baseline,frames:series.length,intersectionFrames:series.filter(x=>x.hit).length,newHits:series.filter(x=>x.hit&&!baseline.hit).length,details:detailed,series};\n  }finally{for(const g of [pg,fg])if(g){g.boundsTree=null;g.dispose()}}\n }\n return {method:\"Frozen run-7 knee profile verified against isolated 0–130° sweep and existing animations. Hip baseline audit: approximate sphere of proximal medial femoral head, pose-relative center drift, unsigned sampled surface distance, exact triangle intersections, local parity estimates not validated on watertight meshes. No hip correction applied.\",knees,hips,pictures};\n};\n";
 await page.route(origin+'/unified-rig/hip-qa-ct.html',async route=>{const response=await route.fetch();const html=await response.text();if(!html.includes('</script></body></html>'))throw Error('Audit injection target missing');await route.fulfill({response,body:html.replace('</script></body></html>',auditSource+'\n</script></body></html>')})});
 await page.goto(origin+'/unified-rig/hip-qa-ct.html',{waitUntil:'domcontentloaded',timeout:120000});
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
 await download.saveAs(path.join(output,'unified-rig-qa-1.8.1.zip'));
 const comparison=parsed.tests?.['knee-depth-comparison']?.result;
 const axis=parsed.tests?.['axis-candidate']?.result;
 const cases=parsed.cases||[];
 const summary={complete:comparison?.complete===true,caseCount:cases.length,validation:axis?.validation,acceptedForPreview:axis?.acceptedForPreview,error:comparison?.error,load:parsed.load};
 await fs.writeFile(path.join(output,'summary.json'),JSON.stringify(summary,null,2));
 log('QA SUMMARY',summary);
 if(!summary.complete||cases.length!==12||axis?.validation?.length!==6)throw Error('Incomplete comparison; artifacts preserved');

 log('INTEGRATED HIP QA START');
 const audit=await page.evaluate(()=>window.__integratedHipQA());
 const {pictures,...reportData}=audit;
 await fs.writeFile(path.join(output,'integrated-hip-qa.json'),JSON.stringify(reportData,null,2));
 for(const p of pictures)await fs.writeFile(path.join(output,p.name),Buffer.from(p.data,'base64'));
 log('INTEGRATED KNEE SUMMARY',Object.fromEntries(Object.entries(reportData.knees).map(([k,{sweep,real,...x}])=>[k,x])));
 log('HIP SUMMARY',Object.fromEntries(Object.entries(reportData.hips).map(([k,{series,fitCandidates,...x}])=>[k,x])));
 if(Object.keys(reportData.knees).length!==2||Object.keys(reportData.hips).length!==2||pictures.length!==8)throw Error('Incomplete integrated audit');
 if(!Object.values(reportData.knees).every(x=>x.accepted))throw Error('Frozen knee profile regression; reports preserved');
}catch(e){log('FAIL',e.stack||String(e));process.exitCode=1}
finally{
 clearInterval(monitor);
 if(page){try{await fs.writeFile(path.join(output,'status.json'),JSON.stringify(await snapshot(),null,2));await page.screenshot({path:path.join(output,'final-page.png'),fullPage:false,timeout:20000})}catch(e){log('Final snapshot failed',String(e))}}
 await fs.writeFile(path.join(output,'browser.log'),logs.join('\n'));
 await browser?.close();server.kill();
}
