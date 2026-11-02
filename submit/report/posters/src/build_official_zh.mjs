import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';

const runtime=process.env.CODEX_RUNTIME_DEPENDENCIES, skill=process.env.CODEX_PRESENTATIONS_SKILL;
if(!runtime || !skill) throw new Error('Set CODEX_RUNTIME_DEPENDENCIES and CODEX_PRESENTATIONS_SKILL.');
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
process.on('uncaughtException',error=>{console.error(error.stack);process.exit(1);});
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(runtime,'node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const lang=process.env.POSTER_LANGUAGE||'zh';
if(!['zh','en'].includes(lang))throw new Error('POSTER_LANGUAGE must be zh or en.');
const en=lang==='en';
const copy=en?JSON.parse(await fs.readFile(path.join(root,'document/posters/assets/copy-en.json'),'utf8')):null;
const translationMap=[];
const work=path.join(root,`codex_out/poster-content-${lang}`);
const evidence=path.join(root,en?'document/evidence/posters-en-20261102':'document/evidence/posters-content-20261101');
const out=path.join(root,'document/posters/output');
for(const d of [work,evidence,out]) await fs.mkdir(d,{recursive:true});
const source=path.join(root,'document/posters/assets/reference/poster-reference.pptx');
const imported=await PresentationFile.importPptx(await FileBlob.load(source));
await fs.writeFile(path.join(evidence,'template-inspection.json'),JSON.stringify(await imported.inspect({kind:'slide,layout,textbox,shape,image',maxChars:50000}),null,2));
const facts=JSON.parse(await fs.readFile(path.join(root,'document/posters/assets/joint-run-facts.json'),'utf8'));
const handoff=await fs.readFile(path.join(root,facts.content_handoff),'utf8');
const p=Presentation.create({slideSize:{width:1280,height:720}}),s=p.slides.add();
const elements=[], black='#000000',red='#FF0000',gray='#2F2F2F',font=en?'Calibri':'Microsoft YaHei';
function box(name,x,y,w,h,fill='#FFFFFF',stroke=black,dashed=false){return s.shapes.add({name,geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:0.8,style:dashed?'dashed':'solid'}});}
function txt(name,text,x,y,w,h,size=14.667,color=black,bold=false,align='left',typeface=font){
 if(en){
  const item=copy.elements[name];
  if(!item)throw new Error(`Missing English text: ${name}`);
  translationMap.push({name,zh:text,en:item.text});
  text=item.text;({x,y,w,h,size,typeface}={x,y,w,h,size,typeface,...item});
 }
 const a=s.shapes.add({name,geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 a.text=text;a.text.style={typeface,fontSize:size,color,bold,alignment:align,verticalAlignment:'top',autoFit:'none',wrap:'square',insets:0};
 elements.push({name,text,x,y,w,h,size});return a;
}
function line(x,y,w,h,dashed=false,arrow=true){return s.shapes.add({geometry:arrow?'connector':'line',kind:arrow?'straight':undefined,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:gray,width:1,style:dashed?'dashed':'solid'},...(arrow?{tail:{type:'triangle',width:'sm',length:'sm'}}:{})});}
function reverseLine(x,y,w,h,dashed=false,both=false){return s.shapes.add({geometry:'connector',kind:'straight',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:gray,width:1,style:dashed?'dashed':'solid'},head:{type:'triangle',width:'sm',length:'sm'},...(both?{tail:{type:'triangle',width:'sm',length:'sm'}}:{})});}
function node(name,text,x,y,w,h,kind='pl'){
 box(name,x,y,w,h,kind==='pl'?'#D39A96':kind==='ps'?'#C4D79B':'#FFFFFF',black,kind==='pending');
 txt(name+'-label',text,x+3,y+5,w-6,h-7,13.333,black,false,'center');
}
// All furniture (banners, rules, AMD marks, rounded frames) is retained from the actual template.
txt('brand','SoundSight',28,42,520,40,32,black,true,'left','Times New Roman');
txt('project-title','会议声源感知与双轴跟随',28,81,520,30,24,black,true,'left','SimSun');
txt('introduction','项目简介',45.71,118,293.47,34,24,'#FFFFFF',true,'center');
txt('team','团队成员：待确认',692,28,267,24,16,black,true,'left','SimSun');
txt('school','学校署名：待确认',738,57,228,24,16,black,true,'left','SimSun');
txt('advisor','指导老师：待确认',780,86,186,24,16,black,true,'left','SimSun');
box('school-logo-slot',973.54,17.21,76.5,75.79,'#FFFFFF','#B0B0B0',true);
txt('school-logo-needed','校徽\n待确认',980,38,63,43,14,'#666666',false,'center');
box('real-device-photo-slot',1086.86,3.91,168.5,147.29,'#FFFFFF','#B0B0B0',true);
txt('real-device-photo-needed','整机实物照片\n待补原件',1098,59,146,44,14.667,'#666666',false,'center');
txt('platform','AMD Zynq-7020｜PL＋PS协同\nLinux / PYNQ',1054,160,207,36,12,black,false,'center');
txt('intro-body','会议发言者的位置与次序不断变化，固定指向设备需要反复调整。SoundSight首先服务会议发言者指向，后续面向机器人等具身智能设备，提供声源方向感知与说话人身份信息。',28,174,373,86);

