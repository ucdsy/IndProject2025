import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "/Users/xizhuxizhu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const input = "/Users/xizhuxizhu/Downloads/重点项目验收答辩PPT_正式答辩版_v2_20260526.pptx";
const outDir = "/Users/xizhuxizhu/Desktop/IndProj04/outputs/manual-20260526-project-defense/presentations/ppt-polish/preview/final";

await fs.mkdir(outDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(input));
console.log(`slides=${presentation.slides.count}`);

for (let i = 0; i < presentation.slides.count; i += 1) {
  const slide = presentation.slides.getItem(i);
  const png = await slide.export({ format: "png", scale: 0.72 });
  const file = path.join(outDir, `slide_${String(i + 1).padStart(2, "0")}.png`);
  await fs.writeFile(file, Buffer.from(await png.arrayBuffer()));
  console.log(file);
}
