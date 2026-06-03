import { PresentationFile, FileBlob } from '@oai/artifact-tool';
import util from 'node:util';
const p=await PresentationFile.importPptx(await FileBlob.load('/Users/xizhuxizhu/Desktop/项目验收答辩PPT.pptx'));
const sh=p.slides.getItem(1).shapes.items[2];
const proto=sh.toProto();
console.log(util.inspect(proto,{depth:12,colors:false,maxArrayLength:40}).slice(0,12000));
