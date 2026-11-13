// Build outputs/submission_word/SMIOT_02_Du_lieu_MongoDB.docx from
// docs/submission/02_kien_truc_du_lieu_mongodb.md
//
// Faithful Markdown -> Word transcription. Does not add or remove content.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageBreak, Header, Footer, PageNumber, LevelFormat,
  ImageRun, VerticalAlign,
} = require("docx");

const ROOT = "D:/IOT Trung/code_full_server";
const MD_PATH = path.join(ROOT, "docs/submission/02_kien_truc_du_lieu_mongodb.md");
const FIG_DIR = path.join(ROOT, "outputs/submission_export/figures");
const OUT_DIR = path.join(ROOT, "outputs/submission_word");
const OUT_PATH = path.join(OUT_DIR, "SMIOT_02_Du_lieu_MongoDB.docx");

const raw = fs.readFileSync(MD_PATH, "utf8");

// ---------------------------------------------------------------------------
// 1. Front matter
// ---------------------------------------------------------------------------
const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
if (!fmMatch) throw new Error("Front matter not found");
const fmText = fmMatch[1];
const bodyText = fmMatch[2];

function fmField(name) {
  const re = new RegExp("^" + name + ":\\s*\"?([^\"\\n]*)\"?\\s*$", "m");
  const m = fmText.match(re);
  return m ? m[1].trim() : "";
}
const fm = {
  title: fmField("title"),
  version: fmField("version"),
  date: fmField("date"),
  project: fmField("project"),
  competition: fmField("competition"),
  submission_section: fmField("submission_section"),
  data_label: fmField("data_label"),
};

// ---------------------------------------------------------------------------
// 2. PNG dimension reader (minimal, no deps)
// ---------------------------------------------------------------------------
function pngSize(buf) {
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}
function fitImage(w, h, maxW, maxH) {
  const scale = Math.min(maxW / w, maxH / h, 1);
  return { width: Math.round(w * scale), height: Math.round(h * scale) };
}

// ---------------------------------------------------------------------------
// 3. Inline markdown tokenizer -> TextRun[]
// ---------------------------------------------------------------------------
function inlineRuns(text, baseOpts) {
  baseOpts = baseOpts || {};
  const runs = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      runs.push(new TextRun({ text: text.slice(last, m.index), ...baseOpts }));
    }
    const tok = m[0];
    if (tok.startsWith("**")) {
      runs.push(new TextRun({ text: tok.slice(2, -2), bold: true, ...baseOpts }));
    } else if (tok.startsWith("`")) {
      runs.push(new TextRun({ text: tok.slice(1, -1), font: "Consolas", ...baseOpts, bold: baseOpts.bold || false }));
    } else {
      runs.push(new TextRun({ text: tok.slice(1, -1), italics: true, ...baseOpts }));
    }
    last = re.lastIndex;
  }
  if (last < text.length) {
    runs.push(new TextRun({ text: text.slice(last), ...baseOpts }));
  }
  if (runs.length === 0) runs.push(new TextRun({ text: "", ...baseOpts }));
  return runs;
}

// Detect a full-line italic caption: *Hình X.Y. ...*
function captionMatch(line) {
  const t = line.trim();
  const m = t.match(/^\*(?!\*)([\s\S]+)\*$/);
  return m ? m[1] : null;
}

// ---------------------------------------------------------------------------
// 4. Markdown table parser
// ---------------------------------------------------------------------------
function splitRow(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  const cells = [];
  let cur = "";
  for (let idx = 0; idx < s.length; idx++) {
    const ch = s[idx];
    if (ch === "\\" && s[idx + 1] === "|") {
      cur += "|";
      idx++;
      continue;
    }
    if (ch === "|") {
      cells.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  cells.push(cur.trim());
  return cells;
}

const CONTENT_WIDTH_DXA = 9638; // A4 (11906) minus 2x1134 margins

function buildTable(headerCells, rows) {
  const nCols = headerCells.length;
  const colWidth = Math.floor(CONTENT_WIDTH_DXA / nCols);
  const colWidths = new Array(nCols).fill(colWidth);
  // give leftover width to the last column so the sum matches exactly
  colWidths[nCols - 1] += CONTENT_WIDTH_DXA - colWidth * nCols;

  const headerRow = new TableRow({
    tableHeader: true,
    children: headerCells.map((h, i) =>
      new TableCell({
        width: { size: colWidths[i], type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: "auto", fill: "D9E2F3" },
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: inlineRuns(h, { size: 20, bold: true, font: "Times New Roman" }) })],
      })
    ),
  });

  const bodyRows = rows.map(
    (r) =>
      new TableRow({
        children: r.map(
          (c, i) =>
            new TableCell({
              width: { size: colWidths[i], type: WidthType.DXA },
              verticalAlign: VerticalAlign.CENTER,
              margins: { top: 60, bottom: 60, left: 100, right: 100 },
              children: [new Paragraph({ children: inlineRuns(c, { size: 20, font: "Times New Roman" }) })],
            })
        ),
      })
  );

  return new Table({
    width: { size: CONTENT_WIDTH_DXA, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...bodyRows],
  });
}

