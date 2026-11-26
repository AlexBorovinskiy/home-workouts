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
 const auditSource="\nwindow.__kneeContactAudit=async()=>{\n if(!rigModel||!axisModel)throw Error(\"No candidate\");\n const model=rigModel,fitModel=axisModel,ref=headData.sequences.find(s=>s.id===model.reference).frames[0];\n const {MeshBVH}=await import(\"https://cdn.jsdelivr.net/npm/three-mesh-bvh@0.9.5/build/index.module.js\");collisionSelfTest(MeshBVH);\n const frames=headData.sequences.flatMap(s=>s.frames.map((f,i)=>{const base=rigDeltaModel(model,f,true),alt=rigDeltaModel(model,f,true);axisApply(model,alt,fitModel);return {f,i,id:s.id,label:s.label,base,alt}}));\n const quant=(a,q)=>{const v=a.slice().sort((a,b)=>a-b);return v[Math.floor((v.length-1)*q)]};\n const localSample=g=>{const a=ctPoints(g,4500),seen=new Set();return a.filter(p=>{const k=p.toArray().map(n=>Math.round(n*4000)).join(\",\");if(seen.has(k))return false;seen.add(k);return true})};\n const near=(p,tree,m)=>{const q=p.clone().applyMatrix4(m),v=tree.closestPointToPoint(q,{});if(!v||!Number.isFinite(v.distance))throw Error(\"BVH nearest point failed\");return v.distance*1000};\n const rows=[],angles={},pictures=[];\n for(const spec of depthSpecs().filter(x=>x.region===\"knees\")){\n  const a=collisionMesh(spec.a,spec.aSide,spec.aFile),b=collisionMesh(spec.b,spec.bSide,spec.bFile);\n  let ga=null,gb=null;\n  try{\n   ga=collisionTree(a,MeshBVH);gb=collisionTree(b,MeshBVH);\n   const pointsA=localSample(ga),pointsB=localSample(gb),neutral=rigDeltaModel(model,ref,true),wa=collisionWorld(a,ref,ref,neutral),wb=collisionWorld(b,ref,ref,neutral),ab=wb.clone().invert().multiply(wa),ba=ab.clone().invert();\n   const rank=(pts,other,m)=>pts.map(p=>({p,d:near(p,other,m)})).sort((x,y)=>x.d-y.d);\n   const pa=rank(pointsA,gb.boundsTree,ab),pb=rank(pointsB,ga.boundsTree,ba);\n   const patch=ranked=>ranked.slice(0,Math.min(160,Math.max(30,Math.ceil(ranked.length*.06)))).map(x=>x.p);\n   const sa=patch(pa),sb=patch(pb);\n   // Fixed reference patches are compared separately from migrating contact areas.\n   function metric(ma,mb){\n    const m=mb.clone().invert().multiply(ma),n=m.clone().invert();\n    const da=sa.map(p=>near(p,gb.boundsTree,m)),db=sb.map(p=>near(p,ga.boundsTree,n));\n    const both=[...da,...db];\n    const broadA=pointsA.filter((_,i)=>i%4===0).map(p=>near(p,gb.boundsTree,m)),broadB=pointsB.filter((_,i)=>i%4===0).map(p=>near(p,ga.boundsTree,n));\n    return {sampleMinMm:Math.min(...broadA,...broadB),movingP05Mm:Math.min(quant(broadA,.05),quant(broadB,.05)),fixedMedianMm:quant(both,.5),fixedP95Mm:quant(both,.95)};\n   }\n   const baseline=metric(wa,wb),cache=new Map(),series=[];\n   function one(x,r){\n    const ma=collisionWorld(a,ref,x.f,r),mb=collisionWorld(b,ref,x.f,r),rel=mb.clone().invert().multiply(ma);\n    const key=rel.elements.map(v=>Math.round(v*1e8)).join(\",\");\n    if(!cache.has(key))cache.set(key,metric(ma,mb));\n    return cache.get(key);\n   }\n   for(const x of frames){series.push({sequence:x.id,frame:x.i+1,base:one(x,x.base),candidate:one(x,x.alt)});if(series.length%20===0)await new Promise(r=>setTimeout(r,0))}\n   const peak=(k)=>series.reduce((best,x)=>!best||x.candidate[k]>best.candidate[k]?x:best,null);\n   rows.push({pair:spec.label,baseline,uniquePoses:cache.size,points:[pointsA.length,pointsB.length],patch:[sa.length,sb.length],maxMovingP05:peak(\"movingP05Mm\"),maxFixedMedian:peak(\"fixedMedianMm\"),maxSampleMin:peak(\"sampleMinMm\"),series});\n   console.log(\"CONTACT PAIR \"+JSON.stringify({...rows.at(-1),series:undefined}));\n  }finally{for(const g of [ga,gb])if(g){g.boundsTree=null;g.dispose()}}\n }\n for(const side of [\"r\",\"l\"]){\n  const a=fitModel.sides[side],fem=armWorldPoints(collisionMesh(\"femur_\"+side),ref,6000),tib=armWorldPoints(collisionMesh(\"tibia_\"+side,null,\"TIBIA_\"),ref,6000),pat=a.geom.patCenter;\n  const shaft=rigCenter(rigRegion(tib,\"y\",false,.15)).sub(rigCenter(rigRegion(tib,\"y\",true,.15))).normalize();\n  const anterior=pat.clone().sub(a.geom.center);anterior.addScaledVector(a.ctAxis,-anterior.dot(a.ctAxis)).normalize();\n  const series=frames.map(x=>{\n   const f=x.alt.moves.get(\"femur_\"+side),t=x.alt.moves.get(\"tibia_\"+side),p=x.alt.moves.get(\"patella_\"+side),rel=f.clone().invert().multiply(t),pr=f.clone().invert().multiply(p);\n   const dir=shaft.clone().transformDirection(rel),d=pat.clone().applyMatrix4(pr).sub(pat);\n   return {sequence:x.id,frame:x.i+1,inputDeg:axisTwist(x.base,side,a.sourceAxis)*180/Math.PI,shaftChangeDeg:shaft.angleTo(dir)*180/Math.PI,posteriorShaftChange:-(dir.dot(anterior)-shaft.dot(anterior)),patellaCenterShiftMm:d.length()*1000,patellaVerticalShiftMm:d.y*1000};\n  });\n  const max=series.reduce((b,x)=>Math.abs(x.inputDeg)>Math.abs(b.inputDeg)?x:b,series[0]);angles[side]={max,axisDifferenceDeg:a.axisDifferenceDeg,series};\n  // Capture candidate in neutral and peak flexion, including clear surfaces.\n  for(const [phase,pose] of [[\"neutral\",{sequence:model.reference,frame:1}],[\"peak\",max]]){\n   $(\"#kneeAxis\").checked=true;$(\"#kneeFix\").checked=false;$(\"#region\").value=\"knees\";$(\"#sequence\").value=pose.sequence;choose();visibility();apply(pose.frame-1);view=\"side\";fit();\n   const center=rigCenter([...rigRegion(fem,\"y\",false,.15),...rigRegion(tib,\"y\",true,.15)]).applyMatrix4(rigDeltaModel(model,seq.frames[frame]).moves.get(\"femur_\"+side));\n   orbit.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(0,.025,side===\"r\"?.42:-.42));orbit.update();\n   for(const [name,d] of [[\"side\",[0,0,side===\"r\"?1:-1]],[\"front\",[1,0,0]]]){\n    camera.position.copy(center).addScaledVector(new THREE.Vector3(...d),.42);camera.lookAt(center);orbit.update();const img=reportImage(side+\"-\"+phase+\"-\"+name+\".jpg\");pictures.push(img);\n   }\n  }\n }\n return {method:\"Unsigned nearest point on opposing full triangle surface from sampled vertices; separate fixed reference patches and migrating near-surface statistics. Distances do not measure cartilage, contact pressure or true joint-space width. No pass threshold inferred.\",frames:frames.length,rows,angles,pictures};\n};\n";
 await page.route(origin+'/unified-rig/knee-axis-ct.html',async route=>{const response=await route.fetch();const html=await response.text();if(!html.includes('</script></body></html>'))throw Error('Audit injection target missing');await route.fulfill({response,body:html.replace('</script></body></html>',auditSource+'\n</script></body></html>')})});
 await page.goto(origin+'/unified-rig/knee-axis-ct.html',{waitUntil:'domcontentloaded',timeout:120000});
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
 await download.saveAs(path.join(output,'unified-rig-qa-1.8.0.zip'));
 const comparison=parsed.tests?.['knee-depth-comparison']?.result;
 const axis=parsed.tests?.['axis-candidate']?.result;
 const cases=parsed.cases||[];
 const summary={complete:comparison?.complete===true,caseCount:cases.length,validation:axis?.validation,acceptedForPreview:axis?.acceptedForPreview,error:comparison?.error,load:parsed.load};
 await fs.writeFile(path.join(output,'summary.json'),JSON.stringify(summary,null,2));
 log('QA SUMMARY',summary);
 if(!summary.complete||cases.length!==12||axis?.validation?.length!==6)throw Error('Incomplete comparison; artifacts preserved');
 log('CONTACT AUDIT START');
 const audit=await page.evaluate(()=>window.__kneeContactAudit());
 const {pictures,...contact}=audit;
 await fs.writeFile(path.join(output,'knee-contact.json'),JSON.stringify(contact,null,2));
 for(const p of pictures)await fs.writeFile(path.join(output,p.name),Buffer.from(p.data,'base64'));
 log('CONTACT SUMMARY',{frames:contact.frames,rows:contact.rows.map(({series,...r})=>r),angles:Object.fromEntries(Object.entries(contact.angles).map(([k,{series,...a}])=>[k,a]))});
 if(contact.rows.length!==6||contact.frames!==310||pictures.length!==8)throw Error('Incomplete contact audit');
}catch(e){log('FAIL',e.stack||String(e));process.exitCode=1}
finally{
 clearInterval(monitor);
 if(page){try{await fs.writeFile(path.join(output,'status.json'),JSON.stringify(await snapshot(),null,2));await page.screenshot({path:path.join(output,'final-page.png'),fullPage:false,timeout:20000})}catch(e){log('Final snapshot failed',String(e))}}
 await fs.writeFile(path.join(output,'browser.log'),logs.join('\n'));
 await browser?.close();server.kill();
}