// Replace the sample project's photographic pipeline with an editable functional use-case schematic.
const apps=[['选择模式','触摸设置\n选择声纹模板'],['发声测向','同步采集\n方位／俯仰'],['判断跟随','声音跟随\n可选声纹许可'],['指向与拾音','双轴指向\n并行合成拾音']];
for(let i=0;i<4;i++){
 const x=28+i*90;
 box('application-'+i,x,270,78,43,i===1?'#D39A96':i===2?'#C4D79B':'#F2F2F2');
 txt('application-label-'+i,apps[i][0],x+2,283,74,22,13.333,black,false,'center');
 txt('application-caption-'+i,apps[i][1],x-1,320,80,36,12.667,black,false,'center');
 if(i<3)line(x+78,291,12,0);
}
txt('application-caption','典型使用流程（最终设计）',68,364,310,24,14.667,black,true,'center');
txt('system-scope','系统以Zynq-7020实现声音感知与指向控制。PL承担同步采集、频域相关和双轴PWM，PS执行三维求解、声纹验证与跟随决策；最终设计通过RGB触摸屏完成本地操作，并以方向引导定向拾音。',28,402,377,96);
txt('technical-heading','关键技术问题与设计要点：',28,508,377,25,14.667,black,true);
txt('technical-body','空间测角：非共面四麦提供水平与垂直约束，\n输出方位角和俯仰角，不估计距离。\n任务协同：定位持续更新，声纹异步计算，\n通过结果在有限时间内参与跟随决策。\n执行控制：方向质量、范围和模式共同决定\n动作，默认不开轴，保留停止与超时保护。\n功能接合：拾音接收同步音频与有效方向，\n触摸交互贯通配置与状态反馈。',28,537,382,157);

