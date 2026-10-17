// 把 markdown 分析報告轉成 Word（標題、段落、項目、編號、表格、圖片）。
// 用法：node scripts/build_md_to_docx.js <報告.md> <輸出.docx>
// 圖片用 ![圖說](檔名.png)（相對於 md 所在資料夾）；需要 npm 套件 docx（NODE_PATH 指向其 node_modules 亦可）。
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, Footer, PageNumber,
  HeadingLevel, AlignmentType, WidthType, ShadingType, BorderStyle, LevelFormat, TableLayoutType,
} = require("docx");

const [, , MD, OUT] = process.argv;
if (!MD || !OUT) { console.error("用法：node build_md_to_docx.js <報告.md> <輸出.docx>"); process.exit(1); }
const DIR = path.dirname(path.resolve(MD));
const FONT = "Microsoft JhengHei";
const BODY = 21;  // 10.5pt
const W = 9638;   // A4 內文寬（2 cm 邊界）

const run = (text, o = {}) => new TextRun({ text, font: { name: FONT, eastAsia: FONT }, size: BODY, ...o });
function inline(text, o = {}) {  // **粗體**、`程式碼` → 純文字
  text = text.replace(/`([^`]*)`/g, "$1");
  return text.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((s) =>
    s.startsWith("**") ? run(s.slice(2, -2), { bold: true, ...o }) : run(s, o));
}
const para = (text) => new Paragraph({ spacing: { after: 100, line: 320 }, children: inline(text) });

const cellsOf = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((s) => s.trim());
function table(rows) {
  const head = cellsOf(rows[0]);
  const body = rows.slice(2).map(cellsOf);
  const n = head.length;
  const longText = Math.max(...body.map((r) => (r[0] || "").length), (head[0] || "").length);
  const first = Math.min(3000, Math.max(1300, Math.round(W * (n <= 3 ? 0.4 : 0.14)) + (longText > 8 ? 600 : 0)));
  const rest = Math.floor((W - first) / (n - 1));
  const widths = [W - rest * (n - 1), ...Array(n - 1).fill(rest)];
  const edge = { style: BorderStyle.SINGLE, size: 4, color: "B8C4BC" };
  const borders = { top: edge, bottom: edge, left: edge, right: edge };
  const mk = (txt, i, isHead) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders,
    shading: isHead ? { type: ShadingType.CLEAR, fill: "DCE8E0", color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    children: [new Paragraph({ alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
      children: inline(txt, { size: n > 7 ? 17 : 18, bold: isHead }) })],
  });
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED,
    rows: [new TableRow({ tableHeader: true, children: head.map((h, i) => mk(h, i, true)) }),
      ...body.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, i, false)) }))],
  });
}

function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function image(cap, file) {
  const p = path.join(DIR, decodeURIComponent(file));
  if (!fs.existsSync(p)) { console.warn("找不到圖：", p); return []; }
  const data = fs.readFileSync(p);
  const { w, h } = pngSize(data);
  const k = Math.min(600 / w, 640 / h);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data, transformation: { width: Math.round(w * k), height: Math.round(h * k) },
        altText: { title: cap, description: cap, name: path.basename(p) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [run(cap, { size: 18, color: "555555" })] }),
  ];
}

function build(md) {
  const lines = md.split(/\r?\n/);
  const kids = [];
  let i = 0, title = "";
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    let m;
    if (l.startsWith("# ")) {
      title = l.slice(2);
      kids.push(new Paragraph({ heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { before: 200, after: 240 },
        children: [run(title, { size: 38, bold: true })] }));
    } else if (l.startsWith("## ")) {
      kids.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 }, keepNext: true,
        children: [run(l.slice(3), { size: 30, bold: true, color: "2F5D46" })] }));
    } else if ((m = l.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/))) {
      kids.push(...image(m[1], m[2]));
    } else if (l.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      kids.push(table(rows), new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    } else if (/^- /.test(l)) {
      kids.push(new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 80, line: 320 }, children: inline(l.slice(2)) }));
    } else if (/^\d+\. /.test(l)) {
      kids.push(new Paragraph({ numbering: { reference: "num", level: 0 }, spacing: { after: 80, line: 320 }, children: inline(l.replace(/^\d+\. /, "")) }));
    } else {
      kids.push(para(l));
    }
    i++;
  }
  return { kids, title };
}

const { kids, title } = build(fs.readFileSync(MD, "utf-8"));
const doc = new Document({
  creator: "統計資料庫", title: title || path.basename(MD),
  styles: { default: { document: { run: { font: { name: FONT, eastAsia: FONT }, size: BODY } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [run("第 ", { size: 18 }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 }), run(" 頁", { size: 18 })] })] }) },
    children: kids,
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log("OK", OUT, b.length); });
