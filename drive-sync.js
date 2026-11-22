/* Google Drive sync (browser-only, least-privilege OAuth).
   No access tokens or client secrets are stored or committed to GitHub.
   Keeps localStorage as source of truth while offline.
*/
(function(){
'use strict';
const CLIENT_KEY='my-home-workouts-google-client-v1';
const META_KEY='my-home-workouts-google-meta-v1';
const FILE_NAME='Мои тренировки — журнал.json';
const DRIVE_SCOPE='https://www.googleapis.com/auth/drive.file';
let clientId='',meta={},token='',tokenExpires=0,connected=false,busy=false,conflict=false,pending=false,debounce=null,applying=false;
let status='Не подключён. Записи пока сохраняются только на устройстве.';
try{clientId=localStorage.getItem(CLIENT_KEY)||'';meta=JSON.parse(localStorage.getItem(META_KEY)||'{}')}catch(e){meta={};}
function snapshot(obj){return JSON.stringify({schemaVersion:obj.schemaVersion,prefs:obj.prefs,sessions:obj.sessions,measurements:obj.measurements});}
function payload(){return JSON.stringify({application:'Мои тренировки',exportedAt:new Date().toISOString(),...db},null,2)}
function storeMeta(){localStorage.setItem(META_KEY,JSON.stringify(meta))}
function note(s){status=s;if(tab==='data')view();}
function validToken(){return Boolean(token&&Date.now()<tokenExpires-30000)}
function apiUrl(path){return 'https://www.googleapis.com/drive/v3/'+path;}
async function api(url,options){
  if(!validToken())throw Error('Авторизация Google завершилась. Нажми «Подключить Google» ещё раз.');
  const init=Object.assign({},options||{});
  init.headers=Object.assign({},options&&options.headers||{},{'Authorization':'Bearer '+token});
  const response=await fetch(url,init);
  if(!response.ok){let info='';try{const er=await response.json();info=er.error?.message||''}catch(e){}throw Error('Google Drive: HTTP '+response.status+(info?' — '+info:''))}
  if(response.status===204)return null;
  return response.json();
}
function fileQuery(){return "name = '"+FILE_NAME.replace(/'/g,"\\'")+"' and trashed = false";}
async function findFile(){
  const url=apiUrl('files?q='+encodeURIComponent(fileQuery())+'&fields='+encodeURIComponent('files(id,name,modifiedTime,webViewLink),nextPageToken')+'&page_size=100');
  const data=await api(url);
  const files=(data.files||[]).sort((a,b)=>String(b.modifiedTime).localeCompare(String(a.modifiedTime)));
  if(files.length>1)throw Error('На Google Диске несколько файлов журнала. Сначала проверь дубликаты в Диске.');
  return files[0]||null;
}
async function getRemote(id){const d=await api(apiUrl('files/'+encodeURIComponent(id)+'?alt=media'));validImport(d);return d;}
async function createRemote(){
  const boundary='workout'+Math.random().toString(36).slice(2);
  const body='--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+
    JSON.stringify({name:FILE_NAME,mimeType:'application/json'})+
    '\r\n--'+boundary+'\r\nContent-Type: application/json\r\n\r\n'+payload()+
    '\r\n--'+boundary+'--';
  const created=await api('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink',{
     method:'POST',headers:{'Content-Type':'multipart/related; boundary='+boundary},body:body
  });
  if(!created.id)throw Error('Google не вернул ID файла.');
  meta.fileId=created.id;meta.fingerprint=snapshot(db);meta.at=new Date().toISOString();storeMeta();
  return created;
}
async function uploadRemote(id){
  const data=payload(),fp=snapshot(db);
  await api('https://www.googleapis.com/upload/drive/v3/files/'+encodeURIComponent(id)+'?uploadType=media',{
     method:'PATCH',headers:{'Content-Type':'application/json; charset=UTF-8'},body:data
  });
  meta.fileId=id;meta.fingerprint=fp;meta.at=new Date().toISOString();storeMeta();
  if(snapshot(db)!==fp){pending=true;}
}
function importRemote(cloud){
  validImport(cloud);applying=true;
  try{
    db={schemaVersion:VERSION,prefs:{...db.prefs,...cloud.prefs},sessions:cloud.sessions,measurements:cloud.measurements,lastBackupAt:cloud.lastBackupAt||null};
    const saved=save();if(!saved)throw Error('Не удалось сохранить загруженный журнал на iPhone.');
  }finally{applying=false}
  editId=null;type=suggestedType();draft=newDraft(type);saveDraft();
}
async function synchronize(){
  if(busy||!validToken()){if(!validToken())note('Google не подключён: авторизуйся ещё раз. Локальные записи сохранены.');return;}
  busy=true;pending=false;
  note('Сверяю журнал с Google Диском…');
  try{
    const found=await findFile();
    if(!found){
      if(meta.fileId)throw Error('Ранее подключённый файл исчез или сейчас недоступен. Ничего не перезаписано.');
      await createRemote();conflict=false;note('Синхронизировано: создан личный файл на Google Диске.');
      return;
    }
    const remote=await getRemote(found.id),rfp=snapshot(remote),lfp=snapshot(db),known=meta.fileId===found.id?meta.fingerprint:null;
    meta.fileId=found.id;
    if(rfp===lfp){meta.fingerprint=rfp;meta.at=new Date().toISOString();storeMeta();conflict=false;note('Синхронизировано: записи на iPhone и в Google Диске одинаковые.');return;}
    if(!known){
      if(!db.sessions.length&&!db.measurements.length){
        importRemote(remote);meta.fingerprint=snapshot(db);meta.at=new Date().toISOString();storeMeta();conflict=false;
        note('История восстановлена из Google Диска.');return;
      }
      conflict=true;note('На Google Диске уже есть другая история. Автоматическая запись остановлена: нажми «Объединить безопасно».');return;
    }
    if(rfp===known){
      await uploadRemote(found.id);conflict=false;note('Сохранено в Google Диск: '+new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}));return;
    }
    if(lfp===known){
      importRemote(remote);meta.fingerprint=snapshot(db);meta.at=new Date().toISOString();storeMeta();conflict=false;
      note('Получены новые записи из Google Диска.');return;
    }
    conflict=true;note('Изменились и телефон, и облачный файл. Ничего не перезаписано: требуется объединение.');
  }catch(e){note('Ошибка синхронизации: '+e.message)}
  finally{busy=false;if(pending&&!conflict&&validToken())schedule();}
}
function schedule(){
  if(!connected||!validToken()||applying||conflict)return;
  clearTimeout(debounce);
  debounce=setTimeout(()=>{if(busy){pending=true;return;}synchronize()},12000);
}
function backupLocal(){
  download('moi-trenirovki-pered-sliyaniem-'+today()+'.json',payload(),'application/json;charset=utf-8');
}
async function merge(){
  if(!validToken())return note('Подключи Google, чтобы объединить данные.');
  if(!confirm('Объединить записи iPhone и Google Диска по ID? Перед объединением скачается локальная резервная копия. Удалённые на одном устройстве записи могут вернуться.'))return;
  busy=true;note('Объединяю записи, сохраняя резервную копию…');
  try{
    backupLocal();
    const file=await findFile();if(!file)throw Error('Файл не найден.');
    const cloud=await getRemote(file.id);
    const map=new Map(cloud.sessions.map(s=>[s.id,s]));
    for(const s of db.sessions){
      const old=map.get(s.id);
      if(!old||String(s.savedAt||'')>=String(old.savedAt||''))map.set(s.id,s);
    }
    const mm=new Map(cloud.measurements.map(m=>[m.id,m]));
    db.measurements.forEach(m=>mm.set(m.id,m));
    db.sessions=Array.from(map.values());
    db.measurements=Array.from(mm.values());
    if(!db.prefs.planOverrides&&cloud.prefs.planOverrides)db.prefs.planOverrides=cloud.prefs.planOverrides;
    applying=true;try{save()}finally{applying=false}
    await uploadRemote(file.id);
    conflict=false;note('Истории объединены и синхронизированы. Проверь записи после объединения.');
  }catch(e){conflict=true;note('Не удалось объединить: '+e.message)}
  finally{busy=false;}
}
function clientFromInput(){
  const field=document.getElementById('cloud-client');return (field?.value||clientId).trim();
}
function saveClient(){
  const id=clientFromInput();
  if(!/^[0-9]+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(id))return note('Нужен OAuth Client ID Google типа Web application (не секретный ключ).');
  if(id!==clientId){meta={};storeMeta();}
  clientId=id;localStorage.setItem(CLIENT_KEY,id);note('Client ID сохранён только на этом устройстве. Теперь нажми «Подключить Google».');
}
function connect(){
  const maybe=clientFromInput();
  if(maybe!==clientId||!clientId){saveClient();if(!clientId)return;}
  if(!window.google?.accounts?.oauth2)return note('Служба входа Google не загрузилась. Открой приложение в Safari при наличии интернета.');
  const c=google.accounts.oauth2.initTokenClient({
    client_id:clientId,scope:DRIVE_SCOPE,
    callback:function(r){
      if(r.error){note('Ошибка входа Google: '+r.error);return;}
      token=r.access_token;tokenExpires=Date.now()+(Number(r.expires_in)||3500)*1000;connected=true;conflict=false;
      synchronize();
    },
    error_callback:function(e){note('Не удалось открыть окно входа Google. Попробуй в Safari.');}
  });
  c.requestAccessToken({prompt:''});
}
function disconnect(){clearTimeout(debounce);token='';tokenExpires=0;connected=false;conflict=false;note('Отключено на этом устройстве. Копия на Google Диске сохранена.');}
function cloudPanel(){
  const shown=validToken()?'Подключён':'Не подключён';
  return '<div class="card"><h3>☁ Синхронизация с Google Диском</h3>'+
    '<p class="small muted">Приватный JSON-файл «'+escapeHTML(FILE_NAME)+'» в твоём Google Диске. Локальные записи сохраняются даже без интернета.</p>'+
    '<div class="field"><label for="cloud-client" class="field-label">OAuth Client ID (Web application)</label>'+
    '<input id="cloud-client" type="text" autocomplete="off" spellcheck="false" value="'+escapeHTML(clientId)+'" placeholder="…apps.googleusercontent.com"></div>'+
    '<div class="button-row"><button class="btn secondary" type="button" data-cloud-action="save-id">Сохранить ID</button>'+
    '<button class="btn" type="button" data-cloud-action="connect">Подключить Google</button></div>'+
    '<div class="button-row"><button class="btn secondary" type="button" data-cloud-action="sync">↻ Синхронизировать</button>'+
    (conflict?'<button class="btn secondary" type="button" data-cloud-action="merge">Объединить безопасно</button>':'')+
    (validToken()?'<button class="btn secondary" type="button" data-cloud-action="disconnect">Отключить</button>':'')+'</div>'+
    '<p class="tiny" id="cloud-status"><strong>'+shown+':</strong> '+escapeHTML(status)+'</p>'+
    (meta.at?'<p class="tiny">Последняя успешная синхронизация: '+escapeHTML(new Date(meta.at).toLocaleString('ru-RU'))+'</p>':'')+
    '<p class="tiny">Для входа нужен OAuth Client ID из Google Cloud Console и разрешённый JavaScript origin <code>https://alexborovinskiy.github.io</code>. Client Secret вводить нельзя. Вход может потребоваться снова после перезапуска приложения. История никогда не публикуется на GitHub.</p></div>';
}
const originalRenderData=renderData;
renderData=function(){
  const html=originalRenderData();
  return html.replace('<div class="card soft">',cloudPanel()+'<div class="card soft">');
};
const originalSave=save;
save=function(){const ok=originalSave();if(ok&&!applying)schedule();return ok;};
document.getElementById('main').addEventListener('click',function(e){
  const button=e.target.closest('[data-cloud-action]');if(!button)return;
  const action=button.dataset.cloudAction;
  if(action==='save-id')saveClient();
  if(action==='connect')connect();
  if(action==='disconnect')disconnect();
  if(action==='sync')synchronize();
  if(action==='merge')merge();
});
if(tab==='data')view();
})();