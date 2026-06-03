import { PresentationFile, FileBlob } from '@oai/artifact-tool';
const INPUT='/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx';
const OUT='/Users/xizhuxizhu/Desktop/IndProj04/outputs/manual-20260602-defense-review/presentations/acceptance-defense-review/qa/test_set_text.pptx';
const p=await PresentationFile.importPptx(await FileBlob.load(INPUT));
const sh=p.slides.getItem(1).shapes.items[2];
console.log('before', sh.toSnapshot().text);
console.log('data paragraphs?', sh.data.paragraphs?.[0]?.runs?.[0]?.text, sh.data.inlineNodes);
try { sh.data.paragraphs[0].runs[0].text='任务书要求与完成闭环：四类指标均已形成验收证据'; } catch(e){ console.log('mutate data paragraphs failed',e.message); }
try { sh.data.paragraphs[0].inlineNodes[0].textRun.text='任务书要求与完成闭环：四类指标均已形成验收证据'; } catch(e){ console.log('mutate inline failed',e.message); }
console.log('after', sh.toSnapshot().text);
const pptx=await PresentationFile.exportPptx(p);
await pptx.save(OUT);
console.log(OUT);
