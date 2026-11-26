import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';

const output = path.resolve('qa-results');
await fs.mkdir(output,{recursive:true});
const logs=[];
const log=(...x)=>{const s=x.map(v=>typeof v==='string'?v:JSON.stringify(v)).join(' ');logs.push(new Date().toISOString()+' '+s);console.log(s)};
const server=spawn('python3',['-m','http.server','8765','--bind','127.0.0.1'],{stdio:'ignore'});
let browser,page,monitor;
const origin='http://127.0.0.1:8765';
const statuses=['status','ctStatus','cacheInfo','fhsStorage','thoraxStatus','pelvisStatus','femurStatus','lowerStatus','skullStatus','shoulderStatus','armFitStatus','rigStatus','axisStatus','depthStatus','depthBatchStatus','reportStatus'];
async function snapshot(){return page.evaluate(ids=>Object.fromEntries(ids.map(id=>[id,document.getElementById(id)?.textContent?.trim()||''])),statuses)}
async function waitServer(){for(let i=0;i<60;i++){try{if((await fetch(origin+'/')).ok)return}catch{}await new Promise(r=>setTimeout(r,500))}throw Error('Local HTTP server failed')}
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
 await page.goto(origin+'/',{waitUntil:'domcontentloaded',timeout:60000});
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
}catch(e){log('FAIL',e.stack||String(e));process.exitCode=1}
finally{
 clearInterval(monitor);
 if(page){try{await fs.writeFile(path.join(output,'status.json'),JSON.stringify(await snapshot(),null,2));await page.screenshot({path:path.join(output,'final-page.png'),fullPage:false,timeout:20000})}catch(e){log('Final snapshot failed',String(e))}}
 await fs.writeFile(path.join(output,'browser.log'),logs.join('\n'));
 await browser?.close();server.kill();
}
