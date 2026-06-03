import { PresentationFile, FileBlob } from '@oai/artifact-tool';
const INPUT='/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx';
const p=await PresentationFile.importPptx(await FileBlob.load(INPUT));
console.log('slides count', p.slides.count);
const s=p.slides.getItem(1);
console.log('slide keys', Object.keys(s));
console.log('slide proto', Object.getOwnPropertyNames(Object.getPrototypeOf(s)));
console.log('shapes', s.shapes?.count, Object.keys(s.shapes||{}), Object.getOwnPropertyNames(Object.getPrototypeOf(s.shapes||{})));
for(let i=0;i<Math.min(8,s.shapes.count);i++){
  const sh=s.shapes.getItem(i);
  console.log('shape',i,Object.keys(sh),Object.getOwnPropertyNames(Object.getPrototypeOf(sh)).slice(0,50), 'text=', sh.text?.slice?.(0,80));
}
