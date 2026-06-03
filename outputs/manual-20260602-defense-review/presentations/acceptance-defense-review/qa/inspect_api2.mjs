import { PresentationFile, FileBlob } from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx'));
const s=p.slides.getItem(1);
console.log('items len', s.shapes.items?.length);
for(let i=0;i<Math.min(20,s.shapes.items.length);i++){
 const sh=s.shapes.items[i];
 console.log('shape',i,'id',sh.id,'name',sh.name,'type',sh.type,'keys',Object.keys(sh).slice(0,20),'proto',Object.getOwnPropertyNames(Object.getPrototypeOf(sh)).slice(0,20),'text',typeof sh.text, sh.text?.slice?.(0,100));
}
console.log('elements len', s.elements?.items?.length);
for(let i=0;i<Math.min(8,s.elements.items.length);i++){
 const el=s.elements.items[i];
 console.log('el',i,el.constructor.name, el.id, el.name, Object.getOwnPropertyNames(Object.getPrototypeOf(el)).slice(0,20), el.text?.slice?.(0,50));
}
