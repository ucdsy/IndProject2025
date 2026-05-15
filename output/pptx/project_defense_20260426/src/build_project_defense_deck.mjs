import fs from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import {
  Presentation,
  PresentationFile,
} from "/Users/xizhuxizhu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const ROOT = "/Users/xizhuxizhu/Desktop/IndProj04";
const OUT_DIR = path.join(ROOT, "output/pptx/project_defense_20260426");
const PREVIEW_DIR = path.join(OUT_DIR, "preview");
const ASSET_DIR = path.join(OUT_DIR, "scratch/assets");
const OUTPUT = path.join(OUT_DIR, "项目评审答辩PPT_20260426.pptx");

const W = 1280;
const H = 720;

const C = {
  navy: "#071A45",
  navy2: "#082B6D",
  blue: "#0B63CE",
  blue2: "#1E83E6",
  cyan: "#27B4FF",
  pale: "#F2F7FF",
  pale2: "#E8F2FF",
  line: "#C9DDF3",
  ink: "#102033",
  muted: "#53657A",
  lightMuted: "#BDD5F2",
  orange: "#F4B000",
  orange2: "#E97132",
  green: "#0E8A57",
  red: "#B93232",
  purple: "#6B49C8",
  white: "#FFFFFF",
};

const FONT = {
  cn: "Microsoft YaHei",
  alt: "PingFang SC",
  en: "Arial",
};

function addShape(slide, cfg) {
  return slide.shapes.add(cfg);
}

function addImage(slide, file, position, opts = {}) {
  const ext = path.extname(file).toLowerCase();
  const mime = ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" : "image/png";
  const dataUrl = `data:${mime};base64,${readFileSync(file).toString("base64")}`;
  return slide.images.add({
    dataUrl,
    position,
    fit: opts.fit ?? "contain",
    alt: opts.alt ?? path.basename(file),
  });
}

function addText(slide, text, position, opts = {}) {
  const shape = addShape(slide, {
    geometry: opts.geometry ?? "rect",
    adjustmentList: opts.adjustmentList,
    position,
    fill: opts.fill ?? "#FFFFFF00",
    line: opts.line ?? { width: 0, fill: "#FFFFFF00" },
  });
  shape.text = Array.isArray(text) ? text : String(text);
  shape.text.typeface = opts.typeface ?? FONT.cn;
  shape.text.fontSize = opts.fontSize ?? 18;
  shape.text.color = opts.color ?? C.ink;
  shape.text.bold = opts.bold ?? false;
  shape.text.alignment = opts.alignment ?? "left";
  shape.text.verticalAlignment = opts.verticalAlignment ?? "top";
  shape.text.autoFit = opts.autoFit ?? "shrinkText";
  shape.text.insets = opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 };
  return shape;
}

function addRoundRect(slide, x, y, w, h, opts = {}) {
  return addShape(slide, {
    geometry: "roundRect",
    adjustmentList: [{ name: "adj", formula: `val ${opts.radius ?? 11000}` }],
    position: { left: x, top: y, width: w, height: h },
    fill: opts.fill ?? C.white,
    line: { width: opts.lineWidth ?? 1, fill: opts.line ?? C.line },
  });
}

function addLine(slide, x, y, w, color = C.line, weight = 1.2) {
  addShape(slide, {
    geometry: "rect",
    position: { left: x, top: y, width: w, height: weight },
    fill: color,
    line: { width: 0, fill: color },
  });
}

function addArrow(slide, x, y, w = 42, color = C.blue2) {
  addShape(slide, {
    geometry: "rightArrow",
    position: { left: x, top: y, width: w, height: 24 },
    fill: color,
    line: { width: 0, fill: color },
  });
}

function addDot(slide, x, y, r, color) {
  addShape(slide, {
    geometry: "ellipse",
    position: { left: x - r, top: y - r, width: r * 2, height: r * 2 },
    fill: color,
    line: { width: 0, fill: color },
  });
}

function addCnnicMark(slide, dark = false) {
  addText(slide, "CNNIC", { left: 1132, top: 29, width: 96, height: 26 }, {
    fontSize: 24,
    bold: true,
    color: dark ? C.white : C.blue,
    alignment: "right",
    typeface: FONT.en,
  });
  addText(slide, "中国互联网络信息中心", { left: 1040, top: 56, width: 188, height: 18 }, {
    fontSize: 10.5,
    color: dark ? "#D7E8FF" : C.muted,
    alignment: "right",
  });
}

function addTopTitle(slide, title, subtitle = "", section = "") {
  addShape(slide, {
    geometry: "rect",
    position: { left: 0, top: 0, width: W, height: 11 },
    fill: C.navy2,
    line: { width: 0, fill: C.navy2 },
  });
  addShape(slide, {
    geometry: "rect",
    position: { left: 0, top: 11, width: W, height: 3 },
    fill: C.blue2,
    line: { width: 0, fill: C.blue2 },
  });
  if (section) {
    addText(slide, section, { left: 50, top: 30, width: 70, height: 24 }, {
      fontSize: 14,
      bold: true,
      color: C.blue,
      alignment: "center",
      fill: C.pale2,
      line: { width: 1, fill: C.line },
      geometry: "roundRect",
      adjustmentList: [{ name: "adj", formula: "val 45000" }],
      verticalAlignment: "middle",
      insets: { left: 0, right: 0, top: 0, bottom: 0 },
    });
  }
  addText(slide, title, { left: section ? 135 : 50, top: 29, width: 850, height: 34 }, {
    fontSize: 24,
    bold: true,
    color: C.ink,
  });
  if (subtitle) {
    addText(slide, subtitle, { left: section ? 135 : 50, top: 64, width: 840, height: 22 }, {
      fontSize: 12.5,
      color: C.muted,
    });
  }
  addCnnicMark(slide, false);
}

function addFooter(slide, page) {
  addLine(slide, 50, 678, 900, "#E4EDF8", 1);
  addText(slide, "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究", { left: 50, top: 688, width: 620, height: 14 }, {
    fontSize: 9,
    color: "#8394A8",
  });
  addText(slide, String(page).padStart(2, "0"), { left: 1195, top: 684, width: 34, height: 18 }, {
    fontSize: 10,
    color: "#8394A8",
    alignment: "right",
    typeface: FONT.en,
  });
}

function addLightBackground(slide) {
  slide.background.fill = C.white;
  addImage(slide, path.join(ASSET_DIR, "light_texture.png"), { left: 0, top: 0, width: W, height: H }, { fit: "cover" });
}

