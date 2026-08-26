import fs from "node:fs/promises";
import { Presentation } from "@oai/artifact-tool";

const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const slide = deck.slides.add();
slide.background.fill = "#FFFFFF";
const variants = [
  ["plain", null],
  ["rtl true", { rtl: true }],
  ["bidi true", { bidi: true }],
  ["direction rtl", { direction: "rtl" }],
  ["rightToLeft true", { rightToLeft: true }],
  ["rtl one", { rtl: 1 }],
];
for (let i = 0; i < variants.length; i += 1) {
  const [label, paragraphStyle] = variants[i];
  const y = 45 + i * 105;
  const lab = slide.shapes.add({ geometry: "textbox", position: { left: 30, top: y, width: 170, height: 45 }, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  lab.text = label;
  lab.text.style = { typeface: "Arial", fontSize: 20, alignment: "left" };
  const box = slide.shapes.add({ geometry: "textbox", position: { left: 220, top: y, width: 1000, height: 75 }, fill: "#F3F4F6", line: { style: "solid", fill: "#D1D5DB", width: 1 } });
  if (paragraphStyle) {
    box.text = [{ runs: ["وضعیت نمازخانه‌های ۶ اداره تابعه در یک نگاه"], paragraphStyle }];
  } else {
    box.text = "وضعیت نمازخانه‌های ۶ اداره تابعه در یک نگاه";
  }
  box.text.style = { typeface: "Tahoma", fontSize: 34, alignment: "right", verticalAlignment: "middle", autoFit: "shrinkText" };
}
const out = "C:/Users/Mohsen/Documents/eitaa/Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send/.codex_work/report_ppt/test_rtl.png";
const blob = await deck.export({ slide, format: "png", scale: 1.5 });
await fs.writeFile(out, new Uint8Array(await blob.arrayBuffer()));
console.log(out);
