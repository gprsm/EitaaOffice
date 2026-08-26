import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/Mohsen/Desktop/Report.xlsx";
const outputDir = "C:/Users/Mohsen/Documents/eitaa/Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send/.codex_work/report_ppt/workbook_preview";

await fs.mkdir(outputDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const overview = await workbook.inspect({
  kind: "workbook,sheet,table,region,drawing",
  maxChars: 12000,
  tableMaxRows: 40,
  tableMaxCols: 30,
  tableMaxCellChars: 160,
});
console.log("WORKBOOK_OVERVIEW");
console.log(overview.ndjson);

for (let i = 0; i < workbook.worksheets.items.length; i += 1) {
  const sheet = workbook.worksheets.items[i];
  const used = sheet.getUsedRange();
  console.log(`SHEET_${i + 1}_NAME=${sheet.name}`);
  if (used) {
    const detail = await workbook.inspect({
      kind: "table,region,formula,computedStyle",
      sheetId: sheet.name,
      range: used.address,
      maxChars: 16000,
      tableMaxRows: 60,
      tableMaxCols: 30,
      tableMaxCellChars: 180,
      options: { maxResults: 200 },
    });
    console.log(detail.ndjson);
    const preview = await workbook.render({
      sheetName: sheet.name,
      autoCrop: "all",
      scale: 1.5,
      format: "png",
    });
    await fs.writeFile(
      `${outputDir}/sheet-${String(i + 1).padStart(2, "0")}.png`,
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}
