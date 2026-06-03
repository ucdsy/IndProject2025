import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "/Users/xizhuxizhu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const INPUT = "/Users/xizhuxizhu/Desktop/重点项目验收答辩PPT.pptx";
const OUT_DIR =
  "/Users/xizhuxizhu/Desktop/IndProj04/outputs/manual-20260526-goal-page-review/presentations/goal-page/preview";

await fs.mkdir(OUT_DIR, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(INPUT));

for (const i of [2, 3, 4, 5]) {
  const slide = presentation.slides.getItem(i - 1);
  const png = await slide.export({ format: "png", scale: 0.72 });
  const file = path.join(OUT_DIR, `slide_${String(i).padStart(2, "0")}.png`);
  await fs.writeFile(file, Buffer.from(await png.arrayBuffer()));
  console.log(file);
}