// ---------------------------------------------------------------------------
// 5. Walk the body line by line
// ---------------------------------------------------------------------------
const lines = bodyText.split(/\r?\n/);
const bodyChildren = [];
let mermaidIndex = 0;
let tableCount = 0;
let imageCount = 0;
let h1 = 0, h2 = 0, h3 = 0;

let i = 0;
while (i < lines.length) {
  const line = lines[i];
  const trimmed = line.trim();

  // Blank line
  if (trimmed === "") { i++; continue; }

  // Fenced code block
  if (trimmed.startsWith("```")) {
    const lang = trimmed.slice(3).trim();
    const codeLines = [];
    i++;
    while (i < lines.length && !lines[i].trim().startsWith("```")) {
      codeLines.push(lines[i]);
      i++;
    }
    i++; // skip closing ```

    if (lang === "mermaid") {
      mermaidIndex++;
      imageCount++;
      const figPath = path.join(FIG_DIR, `fig_02_0${mermaidIndex}.png`);
      const buf = fs.readFileSync(figPath);
      const { width, height } = pngSize(buf);
      const fitted = fitImage(width, height, 560, 820);
      bodyChildren.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 200, after: 80 },
          children: [
            new ImageRun({
              type: "png",
              data: buf,
              transformation: fitted,
            }),
          ],
        })
      );

      // Consume following caption paragraph(s) wrapped in *...*
      while (i < lines.length && lines[i].trim() === "") i++;
      if (i < lines.length) {
        const cap = captionMatch(lines[i]);
        if (cap !== null) {
          bodyChildren.push(
            new Paragraph({
              alignment: AlignmentType.CENTER,
              spacing: { after: 200 },
              children: inlineRuns(cap, { italics: true, size: 20, color: "444444", font: "Times New Roman" }),
            })
          );
          i++;
        }
      }
    } else {
      // Generic code block (javascript/python/etc.) -> monospace paragraphs
      for (const cl of codeLines) {
        bodyChildren.push(
          new Paragraph({
            shading: { type: ShadingType.CLEAR, color: "auto", fill: "F2F2F2" },
            spacing: { before: 0, after: 0 },
            children: [
              new TextRun({ text: cl.length ? cl : " ", font: "Consolas", size: 18 }),
            ],
          })
        );
      }
      bodyChildren.push(new Paragraph({ text: "", spacing: { after: 120 } }));
    }
    continue;
  }

  // Markdown table
  if (trimmed.startsWith("|") && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
    const headerCells = splitRow(lines[i]);
    i += 2; // skip header + separator
    const rows = [];
    while (i < lines.length && lines[i].trim().startsWith("|")) {
      rows.push(splitRow(lines[i]));
      i++;
    }
    tableCount++;
    bodyChildren.push(buildTable(headerCells, rows));
    bodyChildren.push(new Paragraph({ text: "", spacing: { after: 160 } }));
    continue;
  }

  // Headings
  let hm = trimmed.match(/^(#{1,3})\s+(.*)$/);
  if (hm) {
    const level = hm[1].length;
    const text = hm[2].trim();
    const headingLevel = level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
    if (level === 1) h1++;
    else if (level === 2) h2++;
    else h3++;
    bodyChildren.push(
      new Paragraph({
        heading: headingLevel,
        children: inlineRuns(text, {}),
      })
    );
    i++;
    continue;
  }

  // Full-line italic caption appearing outside a mermaid block (defensive; none expected)
  const standaloneCaption = captionMatch(line);
  if (standaloneCaption !== null) {
    bodyChildren.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 100, after: 200 },
        children: inlineRuns(standaloneCaption, { italics: true, size: 20, color: "444444", font: "Times New Roman" }),
      })
    );
    i++;
    continue;
  }

  // Ordered list item: "1. text"
  let om = trimmed.match(/^(\d+)\.\s+(.*)$/);
  if (om) {
    bodyChildren.push(
      new Paragraph({
        numbering: { reference: "numbered-list", level: 0 },
        children: inlineRuns(om[2], {}),
      })
    );
    i++;
    continue;
  }

  // Bullet list item: "- text"
  let bm = trimmed.match(/^-\s+(.*)$/);
  if (bm) {
    bodyChildren.push(
      new Paragraph({
        numbering: { reference: "bullet-list", level: 0 },
        children: inlineRuns(bm[1], {}),
      })
    );
    i++;
    continue;
  }

  // Default: regular paragraph
  bodyChildren.push(
    new Paragraph({
      spacing: { after: 160 },
      alignment: AlignmentType.JUSTIFIED,
      children: inlineRuns(trimmed, {}),
    })
  );
  i++;
}