function addMetric(slide, x, y, value, label, note, color = C.blue) {
  addText(slide, value, { left: x, top: y, width: 160, height: 52 }, {
    fontSize: 39,
    bold: true,
    color,
    typeface: FONT.en,
  });
  addText(slide, label, { left: x + 2, top: y + 54, width: 184, height: 22 }, {
    fontSize: 15,
    bold: true,
    color: C.ink,
  });
  addText(slide, note, { left: x + 2, top: y + 80, width: 190, height: 34 }, {
    fontSize: 10.5,
    color: C.muted,
  });
}

function addSmallLabel(slide, x, y, text, color = C.blue) {
  addText(slide, text, { left: x, top: y, width: 122, height: 28 }, {
    fontSize: 12.5,
    bold: true,
    color,
    alignment: "center",
    verticalAlignment: "middle",
    fill: C.white,
    line: { width: 1, fill: C.line },
    geometry: "roundRect",
    adjustmentList: [{ name: "adj", formula: "val 50000" }],
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

function addSectionSlide(presentation, index, title, subtitle, labels) {
  const slide = presentation.slides.add();
  addImage(slide, path.join(ASSET_DIR, "section_bg.png"), { left: 0, top: 0, width: W, height: H }, { fit: "cover" });
  addCnnicMark(slide, true);
  addText(slide, String(index).padStart(2, "0"), { left: 72, top: 108, width: 90, height: 58 }, {
    fontSize: 43,
    bold: true,
    color: C.cyan,
    typeface: FONT.en,
  });
  addLine(slide, 74, 172, 120, C.cyan, 4);
  addText(slide, title, { left: 72, top: 210, width: 770, height: 58 }, {
    fontSize: 34,
    bold: true,
    color: C.white,
  });
  addText(slide, subtitle, { left: 75, top: 282, width: 800, height: 42 }, {
    fontSize: 17,
    color: "#CFE5FF",
  });
  labels.forEach((label, i) => {
    addText(slide, label, { left: 74 + i * 156, top: 580, width: 132, height: 30 }, {
      fontSize: 12.5,
      color: "#D8ECFF",
      alignment: "center",
      verticalAlignment: "middle",
      fill: "#0F3C7ACC",
      line: { width: 1, fill: "#3F85D9" },
      geometry: "roundRect",
      adjustmentList: [{ name: "adj", formula: "val 50000" }],
      insets: { left: 0, right: 0, top: 0, bottom: 0 },
    });
  });
  return slide;
}

function addFlowNode(slide, x, y, w, h, title, body, color = C.blue, fill = C.white) {
  addRoundRect(slide, x, y, w, h, { fill, line: color, lineWidth: 1.2, radius: 10500 });
  addShape(slide, {
    geometry: "rect",
    position: { left: x, top: y, width: w, height: 6 },
    fill: color,
    line: { width: 0, fill: color },
  });
  addText(slide, title, { left: x + 14, top: y + 17, width: w - 28, height: 24 }, {
    fontSize: 15.5,
    bold: true,
    color,
  });
  addText(slide, body, { left: x + 14, top: y + 47, width: w - 28, height: h - 58 }, {
    fontSize: 11.2,
    color: C.muted,
  });
}

function addBar(slide, x, baseY, w, h, color, label, value) {
  addShape(slide, {
    geometry: "rect",
    position: { left: x, top: baseY - h, width: w, height: h },
    fill: color,
    line: { width: 0, fill: color },
  });
  addText(slide, value, { left: x - 8, top: baseY - h - 24, width: w + 16, height: 18 }, {
    fontSize: 11,
    bold: true,
    color,
    alignment: "center",
    typeface: FONT.en,
  });
  addText(slide, label, { left: x - 32, top: baseY + 10, width: w + 64, height: 36 }, {
    fontSize: 10.5,
    color: C.muted,
    alignment: "center",
  });
}

function slide1(presentation) {
  const slide = presentation.slides.add();
  addImage(slide, path.join(ASSET_DIR, "cover_bg.png"), { left: 0, top: 0, width: W, height: H }, { fit: "cover" });
  addCnnicMark(slide, true);
  addText(slide, "项目评审答辩", { left: 76, top: 83, width: 180, height: 28 }, {
    fontSize: 18,
    bold: true,
    color: C.cyan,
  });
  addLine(slide, 76, 122, 122, C.cyan, 4);
  addText(slide, "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究", {
    left: 74,
    top: 165,
    width: 720,
    height: 126,
  }, {
    fontSize: 35,
    bold: true,
    color: C.white,
  });
  addText(slide, "自立科研重点项目 · 2025年5月-2026年4月", { left: 78, top: 315, width: 610, height: 28 }, {
    fontSize: 17,
    color: "#CFE4FF",
  });
  ["能力命名", "语义路由", "职责化复核", "可信轨迹"].forEach((t, i) => {
    addText(slide, t, { left: 78 + i * 132, top: 394, width: 108, height: 30 }, {
      fontSize: 13,
      bold: true,
      color: "#DCEEFF",
      alignment: "center",
      verticalAlignment: "middle",
      fill: "#1A4C8CCC",
      line: { width: 1, fill: "#4C96E8" },
      geometry: "roundRect",
      adjustmentList: [{ name: "adj", formula: "val 50000" }],
      insets: { left: 0, right: 0, top: 0, bottom: 0 },
    });
  });
  addText(slide, "承研处所：技术发展所    项目负责人：邓斯宇    项目经费：10万元", { left: 78, top: 638, width: 650, height: 20 }, {
    fontSize: 12.5,
    color: "#D3E7FF",
  });
}

function slide2(presentation) {
  const slide = addSectionSlide(
    presentation,
    0,
    "答辩提纲",
    "按评审最关心的四件事展开：任务是否完成、路线是否可信、原型是否落地、成果是否可复用。",
    ["项目定位", "技术路线", "原型实现", "实验验证", "成果计划"]
  );
  const items = [
    ["01", "项目定位与完成情况", "对照任务书说明目标、周期、指标和交付物。"],
    ["02", "关键问题与技术路线", "用能力命名空间、语义路由、职责化复核串起主线。"],
    ["03", "原型系统与工程实现", "展示代码模块、运行链路、过程记录和执行落点。"],
    ["04", "数据实验与量化结果", "汇报 563 条冻结样本、主指标、消融和配置结果。"],
    ["05", "成果凝练与下一步", "报告、论文、专利、宣传材料和后续演示联调。"],
  ];
  items.forEach((item, i) => {
    const y = 108 + i * 86;
    addDot(slide, 856, y + 18, 20, i === 0 ? C.orange : "#1E70CB");
    addText(slide, item[0], { left: 835, top: y + 6, width: 42, height: 24 }, {
      fontSize: 13,
      bold: true,
      color: C.white,
      alignment: "center",
      verticalAlignment: "middle",
      typeface: FONT.en,
    });
    addText(slide, item[1], { left: 900, top: y, width: 260, height: 24 }, {
      fontSize: 17,
      bold: true,
      color: C.white,
    });
    addText(slide, item[2], { left: 900, top: y + 31, width: 300, height: 28 }, {
      fontSize: 11.5,
      color: "#C8DDF8",
    });
  });
}

function slide3(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "一页讲清项目完成情况", "项目已形成从能力命名、语义路由、协作复核到可信轨迹的完整研究与原型链路。", "01");

  addRoundRect(slide, 58, 118, 395, 460, { fill: C.white, line: C.line, lineWidth: 1.1 });
  addText(slide, "项目基本信息", { left: 82, top: 142, width: 200, height: 28 }, {
    fontSize: 20,
    bold: true,
    color: C.ink,
  });
  const rows = [
    ["项目名称", "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究"],
    ["项目类型", "自立科研重点项目"],
    ["实施周期", "2025年5月-2026年4月"],
    ["承研处所", "技术发展所"],
    ["负责人", "邓斯宇"],
  ];
  rows.forEach((r, i) => {
    const y = 196 + i * 62;
    addText(slide, r[0], { left: 82, top: y, width: 84, height: 22 }, {
      fontSize: 12,
      bold: true,
      color: C.blue,
    });
    addText(slide, r[1], { left: 176, top: y - 2, width: 232, height: 40 }, {
      fontSize: i === 0 ? 12.4 : 13,
      color: C.ink,
    });
    addLine(slide, 82, y + 46, 320, "#E8F0FA", 1);
  });

  addText(slide, "任务书指标对照", { left: 504, top: 124, width: 280, height: 32 }, {
    fontSize: 22,
    bold: true,
    color: C.ink,
  });
  const indicators = [
    ["原型框架", "已形成能力命名、候选召回、结构化裁决、协作复核、过程记录和执行落点模块。"],
    ["研究报告/论文", "已形成技术研究报告、论文稿和成果汇编材料，覆盖方法、实验与分析。"],
    ["专利材料", "已形成技术交底书、权利要求书、说明书摘要和附图材料。"],
    ["展示支撑", "已形成演示脚本、图表、宣传稿和原型运行链路，可支撑对内汇报。"],
  ];
  indicators.forEach((r, i) => {
    const x = 508 + (i % 2) * 345;
    const y = 174 + Math.floor(i / 2) * 157;
    addRoundRect(slide, x, y, 310, 118, { fill: i === 0 ? C.pale2 : C.white, line: i === 0 ? C.blue2 : C.line, lineWidth: 1.2 });
    addDot(slide, x + 30, y + 32, 17, [C.blue, C.green, C.orange2, C.purple][i]);
    addText(slide, "✓", { left: x + 18, top: y + 17, width: 24, height: 26 }, {
      fontSize: 18,
      bold: true,
      color: C.white,
      alignment: "center",
      verticalAlignment: "middle",
    });
    addText(slide, r[0], { left: x + 58, top: y + 22, width: 200, height: 24 }, {
      fontSize: 17,
      bold: true,
      color: C.ink,
    });
    addText(slide, r[1], { left: x + 58, top: y + 52, width: 220, height: 46 }, {
      fontSize: 11.5,
      color: C.muted,
    });
  });

  addShape(slide, {
    geometry: "rect",
    position: { left: 505, top: 511, width: 654, height: 4 },
    fill: C.blue,
    line: { width: 0, fill: C.blue },
  });
  addText(slide, "结论", { left: 505, top: 535, width: 80, height: 26 }, {
    fontSize: 18,
    bold: true,
    color: C.blue,
  });
  addText(slide, "项目不只形成文档材料，也完成了可运行链路、冻结样本协议和可复盘实验结果，具备进入评审验收与后续演示联调的基础。", {
    left: 586,
    top: 535,
    width: 573,
    height: 50,
  }, {
    fontSize: 14.5,
    color: C.ink,
  });
  addFooter(slide, 3);
}

function slide4(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "问题背景：智能体服务从“能调用”走向“可信路由”", "智能体数量增加后，评审关注的不只是单次回答质量，更是能力入口能否稳定发现、受控调用和可复核治理。", "02");
  addText(slide, "核心问题", { left: 72, top: 137, width: 140, height: 26 }, {
    fontSize: 17,
    bold: true,
    color: C.blue,
  });
  addText(slide, "自然语言请求如何稳定映射到正确能力地址，并进一步选择可执行实例？", { left: 72, top: 172, width: 700, height: 58 }, {
    fontSize: 28,
    bold: true,
    color: C.ink,
  });
  const blocks = [
    ["能力入口多", "智能体能力、服务实例、协议与运行状态不断变化，简单目录难以支撑准确发现。", C.blue],
    ["语义边界复杂", "用户请求常同时包含主任务、辅助诉求、风险限制和行业语境，容易出现层级竞争。", C.orange2],
    ["过程需要审计", "评审和工程运维需要知道为何选择、为何复核、为何改判，以及错误属于哪一阶段。", C.green],
  ];
  blocks.forEach((b, i) => {
    const x = 72 + i * 385;
    addRoundRect(slide, x, 280, 322, 164, { fill: C.white, line: b[2], lineWidth: 1.3 });
    addShape(slide, {
      geometry: "rect",
      position: { left: x, top: 280, width: 322, height: 7 },
      fill: b[2],
      line: { width: 0, fill: b[2] },
    });
    addText(slide, `0${i + 1}`, { left: x + 23, top: 314, width: 44, height: 30 }, {
      fontSize: 20,
      bold: true,
      color: b[2],
      typeface: FONT.en,
    });
    addText(slide, b[0], { left: x + 78, top: 315, width: 160, height: 25 }, {
      fontSize: 18,
      bold: true,
      color: C.ink,
    });
    addText(slide, b[1], { left: x + 78, top: 354, width: 205, height: 64 }, {
      fontSize: 12.8,
      color: C.muted,
    });
  });
  const chainX = 130;
  const y = 540;
  const chain = [
    ["用户请求", "query + context"],
    ["能力地址", "routing_fqdn"],
    ["执行实例", "agent_fqdn"],
    ["过程证据", "trace contract"],
  ];
  chain.forEach((c, i) => {
    const x = chainX + i * 260;
    addText(slide, c[0], { left: x, top: y, width: 150, height: 24 }, {
      fontSize: 16,
      bold: true,
      color: C.ink,
      alignment: "center",
    });
    addText(slide, c[1], { left: x, top: y + 28, width: 150, height: 18 }, {
      fontSize: 10.8,
      color: C.muted,
      alignment: "center",
      typeface: FONT.en,
    });
    addDot(slide, x + 75, y - 24, 20, [C.blue, C.green, C.orange2, C.purple][i]);
    if (i < chain.length - 1) addArrow(slide, x + 154, y - 36, 76, "#A9C8EA");
  });
  addFooter(slide, 4);
}

function slide5(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "总体技术路线：候选召回、语义裁决、协作复核、执行落点一体化", "系统以能力命名空间为底座，将开放式生成问题收敛为候选内语义路由与可回放决策过程。", "03");
  addRoundRect(slide, 58, 116, 1164, 392, { fill: C.white, line: C.line, lineWidth: 1.1 });
  addImage(slide, path.join(ROOT, "图1.png"), { left: 76, top: 141, width: 1128, height: 340 }, { fit: "contain", alt: "系统总体结构示意图" });
  const items = [
    ["Stage R", "候选集合构造", C.blue],
    ["Stage A", "结构化语义路由", C.green],
    ["Stage B", "职责化协作复核", C.orange2],
    ["Stage C", "执行落点解析", C.purple],
    ["Trace", "过程记录轨迹", C.blue2],
  ];
  items.forEach((it, i) => {
    const x = 72 + i * 225;
    addText(slide, it[0], { left: x, top: 542, width: 80, height: 24 }, {
      fontSize: 17,
      bold: true,
      color: it[2],
      typeface: FONT.en,
    });
    addText(slide, it[1], { left: x + 84, top: 545, width: 128, height: 19 }, {
      fontSize: 12.5,
      color: C.ink,
    });
    addLine(slide, x, 574, 190, "#D8E7F7", 1);
  });
  addText(slide, "技术路线强调“先限定候选，再结构化裁决；只在必要时复核，且全过程留痕”。", { left: 76, top: 612, width: 840, height: 24 }, {
    fontSize: 15.5,
    bold: true,
    color: C.ink,
  });
  addText(slide, "候选内决策边界使错误归因更清晰：召回错误、主标签判断错误、相关能力恢复不足可以分层定位。", { left: 77, top: 642, width: 940, height: 20 }, {
    fontSize: 12.5,
    color: C.muted,
  });
  addFooter(slide, 5);
}

