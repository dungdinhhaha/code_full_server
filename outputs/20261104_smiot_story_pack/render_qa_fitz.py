import fitz
from pathlib import Path
root = Path(r'D:\IOT Trung\code_full_server\outputs\20261104_smiot_story_pack')
for folder, stem in [('qa_report','Bao_cau_chuyen_MongoDB_Datadog'),('qa_demo','Kich_ban_demo_Datadog_theo_bang_chung')]:
    doc = fitz.open(root / folder / f'{stem}.pdf')
    print(folder, 'pages', len(doc))
    for i, page in enumerate(doc, 1):
        page.get_pixmap(matrix=fitz.Matrix(1.2,1.2), alpha=False).save(root / folder / f'page-{i:02}.png')
