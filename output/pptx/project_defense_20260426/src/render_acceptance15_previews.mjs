import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "/Users/xizhuxizhu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const INPUT =
  "/Users/xizhuxizhu/Desktop/IndProj04/output/pptx/project_defense_20260426/项目评审答辩PPT_验收答辩15页版_20260524.pptx";
const OUT_DIR =
  "/Users/xizhuxizhu/Desktop/IndProj04/output/pptx/project_defense_20260426/acceptance15_preview";

await fs.mkdir(OUT_DIR, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(INPUT));
console.log(`slides=${presentation.slides.count}`);

for (let i = 0; i < presentation.slides.count; i += 1) {
  const slide = presentation.slides.getItem(i);
  const png = await slide.export({ format: "png", scale: 0.72 });
  const file = path.join(OUT_DIR, `slide_${String(i + 1).padStart(2, "0")}.png`);
  await fs.writeFile(file, Buffer.from(await png.arrayBuffer()));
  console.log(file);
}