function slide6(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "关键机制一：受限能力命名空间内的结构化语义裁决", "Stage R/A 将模型能力限定在固定候选集合内部，输出可复核字段，而不是开放生成答案。", "04");
  const nodes = [
    ["输入请求", "自然语言 query、上下文 metadata、风险约束与用户偏好线索。", C.blue],
    ["Stage R 候选召回", "基于描述、别名、层级和元数据标签构造候选集合。", C.blue2],
    ["Stage A 语义路由", "输出 primary、related、置信度、不确定性摘要和竞争候选说明。", C.green],
    ["候选内结果", "固定 routing_fqdn，并传递给复核或执行落点模块。", C.purple],
  ];
  nodes.forEach((n, i) => {
    const x = 72 + i * 285;
    addFlowNode(slide, x, 164, 230, 150, n[0], n[1], n[2], i === 2 ? "#F2FFF8" : C.white);
    if (i < nodes.length - 1) addArrow(slide, x + 236, 224, 44, "#8AB8EA");
  });
  addRoundRect(slide, 76, 384, 530, 176, { fill: C.white, line: C.line });
  addText(slide, "结构化输出字段", { left: 104, top: 410, width: 210, height: 26 }, {
    fontSize: 19,
    bold: true,
    color: C.ink,
  });
  const fields = [
    "selected_primary_fqdn",
    "selected_related_fqdns",
    "primary_rationale",
    "challenger_notes",
    "uncertainty_summary",
    "override_sensitivity",
  ];
  fields.forEach((f, i) => addSmallLabel(slide, 104 + (i % 3) * 155, 455 + Math.floor(i / 3) * 48, f, [C.blue, C.green, C.orange2][i % 3]));
  addRoundRect(slide, 690, 384, 468, 176, { fill: C.pale, line: C.blue2, lineWidth: 1.2 });
  addText(slide, "约束带来的工程价值", { left: 720, top: 410, width: 250, height: 26 }, {
    fontSize: 19,
    bold: true,
    color: C.blue,
  });
  const values = [
    "候选来源可追踪，避免下游凭空发明路由",
    "模型判断被压缩为短字段，便于复核和回放",
    "Stage B 能看到真实困惑点，而不是只看分数",
  ];
  values.forEach((v, i) => {
    addDot(slide, 727, 461 + i * 36, 4, C.blue);
    addText(slide, v, { left: 744, top: 452 + i * 36, width: 365, height: 22 }, {
      fontSize: 13,
      color: C.ink,
    });
  });
  addFooter(slide, 6);
}

