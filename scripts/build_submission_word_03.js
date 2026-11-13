"use strict";
/*
 * Build outputs/submission_word/SMIOT_03_Observability_Datadog.docx
 * from docs/submission/03_kien_truc_observability_datadog.md
 *
 * Faithful markdown -> docx transcription. Does not add or remove content.
 * See task instructions for the mermaid-image mapping rule (block #9 skipped).
 */

const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  Table,
  TableRow,
  TableCell,
  WidthType,
  ShadingType,
  BorderStyle,
  ImageRun,
  PageBreak,
  Header,
  Footer,
  PageNumber,
  TableOfContents,
  LevelFormat,
  TableLayoutType,
  VerticalAlign,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const MD_PATH = path.join(ROOT, "docs", "submission", "03_kien_truc_observability_datadog.md");
const FIG_DIR = path.join(ROOT, "outputs", "submission_export", "figures");
const OUT_DIR = path.join(ROOT, "outputs", "submission_word");
const OUT_PATH = path.join(OUT_DIR, "SMIOT_03_Observability_Datadog.docx");

const FONT = "Calibri";
const CODE_FONT = "Consolas";

// ---------------------------------------------------------------------------
// Layout constants (A4, 1 inch margins)
// ---------------------------------------------------------------------------
const PAGE_WIDTH_TWIPS = 11906;
const PAGE_HEIGHT_TWIPS = 16838;
const MARGIN_TWIPS = 1440;
const CONTENT_WIDTH_TWIPS = PAGE_WIDTH_TWIPS - MARGIN_TWIPS * 2; // 9026
const IMAGE_MAX_WIDTH_PX = 560;
const IMAGE_MAX_HEIGHT_PX = 800;

// ---------------------------------------------------------------------------
// Read source markdown
// ---------------------------------------------------------------------------
const raw = fs.readFileSync(MD_PATH, "utf8");
const lines = raw.split(/\r?\n/);

// ---- front matter -----------------------------------------------------
if (lines[0].trim() !== "---") {
  throw new Error("Expected YAML front matter at top of file");
}
let fmEnd = -1;
for (let i = 1; i < lines.length; i++) {
  if (lines[i].trim() === "---") {
    fmEnd = i;
    break;
  }
}
if (fmEnd === -1) throw new Error("Front matter not closed");
const fmLines = lines.slice(1, fmEnd);
function fmValue(key) {
  const re = new RegExp("^" + key + ":\\s*(.*)$");
  for (const l of fmLines) {
    const m = l.match(re);
    if (m) {
      let v = m[1].trim();
      if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
      return v;
    }
  }
  return "";
}
const fm = {
  title: fmValue("title"),
  version: fmValue("version"),
  date: fmValue("date"),
  project: fmValue("project"),
  competition: fmValue("competition"),
};

const bodyLines = lines.slice(fmEnd + 1);

// ---------------------------------------------------------------------------
// Inline markdown -> TextRun options
// ---------------------------------------------------------------------------
function tokenizeInline(text) {
  // Order matters: bold (**), then code (`), then italic (*)
  const re = /(\*\*.+?\*\*|`.+?`|\*[^*]+?\*)/g;
  const tokens = [];
  let lastIndex = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) {
      tokens.push({ text: text.slice(lastIndex, m.index) });
    }
    const tok = m[0];
    if (tok.startsWith("**")) {
      tokens.push({ text: tok.slice(2, -2), bold: true });
    } else if (tok.startsWith("`")) {
      tokens.push({ text: tok.slice(1, -1), code: true });
    } else {
      tokens.push({ text: tok.slice(1, -1), italic: true });
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) tokens.push({ text: text.slice(lastIndex) });
  return tokens.filter((t) => t.text.length > 0);
}

function buildRuns(text, extra) {
  extra = extra || {};
  const tokens = tokenizeInline(text);
  if (tokens.length === 0) return [new TextRun({ text: "", ...extra })];
  return tokens.map((t) => {
    const opts = {
      text: t.text,
      font: t.code ? CODE_FONT : extra.font || FONT,
      bold: !!t.bold || !!extra.bold,
      italics: !!t.italic || !!extra.italics,
    };
    if (extra.size) opts.size = extra.size;
    if (extra.color) opts.color = extra.color;
    return new TextRun(opts);
  });
}

