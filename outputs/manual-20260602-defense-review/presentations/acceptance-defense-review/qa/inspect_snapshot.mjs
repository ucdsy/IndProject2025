import { PresentationFile, FileBlob } from '@oai/artifact-tool';
import util from 'node:util';
const p=await PresentationFile.importPptx(await FileBlob.load('/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx'));
const s=p.slides.getItem(1);
for(const idx of [1,2,3,9,10,11,14,15,16,31,32,33]){
 const sh=s.shapes.items[idx];
 const snap=sh.toSnapshot?.();
 console.log('--- shape',idx,sh.id,sh.name,'---');
 console.log(util.inspect(snap,{depth:8,colors:false,maxArrayLength:20}).slice(0,5000));
}