function slide7(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "关键机制二：多智能体职责化复核与授权控制", "Stage B 只在低置信、高风险、多意图冲突和层级竞争样本上触发，目标是谨慎修正而非重复推理。", "05");
  addRoundRect(slide, 58, 122, 1164, 326, { fill: C.white, line: C.line });
  addImage(slide, path.join(ROOT, "图2.png"), { left: 80, top: 144, width: 1120, height: 270 }, { fit: "contain", alt: "职责化复核流程示意图" });
  const roles = [
    ["DomainExpert", "任务语义匹配", C.blue],
    ["GovernanceRisk", "治理与风险边界", C.orange2],
    ["HierarchyResolver", "层级粒度冲突", C.green],
    ["UserPreference", "主次意图拆分", C.purple],
  ];
  roles.forEach((r, i) => {
    const x = 92 + i * 284;
    addRoundRect(slide, x, 500, 248, 74, { fill: C.white, line: r[2], lineWidth: 1.2 });
    addText(slide, r[0], { left: x + 18, top: 516, width: 160, height: 20 }, {
      fontSize: 14,
      bold: true,
      color: r[2],
      typeface: FONT.en,
    });
    addText(slide, r[1], { left: x + 18, top: 542, width: 180, height: 18 }, {
      fontSize: 12.5,
      color: C.ink,
    });
  });
  addText(slide, "复核输出不会突破候选边界；改判需要具备明确证据、授权依据和最终日志匹配。", { left: 92, top: 612, width: 760, height: 24 }, {
    fontSize: 15.5,
    bold: true,
    color: C.ink,
  });
  addText(slide, "这种设计使协作收益来自职责分工、结构化证据和改判控制的组合，而不是简单增加调用轮次。", { left: 92, top: 642, width: 850, height: 20 }, {
    fontSize: 12.5,
    color: C.muted,
  });
  addFooter(slide, 7);
}

