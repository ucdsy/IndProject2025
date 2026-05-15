import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "@oai/artifact-tool";

const INPUT =
  "/Users/xizhuxizhu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_tt5mguhxte5g22_44ce/temp/drag/dsy汇报.pptx";
const OUT_DIR = "/Users/xizhuxizhu/Desktop/IndProj04/output/pptx/dsy_insert_20260420";
const OUTPUT = path.join(OUT_DIR, "dsy汇报_加入智能体研究支撑页.pptx");
const PREVIEW_DIR = path.join(OUT_DIR, "preview");

const C = {
  title: "#0E2841",
  blue: "#1D4F8C",
  blue2: "#156082",
  paleBlue: "#EEF5FF",
  paleBlue2: "#F5F9FF",
  border: "#BFD7F6",
  text: "#1F2D3D",
  muted: "#4B5563",
  slate: "#64748B",
  line: "#D8E0EA",
  green: "#196B24",
  orange: "#E97132",
  white: "#FFFFFF",
};

const FONT = {
  title: "Microsoft YaHei",
  body: "Microsoft YaHei",
  en: "Times New Roman",
};

function addShape(slide, cfg) {
  return slide.shapes.add(cfg);
}

function addText(slide, text, position, opts = {}) {
  const shape = addShape(slide, {
    geometry: "rect",
    position,
    fill: opts.fill ?? "#FFFFFF00",
    line: opts.line ?? { width: 0, fill: "#FFFFFF00" },
  });
  shape.text = Array.isArray(text) ? text : String(text);
  shape.text.typeface = opts.typeface ?? FONT.body;
  shape.text.fontSize = opts.fontSize ?? 18;
  shape.text.color = opts.color ?? C.text;
  shape.text.bold = opts.bold ?? false;
  shape.text.alignment = opts.alignment ?? "left";
  shape.text.verticalAlignment = opts.verticalAlignment ?? "top";
  shape.text.autoFit = opts.autoFit ?? "shrinkText";
  shape.text.insets = opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 };
  return shape;
}

function addCard(slide, x, y, w, h, opts = {}) {
  return addShape(slide, {
    geometry: "roundRect",
    adjustmentList: [{ name: "adj", formula: "val 9000" }],
    position: { left: x, top: y, width: w, height: h },
    fill: opts.fill ?? C.white,
    line: { width: opts.lineWidth ?? 1.1, fill: opts.line ?? C.line },
  });
}

function addMetric(slide, x, y, value, label, caption, accent = C.blue) {
  addCard(slide, x, y, 132, 108, { fill: C.white, line: C.line, lineWidth: 1 });
  addShape(slide, {
    geometry: "rect",
    position: { left: x, top: y, width: 132, height: 6 },
    fill: accent,
    line: { width: 0, fill: accent },
  });
  addText(slide, value, { left: x + 14, top: y + 17, width: 104, height: 32 }, {
    fontSize: 30,
    bold: true,
    color: accent,
    typeface: FONT.en,
  });
  addText(slide, label, { left: x + 14, top: y + 53, width: 104, height: 22 }, {
    fontSize: 15,
    bold: true,
    color: C.title,
  });
  addText(slide, caption, { left: x + 14, top: y + 76, width: 104, height: 26 }, {
    fontSize: 11,
    color: C.muted,
  });
}

function addFlowNode(slide, x, y, w, h, title, body, accent = C.blue) {
  addCard(slide, x, y, w, h, { fill: C.paleBlue, line: C.border, lineWidth: 1.2 });
  addText(slide, title, { left: x + 14, top: y + 12, width: w - 28, height: 26 }, {
    fontSize: 18,
    bold: true,
    color: accent,
  });
  addText(slide, body, { left: x + 14, top: y + 45, width: w - 28, height: h - 52 }, {
    fontSize: 12.5,
    color: C.muted,
  });
}

function addCompactFlowNode(slide, x, y, w, h, title, body, accent = C.blue) {
  addCard(slide, x, y, w, h, { fill: C.paleBlue, line: C.border, lineWidth: 1.2 });
  addText(slide, title, { left: x + 12, top: y + 10, width: w - 24, height: 20 }, {
    fontSize: 15.5,
    bold: true,
    color: accent,
  });
  addText(slide, body, { left: x + 12, top: y + 34, width: w - 24, height: h - 39 }, {
    fontSize: 10.7,
    color: C.muted,
  });
}