if (mermaidIndex !== 7) {
  throw new Error(`Expected 7 mermaid blocks, found ${mermaidIndex}`);
}

// ---------------------------------------------------------------------------
// 6. Cover page + TOC
// ---------------------------------------------------------------------------
const coverChildren = [
  new Paragraph({ text: "", spacing: { before: 1200 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: fm.project, bold: true, size: 48, font: "Times New Roman" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200 },
    children: [new TextRun({ text: fm.competition, size: 32, font: "Times New Roman", color: "444444" })],
  }),
  new Paragraph({ text: "", spacing: { before: 800 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: fm.title, bold: true, size: 36, font: "Times New Roman" })],
  }),
  new Paragraph({ text: "", spacing: { before: 600 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: `Mục hồ sơ: ${fm.submission_section}`, size: 26, font: "Times New Roman" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120 },
    children: [new TextRun({ text: `Phiên bản: ${fm.version}`, size: 26, font: "Times New Roman" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120 },
    children: [new TextRun({ text: `Ngày: ${fm.date}`, size: 26, font: "Times New Roman" })],
  }),
  new Paragraph({ text: "", spacing: { before: 600 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({
        text: "Dữ liệu tổng hợp (synthetic data)",
        italics: true,
        size: 24,
        font: "Times New Roman",
        color: "666666",
      }),
    ],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

const tocChildren = [
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "Mục lục" })],
  }),
  new TableOfContents("Mục lục", {
    hyperlink: true,
    headingStyleRange: "1-3",
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------------------------------------------------------------------------
// 7. Document assembly
// ---------------------------------------------------------------------------
const doc = new Document({
  creator: "SMIOT",
  title: fm.title,
  description: `${fm.project} - ${fm.competition}`,
  styles: {
    default: {
      document: {
        run: { font: "Times New Roman", size: 24 }, // 12pt
        paragraph: { spacing: { line: 300 } },
      },
      heading1: {
        run: { font: "Times New Roman", size: 32, bold: true, color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 180 }, keepNext: true },
      },
      heading2: {
        run: { font: "Times New Roman", size: 28, bold: true, color: "2E5496" },
        paragraph: { spacing: { before: 280, after: 140 }, keepNext: true },
      },
      heading3: {
        run: { font: "Times New Roman", size: 24, bold: true, italics: true, color: "2E5496" },
        paragraph: { spacing: { before: 220, after: 100 }, keepNext: true },
      },
    },
  },
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "\u2022",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "numbered-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 },
        },
      },
      children: coverChildren,
    },
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ children: [PageNumber.CURRENT], font: "Times New Roman", size: 20 })],
            }),
          ],
        }),
      },
      children: tocChildren,
    },
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ children: [PageNumber.CURRENT], font: "Times New Roman", size: 20 })],
            }),
          ],
        }),
      },
      children: bodyChildren,
    },
  ],
});

if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT_PATH, buf);
  console.log("Wrote", OUT_PATH, buf.length, "bytes");
  console.log("Heading1:", h1, "Heading2:", h2, "Heading3:", h3);
  console.log("Tables:", tableCount, "Images:", imageCount);
});
