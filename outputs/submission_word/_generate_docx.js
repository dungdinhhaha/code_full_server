'use strict';
/*
 * Builds outputs/submission_word/SMIOT_01_Kien_truc_giai_phap.docx
 * from docs/submission/01_kien_truc_giai_phap.md
 *
 * Run from the project working directory:
 *   node outputs/submission_word/_generate_docx.js
 */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageNumber, Footer, Header, ImageRun,
  LevelFormat, convertInchesToTwip, PageBreak, VerticalAlign,
} = require('docx');

const ROOT = path.resolve(__dirname, '..', '..');
const MD_PATH = path.join(ROOT, 'docs', 'submission', '01_kien_truc_giai_phap.md');
const FIG_DIR = path.join(ROOT, 'outputs', 'submission_export', 'figures');
const OUT_PATH = path.join(ROOT, 'outputs', 'submission_word', 'SMIOT_01_Kien_truc_giai_phap.docx');

const raw = fs.readFileSync(MD_PATH, 'utf8');

// ---------- Front matter ----------
const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
if (!fmMatch) throw new Error('Front matter not found');
const fmBlock = fmMatch[1];
const bodyRaw = raw.slice(fmMatch[0].length);

function fmField(name) {
  const re = new RegExp('^' + name + ':\\s*(.*)$', 'm');
  const m = fmBlock.match(re);
  if (!m) return null;
  let v = m[1].trim();
  if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
  return v;
}
const fmTitle = fmField('title');
const fmVersion = fmField('version');
const fmDate = fmField('date');
const fmProject = fmField('project');
const fmCompetition = fmField('competition');

console.log('Front matter:', { fmTitle, fmVersion, fmDate, fmProject, fmCompetition });

// ---------- Image sizes (read PNG IHDR) ----------
function pngSize(p) {
  const buf = fs.readFileSync(p);
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

const MAX_W_IN = 6.0;
const MAX_H_IN = 7.4;
function fitImage(p) {
  const { width, height } = pngSize(p);
  const aspect = width / height;
  let wIn = MAX_W_IN;
  let hIn = wIn / aspect;
  if (hIn > MAX_H_IN) {
    hIn = MAX_H_IN;
    wIn = hIn * aspect;
  }
  return { wPx: Math.round(wIn * 96), hPx: Math.round(hIn * 96) };
}

// ---------- Inline markdown parsing (bold / italic / code) ----------
// Tokenize a plain line into runs: **bold**, *italic*, `code`
function parseInline(text) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let lastIndex = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) {
      runs.push({ text: text.slice(lastIndex, m.index) });
    }
    const tok = m[0];
    if (tok.startsWith('**')) {
      runs.push({ text: tok.slice(2, -2), bold: true });
    } else if (tok.startsWith('`')) {
      runs.push({ text: tok.slice(1, -1), code: true });
    } else {
      runs.push({ text: tok.slice(1, -1), italic: true });
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) runs.push({ text: text.slice(lastIndex) });
  return runs;
}

function makeRuns(text, opts = {}) {
  const tokens = parseInline(text);
  return tokens.map((t) => new TextRun({
    text: t.text,
    bold: !!t.bold || !!opts.bold,
    italics: !!t.italic || !!opts.italics,
    font: t.code ? 'Consolas' : undefined,
    size: opts.size,
    color: opts.color,
  }));
}

function paraFromText(text, opts = {}) {
  return new Paragraph({
    children: makeRuns(text, opts),
    alignment: opts.alignment,
    spacing: opts.spacing || { after: 160 },
    indent: opts.indent,
  });
}

// ---------- Table parsing ----------
function splitTableRow(line) {
  let s = line.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|')) s = s.slice(0, -1);
  return s.split('|').map((c) => c.trim());
}

function isSeparatorRow(line) {
  return /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line.trim());
}

const HEADER_SHADING = { fill: 'D9E2F3', type: ShadingType.CLEAR, color: 'auto' };