function slide8(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "关键机制三：可信认知标识落到可回放、可归因、可审计轨迹", "当前阶段将可信定位为工程可审计能力，保留身份、行为和证据链结构，为后续增强校验预留接口。", "06");
  const y = 210;
  const steps = [
    ["源站快照", "candidate snapshot", C.blue],
    ["语义摘要", "uncertainty packet", C.green],
    ["复核提案", "role proposals", C.orange2],
    ["授权依据", "override evidence", C.purple],
    ["执行落点", "endpoint selection", C.blue2],
  ];
  addLine(slide, 130, y + 48, 940, "#B9D3EE", 3);
  steps.forEach((s, i) => {
    const x = 110 + i * 235;
    addDot(slide, x + 34, y + 48, 29, s[2]);
    addText(slide, String(i + 1), { left: x + 18, top: y + 31, width: 32, height: 28 }, {
      fontSize: 16,
      bold: true,
      color: C.white,
      alignment: "center",
      verticalAlignment: "middle",
      typeface: FONT.en,
    });
    addText(slide, s[0], { left: x - 18, top: y + 95, width: 105, height: 24 }, {
      fontSize: 16,
      bold: true,
      color: C.ink,
      alignment: "center",
    });
    addText(slide, s[1], { left: x - 36, top: y + 124, width: 142, height: 18 }, {
      fontSize: 10.8,
      color: C.muted,
      alignment: "center",
      typeface: FONT.en,
    });
  });
  addRoundRect(slide, 88, 430, 478, 150, { fill: C.white, line: C.line });
  addText(slide, "评审可追问的问题有明确落点", { left: 116, top: 456, width: 310, height: 26 }, {
    fontSize: 18,
    bold: true,
    color: C.ink,
  });
  ["为什么选择该能力", "为何触发慢路径复核", "改判依据来自哪个角色", "错误属于召回、裁决还是 related 恢复"].forEach((t, i) => {
    addDot(slide, 126, 505 + i * 24, 4, C.blue);
    addText(slide, t, { left: 141, top: 496 + i * 24, width: 350, height: 18 }, {
      fontSize: 12.5,
      color: C.muted,
    });
  });
  addRoundRect(slide, 644, 430, 490, 150, { fill: C.pale, line: C.blue2, lineWidth: 1.2 });
  addText(slide, "后续可增强方向", { left: 674, top: 456, width: 180, height: 26 }, {
    fontSize: 18,
    bold: true,
    color: C.blue,
  });
  ["hash-chain 校验与篡改检测", "演示端 routing_trace 可视化", "多批次审计扫描与错误桶复盘"].forEach((t, i) => {
    addSmallLabel(slide, 674 + i * 142, 507, t, [C.blue, C.green, C.orange2][i]);
  });
  addFooter(slide, 8);
}

function slide9(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "原型系统与代码实现：研究链路已经沉淀为可运行模块", "仓库已形成面向 AgentDNS 风格场景的路由服务、实验脚本、评测脚本和测试用例。", "07");
  const modules = [
    ["命名空间", "namespace.py", "能力节点、FQDN、标签与层级关系。", C.blue],
    ["候选召回", "stage_r_clean.py", "基于描述、别名和元数据构造候选集合。", C.blue2],
    ["语义裁决", "stage_a_llm.py", "输出结构化 primary / related / uncertainty。", C.green],
    ["协作复核", "stage_b_consensus.py", "角色提案、授权控制和改判判断。", C.orange2],
    ["执行选择", "stage_c_selector.py", "exact match、schema、health 和 endpoint 过滤。", C.purple],
  ];
  modules.forEach((m, i) => {
    const x = 72 + i * 232;
    addFlowNode(slide, x, 154, 190, 145, m[0], m[2], m[3], C.white);
    addText(slide, m[1], { left: x + 14, top: 265, width: 160, height: 18 }, {
      fontSize: 10.4,
      color: m[3],
      typeface: FONT.en,
    });
    if (i < modules.length - 1) addArrow(slide, x + 196, 210, 32, "#9EC4EE");
  });
  addRoundRect(slide, 76, 386, 510, 166, { fill: "#071A45", line: "#194F93", lineWidth: 1.1 });
  addText(slide, "运行入口", { left: 104, top: 411, width: 120, height: 22 }, {
    fontSize: 17,
    bold: true,
    color: C.white,
  });
  const cmdLines = [
    "scripts/run_stage_r_clean_snapshot.py",
    "scripts/run_stage_a_llm.py",
    "scripts/run_stage_b.py",
    "scripts/run_routing_service.py",
  ];
  cmdLines.forEach((line, i) => {
    addText(slide, line, { left: 106, top: 452 + i * 24, width: 410, height: 18 }, {
      fontSize: 11.2,
      color: "#D5E8FF",
      typeface: FONT.en,
    });
  });
  addRoundRect(slide, 650, 386, 500, 166, { fill: C.white, line: C.line });
  addText(slide, "验证覆盖", { left: 678, top: 411, width: 120, height: 22 }, {
    fontSize: 17,
    bold: true,
    color: C.ink,
  });
  const tests = ["test_stage_r_clean.py", "test_stage_a_llm.py", "test_stage_b.py", "test_stage_c.py"];
  tests.forEach((line, i) => {
    addSmallLabel(slide, 680 + (i % 2) * 210, 452 + Math.floor(i / 2) * 45, line, [C.blue, C.green, C.orange2, C.purple][i]);
  });
  addText(slide, "代码结构支撑从离线实验到服务化调用的迁移；后续重点是与演示端做更稳定的端到端联调。", { left: 82, top: 614, width: 820, height: 25 }, {
    fontSize: 15,
    bold: true,
    color: C.ink,
  });
  addFooter(slide, 9);
}

