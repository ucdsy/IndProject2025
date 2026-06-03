import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const INPUT = '/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx';
const OUTPUT = '/Users/xizhuxizhu/Desktop/项目验收答辩PPT_答辩强化版_20260602.pptx';

const C = {
  bg: '#F7FBFF',
  white: '#FFFFFF',
  navy: '#061A46',
  blue: '#2F68EF',
  blue2: '#0B63CE',
  cyan: '#1EA7E1',
  pale: '#EAF3FF',
  line: '#BFD5F4',
  ink: '#102033',
  muted: '#53657A',
  green: '#0E9F5C',
  orange: '#F59E0B',
  purple: '#6B49C8',
  red: '#B93232',
};
const FONT = 'Microsoft YaHei';

function addShape(slide, cfg) { return slide.shapes.add(cfg); }
function addRect(slide, x, y, w, h, fill = C.white, line = '#FFFFFF00', radius = false) {
  return addShape(slide, {
    geometry: radius ? 'roundRect' : 'rect',
    adjustmentList: radius ? [{ name: 'adj', formula: 'val 10000' }] : undefined,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { width: line === '#FFFFFF00' ? 0 : 1.2, fill: line },
  });
}
function addText(slide, text, x, y, w, h, opts = {}) {
  const shape = addShape(slide, {
    geometry: opts.geometry ?? 'rect',
    adjustmentList: opts.radius ? [{ name: 'adj', formula: `val ${opts.radius}` }] : undefined,
    position: { left: x, top: y, width: w, height: h },
    fill: opts.fill ?? '#FFFFFF00',
    line: opts.line ?? { width: 0, fill: '#FFFFFF00' },
  });
  shape.text = String(text);
  shape.text.typeface = opts.typeface ?? FONT;
  shape.text.fontSize = opts.fontSize ?? 18;
  shape.text.color = opts.color ?? C.ink;
  shape.text.bold = opts.bold ?? false;
  shape.text.alignment = opts.alignment ?? 'left';
  shape.text.verticalAlignment = opts.verticalAlignment ?? 'top';
  shape.text.autoFit = opts.autoFit ?? 'shrinkText';
  shape.text.insets = opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 };
  return shape;
}
function addCard(slide, x, y, w, h, title, body, accent = C.blue) {
  addRect(slide, x, y, w, h, C.white, C.line, true);
  addRect(slide, x, y, 6, h, accent, accent, false);
  addText(slide, title, x + 20, y + 15, w - 36, 26, { fontSize: 18, bold: true, color: accent });
  addText(slide, body, x + 20, y + 47, w - 34, h - 58, { fontSize: 13.4, color: C.ink, autoFit: 'shrinkText', insets: {left:0,right:0,top:0,bottom:0} });
}
function coverTitle(slide) {
  addRect(slide, 82, 25, 930, 76, C.bg, '#FFFFFF00', false);
}
function addFooterPage(slide, page) {
  addRect(slide, 1186, 682, 55, 22, C.bg, '#FFFFFF00', false);
  addText(slide, String(page).padStart(2, '0'), 1196, 687, 36, 14, {
    fontSize: 7.5, color: C.muted, alignment: 'right', autoFit: 'shrinkText',
  });
}
function slide2(slide) {
  // Replace agenda/meta page with acceptance-evidence closure.
  coverTitle(slide);
  addText(slide, '任务书要求与完成总览：原型、算法、数据、成果均形成验收证据', 90, 39, 920, 34, {
    fontSize: 27, bold: true, color: C.blue,
  });
  addRect(slide, 64, 112, 1152, 448, '#F8FBFF', C.line, true);
  addText(slide, '验收逻辑：任务要求 → 技术攻关 → 实验验证 → 原型系统 → 成果材料', 120, 128, 1030, 30, {
    fontSize: 20, bold: true, color: C.navy, alignment: 'center',
  });
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
    addText(slide, req, 130, y + 17, 250, 22, { fontSize: 16.5, bold: true, color: C.navy, autoFit: 'shrinkText' });
    addText(slide, status, 404, y + 17, 118, 22, { fontSize: 16, bold: true, color: accent, alignment: 'center', autoFit: 'shrinkText' });
    addText(slide, proof, 548, y + 16, 590, 24, { fontSize: 13.3, color: C.ink, autoFit: 'shrinkText' });
    y += 68;
  }
  addRect(slide, 96, 593, 1085, 56, '#E5EFFF', C.blue, true);
  addText(slide, '本项目已形成“任务要求—技术链路—实验数据—原型系统—成果材料”的五类验收证据。', 126, 609, 1026, 23, {
    fontSize: 18, bold: true, color: C.blue, alignment: 'center',
  });
}
function slide4(slide) {
  coverTitle(slide);
  addText(slide, '研究定位与目标：语义路由是典型验证场景，不是项目主题偏移', 90, 39, 940, 34, {
    fontSize: 26, bold: true, color: C.blue,
  });
  // Strengthen scope statement at the bottom without disturbing the main flow.
  addRect(slide, 82, 581, 1110, 50, C.navy, C.navy, true);
  addText(slide, '验收口径：语义路由用于验证能力命名、候选内判别、职责化复核和可信留痕；生产级 DNS 解析与端到端业务联调属于后续工程化范围。', 117, 596, 1040, 18, {
    fontSize: 14.2, bold: true, color: C.white, alignment: 'center', autoFit: 'shrinkText',
  });
}
function slide6(slide) {
  coverTitle(slide);
  addText(slide, '攻关难点：在固定候选边界内完成复合语义判断与受控纠错', 90, 39, 940, 34, {
    fontSize: 27, bold: true, color: C.blue,
  });
  addRect(slide, 86, 515, 1114, 80, '#E5EFFF', C.blue, true);
  addText(slide, '技术抓手：把“自然语言请求到能力地址”定义为受限能力命名空间下的语义路由问题，并用职责化多智能体复核处理复杂边界样本。', 124, 538, 1040, 26, {
    fontSize: 18.2, bold: true, color: C.navy, alignment: 'center', autoFit: 'shrinkText',
  });
}
function slide11(slide) {
  // Replace tiny code table with a readable engineering asset rail.
  addRect(slide, 36, 548, 570, 125, '#F8FBFF', '#D8E5F7', true);
  addText(slide, '工程实现规模：66 个文件 / 20,226 行有效代码', 62, 562, 520, 22, {
    fontSize: 15.8, bold: true, color: C.navy, alignment: 'center',
  });
  const cols = [
    ['src/', '14', '7,654', C.blue],
    ['scripts/', '31', '9,008', C.orange],
    ['tests/', '7', '2,609', C.green],
    ['schemas/', '14', '955', C.purple],
  ];
  cols.forEach(([scope, files, lines, accent], i) => {
    const x = 58 + i * 133;
    addRect(slide, x, 596, 112, 56, C.white, accent, true);
    addText(slide, scope, x + 8, 603, 96, 13, { fontSize: 8.8, bold: true, color: accent, alignment: 'center' });
    addText(slide, `${files} 个文件`, x + 8, 620, 96, 12, { fontSize: 8.4, color: C.ink, alignment: 'center' });
    addText(slide, `${lines} 行`, x + 8, 635, 96, 12, { fontSize: 8.4, bold: true, color: C.navy, alignment: 'center' });
  });
}
function slide17(slide) {
  // Make patent status more conservative and acceptance-safe.
  addRect(slide, 362, 265, 338, 44, C.white, '#FFFFFF00', false);
  addText(slide, '材料已形成，经中心签报提交；\n受理证明按正式流程补充', 370, 270, 320, 34, {
    fontSize: 12.2, bold: true, color: C.green, alignment: 'center', verticalAlignment: 'middle', autoFit: 'shrinkText',
  });
}

await fs.copyFile(INPUT, OUTPUT);
const presentation = await PresentationFile.importPptx(await FileBlob.load(INPUT));
slide2(presentation.slides.getItem(1));
slide4(presentation.slides.getItem(3));
slide6(presentation.slides.getItem(5));
slide11(presentation.slides.getItem(10));
slide17(presentation.slides.getItem(16));
for (let i = 1; i < 18; i++) addFooterPage(presentation.slides.getItem(i), i + 1);
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUTPUT);
console.log(OUTPUT);