// Explicit signal paths; prefixes identify physical PL/PS ownership without implying electrical UI wiring.
node('array','正四面体四麦',436,123,103,27,'input');
node('acquisition','PL 同步采集',563,123,103,27);
line(539,136,24,0);
node('correlation','PL 相关特征',436,181,103,27);
node('solver','PS 三维求解',563,181,103,27,'ps');
node('das','PS DAS拾音',704,181,91,27,'pending');
// Synchronous audio to correlation; the parallel PCM/DMA branch feeds speaker input and DAS.
line(614,150,0,13,false,false);line(487,163,127,0,false,false);line(487,163,0,18);
txt('sync-audio','同步音频',494,163,65,17,11.333);
line(666,136,4,0,false,false);line(670,136,0,28,false,false);line(670,164,131,0,false,false);line(750,164,0,17,true);
line(801,164,0,100,false,false);reverseLine(795,264,6,0);
txt('pcm-dma','四路PCM\nDMA',678,131,72,30,11.333);
line(539,195,24,0);
txt('feature-bus','六对特征 / AXI',493,214,106,18,11.333);
line(666,195,38,0,true);txt('direction-das','方向',671,177,32,16,10.667);
line(750,208,0,10,true);txt('mono-output','单声道音频',702,216,94,18,11.333,black,false,'center');
node('pwm','PL 双轴PWM',436,250,103,27);
node('decision','PS 跟随决策',563,250,103,27,'ps');
box('speaker',704,244,91,38,'#C4D79B');
txt('speaker-label','PS 声纹验证\n单路取样',707,247,85,33,12,black,false,'center');
line(614,208,0,42);txt('angles','方位／俯仰',620,219,79,18,11.333);
reverseLine(539,264,24,0);txt('angle-command','角度命令',526,232,71,18,11.333);
reverseLine(666,264,38,0);txt('permit','限时许可',659,284,69,18,11.333);
txt('speaker-mode','仅声纹模式',725,284,74,18,10.667);
node('axes','双轴机构',436,309,103,27,'output');line(487,277,0,32);
node('touchscreen','RGB触摸屏',563,309,103,27,'pending');reverseLine(614,277,0,32,true,true);
txt('ui-link','操作\n状态',622,279,34,29,10.667);
txt('architecture-status','虚线部分待整机接合验证；DAS已有PC参考实现。\n声纹当前使用单路音频，未接入DAS输出。',436,342,365,31,11.333,'#555555');
txt('architecture-caption','系统结构与关键创新点',452,376,314,25,14.667,black,true,'center');

txt('design-vertical','创\n新\n设\n计',817,280,33,214,24,'#FFFFFF',false,'center');
txt('result-vertical','测\n试\n结\n果',897,236,31,140,22.667,'#FFFFFF',false,'center');
txt('tetra-heading','正四面体四麦三维测角',460,422,309,25,16,red);
txt('tetra-description','正四面体四麦的非共面布局形成六组时差约束。PL提取通道间相关特征，PS通过亚采样插值、最小二乘求解和方向筛选，计算声源方位角与俯仰角。阵列几何、求解程序与软硬件处理链路共同构成三维测角方案，为双轴指向和定向拾音提供方向输入。',460,451,308,110);
txt('async-heading','异步声纹授权跟随',458,591,314,25,16,red);
txt('async-description','声纹异步计算，通过后在限时内允许双轴按新方向更新，避免动作逐次等待推理。许可作用于当前声源方向，尚不保证多人身份与方向绑定。',458,616,315,73);

txt('joint-heading','定位、声纹与双轴联合运行',948,220,310,24,16,black,true);
const vals=[['指标','第一轮','第二轮'],
 ['日志运行时间 / s',...facts.runs.map(r=>r.seconds.toFixed(3))],
 ['读取定位帧 / 帧',...facts.runs.map(r=>String(r.frames))],
 ['停止前声纹计算 / 次',...facts.runs.map(r=>String(r.speaker_before_stop))],
 ['双轴目标提交 / 次',...facts.runs.map(r=>String(r.commits))],
 ['运行故障值',...facts.runs.map(r=>String(r.runtime_fault))],
 ['旧定位结果淘汰 / 帧',...facts.runs.map(r=>String(r.drops))]];