// ---------------------------------------------------------------------------
// PNG dimension reader (IHDR chunk) + scaling helper
// ---------------------------------------------------------------------------
function readPngSize(buffer) {
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  return { width, height };
}
function scaleToFit(natW, natH, maxW, maxH) {
  const ratio = Math.min(maxW / natW, maxH / natH, 1);
  return { width: Math.round(natW * ratio), height: Math.round(natH * ratio) };
}

function figureParagraphs(figNum) {
  const fname = "fig_03_" + String(figNum).padStart(2, "0") + ".png";
  const fpath = path.join(FIG_DIR, fname);
  const data = fs.readFileSync(fpath);
  const { width: natW, height: natH } = readPngSize(data);
  const { width, height } = scaleToFit(natW, natH, IMAGE_MAX_WIDTH_PX, IMAGE_MAX_HEIGHT_PX);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 80 },
      children: [
        new ImageRun({
          type: "png",
          data,
          transformation: { width, height },
        }),
      ],
    }),
  ];
}

// Ordered-list style paragraph using literal numbering text (preserves exact
// source numbering, including intentional gaps such as section 10's 1..5,7..17).
function literalListParagraph(label, restText) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 100 },
    indent: { left: 540, hanging: 360 },
    children: [
      new TextRun({ text: label + " ", font: FONT, bold: false }),
      ...buildRuns(restText),
    ],
  });
}

function bulletListParagraph(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 80 },
    numbering: { reference: "bullet-list", level: 0 },
    children: buildRuns(text),
  });
}

function captionParagraph(text) {
  // text is the full line including leading/trailing '*'
  const inner = text.trim().replace(/^\*/, "").replace(/\*$/, "");
  const tokens = tokenizeInline(inner);
  const runs = tokens.map(
    (t) =>
      new TextRun({
        text: t.text,
        font: t.code ? CODE_FONT : FONT,
        bold: !!t.bold,
        italics: true,
      })
  );
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: runs,
  });
}

function normalParagraph(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 120 },
    children: buildRuns(text),
  });
}

function headingParagraph(level, text) {
  const map = {
    1: HeadingLevel.HEADING_1,
    2: HeadingLevel.HEADING_2,
    3: HeadingLevel.HEADING_3,
  };
  return new Paragraph({
    heading: map[level],
    children: buildRuns(text),
  });
}