function addArrow(slide, x, y, w = 34) {
  const arrow = addShape(slide, {
    geometry: "rightArrow",
    position: { left: x, top: y, width: w, height: 22 },
    fill: "#BFD7F6",
    line: { width: 0, fill: "#BFD7F6" },
  });
  return arrow;
}

function addDeliverable(slide, x, y, title, body, idx) {
  const colors = [C.blue, C.blue2, C.green, C.orange];
  addCard(slide, x, y, 254, 78, { fill: C.white, line: C.line, lineWidth: 1 });
  addShape(slide, {
    geometry: "ellipse",
    position: { left: x + 14, top: y + 16, width: 32, height: 32 },
    fill: colors[idx % colors.length],
    line: { width: 0, fill: colors[idx % colors.length] },
  });
  addText(slide, String(idx + 1).padStart(2, "0"), { left: x + 14, top: y + 20, width: 32, height: 22 }, {
    fontSize: 13,
    bold: true,
    color: C.white,
    alignment: "center",
    verticalAlignment: "middle",
    typeface: FONT.en,
  });
  addText(slide, title, { left: x + 56, top: y + 13, width: 180, height: 22 }, {
    fontSize: 15.5,
    bold: true,
    color: C.title,
  });
  addText(slide, body, { left: x + 56, top: y + 39, width: 176, height: 30 }, {
    fontSize: 11.5,
    color: C.muted,
  });
}

function addSmallPill(slide, x, y, text, accent = C.blue) {
  addShape(slide, {
    geometry: "roundRect",
    adjustmentList: [{ name: "adj", formula: "val 50000" }],
    position: { left: x, top: y, width: 104, height: 32 },
    fill: C.white,
    line: { width: 1, fill: C.border },
  });
  addShape(slide, {
    geometry: "ellipse",
    position: { left: x + 10, top: y + 10, width: 12, height: 12 },
    fill: accent,
    line: { width: 0, fill: accent },
  });
  addText(slide, text, { left: x + 28, top: y + 7, width: 66, height: 18 }, {
    fontSize: 13.5,
    bold: true,
    color: C.title,
    verticalAlignment: "middle",
  });
}

