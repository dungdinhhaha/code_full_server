from PIL import Image,ImageOps,ImageDraw
from pathlib import Path
root=Path(r'D:\IOT Trung\code_full_server\outputs\20261104_smiot_story_pack')
for folder,out in [('qa_report','report-contact.png'),('qa_demo','demo-contact.png')]:
    files=sorted((root/folder).glob('page-*.png'))
    thumbs=[]
    for f in files:
        im=Image.open(f).convert('RGB'); im.thumbnail((520,700)); canvas=Image.new('RGB',(540,740),'white'); canvas.paste(im,((540-im.width)//2,20)); ImageDraw.Draw(canvas).text((12,710),f.name,fill='black'); thumbs.append(canvas)
    cols=2; rows=(len(thumbs)+1)//2; sheet=Image.new('RGB',(cols*540,rows*740),(220,228,232))
    for i,im in enumerate(thumbs): sheet.paste(im,((i%cols)*540,(i//cols)*740))
    sheet.save(root/'evidence'/out)