// ---------------------------------------------------------------------------
// Table parsing
// ---------------------------------------------------------------------------
function isSeparatorRow(cells) {
  return cells.every((c) => /^:?-+:?$/.test(c.trim()));
}
function splitRow(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

function buildTable(rows) {
  const header = splitRow(rows[0]);
  const numCols = header.length;
  const dataRows = [];
  for (let i = 1; i < rows.length; i++) {
    const cells = splitRow(rows[i]);
    if (isSeparatorRow(cells)) continue;
    dataRows.push(cells);
  }
  const colWidth = Math.floor(CONTENT_WIDTH_TWIPS / numCols);
  const widths = new Array(numCols).fill(colWidth);
  widths[numCols - 1] += CONTENT_WIDTH_TWIPS - colWidth * numCols;

  const headerRow = new TableRow({
    tableHeader: true,
    children: header.map(
      (text, idx) =>
        new TableCell({
          width: { size: widths[idx], type: WidthType.DXA },
          verticalAlign: VerticalAlign.CENTER,
          shading: { type: ShadingType.CLEAR, fill: "D9D9D9", color: "auto" },
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
          children: [
            new Paragraph({
              alignment: AlignmentType.LEFT,
              children: buildRuns(text, { bold: true }),
            }),
          ],
        })
    ),
  });

  const bodyRows = dataRows.map(
    (cells) =>
      new TableRow({
        children: cells.map(
          (text, idx) =>
            new TableCell({
              width: { size: widths[idx] || colWidth, type: WidthType.DXA },
              verticalAlign: VerticalAlign.CENTER,
              margins: { top: 60, bottom: 60, left: 100, right: 100 },
              children: [
                new Paragraph({
                  alignment: AlignmentType.LEFT,
                  children: buildRuns(text),
                }),
              ],
            })
        ),
      })
  );

  return new Table({
    width: { size: CONTENT_WIDTH_TWIPS, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    rows: [headerRow, ...bodyRows],
  });
}

// ---------------------------------------------------------------------------
// LLM Observability branch (mermaid block #9) - text description, numbered list
// ---------------------------------------------------------------------------
function llmObsDescriptionParagraphs() {
  const items = [
    "Trợ lý AI gọi mô hình Gemini qua GenerateContent.",
    "Kiểm tra LLM Observability có đang bật hay không.",
    "Nếu bật: tạo span, gắn metadata (số ký tự, token, tên mô hình, nhà cung cấp...); không gắn nội dung.",
    "Nếu chú thích span bị lỗi: bỏ qua lỗi, mô hình vẫn trả kết quả. Nếu không lỗi: span hiện trên Datadog.",
  ];
  return items.map((t, i) => literalListParagraph(String(i + 1) + ".", t));
}

// ---------------------------------------------------------------------------
// Main body conversion
// ---------------------------------------------------------------------------
let mermaidCounter = 0;
const bodyChildren = [];

let i = 0;
const n = bodyLines.length;
let headingCount = { h1: 0, h2: 0, h3: 0 };
let imagesInserted = 0;
let tablesInserted = 0;

while (i < n) {
  const line = bodyLines[i];
  const trimmed = line.trim();

  if (trimmed === "") {
    i++;
    continue;
  }

  // Horizontal rule separators between sections
  if (/^-{3,}$/.test(trimmed)) {
    i++;
    continue;
  }

  // Mermaid fenced code block
  if (trimmed.startsWith("```mermaid")) {
    let j = i + 1;
    while (j < n && bodyLines[j].trim() !== "```") j++;
    // j is the closing fence line (or n if unterminated)
    mermaidCounter++;
    if (mermaidCounter === 9) {
      bodyChildren.push(...llmObsDescriptionParagraphs());
    } else {
      bodyChildren.push(...figureParagraphs(mermaidCounter));
      imagesInserted++;
    }
    i = j + 1;
    // Following line is expected to be the italic caption; let generic loop
    // handle it as a normal caption paragraph (falls through next iteration).
    continue;
  }

  // Headings
  const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
  if (headingMatch) {
    const level = headingMatch[1].length;
    const text = headingMatch[2].trim();

    // Special-case "Mục lục" section: render its item lines literally,
    // preserving exact labels (0., 1., ..., 5A., Phụ lục A., Phụ lục B.)
    if (text === "Mục lục") {
      bodyChildren.push(headingParagraph(level, text));
      if (level === 1) headingCount.h1++;
      else if (level === 2) headingCount.h2++;
      else headingCount.h3++;
      i++;
      // consume following non-blank lines until blank line
      while (i < n && bodyLines[i].trim() !== "") {
        const itemText = bodyLines[i].trim();
        const im = itemText.match(/^(\S+\.)\s+(.*)$/);
        if (im) {
          bodyChildren.push(literalListParagraph(im[1], im[2]));
        } else {
          bodyChildren.push(normalParagraph(itemText));
        }
        i++;
      }
      continue;
    }

    bodyChildren.push(headingParagraph(level, text));
    if (level === 1) headingCount.h1++;
    else if (level === 2) headingCount.h2++;
    else headingCount.h3++;
    i++;
    continue;
  }

  // Table block
  if (trimmed.startsWith("|")) {
    const rows = [];
    let j = i;
    while (j < n && bodyLines[j].trim().startsWith("|")) {
      rows.push(bodyLines[j]);
      j++;
    }
    bodyChildren.push(buildTable(rows));
    bodyChildren.push(new Paragraph({ text: "", spacing: { after: 160 } }));
    tablesInserted++;
    i = j;
    continue;
  }

  // Italic caption line: *Hình X.Y. ...*
  if (/^\*.+\*$/.test(trimmed) && !trimmed.startsWith("**")) {
    bodyChildren.push(captionParagraph(trimmed));
    i++;
    continue;
  }

  // Bullet list item
  if (/^-\s+/.test(trimmed)) {
    const text = trimmed.replace(/^-\s+/, "");
    bodyChildren.push(bulletListParagraph(text));
    i++;
    continue;
  }

  // Ordered list item "N. text" (preserve literal numbers, including gaps)
  const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
  if (olMatch) {
    bodyChildren.push(literalListParagraph(olMatch[1] + ".", olMatch[2]));
    i++;
    continue;
  }

  // Plain paragraph
  bodyChildren.push(normalParagraph(trimmed));
  i++;
}

if (mermaidCounter !== 13) {
  throw new Error("Expected 13 mermaid blocks, found " + mermaidCounter);
}
if (imagesInserted !== 12) {
  throw new Error("Expected 12 inserted images, found " + imagesInserted);
}

// ---------------------------------------------------------------------------
// Cover page
// ---------------------------------------------------------------------------
const coverChildren = [
  new Paragraph({ text: "", spacing: { before: 1800 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: fm.project || "SMIOT Smart Farm", bold: true, size: 56, font: FONT })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 600 },
    children: [
      new TextRun({
        text: fm.competition || "Mini Hackathon MongoDB x Datadog 2026",
        size: 32,
        font: FONT,
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 300 },
    children: [new TextRun({ text: fm.title, bold: true, size: 40, font: FONT })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160 },
    children: [new TextRun({ text: "Mục hồ sơ: 5", size: 26, font: FONT })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160 },
    children: [
      new TextRun({
        text: "Phiên bản " + fm.version + " — " + fm.date,
        size: 24,
        font: FONT,
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160 },
    children: [
      new TextRun({
        text: "Dữ liệu tổng hợp (synthetic data)",
        italics: true,
        size: 24,
        font: FONT,
      }),
    ],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------------------------------------------------------------------------
// Table of contents page
// ---------------------------------------------------------------------------
const tocChildren = [
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "Mục lục", font: FONT })],
  }),
  new TableOfContents("Mục lục", {
    hyperlink: true,
    headingStyleRange: "1-3",
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------------------------------------------------------------------------
// Document assembly
// ---------------------------------------------------------------------------
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 22 }, // 11pt
      },
      heading1: {
        run: { font: FONT, bold: true, size: 32, color: "1F3864" }, // 16pt
        paragraph: { spacing: { before: 360, after: 200 }, keepNext: true },
      },
      heading2: {
        run: { font: FONT, bold: true, size: 26, color: "2E5496" }, // 13pt
        paragraph: { spacing: { before: 280, after: 160 }, keepNext: true },
      },
      heading3: {
        run: { font: FONT, bold: true, size: 24, color: "44546A" }, // 12pt
        paragraph: { spacing: { before: 220, after: 120 }, keepNext: true },
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
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 540, hanging: 300 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH_TWIPS, height: PAGE_HEIGHT_TWIPS },
          margin: {
            top: MARGIN_TWIPS,
            bottom: MARGIN_TWIPS,
            left: MARGIN_TWIPS,
            right: MARGIN_TWIPS,
          },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 }),
              ],
            }),
          ],
        }),
      },
      children: [...coverChildren, ...tocChildren, ...bodyChildren],
    },
  ],
});

// ---------------------------------------------------------------------------
// Write file
// ---------------------------------------------------------------------------
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT_PATH, buf);
  const stat = fs.statSync(OUT_PATH);
  console.log("Written:", OUT_PATH, stat.size, "bytes");
  console.log("Headings: H1=" + headingCount.h1, "H2=" + headingCount.h2, "H3=" + headingCount.h3);
  console.log("Tables:", tablesInserted);
  console.log("Images inserted:", imagesInserted, "(mermaid blocks total:", mermaidCounter, ")");
});