async function renderPreview(presentation, slide, file) {
  const png = await slide.export({ format: "png", scale: 1 });
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, Buffer.from(await png.arrayBuffer()));
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const presentation = await PresentationFile.importPptx(await FileBlob.load(INPUT));

  const slide = presentation.slides.add();
  slide.background.fill = C.white;

  addText(
    slide,
    "智能体方向前期研究及原型支撑",
    { left: 48, top: 27, width: 720, height: 34 },
    { fontSize: 25, bold: true, color: C.title }
  );
  addShape(slide, {
    geometry: "rect",
    position: { left: 48, top: 72, width: 180, height: 4 },
    fill: C.blue,
    line: { width: 0, fill: C.blue },
  });
  addText(slide, "围绕未来大量智能程序的有序组织、发现、使用和治理，先做趋势研判，再形成原型探索和对外交流支撑。", {
    left: 48,
    top: 88,
    width: 930,
    height: 33,
  }, {
    fontSize: 17,
    color: C.muted,
  });

  addCard(slide, 48, 145, 500, 210, { fill: C.paleBlue2, line: C.border, lineWidth: 1 });
  addText(slide, "前期研究看清一个基础问题", { left: 72, top: 166, width: 300, height: 28 }, {
    fontSize: 19,
    bold: true,
    color: C.title,
  });
  addText(slide, "我们不是简单跟踪技术热点，而是围绕智能体规模化以后真正要解决的问题展开系统研究：未来各类智能程序越来越多，关键不只是“有没有”，而是“怎么找、怎么用、怎么管”。", {
    left: 72,
    top: 208,
    width: 440,
    height: 74,
  }, {
    fontSize: 15,
    color: C.text,
  });
  addSmallPill(slide, 73, 298, "怎么找", C.blue);
  addSmallPill(slide, 194, 298, "怎么用", C.green);
  addSmallPill(slide, 315, 298, "怎么管", C.orange);

  addCard(slide, 570, 145, 660, 210, { fill: C.white, line: C.line, lineWidth: 1 });
  addText(slide, "形成的基本判断", { left: 594, top: 166, width: 220, height: 28 }, {
    fontSize: 19,
    bold: true,
    color: C.title,
  });
  addText(slide, "如果缺少相对清晰的规则体系和组织方式，智能体数量上来后很容易出现：需要时找不准，找到后不好协同，投入使用后也不利于管理。", {
    left: 594,
    top: 207,
    width: 578,
    height: 52,
  }, {
    fontSize: 15,
    color: C.text,
  });
  addText(slide, "这看起来是新问题，本质上与中心长期开展的基础资源工作相通，都是解决网络空间中各类对象如何有序识别、可靠连接和规范运行。", {
    left: 594,
    top: 275,
    width: 578,
    height: 46,
  }, {
    fontSize: 14,
    color: C.muted,
  });

  addCard(slide, 48, 384, 1182, 132, { fill: C.paleBlue2, line: C.border, lineWidth: 1 });
  addText(slide, "从研究判断到原型支撑", { left: 72, top: 404, width: 240, height: 26 }, {
    fontSize: 18,
    bold: true,
    color: C.title,
  });
  addCompactFlowNode(slide, 72, 447, 190, 52, "前期研究", "系统研究智能体方向，识别基础性问题", C.blue);
  addArrow(slide, 278, 462, 34);
  addCompactFlowNode(slide, 326, 447, 190, 52, "基本判断", "需要规则体系和组织方式，支撑发现、协同、管理", C.blue2);
  addArrow(slide, 532, 462, 34);
  addCompactFlowNode(slide, 580, 447, 190, 52, "原型完善", "结合中心工作基础，支撑智能体域名系统原型", C.green);
  addArrow(slide, 786, 462, 34);
  addCompactFlowNode(slide, 834, 447, 190, 52, "IETF125交流", "带出中心判断、方案和原型，展示技术积累", C.orange);

  addCard(slide, 1048, 407, 146, 76, { fill: C.white, line: C.line, lineWidth: 1 });
  addText(slide, "先行一步", { left: 1068, top: 424, width: 106, height: 24 }, {
    fontSize: 18,
    bold: true,
    color: C.title,
    alignment: "center",
  });
  addText(slide, "做出原型\n探索路径", { left: 1068, top: 452, width: 106, height: 26 }, {
    fontSize: 12,
    color: C.muted,
    alignment: "center",
  });

  addText(slide, "工作意义", { left: 48, top: 541, width: 120, height: 24 }, {
    fontSize: 18,
    bold: true,
    color: C.title,
  });
  addDeliverable(slide, 48, 579, "主动研判趋势", "不是被动跟热点，而是提前谋划布局", 0);
  addDeliverable(slide, 326, 579, "延伸基础资源能力", "立足已有积累，向智能体新方向拓展", 1);
  addDeliverable(slide, 604, 579, "带着方案交流", "在国际场合展示自己的思考和原型", 2);
  addCard(slide, 882, 579, 348, 78, { fill: C.paleBlue, line: C.border, lineWidth: 1 });
  addText(slide, "最终目标", { left: 908, top: 594, width: 90, height: 22 }, {
    fontSize: 15.5,
    bold: true,
    color: C.title,
  });
  addText(slide, "通过提前研究智能体时代的一类基础性问题，为中心下一步抢占方向、形成影响打基础。", {
    left: 908,
    top: 619,
    width: 284,
    height: 29,
  }, {
    fontSize: 12.5,
    color: C.muted,
  });

  addText(slide, "支撑方向：智能体域名系统原型完善与 IETF125 相关活动交流", {
    left: 48,
    top: 675,
    width: 720,
    height: 22,
  }, {
    fontSize: 11.5,
    color: C.slate,
  });
  addText(slide, "2026-04", { left: 1140, top: 675, width: 90, height: 22 }, {
    fontSize: 11.5,
    color: C.slate,
    alignment: "right",
  });

  slide.moveTo(0);

  await renderPreview(presentation, presentation.slides.getItem(0), path.join(PREVIEW_DIR, "slide1.png"));
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(OUTPUT);
  console.log(JSON.stringify({
    output: OUTPUT,
    preview: path.join(PREVIEW_DIR, "slide1.png"),
    slideCount: presentation.slides.count,
  }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