function slide10(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "数据与评测协议：冻结样本池支撑统一口径验收", "主结果采用 dev + blind + challenge + holdout2 + holdout3 合并后的固定 train/test 协议。", "08");
  addMetric(slide, 86, 145, "563", "总样本数", "覆盖 9 类领域、25 个能力基座", C.blue);
  addMetric(slide, 280, 145, "450", "训练划分", "用于方案开发与配置选择", C.green);
  addMetric(slide, 470, 145, "113", "测试划分", "用于一次性主结果报告", C.orange2);
  addRoundRect(slide, 710, 132, 420, 134, { fill: C.white, line: C.line });
  addText(slide, "指标体系", { left: 740, top: 156, width: 140, height: 24 }, {
    fontSize: 18,
    bold: true,
    color: C.ink,
  });
  ["PrimaryAcc@1", "Acceptable@1", "RelatedRecall", "RelatedPrecision", "改写/修正/回归"].forEach((m, i) => {
    addSmallLabel(slide, 740 + (i % 3) * 122, 198 + Math.floor(i / 3) * 38, m, [C.blue, C.green, C.orange2][i % 3]);
  });

  const splits = [
    ["dev", "50"],
    ["blind", "35"],
    ["challenge", "24"],
    ["holdout2", "54"],
    ["holdout3", "400"],
  ];
  splits.forEach((s, i) => {
    const x = 86 + i * 194;
    addRoundRect(slide, x, 365, 130, 70, { fill: C.white, line: C.line });
    addText(slide, s[0], { left: x + 14, top: 382, width: 72, height: 20 }, {
      fontSize: 14,
      bold: true,
      color: C.blue,
      typeface: FONT.en,
    });
    addText(slide, s[1], { left: x + 82, top: 378, width: 36, height: 24 }, {
      fontSize: 18,
      bold: true,
      color: C.ink,
      typeface: FONT.en,
      alignment: "right",
    });
    if (i < splits.length - 1) addArrow(slide, x + 137, 387, 42, "#BED5EF");
  });
  addArrow(slide, 550, 460, 100, C.blue2);
  addRoundRect(slide, 670, 452, 210, 78, { fill: C.pale2, line: C.blue2, lineWidth: 1.3 });
  addText(slide, "统一样本池", { left: 710, top: 470, width: 120, height: 22 }, {
    fontSize: 17,
    bold: true,
    color: C.ink,
    alignment: "center",
  });
  addText(slide, "seed=20260331", { left: 710, top: 498, width: 120, height: 18 }, {
    fontSize: 10.8,
    color: C.muted,
    alignment: "center",
    typeface: FONT.en,
  });
  addArrow(slide, 900, 460, 96, C.blue2);
  addRoundRect(slide, 1018, 432, 108, 52, { fill: "#F2FFF8", line: C.green, lineWidth: 1.2 });
  addRoundRect(slide, 1018, 502, 108, 52, { fill: "#FFF8EA", line: C.orange2, lineWidth: 1.2 });
  addText(slide, "train=450", { left: 1029, top: 449, width: 84, height: 18 }, {
    fontSize: 12.5,
    bold: true,
    color: C.green,
    typeface: FONT.en,
    alignment: "center",
  });
  addText(slide, "test=113", { left: 1029, top: 519, width: 84, height: 18 }, {
    fontSize: 12.5,
    bold: true,
    color: C.orange2,
    typeface: FONT.en,
    alignment: "center",
  });
  addText(slide, "对外汇报统一使用冻结 train/test 主口径；历史 split-by-split 结果只作为诊断和补充分析。", { left: 86, top: 614, width: 760, height: 23 }, {
    fontSize: 14.5,
    bold: true,
    color: C.ink,
  });
  addFooter(slide, 10);
}

