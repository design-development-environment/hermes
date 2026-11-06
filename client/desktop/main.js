const {app, BrowserWindow, Menu, dialog, session} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {validate} = require('./origin');
const setupURL = pathToFileURL(path.join(__dirname,'welcome.html')).href;
let win, host;
const config = () => path.join(app.getPath('userData'),'host.json');
function welcome() {
  host = null;
  return win.loadFile(path.join(__dirname,'welcome.html'));
}
async function connect(raw) {
  try {
    const target = validate(raw);
    host = target;
    await win.loadURL(target);
    fs.writeFileSync(config(), JSON.stringify({host:target}), {mode:0o600});
  } catch (err) {
    await welcome();
    dialog.showErrorBox('Connection unavailable', err.message);
  }
}
app.setName('Hermes');
app.whenReady().then(async () => {
  win = new BrowserWindow({title:'Hermes',width:1180,height:790,minWidth:680,minHeight:480,
    icon:path.join(__dirname,'icon.png'),autoHideMenuBar:true,
    webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}});
  const wc = win.webContents;
  const trusted = url => {try{return !!host && new URL(url).origin === host}catch{return false}};
  wc.on('will-navigate',(event,url)=>{
    if (wc.getURL() === setupURL && url.startsWith(setupURL+'?')) {
      event.preventDefault();
      connect(new URL(url).searchParams.get('host'));
    } else if (!trusted(url)) event.preventDefault();
  });
  wc.on('will-redirect',(event,url)=>{if(!trusted(url))event.preventDefault()});
  wc.setWindowOpenHandler(()=>({action:'deny'}));
  session.defaultSession.setPermissionCheckHandler((contents,perm,origin)=>contents===wc && trusted(origin) && perm==='media');
  session.defaultSession.setPermissionRequestHandler(async(contents,perm,cb,details)=>{
    if(contents!==wc || !trusted(details.requestingUrl) || !details.isMainFrame || perm!=='media' || details.mediaTypes?.includes('video')) return cb(false);
    const result=await dialog.showMessageBox(win,{message:'Allow Hermes to use your microphone?',buttons:['Allow','Cancel'],cancelId:1});
    cb(result.response===0 && trusted(wc.getURL()));
  });
  const logo = fs.readFileSync(path.join(__dirname,'hermes-light.svg')).toString('base64');
  const style = fs.readFileSync(path.join(__dirname,'chat.css'),'utf8') +
    `form:has(#password)::before{content:"";display:block;width:112px;height:20px;margin:0 auto 22px;background:currentColor;mask:url(data:image/svg+xml;base64,${logo}) center/contain no-repeat}`;
  const modelFilter = `(() => {
    if (window.__hermesModelFilter) return;
    window.__hermesModelFilter = true;
    const raw = new Set([
      'nvidia/nemotron-3-ultra-550b-a55b',
      'nvidia/nemotron-3.5-super-vl-120b-a12b',
      'nvidia/nemotron-3.5-lightning-30b-a3b'
    ]);
    const filter = () => document.querySelectorAll('[data-model-id]').forEach(node => {
      if (raw.has(node.getAttribute('data-model-id'))) node.style.display = 'none';
    });
    new MutationObserver(filter).observe(document.documentElement,{subtree:true,childList:true});
    filter();
  })()`;
  wc.on('did-finish-load',()=>{if(trusted(wc.getURL())) {
    wc.insertCSS(style).catch(()=>{});
    wc.executeJavaScript(modelFilter, true).catch(()=>{});
  }});
  Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'Hermes',submenu:[
    {label:'Change host…',click:welcome},{role:'reload'},{role:'quit'}]},
    {role:'editMenu'},{role:'viewMenu'}]));
  let saved;
  try {saved=JSON.parse(fs.readFileSync(config(),'utf8')).host}catch{}
  if(saved) await connect(saved); else await welcome();
});
app.on('window-all-closed',()=>app.quit());
