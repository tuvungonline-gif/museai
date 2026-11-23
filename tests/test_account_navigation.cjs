// Server-render unit check of the real navigation components (not a browser/layout test).
const path=require('node:path');
const fs=require('node:fs');
const os=require('node:os');
const {createRequire}=require('node:module');
const {execFileSync}=require('node:child_process');
const web=process.argv[2] ? path.resolve(process.argv[2]) : path.resolve(__dirname,'../source/infinite-canvas/web');
const webRequire=createRequire(path.join(web,'package.json'));
const esbuild=createRequire(webRequire.resolve('vite'))('esbuild');
const root=path.join(web,'src');
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'account-nav-'));
const output=path.join(temporary,'navigation.cjs');
const stubs={
'antd':'export const Tooltip=({children})=>children;',
'react-i18next':'export const useTranslation=()=>({i18n:{resolvedLanguage:"vi-VN"},t:(k)=>k==="navigation.config"?"Cài đặt":k});',
'@/components/ui/animated-theme-toggler':'export const AnimatedThemeToggler=()=>null;',
'@/constant/env':'export const DOCS_URL="https://docs.canvas.best/";',
'@/i18n':'export const changeAppLocale=()=>{};',
'@/lib/utils':'export const cn=(...values)=>values.filter(Boolean).join(" ");',
'@/lib/canvas-theme':'export const canvasThemes={dark:{node:{text:"white"}}};',
'@/stores/use-config-store':'export const useConfigStore=(select)=>select({openConfigDialog:()=>{}});',
'@/stores/use-theme-store':'export const useThemeStore=(select)=>select({theme:"dark",setTheme:()=>{}});'
};
esbuild.build({stdin:{contents:`export {UserStatusActions} from '${root}/components/layout/user-status-actions.tsx';export {navigationTools} from '${root}/constant/navigation-tools.ts';`,resolveDir:root,loader:'tsx'},bundle:true,platform:'node',format:'cjs',jsx:'automatic',define:{'import.meta.env':'{}'},outfile:output,plugins:[{name:'unit-dependencies',setup(build){build.onResolve({filter:/.*/},args=>{if(stubs[args.path])return {path:args.path,namespace:'stub'};if(args.path.startsWith('@/'))return {path:root+'/'+args.path.slice(2)+'.ts'};if(args.path==='react'||args.path==='react/jsx-runtime')return {path:args.path,external:true};});build.onLoad({filter:/.*/,namespace:'stub'},args=>({contents:stubs[args.path],loader:'js'}));}}] }).then(()=>{
  const check=`const assert=require('node:assert/strict');
const role=process.argv[1];
global.window={__RUNTIME_CONFIG__:{MEMBERS_ENABLED:true,MEMBER_ROLE:role}};
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const {UserStatusActions,navigationTools}=require(process.argv[2]);
const html=renderToStaticMarkup(React.createElement(UserStatusActions));
assert.match(html,/href="\\/account"/);assert.match(html,/Quản lý tài khoản/);
assert.doesNotMatch(html,/v0\\.20\\.0|github.com\\/basketikun/);
assert.equal(html.includes('Cài đặt'),role==='admin');
assert.equal(navigationTools.some(t=>t.slug==='config'),role==='admin');
for(const slug of ['canvas','image','video','prompts','assets'])assert(navigationTools.some(t=>t.slug===slug));
console.log('PASS account link, legacy links removed, settings visibility: '+role);`;
  for(const role of ['member','admin'])execFileSync(process.execPath,['-e',check,role,output],{stdio:'inherit',env:{...process.env,NODE_PATH:path.join(web,'node_modules')}});
}).finally(()=>fs.rmSync(temporary,{recursive:true,force:true})).catch(e=>{console.error(e);process.exitCode=1;});
