import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/intern1/Desktop/fintech";
const csvPath = path.join(root, "evaluation/reports/p5_manual_seed_review.csv");
const outputDir = path.join(root, "outputs/p5-review");
const csvText = (await fs.readFile(csvPath, "utf8")).replace(/^\uFEFF/, "");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "Seed review" });
const sheet = workbook.worksheets.getItem("Seed review");

await fs.mkdir(outputDir, { recursive: true });
const before = await workbook.render({
  sheetName: "Seed review",
  range: "A1:I18",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "p5_manual_seed_review_before.png"),
  new Uint8Array(await before.arrayBuffer()),
);

const approvalRows = Array.from({ length: 100 }, () => ["approved"]);
const noteRows = Array.from(
  { length: 100 },
  () => ["Project owner confirmed second review on 2026-10-26"],
);
sheet.getRange("H2:H101").values = approvalRows;
sheet.getRange("I2:I101").values = noteRows;
sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;
sheet.getRange("A1:I101").format.font = { name: "Arial", size: 10, color: "#1F2937" };
sheet.getRange("A1:I1").format = {
  fill: "#163C32",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("A2:I101").format.verticalAlignment = "center";
sheet.getRange("H2:H101").format = {
  fill: "#E8F3DF",
  font: { name: "Arial", size: 10, bold: true, color: "#276749" },
  horizontalAlignment: "center",
};
sheet.getRange("A:A").format.columnWidth = 16;
sheet.getRange("B:B").format.columnWidth = 10;
sheet.getRange("C:C").format.columnWidth = 42;
sheet.getRange("D:E").format.columnWidth = 23;
sheet.getRange("F:F").format.columnWidth = 44;
sheet.getRange("F2:F101").format.wrapText = true;
sheet.getRange("G:G").format.columnWidth = 24;
sheet.getRange("H:H").format.columnWidth = 14;
sheet.getRange("I:I").format.columnWidth = 42;
sheet.getRange("A1:I1").format.rowHeight = 22;
sheet.getRange("A2:I101").format.rowHeight = 32;

workbook.recalculate();
const check = await workbook.inspect({
  kind: "table",
  range: "Seed review!A1:I8",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 9,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
const after = await workbook.render({
  sheetName: "Seed review",
  range: "A1:I18",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "p5_manual_seed_review.png"),
  new Uint8Array(await after.arrayBuffer()),
);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "p5_manual_seed_review.xlsx"));

const values = sheet.getRange("A1:I101").values;
const escapeCsv = (value) => {
  const text = value == null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const updatedCsv = values.map((row) => row.map(escapeCsv).join(",")).join("\r\n") + "\r\n";
await fs.writeFile(csvPath, `\uFEFF${updatedCsv}`, "utf8");

console.log(JSON.stringify({ check: check.ndjson, errors: errors.ndjson, rows: values.length - 1 }));