function buildTable(headerCells, bodyRows) {
  const nCols = headerCells.length;
  const totalWidth = 9026; // twips, approx content width (A4, 1in margins)
  const colWidth = Math.floor(totalWidth / nCols);
  const columnWidths = new Array(nCols).fill(colWidth);
  // adjust last column to absorb rounding remainder
  columnWidths[nCols - 1] += totalWidth - colWidth * nCols;

  function cell(text, isHeader) {
    return new TableCell({
      width: { size: columnWidths[0], type: WidthType.DXA },
      shading: isHeader ? HEADER_SHADING : undefined,
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({
        children: makeRuns(text, { bold: isHeader, size: 20 }),
        spacing: { after: 0 },
      })],
    });
  }

  const rows = [];
  rows.push(new TableRow({
    tableHeader: true,
    children: headerCells.map((t, i) => new TableCell({
      width: { size: columnWidths[i], type: WidthType.DXA },
      shading: HEADER_SHADING,
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ children: makeRuns(t, { bold: true, size: 20 }), spacing: { after: 0 } })],
    })),
  }));
  for (const r of bodyRows) {
    rows.push(new TableRow({
      children: r.map((t, i) => new TableCell({
        width: { size: columnWidths[i], type: WidthType.DXA },
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ children: makeRuns(t, { size: 20 }), spacing: { after: 0 } })],
      })),
    }));
  }

  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths,
    rows,
  });
}

// ---------- Main body parser ----------
const lines = bodyRaw.split(/\r?\n/);
let i = 0;
let figCounter = 0;
const bodyChildren = [];
let tableCount = 0;
let h1 = 0, h2 = 0, h3 = 0;

function isBlank(l) { return l.trim() === ''; }

while (i < lines.length) {
  const line = lines[i];

  if (isBlank(line)) { i++; continue; }

  // Heading
  let m = line.match(/^(#{1,3})\s+(.*)$/);
  if (m) {
    const level = m[1].length;
    const text = m[2].trim();
    if (level === 1) {
      // Document's own top-level title line, duplicate of cover page title.
      // Skipped in body to avoid repeating the cover title verbatim;
      // its text is already shown on the cover page from front matter.
      i++; continue;
    }
    const headingLevel = level === 2 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2;
    if (level === 2) h1++; else h2++;
    bodyChildren.push(new Paragraph({
      heading: headingLevel,
      children: makeRuns(text),
    }));
    i++;
    continue;
  }

  // Mermaid code fence -> figure image
  if (line.trim().startsWith('```mermaid')) {
    i++;
    while (i < lines.length && !lines[i].trim().startsWith('```')) i++;
    i++; // skip closing fence
    figCounter++;
    const figPath = path.join(FIG_DIR, `fig_01_0${figCounter}.png`);
    const { wPx, hPx } = fitImage(figPath);
    const imgData = fs.readFileSync(figPath);
    bodyChildren.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 80 },
      children: [new ImageRun({
        type: 'png',
        data: imgData,
        transformation: { width: wPx, height: hPx },
      })],
    }));
    // look ahead for italic caption line "*Hình X.Y. ...*"
    // skip blank lines
    let j = i;
    while (j < lines.length && isBlank(lines[j])) j++;
    if (j < lines.length) {
      const capMatch = lines[j].trim().match(/^\*(Hình[^*]+)\*$/);
      if (capMatch) {
        bodyChildren.push(new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: capMatch[1], italics: true, size: 20 })],
        }));
        i = j + 1;
        continue;
      }
    }
    continue;
  }

  // Generic (non-mermaid) code fence - render as monospace block (not expected in this doc, safety net)
  if (line.trim().startsWith('```')) {
    i++;
    const codeLines = [];
    while (i < lines.length && !lines[i].trim().startsWith('```')) {
      codeLines.push(lines[i]);
      i++;
    }
    i++;
    for (const cl of codeLines) {
      bodyChildren.push(new Paragraph({
        children: [new TextRun({ text: cl, font: 'Consolas', size: 20 })],
        spacing: { after: 0 },
      }));
    }
    continue;
  }

  // Table
  if (line.trim().startsWith('|') && i + 1 < lines.length && isSeparatorRow(lines[i + 1])) {
    const headerCells = splitTableRow(line);
    i += 2;
    const bodyRows = [];
    while (i < lines.length && lines[i].trim().startsWith('|')) {
      bodyRows.push(splitTableRow(lines[i]));
      i++;
    }
    bodyChildren.push(buildTable(headerCells, bodyRows));
    bodyChildren.push(new Paragraph({ text: '', spacing: { after: 160 } }));
    tableCount++;
    continue;
  }

  // Bullet list ("- ")
  if (/^-\s+/.test(line.trim())) {
    const itemText = line.trim().replace(/^-\s+/, '');
    bodyChildren.push(new Paragraph({
      children: makeRuns(itemText),
      numbering: { reference: 'bullet-list', level: 0 },
      spacing: { after: 100 },
    }));
    i++;
    continue;
  }

  // Numbered list ("1. ", "2. ", ...) - rendered with the literal source
  // number preserved verbatim (source numbering has an intentional gap in
  // section 8, so automatic re-numbering would alter the visible content).
  m = line.trim().match(/^(\d+)\.\s+(.*)$/);
  if (m) {
    const num = m[1];
    const rest = m[2];
    bodyChildren.push(new Paragraph({
      children: [
        new TextRun({ text: `${num}. `, bold: false }),
        ...makeRuns(rest),
      ],
      indent: { left: convertInchesToTwip(0.25), hanging: convertInchesToTwip(0.25) },
      spacing: { after: 100 },
    }));
    i++;
    continue;
  }

  // Standalone italic caption-like paragraph, e.g. "*Hình 3.1. ...*" not
  // already consumed after a mermaid block (defensive; should not normally hit)
  const soloItalic = line.trim().match(/^\*(.+)\*$/);
  if (soloItalic) {
    bodyChildren.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: soloItalic[1], italics: true, size: 20 })],
      spacing: { after: 200 },
    }));
    i++;
    continue;
  }

  // Plain paragraph
  bodyChildren.push(paraFromText(line.trim()));
  i++;
}

