import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';

// Runtime locations belong to the invoking machine, never to the poster package.
const runtime = process.env.CODEX_RUNTIME_DEPENDENCIES;
const skill = process.env.CODEX_PRESENTATIONS_SKILL;
if (!runtime || !skill) throw new Error('Set CODEX_RUNTIME_DEPENDENCIES and CODEX_PRESENTATIONS_SKILL.');
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
const modulePath = path.join(runtime,'node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs');
const {Presentation, PresentationFile} = await import(pathToFileURL(modulePath).href);
const {finalizePresentation, applyPresentationChartFont} = await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const work = path.join(root,'codex_out/posters');
const out = path.join(root,'document/posters/output');
const evidence = path.join(root,'document/evidence/posters-20261031');
for (const dir of [work,out,evidence]) await fs.mkdir(dir,{recursive:true});
const facts = JSON.parse(await fs.readFile(path.join(root,'document/posters/assets/facts.json'),'utf8'));
const navy='#122D46', teal='#007F85', ink='#183347', muted='#506574', pale='#EAF4F4', amber='#A86210', grey='#D9E1E5';
const C = {
 zh: {
  subtitle:'三维声源定位与身份许可双轴跟随',
  functions:'RGB触摸屏   定向拾音   三维定位   声纹识别   双轴跟随',
  draft:'内部预写稿 · 2026-10-31', identity:'学校／团队署名及印刷尺寸待确认',
  platform:'Zynq-7020\nPL + PS / PYNQ', device:'真实FPGA实现视图',
  h1:'01  应用价值', h2:'02  系统与设计', h3:'03  关键结果',
  intro:'将声音方向、说话人验证与双轴指向结合，为设备提供本地声学感知与交互能力。三维定位输出方位角和俯仰角，不估计声源距离。',
  app1:'会议与教学', app1body:'面向发言位置变化的场景，辅助拾音方向调整，减少反复手动对准。',
  app2:'机器人与交互终端', app2body:'为“转向发声者”提供方向信息；声纹许可模式增加目标用户的授权条件。',
  ui:'RGB触摸屏独立操作', uibody:'通过FPC连接显示与触摸，选择模式、配置参数、查看状态。整机交互待实证。',
  photo:'整机与触摸屏实拍', photobody:'待补原件\n正面／斜45°照片与真实操作界面',
  potential:'应用收益以标定、识别可靠性与长稳验证为前提。',
  array:'四麦正四面体阵列 · 标称边长40 mm',
  pl:'PL  连续数据处理', plbody:'四麦采集\nFFT / PHAT / IFFT\n六对相关特征与PCM',
  ps:'PS  Linux / PYNQ', psbody:'三维C求解与方向筛选\n说话人评分与时限许可\n模式及动作管理',
  bus:'AXI\n特征 / PCM',
  touch:'RGB触摸屏\n交互与状态', das:'定向拾音\nDAS延迟叠加', axes:'双轴跟随\nPL PWM与保护',
  diagramnote:'功能框图：虚线表示待完成整机接合验证的路径。\n声纹当前使用单麦PCM，未证实接入DAS输出。',
  contribution:'核心设计贡献',
  c1:'连续采集与计算解耦', c1body:'PL处理连续数据，PS完成求解、识别与交互。',
  c2:'有界队列与结果保新', c2body:'淘汰旧READY，保护LOCKED帧，抑制旧角度驱动。',
  c3:'分层跟随许可', c3body:'两种自动模式分开；默认不开轴，方向与STOP保护独立。',
  bench:'声纹前端离线优化', less:'平均耗时减少', baseline:'优化前', opt:'优化后',
  condition:'两段录音各10.912 s，板端顺序处理，不含加载。\n新旧评分相同；网络推理耗时基本不变。\n本结果不代表在线端到端加速。 [E1]',
  live:'声纹双轴现场测试',
  tableHead:['项目','第1轮','第2轮'],
  rowNames:['运行时长 / s','消费定位帧','双轴命令提交','运行故障值','旧结果淘汰'],
  liveNote:'试验门限0.45，许可10 s。用户确认出现跟随。\n命令提交不代表机械到位；第二轮有1次序号间隙。\n两轮短测不构成识别准确率或长稳结论。 [E2]',
  next:'下一步：补齐三维误差、身份对照与实麦拾音效果。',
  footer:'声纹时限许可不等于多人身份与方向绑定。CAM++、Silero及厂商IP归原作者。E1/E2原始证据索引见备注。'
 },
 en: {
  subtitle:'3D Sound Localization and Speaker-Gated Pan–Tilt Tracking',
  functions:'RGB touchscreen   Directional audio   3D localization   Speaker verification   Pan–tilt tracking',
  draft:'INTERNAL DRAFT · 2026-10-31', identity:'Affiliation, team credits and print size to confirm',
  platform:'Zynq-7020\nPL + PS / PYNQ', device:'Actual FPGA implementation',
  h1:'01  Application value', h2:'02  System and design', h3:'03  Key results',
  intro:'SoundSight combines sound direction, speaker verification and pan–tilt control for local acoustic interaction. Localization estimates azimuth and elevation, not source distance.',
  app1:'Meetings and classrooms', app1body:'Directional audio could reduce manual aiming as speakers move or take turns.',
  app2:'Robots and interactive devices', app2body:'Direction estimates support turning toward a voice. Speaker-gated mode adds authorization for an enrolled user.',
  ui:'Standalone RGB touchscreen', uibody:'FPC display and touch for modes, settings and status. Integration awaits evidence.',
  photo:'Device and touchscreen photos', photobody:'Originals needed\nFront / 45° view and actual interface',
  potential:'Benefits depend on calibration, reliable verification\nand sustained operation.',
  array:'Four-mic tetrahedral array · 40 mm nominal edge',
  pl:'PL  Stream processing', plbody:'Mic acquisition\nFFT / PHAT / IFFT\nSix pair features / PCM',
  ps:'PS  Linux / PYNQ', psbody:'3D C solver and filtering\nSpeaker scores / permits\nModes and motion',
  bus:'AXI\nFeatures / PCM',
  touch:'RGB touchscreen\nControls and status', das:'Directional audio\nDelay-and-sum', axes:'Pan–tilt tracking\nPL PWM guards',
  diagramnote:'Functional diagram. Dashed paths await integration validation.\nSpeaker input is currently single-mic PCM, not verified DAS output.',
  contribution:'Core design contributions',
  c1:'Decoupled acquisition and processing', c1body:'PL handles streams; PS runs estimation, verification and UI.',
  c2:'Bounded queues and fresh results', c2body:'Drop old READY results, protect LOCKED frames and reject stale angles.',
  c3:'Layered motion permission', c3body:'Separate tracking modes; axes default off. Direction and STOP guards remain.',
  bench:'Offline speech front-end optimization', less:'less processing time', baseline:'Before', opt:'After',
  condition:'Two 10.912 s recordings, sequential board benchmark.\nLoading excluded. Scores unchanged; inference time\nessentially unchanged. Not an online end-to-end gain. [E1]',
  live:'Speaker-gated pan–tilt field tests',
  tableHead:['Metric','Run 1','Run 2'],
  rowNames:['Duration / s','Frames consumed','Motion commands','Runtime fault value','Old results dropped'],
  liveNote:'Trial threshold 0.45; permit 10 s. User observed tracking.\nCommands do not prove arrival; Run 2 has one sequence gap.\nShort trials do not establish accuracy or long-term stability. [E2]',
  next:'Next: measure 3D error, identity rejection and directional audio.',
  footer:'A time-limited permit does not bind a person to a direction in a multi-speaker scene. CAM++, Silero and vendor IP retain their attribution. Sources: notes.'
 }
};

