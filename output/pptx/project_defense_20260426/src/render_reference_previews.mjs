import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "/Users/xizhuxizhu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const OUT_DIR = "/Users/xizhuxizhu/Desktop/IndProj04/output/pptx/project_defense_20260426/scratch/ref_previews";

const decks = [
  {
    name: "mayongzheng",
    path: "/Users/xizhuxizhu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_tt5mguhxte5g22_44ce/temp/drag/马永征 - 技术研发部（提交版）.pptx",
    slides: [0, 1, 5, 7, 8, 26, 31],
  },
  {
    name: "lab_defense",
    path: "/Users/xizhuxizhu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_tt5mguhxte5g22_44ce/msg/file/2026-04/市重点实验室答辩04244.pptx",
    slides: [0, 2, 3, 5, 6, 10, 18, 25],
  },
  {
    name: "liuzhuren",
    path: "/Users/xizhuxizhu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_tt5mguhxte5g22_44ce/temp/drag/刘主任 - 互联网资源大会发言稿1212-final.pptx",
    slides: [0, 1, 4, 9, 11, 20, 26],
  },
  {
    name: "cnnic_agent_dns",
    path: "/Users/xizhuxizhu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_tt5mguhxte5g22_44ce/temp/drag/1. CNNIC智能体域名系统介绍(1).pptx",
    slides: [0, 1, 4, 5, 6, 9, 10, 11, 18],
  },
  {
    name: "frameworks",
    path: "/Users/xizhuxizhu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_tt5mguhxte5g22_44ce/temp/drag/199个经典逻辑思维工具框架模型 300页PPT课件.pptx",
    slides: [0, 9, 12, 31, 45, 83],
  },
];

async function renderDeck(deck) {
  const presentation = await PresentationFile.importPptx(await FileBlob.load(deck.path));
  const deckDir = path.join(OUT_DIR, deck.name);
  await fs.mkdir(deckDir, { recursive: true });
  console.log(`${deck.name}: ${presentation.slides.count} slides`);

  for (const index of deck.slides) {
    if (index >= presentation.slides.count) continue;
    const slide = presentation.slides.getItem(index);
    if (!slide) continue;
    const png = await slide.export({ format: "png", scale: 0.6 });
    const file = path.join(deckDir, `slide_${String(index + 1).padStart(2, "0")}.png`);
    await fs.writeFile(file, Buffer.from(await png.arrayBuffer()));
    console.log(`  ${file}`);
  }
}

await fs.mkdir(OUT_DIR, { recursive: true });
for (const deck of decks) {
  try {
    await renderDeck(deck);
  } catch (err) {
    console.error(`${deck.name} failed:`, err?.stack || err);
  }
}