function slide11(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "实验结果：主系统准确率形成清晰提升阶梯", "冻结测试集上，结构化语义裁决构成主增益，职责化复核与放行配置进一步释放修正能力。", "09");
  addRoundRect(slide, 74, 124, 720, 430, { fill: C.white, line: C.line });
  addText(slide, "PrimaryAcc@1 / test=113", { left: 106, top: 152, width: 240, height: 24 }, {
    fontSize: 16,
    bold: true,
    color: C.ink,
  });
  const baseY = 486;
  addLine(slide, 126, baseY, 600, "#D9E7F6", 1);
  addLine(slide, 126, baseY - 95, 600, "#EEF4FB", 1);
  addLine(slide, 126, baseY - 190, 600, "#EEF4FB", 1);
  addLine(slide, 126, baseY - 285, 600, "#EEF4FB", 1);
  const bars = [
    ["规则路由", 0.7876, C.blue],
    ["结构化语义路由", 0.8761, C.green],
    ["默认协作复核", 0.8850, C.orange2],
    ["扩展决策配置", 0.9292, C.red],
  ];
  bars.forEach((b, i) => {
    const h = Math.round((b[1] - 0.74) / (0.95 - 0.74) * 300);
    addBar(slide, 165 + i * 142, baseY, 72, h, b[2], b[0], `${(b[1] * 100).toFixed(2)}%`);
  });
  addText(slide, "+14.16pct", { left: 602, top: 176, width: 92, height: 24 }, {
    fontSize: 16,
    bold: true,
    color: C.red,
    alignment: "center",
    fill: "#FFF1F1",
    line: { width: 1, fill: "#F1C3C3" },
    geometry: "roundRect",
    adjustmentList: [{ name: "adj", formula: "val 50000" }],
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
  addRoundRect(slide, 850, 132, 320, 132, { fill: C.pale, line: C.blue2, lineWidth: 1.2 });
  addMetric(slide, 882, 156, "92.92%", "扩展配置测试准确率", "训练集选型后在冻结测试集一次性报告", C.red);
  addRoundRect(slide, 850, 300, 320, 112, { fill: C.white, line: C.line });
  addText(slide, "可接受准确率", { left: 878, top: 326, width: 140, height: 22 }, {
    fontSize: 17,
    bold: true,
    color: C.ink,
  });
  addText(slide, "81.42% → 91.15%", { left: 878, top: 358, width: 220, height: 26 }, {
    fontSize: 23,
    bold: true,
    color: C.blue,
    typeface: FONT.en,
  });
  addText(slide, "说明系统不仅选主能力，也提升了可接受等价标签命中能力。", { left: 878, top: 390, width: 245, height: 20 }, {
    fontSize: 10.5,
    color: C.muted,
  });
  addRoundRect(slide, 850, 450, 320, 84, { fill: C.white, line: C.line });
  addText(slide, "相关能力恢复", { left: 878, top: 468, width: 150, height: 20 }, {
    fontSize: 15.5,
    bold: true,
    color: C.ink,
  });
  addText(slide, "Recall 28.95% → 36.84%    Precision 37.93% → 42.42%", { left: 878, top: 498, width: 250, height: 20 }, {
    fontSize: 10.5,
    color: C.muted,
    typeface: FONT.en,
  });
  addText(slide, "主结果表明：模型增益来自结构化字段与候选内约束，协作复核在复杂样本上承担谨慎补充修正。", { left: 86, top: 614, width: 900, height: 24 }, {
    fontSize: 14.5,
    bold: true,
    color: C.ink,
  });
  addFooter(slide, 11);
}

function slide12(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "消融与配置：职责化证据需要与放行边界配套", "在 holdout3 对齐子集上，默认配置下多种协作协议表现接近；接入 expanded 配置后释放净修正。", "10");
  addRoundRect(slide, 70, 130, 620, 400, { fill: C.white, line: C.line });
  addText(slide, "holdout3 对齐子集 PrimaryAcc@1", { left: 100, top: 158, width: 320, height: 24 }, {
    fontSize: 16,
    bold: true,
    color: C.ink,
  });
  const baseY = 462;
  addLine(slide, 112, baseY, 510, "#D9E7F6", 1);
  const collabBars = [
    ["fastpath", 0.8625, C.blue],
    ["single", 0.8625, "#9FB2C9"],
    ["homogeneous", 0.8625, "#9FB2C9"],
    ["hetero-v3", 0.8625, C.orange2],
    ["hetero-v3 + expanded", 0.9250, C.red],
  ];
  collabBars.forEach((b, i) => {
    const h = Math.round((b[1] - 0.82) / (0.94 - 0.82) * 260);
    addBar(slide, 124 + i * 96, baseY, 54, h, b[2], b[0], `${(b[1] * 100).toFixed(2)}%`);
  });
  addRoundRect(slide, 760, 142, 330, 142, { fill: C.pale, line: C.red, lineWidth: 1.3 });
  addText(slide, "5 / 5 / 0", { left: 810, top: 170, width: 230, height: 54 }, {
    fontSize: 42,
    bold: true,
    color: C.red,
    alignment: "center",
    typeface: FONT.en,
  });
  addText(slide, "测试集改写 / 有效修正 / 回归", { left: 815, top: 232, width: 220, height: 20 }, {
    fontSize: 12.5,
    color: C.muted,
    alignment: "center",
  });
  addRoundRect(slide, 760, 322, 366, 156, { fill: C.white, line: C.line });
  addText(slide, "结论解释", { left: 792, top: 346, width: 140, height: 24 }, {
    fontSize: 18,
    bold: true,
    color: C.ink,
  });
  const bullets = [
    "异质角色产生了更有信息量的职责化判断",
    "默认配置较保守，未充分释放改判收益",
    "expanded 在训练集选型后，于冻结测试集报告一次性结果",
  ];
  bullets.forEach((b, i) => {
    addDot(slide, 801, 393 + i * 30, 4, C.blue);
    addText(slide, b, { left: 816, top: 384 + i * 30, width: 268, height: 20 }, {
      fontSize: 12.3,
      color: C.muted,
    });
  });
  addText(slide, "因此，本项目的多智能体协作价值不体现在“更多轮次”，而体现在角色分工、证据结构和授权边界共同作用。", { left: 84, top: 612, width: 940, height: 24 }, {
    fontSize: 14.5,
    bold: true,
    color: C.ink,
  });
  addFooter(slide, 12);
}

function slide13(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "原型演示：把路由结果和过程轨迹一起展示给评审", "演示页建议固定 2-3 个输入样例，展示 chosen route、related capabilities 和 trace replay。", "11");
  addRoundRect(slide, 78, 128, 1120, 426, { fill: "#071A45", line: "#1B5CA5", lineWidth: 1.2 });
  addText(slide, "AgentDNS Routing Console", { left: 112, top: 158, width: 330, height: 26 }, {
    fontSize: 18,
    bold: true,
    color: C.white,
    typeface: FONT.en,
  });
  addText(slide, "演示输入", { left: 116, top: 210, width: 88, height: 20 }, {
    fontSize: 13,
    bold: true,
    color: "#9FD4FF",
  });
  addRoundRect(slide, 112, 238, 430, 82, { fill: "#0E3268", line: "#2F80D3", lineWidth: 1 });
  addText(slide, "“帮我找一个能判断域名风险并给出处置建议的智能体，最好能保留分析依据。”", {
    left: 134,
    top: 258,
    width: 380,
    height: 42,
  }, {
    fontSize: 14,
    color: C.white,
  });
  const timeline = [
    ["Stage R", "候选召回"],
    ["Stage A", "语义裁决"],
    ["Stage B", "职责复核"],
    ["Stage C", "执行落点"],
  ];
  timeline.forEach((t, i) => {
    const x = 610 + i * 130;
    addDot(slide, x, 265, 22, [C.blue2, C.green, C.orange2, C.purple][i]);
    addText(slide, t[0], { left: x - 35, top: 251, width: 70, height: 18 }, {
      fontSize: 11.8,
      bold: true,
      color: C.white,
      alignment: "center",
      typeface: FONT.en,
    });
    addText(slide, t[1], { left: x - 45, top: 302, width: 90, height: 18 }, {
      fontSize: 10.5,
      color: "#C8E3FF",
      alignment: "center",
    });
    if (i < timeline.length - 1) addLine(slide, x + 25, 265, 80, "#5AA1E8", 2);
  });
  addRoundRect(slide, 112, 368, 470, 112, { fill: "#0A2D62", line: "#2F80D3", lineWidth: 1 });
  addText(slide, "最终路由", { left: 140, top: 390, width: 100, height: 20 }, {
    fontSize: 13,
    bold: true,
    color: "#9FD4FF",
  });
  addText(slide, "risk_domain_analysis.agentdns.cn", { left: 140, top: 422, width: 320, height: 26 }, {
    fontSize: 19,
    bold: true,
    color: C.white,
    typeface: FONT.en,
  });
  addText(slide, "final_decision_source = stage_b    entered_stage_b = true", { left: 140, top: 454, width: 380, height: 18 }, {
    fontSize: 10.5,
    color: "#B8D9FF",
    typeface: FONT.en,
  });
  const trace = [
    ["候选快照", "6 个候选能力"],
    ["竞争点", "风险分析 vs 处置建议"],
    ["复核证据", "GovernanceRisk 支持升级"],
  ];
  trace.forEach((t, i) => {
    const x = 650 + i * 160;
    addRoundRect(slide, x, 376, 132, 86, { fill: "#0E3268", line: "#2F80D3", lineWidth: 1 });
    addText(slide, t[0], { left: x + 14, top: 396, width: 100, height: 18 }, {
      fontSize: 12.5,
      bold: true,
      color: C.white,
    });
    addText(slide, t[1], { left: x + 14, top: 425, width: 100, height: 22 }, {
      fontSize: 10.5,
      color: "#C8E3FF",
    });
  });
  addText(slide, "演示重点：让评审看到“输入、候选、复核、授权、执行落点”同屏出现，降低对黑盒大模型的疑虑。", { left: 86, top: 612, width: 940, height: 24 }, {
    fontSize: 14.5,
    bold: true,
    color: C.ink,
  });
  addFooter(slide, 13);
}