if(en){vals[0]=copy.table_headers;for(let r=1;r<7;r++)vals[r][0]=copy.table_rows[r-1];}
const tableWidths=en?[193,60,60]:[183,65,65];
const tab=s.tables.add({rows:7,columns:3,left:948,top:251,width:313,height:147,columnWidths:tableWidths,values:vals});
tab.borders.assign({fill:'#808080',width:0.6,style:'solid'});
for(let r=0;r<7;r++){
 tab.rows[r].height=21;
 for(let c=0;c<3;c++){
  const cell=tab.getCell(r,c);cell.fill=r===0?gray:(r%2?'#F2F2F2':'#FFFFFF');
  cell.text.style={typeface:font,fontSize:13.333,color:r===0?'#FFFFFF':black,bold:r===0,alignment:c===0?'left':'center',verticalAlignment:'middle',insets:0,autoFit:'none'};
 }
}
tab.cells.block({row:0,column:0,rowCount:7,columnCount:3}).assign({margins:{top:0,bottom:0,left:4,right:4}});
txt('test-conditions','48 kHz采样；方向筛选窗3帧，至少1帧合格；\n音量门限12000（PCM统计量）。',910,406,354,35,12.667,'#555555');
txt('joint-result','两轮板端试验均完成了定位读取、声纹评分和双轴目标提交，运行期间故障值均为0；用户现场观察到机构随声音方向转动。结果支持三类任务在同一平台联合运行，提交次数仅表示控制命令，不代表机械到位。',910,448,354,98);
txt('test-limitations','测试采用同一目标模板，声纹试验门限为0.45、许可时长为10 s，两轴同时启用。两轮停止前各完成6次声纹计算，方向通路在其间持续更新。第二轮淘汰1个旧定位结果；当前证据尚不能给出角度误差、身份识别准确率或长期稳定性结论。',910,551,354,107);
txt('outlook','补齐方向与指向误差、他人声纹对照、实麦拾音及触摸操作验证，再拓展机器人听觉交互。',910,668,354,39,13.333);
// Retain explicit evidence boundaries in editable notes, outside the visual poster.
s.speakerNotes.text=[
 'SoundSight中文内部预写稿。按用户指定AMD_poster_template(3).pptx的原始版式编辑；仓库poster-reference.pptx与指定文件SHA256一致。模板注释不是项目内容。学校、人员、实物图片、印刷要求待确认。英文版未改。',
 'E2: document/evidence/speaker-dual-axis-20261030/board-tests.zip中的logs/speaker-3d-20211118-232743-532522.json与logs/speaker-3d-20211118-233002-942132.json；运行时长32.158704651/27.254283026 s，帧3012/2552，命令117/94，runtime_fault_or=0/0，旧结果淘汰0/1，序号间隙0/1。正常STOP尾帧不计入运行故障。归档日期2026-10-30，板卡时钟2021为旧值。用户观察到跟随，不代表到位、精度、识别率或长稳验收。',
 '最终范围RGB触摸屏、定向拾音、三维方向估计、声纹识别、双轴跟随；唯一主案Zynq-7020 PL+PS/PYNQ。三维只估方位/俯仰，不估距离。follow-sound只按方向；speaker与run --axes要求声纹许可，默认不开轴；时限许可不构成多人身份与方向绑定。',
 '功能图为自行绘制的可编辑说明图，不是Vivado原始BD，不是实物照片。RGB独立操作与DAS实麦接合仍待证据；当前声纹使用单麦PCM，未证明以DAS输出作为输入。核心贡献为系统集成、调度与实现优化；CAM++、Silero与厂商IP归原作者。',
 '材料缺口及内部预写核验：document/posters/verification-checklist.md。未编造测量数字；无Vivado、硬件操作或Git提交。实际印刷尺寸待确认，当前沿用模板13⅓×7½英寸。',
 '上版依据与完整独立证据表：'+facts.content_handoff+'。图示DAS由四路PCM和有效方向共同驱动，声纹当前从单路音频取样。RGB与PS应用为逻辑交互关系，不确认电气连接。停止前声纹计算由有限数值评分且completed_at <= 会话at统计，两轮各6次；包含STOP后收尾的总次数8/7不用于海报。48kHz取自settings.geometry.sample_rate_hz，3帧/至少1帧/12000来自settings；12000不是分贝。',
 '交接文件内部核验与同步条目（供备注查询，不作海报正文）：\n'+handoff.slice(handoff.indexOf('## 3.'))
].join('\n\n');
if(en){
 if(translationMap.length!==Object.keys(copy.elements).length)throw new Error('Unused or missing English translation.');
 s.speakerNotes.text=[
  'English counterpart of document/posters/output/SoundSight-poster-zh-content-v3.pptx. Internal draft; affiliation, credits, original device photographs and print dimensions remain to be confirmed. Content basis: '+facts.content_handoff+'.',
  'E2: document/evidence/speaker-dual-axis-20261030/board-tests.zip, logs/speaker-3d-20211118-232743-532522.json and logs/speaker-3d-20211118-233002-942132.json. Logged durations: 32.158704651 / 27.254283026 s. Localization frames read: 3012 / 2552, including invalid-direction frames. Speaker evaluations completed before STOP: 6 / 6. Pan–tilt target commands: 117 / 94. Runtime fault values: 0 / 0. Old localization results dropped: 0 / 1; sequence gaps: 0 / 1. The normal STOP tail is excluded from runtime faults. These are two short trials, not before/after performance comparisons.',
  'Before-STOP counts include finite numeric scores with completed_at <= the session at timestamp. The totals including post-STOP completion are 8 / 7 and are not used in the table. Sampling: 48 kHz. Direction window: 3 frames, at least 1 valid. Level threshold: 12000 in a PCM statistic, not dB. Same enrolled target template, trial score threshold 0.45, permit 10 s, both axes enabled. Calculations are not correct identifications; target commands do not prove mechanical arrival. The user observed sound-following motion. No angular-error, recognition-accuracy or long-term-stability claim is made.',
  'Main system: Zynq-7020 PL + PS / Linux/PYNQ. PL handles acquisition, correlation and PWM; PS handles 3D solving, speaker verification and tracking decisions. Localization estimates azimuth and elevation, not range. follow-sound uses direction only; speaker and run --axes require a permit. Axes default off. A permit does not bind identity to direction in a multi-speaker scene.',
  'The editable diagram explains the functional design; it is not a vendor-generated block design or device photograph. DAS takes four-channel PCM plus valid direction. The current speaker input uses one channel and is not DAS output. Dashed blocks/paths await system integration evidence in this approved content snapshot. Touch links describe application interaction, not a verified electrical interface. DAS has a PC reference implementation. CAM++, Silero, DAS methods and vendor FFT/IFFT IP retain their attribution.',
  'Supporting evidence and pending checks: document/posters/verification-checklist.md; document/posters/assets/joint-run-facts.json; '+facts.content_handoff+'. Archive receipt date: 2026-10-30; the board calendar still shows 2021 and has not been rewritten. The 2026-11-02 CF1A/USB/screen progress is outside this bilingual content snapshot and requires a coordinated content revision.'
 ].join('\n\n');
 await fs.writeFile(path.join(evidence,'translation-map.json'),JSON.stringify(translationMap,null,2));
}
const donor=path.join(work,'content.pptx'),candidate=path.join(work,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(donor);
await fs.writeFile(path.join(evidence,'authored-elements.json'),JSON.stringify(elements,null,2));
if(en)await fs.writeFile(path.join(evidence,'table-layout.json'),JSON.stringify({x:948,y:251,widths:tableWidths,rowHeight:21,values:vals},null,2));
const py=path.join(runtime,'python/python.exe');
execFileSync(py,[path.join(root,'document/posters/src/merge_official_template.py'),source,donor,candidate,lang],{stdio:'inherit'});
const revision=process.env.POSTER_REVISION||'content-v3';
const finalPath=path.join(out,`SoundSight-poster-${lang}-${revision}.pptx`);
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath,pythonExecutable:py,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','1'],
 explicitTotalSlideCount:1,requiredNativeChartOwnerSlides:[],requiredNativeTableOwnerSlides:[1],
 fontPolicy:{basis:'design',families:[font,'Times New Roman','SimSun','Calibri','Arial']},
 verifyArtifactToolImport:true,receiptPath:path.join(evidence,`${revision}-validation.json`)});
console.log(JSON.stringify({finalPath,integrity:result.packageIntegrity.status,layout:result.presentationLayout.findingCount,warnings:result.presentationLayout.warnings}));
