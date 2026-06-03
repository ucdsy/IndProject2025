import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "/Users/xizhuxizhu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const INPUT =
  "/Users/xizhuxizhu/Downloads/%E9%87%8D%E7%82%B9%E9%A1%B9%E7%9B%AE%E9%AA%8C%E6%94%B6%E7%AD%94%E8%BE%A9PPT_%E6%9D%90%E6%96%99%E5%9B%BE%E7%89%88_v1_20260526.pptx";
const OUT_DIR =
  "/Users/xizhuxizhu/Desktop/IndProj04/outputs/manual-20260526-pptbeauty/presentations/project-defense-beautify/preview/source";

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