console.log('Parsed body: headings H1=%d H2=%d tables=%d figures=%d', h1, h2, tableCount, figCounter);

// ---------- Cover page ----------
const coverChildren = [
  new Paragraph({ text: '', spacing: { before: 1200 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: fmProject || 'SMIOT Smart Farm', bold: true, size: 40 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 600 },
    children: [new TextRun({ text: fmCompetition || 'Mini Hackathon MongoDB x Datadog 2026', size: 28 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 800, after: 300 },
    children: [new TextRun({ text: fmTitle || '', bold: true, size: 32 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 150 },
    children: [new TextRun({ text: 'Mục hồ sơ: 3', size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 150 },
    children: [new TextRun({ text: `Phiên bản: ${fmVersion || ''}`, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 400 },
    children: [new TextRun({ text: `Ngày: ${fmDate || ''}`, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 150 },
    children: [new TextRun({ text: 'Dữ liệu tổng hợp (synthetic data)', italics: true, size: 22 })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Table of contents ----------
const tocChildren = [
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: 'Mục lục' })],
  }),
  new Paragraph({
    children: [new TextRun({ text: '(Nhấn F9 trong Word để cập nhật mục lục này sau khi mở tài liệu.)', italics: true, size: 20 })],
    spacing: { after: 200 },
  }),
  new TableOfContents('Mục lục', {
    hyperlink: true,
    headingStyleRange: '1-2',
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Styles ----------
const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullet-list',
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: '•',
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: convertInchesToTwip(0.25), hanging: convertInchesToTwip(0.25) },
              },
            },
          },
        ],
      },
    ],
  },
  styles: {
    default: {
      document: {
        run: { font: 'Times New Roman', size: 22 },
      },
      heading1: {
        run: { font: 'Times New Roman', size: 30, bold: true, color: '1F3864' },
        paragraph: { spacing: { before: 360, after: 200 }, keepNext: true },
      },
      heading2: {
        run: { font: 'Times New Roman', size: 26, bold: true, color: '2E5395' },
        paragraph: { spacing: { before: 280, after: 160 }, keepNext: true },
      },
      heading3: {
        run: { font: 'Times New Roman', size: 24, bold: true, color: '2E5395' },
        paragraph: { spacing: { before: 220, after: 120 }, keepNext: true },
      },
    },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: convertInchesToTwip(8.27), height: convertInchesToTwip(11.69) }, // A4
          margin: {
            top: convertInchesToTwip(1),
            bottom: convertInchesToTwip(1),
            left: convertInchesToTwip(1),
            right: convertInchesToTwip(1),
          },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ children: [PageNumber.CURRENT], size: 20 }),
              ],
            }),
          ],
        }),
      },
      children: [...coverChildren, ...tocChildren, ...bodyChildren],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, buf);
  console.log('Wrote', OUT_PATH, buf.length, 'bytes');
  console.log(JSON.stringify({ h1, h2, tableCount, figCounter }));
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
