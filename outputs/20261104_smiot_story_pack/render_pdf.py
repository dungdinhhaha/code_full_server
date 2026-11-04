from pdf2image import convert_from_path
from pathlib import Path
root=Path(r'D:\IOT Trung\code_full_server\outputs\20261104_smiot_story_pack')
for folder,stem in [('qa_report','Bao_cao_cau_chuyen_MongoDB_Datadog'),('qa_demo','Kich_ban_demo_Datadog_theo_bang_chung')]:
    p=root/folder/(stem+'.pdf')
    imgs=convert_from_path(str(p),dpi=100)
    for i,img in enumerate(imgs,1): img.save(root/folder/f'page-{i:02}.png')
    print(folder,'pages',len(imgs))
