import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const INPUT = '/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx';
const OUTPUT = '/Users/xizhuxizhu/Desktop/IndProj04/outputs/manual-20260602-defense-review/presentations/acceptance-defense-review/output/项目验收答辩PPT_答辩强化版_base.pptx';

const C = {
  white: '#FFFFFF', navy: '#061A46', blue: '#2F68EF', pale: '#EAF3FF', line: '#BFD5F4',
  ink: '#102033', muted: '#53657A', green: '#0E9F5C', orange: '#F59E0B', purple: '#6B49C8', red: '#B93232'
};
const FONT = 'Microsoft YaHei';
function addShape(slide, cfg) { return slide.shapes.add(cfg); }
function addRect(slide, x, y, w, h, fill = C.white, line = '#FFFFFF00', radius = false) {
  return addShape(slide, { geometry: radius ? 'roundRect' : 'rect', adjustmentList: radius ? [{ name:'adj', formula:'val 10000' }] : undefined, position:{left:x,top:y,width:w,height:h}, fill, line:{ width: line === '#FFFFFF00' ? 0 : 1.2, fill: line }});
}
function addText(slide, text, x, y, w, h, opts = {}) {
  const shape = addShape(slide, { geometry: opts.geometry ?? 'rect', adjustmentList: opts.radius ? [{ name:'adj', formula:`val ${opts.radius}` }] : undefined, position:{left:x,top:y,width:w,height:h}, fill: opts.fill ?? '#FFFFFF00', line: opts.line ?? {width:0,fill:'#FFFFFF00'} });
  shape.text = String(text); shape.text.typeface = opts.typeface ?? FONT; shape.text.fontSize = opts.fontSize ?? 18; shape.text.color = opts.color ?? C.ink; shape.text.bold = opts.bold ?? false; shape.text.alignment = opts.alignment ?? 'left'; shape.text.verticalAlignment = opts.verticalAlignment ?? 'top'; shape.text.autoFit = opts.autoFit ?? 'shrinkText'; shape.text.insets = opts.insets ?? {left:0,right:0,top:0,bottom:0}; return shape;
}
function slide2(slide) {
  addRect(slide, 60, 110, 1168, 456, '#F8FBFF', C.line, true);
  addText(slide, '验收逻辑：任务要求 → 技术攻关 → 实验验证 → 原型系统 → 成果材料', 118, 130, 1040, 28, {fontSize:20,bold:true,color:C.navy,alignment:'center'});
  const rows = [
    ['多智能体协作原型框架', '已完成', '能力命名、结构化判别、职责化复核、授权改判、执行映射与过程记录形成闭环。', C.blue],
    ['多智能体交互与共识机制', '已验证', '四类职责角色、二轮定向复核与显式授权门禁，支撑复杂样本受控净修正。', C.orange],
    ['智能体行为可信标识', '已落地', '候选快照、结构化裁决、角色提案、授权判断、选择轨迹与实例映射可回放。', C.purple],
    ['真实标签反馈验证', '有数据', '563 条冻结样本；train=450、test=113；主结果 78.76% → 88.50%，扩展配置 92.92%。', C.green],
    ['成果凝练与材料交付', '已形成', '原型系统、技术报告、论文稿、专利材料、成果汇编、实验图表和演示材料同步支撑。', C.red],
  ];
  let y = 177;
  for (const [req, status, proof, accent] of rows) {
    addRect(slide, 104, y, 1072, 58, C.white, '#D3E2F7', true);
    addRect(slide, 104, y, 9, 58, accent, accent, false);
    addText(slide, req, 130, y + 17, 250, 22, {fontSize:16.5,bold:true,color:C.navy,autoFit:'shrinkText'});
    addText(slide, status, 404, y + 17, 118, 22, {fontSize:16,bold:true,color:accent,alignment:'center',autoFit:'shrinkText'});
    addText(slide, proof, 548, y + 16, 590, 24, {fontSize:13.3,color:C.ink,autoFit:'shrinkText'});
    y += 68;
  }
}
function slide11(slide) {
  addRect(slide, 36, 548, 570, 125, '#F8FBFF', '#D8E5F7', true);
  addText(slide, '工程实现规模：66 个文件 / 20,226 行有效代码', 62, 562, 520, 22, {fontSize:15.8,bold:true,color:C.navy,alignment:'center'});
  const cols = [['src/','14','7,654',C.blue],['scripts/','31','9,008',C.orange],['tests/','7','2,609',C.green],['schemas/','14','955',C.purple]];
  cols.forEach(([scope, files, lines, accent], i) => { const x=58+i*133; addRect(slide,x,596,112,56,C.white,accent,true); addText(slide,scope,x+8,603,96,13,{fontSize:8.8,bold:true,color:accent,alignment:'center'}); addText(slide,`${files} 个文件`,x+8,620,96,12,{fontSize:8.4,color:C.ink,alignment:'center'}); addText(slide,`${lines} 行`,x+8,635,96,12,{fontSize:8.4,bold:true,color:C.navy,alignment:'center'}); });
}
function slide17(slide) {
  addRect(slide, 362, 265, 338, 44, C.white, '#FFFFFF00', false);
  addText(slide, '材料已形成，经中心签报提交；\n受理证明按正式流程补充', 370, 270, 320, 34, {fontSize:12.2,bold:true,color:C.green,alignment:'center',verticalAlignment:'middle',autoFit:'shrinkText'});
}
const p = await PresentationFile.importPptx(await FileBlob.load(INPUT));
slide2(p.slides.getItem(1));
slide11(p.slides.getItem(10));
slide17(p.slides.getItem(16));
const pptx = await PresentationFile.exportPptx(p);
await pptx.save(OUTPUT);
console.log(OUTPUT);