for (const lang of ['zh','en']) {
 const t=C[lang], font=lang==='zh'?'Microsoft YaHei':'Arial';
 const p=Presentation.create({slideSize:{width:1920,height:1080}}), s=p.slides.add();
 s.background.fill='#FFFFFF';
 const elements=[];
 function rect(name,x,y,w,h,fill,lineFill='none',lineWidth=0,lineStyle='solid') {
  return s.shapes.add({name,geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:lineFill,width:lineWidth,style:lineStyle}});
 }
 function txt(name,text,x,y,w,h,size=24,color=ink,bold=false,align='left') {
  const a=s.shapes.add({name,geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  a.text=text; a.text.style={typeface:font,fontSize:size,color,bold,alignment:align,verticalAlignment:'top',autoFit:'none',wrap:'square',insets:0};
  elements.push({name,text,x,y,w,h,size});return a;
 }
 function line(x,y,w,h,color=grey,width=1.5,dashed=false,arrow=false) {
  return s.shapes.add({geometry:arrow?'connector':'line',kind:arrow?'straight':undefined,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:color,width,style:dashed?'dashed':'solid'},...(arrow?{tail:{type:'triangle',width:'sm',length:'sm'}}:{})});
 }
 function node(name,title,body,x,y,w,h,fill=pale,dashed=false) {
  const a=rect(name,x,y,w,h,fill,dashed?amber:teal,1.5,dashed?'dashed':'solid');
  txt(name+'-title',title,x+14,y+12,w-28,32,lang==='zh'?25:23,navy,true);
  if(body)txt(name+'-body',body,x+14,y+53,w-28,h-61,lang==='zh'?23:22,ink);
  return a;
 }
 rect('header',0,0,1920,178,navy);
 txt('brand','SoundSight',54,18,1150,82,70,'#FFFFFF',true);
 txt('subtitle',t.subtitle,56,102,1350,48,lang==='zh'?34:30,'#FFFFFF');
 txt('platform',t.platform,1455,31,290,95,30,'#FFFFFF',true);
 const b=await fs.readFile(path.join(root,'document/posters/assets/fpga-implementation-original.png'));
 s.images.add({name:'original-fpga-view',blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:t.device,fit:'contain',position:{left:1757,top:12,width:122,height:122}});
 txt('fpga-caption',t.device,1430,143,455,27,18,'#D7E9EE',false,'right');
 txt('functions',t.functions,56,186,1360,30,lang==='zh'?23:22,teal,true);
 txt('draft',t.draft,1415,185,453,27,19,amber,true,'right');
 txt('identity',t.identity,1130,213,737,24,18,muted,false,'right');
 line(54,244,1812,0,grey);
 line(524,271,0,730); line(1270,271,0,730);
 txt('h-value',t.h1,54,267,450,46,32,navy,true);
 txt('h-system',t.h2,552,267,690,46,32,navy,true);
 txt('h-results',t.h3,1298,267,568,46,32,navy,true);
 // Left column: application, interaction and an explicit genuine-photo slot.
 txt('intro',t.intro,54,328,446,156,lang==='zh'?25:25);
 txt('application-1',t.app1,54,492,446,37,27,teal,true);
 txt('application-1-body',t.app1body,54,535,446,78,24);
 txt('application-2',t.app2,54,620,446,37,27,teal,true);
 txt('application-2-body',t.app2body,54,663,446,103,24);
 txt('ui-heading',t.ui,54,777,446,35,lang==='zh'?27:26,teal,true);
 txt('ui-body',t.uibody,54,820,446,86,23);
 // A separate editable note reserves the missing real-world visual, never a mock device.
 rect('photo-reservation',54,912,446,61,'#F5F7F8',grey,1.5,'dashed');
 txt('photo-heading',t.photo,64,918,426,28,22,navy,true,'center');
 txt('photo-needed',lang==='zh'?'待补正面／斜45°照片与真实界面':'Original front / 45° views and interface needed',64,948,426,24,18,muted,false,'center');
 txt('application-conditions',t.potential,54,983,446,43,lang==='zh'?18:17,muted);
 // Central editable functional architecture.
 const mic=node('microphone-array',t.array,null,552,330,690,61,'#EAF4F4');
 const pl=node('pl',t.pl,t.plbody,552,433,300,147);
 const ps=node('ps',t.ps,t.psbody,946,433,296,147);
 line(702,391,0,42,teal,2.5,false,true);
 line(852,504,94,0,teal,2.5,false,true);
 txt('axi-label',t.bus,855,445,88,52,17,muted,false,'center');
 rect('touch-node',552,642,214,71,'#FFF7EC',amber,1.5,'dashed');
 rect('das-node',790,642,214,71,'#FFF7EC',amber,1.5,'dashed');
 rect('axes-node',1028,642,214,71,pale,teal,1.5);
 txt('touch-label',t.touch,560,651,198,54,lang==='zh'?23:21,ink,true,'center');
 txt('das-label',t.das,798,651,198,54,lang==='zh'?23:21,ink,true,'center');
 txt('axes-label',t.axes,1036,651,198,54,lang==='zh'?23:21,ink,true,'center');
 // Orthogonal routing has separate levels to avoid labels and crossings through boxes.
 line(1094,580,0,20,teal,2);
 line(659,600,476,0,teal,2);
 line(659,600,0,42,amber,2,true,true);
 line(897,600,0,42,amber,2,true,true);
 line(1135,600,0,42,teal,2,false,true);
 txt('diagram-boundary',t.diagramnote,552,724,690,61,lang==='zh'?20:19,muted);
 txt('contributions',t.contribution,552,799,690,38,29,navy,true);
 const cy=[842,902,962];
 for(let i=1;i<=3;i++){
  txt('contribution-'+i,t['c'+i],552,cy[i-1],690,30,24,teal,true);
  txt('contribution-body-'+i,t['c'+i+'body'],552,cy[i-1]+31,690,27,lang==='zh'?21:19,ink);
 }
 // Right column: editable chart computed from the two original benchmark inputs.
 txt('benchmark-heading',t.bench,1298,328,568,35,27,teal,true);
 txt('reduction',facts.frontend_reduction_percent.toFixed(2)+'%',1298,368,283,66,55,teal,true);
 txt('reduction-label',t.less,1590,389,276,35,lang==='zh'?24:23,ink);
 const chart=s.charts.add('bar',{
  name:'frontend-comparison', position:{left:1298,top:440,width:568,height:142},
  categories:[t.baseline,t.opt], series:[{name:lang==='zh'?'前端平均耗时 / s':'Mean front-end time / s',values:[Number(facts.frontend_mean_seconds.baseline.toFixed(3)),Number(facts.frontend_mean_seconds.opt1.toFixed(3))],points:[{idx:0,fill:'#92A6B3'},{idx:1,fill:teal}],fill:teal}],
  hasLegend:false,barOptions:{direction:'column',grouping:'clustered',gapWidth:120},
  xAxis:{visible:true,textStyle:{fontSize:20,fill:ink},majorGridlines:null},
  yAxis:{visible:true,min:0,max:10,majorUnit:5,numberFormatCode:'0" s"',textStyle:{fontSize:18,fill:muted},majorGridlines:{fill:grey,width:1}},
  dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.000',textStyle:{fontSize:21,fill:ink,bold:true}},
  chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF'
 });
 applyPresentationChartFont(chart,{fontFamily:font});
 txt('benchmark-conditions',t.condition,1298,590,568,90,lang==='zh'?20:19,muted);
 txt('field-heading',t.live,1298,696,568,36,lang==='zh'?27:26,teal,true);
 const vals=[t.tableHead,
  [t.rowNames[0],...facts.runs.map(r=>r.seconds.toFixed(3))],
  [t.rowNames[1],...facts.runs.map(r=>String(r.frames))],
  [t.rowNames[2],...facts.runs.map(r=>String(r.commits))],
  [t.rowNames[3],...facts.runs.map(r=>String(r.runtime_fault))],
  [t.rowNames[4],...facts.runs.map(r=>String(r.drops))]];
 const tab=s.tables.add({rows:6,columns:3,left:1298,top:741,width:568,height:168,columnWidths:[290,139,139],values:vals});
 tab.borders.assign({fill:grey,width:0.7,style:'solid'});
 for(let r=0;r<6;r++){
  tab.rows[r].height=28;
  for(let c=0;c<3;c++){
   const cell=tab.getCell(r,c);cell.fill=r===0?navy:(r%2?'#F1F6F7':'#FFFFFF');
   cell.text.style={typeface:font,fontSize:20,color:r===0?'#FFFFFF':ink,bold:r===0,alignment:c===0?'left':'center',verticalAlignment:'middle',insets:0,autoFit:'none'};
  }
 }
 tab.cells.block({row:0,column:0,rowCount:6,columnCount:3}).assign({margins:{top:0,bottom:0,left:6,right:6}});
 txt('field-conditions',t.liveNote,1298,934,568,65,lang==='zh'?18:17,muted);
 txt('next',t.next,1298,1005,568,22,lang==='zh'?18:17,teal,true);
 line(54,1030,1812,0,grey);
 txt('footer',t.footer,54,1042,1812,27,lang==='zh'?18:17,muted);
 // Notes supply exact evidence locations and map pending assertions to a separate checklist.
 s.speakerNotes.text=[
  'SoundSight bilingual poster, internal draft. Facts current as read on 2026-10-31. No new hardware or EDA execution.',
  'E1: document/evidence/ps-speaker-live-opt-20261025/board-opt1-bench-user.log and board-opt1-bench.json. Two reused recordings, 10.912 s each. Mean front-end times calculated from both rows per variant. Loading excluded; fixed-order sequential board benchmark, not concurrent capture. Network time essentially unchanged. Scores unchanged. No general recognition-accuracy claim.',
  'E2: document/evidence/speaker-dual-axis-20261030/board-tests.zip, logs/speaker-3d-20211118-232743-532522.json and logs/speaker-3d-20211118-233002-942132.json. Values from elapsed_seconds and stats. Runtime fault excludes the intentional STOP tail. User-observed tracking from the archive README. Board date is stale (2021); receipt date 2026-10-30. Threshold 0.45 is experimental, TTL 10 s. One old READY result dropped in Run 2. Motion commands are not independent mechanical arrivals.',
  'Original FPGA image: project/reports/ps_3d/latest_result/user-export/imp_schematic.png, copied unchanged. It is a physical implementation view, not a logical schematic or device photograph. No claim of complete timing closure: current servo_vertical_pwm output timing is incomplete.',
  'Architecture: document/main-architecture.md; software/tetra3d/README.md; document/requirements/report-poster-master-guide.md. Diagram is an authored functional explanation, not a tool-exported block design. Direction-only localization; far-field dominant-source model. RGB display/touch uses FPC as the final product scope, integration evidence pending. DAS reference implementation exists; microphone integration/gain and use as speaker input are unverified.',
  'Modes: follow-sound follows direction only; speaker and run --axes require a permit. Motion defaults off. Manual calibration is independent. A permit from prior audio does not bind current direction to that same person.',
  'Pending evidence and public identity/print decisions: document/posters/verification-checklist.md, V01–V03 and P04–P10. CAM++/Silero/vendor IP belong to their respective authors. Project contribution is system integration, scheduling and implementation optimization, not invention of those algorithms.'
 ].join('\n\n');
 const candidatePath=path.join(work,`soundsight-poster-${lang}-draft.pptx`);
 await (await PresentationFile.exportPptx(p)).save(candidatePath);
 execFileSync(path.join(runtime,'python/python.exe'),[path.join(root,'document/posters/src/fix_chart_label_wrap.py'),candidatePath]);
 await fs.writeFile(path.join(evidence,`${lang}-authored-elements.json`),JSON.stringify(elements,null,2));
 // Finalizer writes only a fresh output. It validates native tables/charts and package structure.
 const revision=process.env.POSTER_REVISION || 'review';
 const finalPath=path.join(out,`SoundSight-poster-${lang}-${revision}.pptx`);
 const result=await finalizePresentation({workspaceDir:root,candidatePath,finalPath,
  pythonExecutable:path.join(runtime,'python/python.exe'),
  integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','18288000,10287000','--validate-heading-fit','--require-native-table-slide','1'],
  explicitTotalSlideCount:1,requiredNativeTableOwnerSlides:[1],requiredNativeChartOwnerSlides:[1],
  materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[font]},
  verifyArtifactToolImport:true,receiptPath:path.join(evidence,`${lang}-${revision}-validation.json`)});
 console.log(JSON.stringify({lang,finalPath,integrity:result.packageIntegrity.status,layout:result.presentationLayout.findingCount,warnings:result.presentationLayout.warnings}));
}