function slide14(presentation) {
  const slide = presentation.slides.add();
  addLightBackground(slide);
  addTopTitle(slide, "成果体系：从原型、数据、实验到报告与专利材料已成套沉淀", "成果材料可支撑验收审阅、内部汇报、成果宣传、论文投稿和后续知识产权工作。", "12");
  const items = [
    ["原型系统", "src/agentdns_routing/ + scripts/run_*", C.blue],
    ["研究报告", "技术研究报告_20260406.md", C.green],
    ["论文材料", "gjtx_submission_20260413 / overleaf 技术报告", C.orange2],
    ["专利材料", "技术交底书、权利要求书、说明书摘要和附图", C.purple],
    ["数据图表", "563 条样本、统一 train/test、回顾性实验图", C.blue2],
    ["验收材料", "自立科研项目验收报告_填写版_20260426.md", C.red],
  ];
  items.forEach((it, i) => {
    const x = 76 + (i % 3) * 375;
    const y = 150 + Math.floor(i / 3) * 183;
    addRoundRect(slide, x, y, 315, 132, { fill: C.white, line: it[2], lineWidth: 1.2 });
    addText(slide, `0${i + 1}`, { left: x + 22, top: y + 22, width: 48, height: 28 }, {
      fontSize: 18,
      bold: true,
      color: it[2],
      typeface: FONT.en,
    });
    addText(slide, it[0], { left: x + 80, top: y + 24, width: 150, height: 24 }, {
      fontSize: 18,
      bold: true,
      color: C.ink,
    });
    addText(slide, it[1], { left: x + 80, top: y + 62, width: 200, height: 42 }, {
      fontSize: 11.5,
      color: C.muted,
    });
  });
  addRoundRect(slide, 88, 554, 1030, 58, { fill: C.pale, line: C.line });
  addText(slide, "验收提交建议", { left: 118, top: 573, width: 126, height: 22 }, {
    fontSize: 16,
    bold: true,
    color: C.blue,
  });
  addText(slide, "汇报 PPT、研究报告/论文稿、专利材料、原型与演示、实验与复现、附录数据说明可以按目录打包，便于评审快速定位证据。", {
    left: 246,
    top: 574,
    width: 820,
    height: 20,
  }, {
    fontSize: 12.5,
    color: C.ink,
  });
  addFooter(slide, 14);
}

function slide15(presentation) {
  const slide = presentation.slides.add();
  addImage(slide, path.join(ASSET_DIR, "section_bg.png"), { left: 0, top: 0, width: W, height: H }, { fit: "cover" });
  addCnnicMark(slide, true);
  addText(slide, "总结与下一步", { left: 76, top: 96, width: 380, height: 46 }, {
    fontSize: 35,
    bold: true,
    color: C.white,
  });
  addLine(slide, 78, 158, 150, C.cyan, 4);
  const points = [
    ["完成任务书指标", "形成原型框架、研究报告/论文材料、专利文本、展示与验收支撑材料。"],
    ["形成可复盘技术链条", "能力命名空间、结构化语义路由、职责化复核和可信过程记录已经闭环。"],
    ["支撑后续方向布局", "可继续面向 AgentDNS、智能体标识、服务发现和治理审计场景深化。"],
  ];
  points.forEach((p, i) => {
    const y = 228 + i * 110;
    addDot(slide, 111, y + 14, 18, [C.cyan, C.orange, C.green][i]);
    addText(slide, String(i + 1), { left: 98, top: y + 2, width: 26, height: 24 }, {
      fontSize: 14,
      bold: true,
      color: C.navy,
      alignment: "center",
      verticalAlignment: "middle",
      typeface: FONT.en,
    });
    addText(slide, p[0], { left: 154, top: y, width: 290, height: 26 }, {
      fontSize: 21,
      bold: true,
      color: C.white,
    });
    addText(slide, p[1], { left: 154, top: y + 38, width: 650, height: 34 }, {
      fontSize: 14,
      color: "#D4E8FF",
    });
  });
  addRoundRect(slide, 862, 216, 300, 246, { fill: "#082E66CC", line: "#3F85D9", lineWidth: 1.2 });
  addText(slide, "后续工作重点", { left: 895, top: 246, width: 170, height: 24 }, {
    fontSize: 19,
    bold: true,
    color: C.white,
  });
  ["扩展独立验证样本与场景", "记录真实运行时延、成本和稳定性", "推动演示端端到端联调", "凝练标准化表达与业务试点"].forEach((t, i) => {
    addDot(slide, 905, 302 + i * 38, 4, C.cyan);
    addText(slide, t, { left: 921, top: 293 + i * 38, width: 200, height: 20 }, {
      fontSize: 12.5,
      color: "#D8ECFF",
    });
  });
  addText(slide, "谢谢，请各位专家批评指正", { left: 78, top: 628, width: 420, height: 28 }, {
    fontSize: 20,
    bold: true,
    color: C.white,
  });
}

async function renderPreview(slide, file) {
  const png = await slide.export({ format: "png", scale: 1 });
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, Buffer.from(await png.arrayBuffer()));
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });

  slide1(presentation);
  slide2(presentation);
  slide3(presentation);
  slide4(presentation);
  slide5(presentation);
  slide6(presentation);
  slide7(presentation);
  slide8(presentation);
  slide9(presentation);
  slide10(presentation);
  slide11(presentation);
  slide12(presentation);
  slide13(presentation);
  slide14(presentation);
  slide15(presentation);

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(OUTPUT);

  for (let i = 0; i < presentation.slides.count; i += 1) {
    await renderPreview(
      presentation.slides.getItem(i),
      path.join(PREVIEW_DIR, `slide_${String(i + 1).padStart(2, "0")}.png`)
    );
  }
  console.log(JSON.stringify({ output: OUTPUT, previewDir: PREVIEW_DIR, slideCount: presentation.slides.count }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
