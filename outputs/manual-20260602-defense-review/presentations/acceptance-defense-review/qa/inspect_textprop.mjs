import { PresentationFile, FileBlob } from '@oai/artifact-tool';
import util from 'node:util';
const p=await PresentationFile.importPptx(await FileBlob.load('/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx'));
const sh=p.slides.getItem(1).shapes.items[2];
console.log('shape text prop', util.inspect(sh.text,{depth:6,colors:false,maxArrayLength:20}).slice(0,5000));
console.log('proto desc text', Object.getOwnPropertyDescriptor(Object.getPrototypeOf(sh),'text'));
console.log('own desc text', Object.getOwnPropertyDescriptor(sh,'text'));
console.log('all proto names', Object.getOwnPropertyNames(Object.getPrototypeOf(sh)).join('\n'));
