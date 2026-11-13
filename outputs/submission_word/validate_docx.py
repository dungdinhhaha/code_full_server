import re
import zipfile
from xml.dom.minidom import parseString

path = r"D:\IOT Trung\code_full_server\outputs\submission_word\SMIOT_05_Use_case.docx"

with zipfile.ZipFile(path) as z:
    names = z.namelist()
    xml = z.read("word/document.xml")

try:
    parseString(xml)
    print("XML_VALID: pass")
except Exception as e:
    print("XML_VALID: FAIL", e)

text = xml.decode("utf-8")
h1 = len(re.findall(r'w:val="Heading1"', text))
h2 = len(re.findall(r'w:val="Heading2"', text))
h3 = len(re.findall(r'w:val="Heading3"', text))
tbl = len(re.findall(r"<w:tbl>", text))
img = len(re.findall(r"<w:drawing>", text))
print("Heading1:", h1)
print("Heading2:", h2)
print("Heading3:", h3)
print("Tables (<w:tbl>):", tbl)
print("Drawings (images):", img)
print("num files in zip:", len(names))
print("media files:", [n for n in names if n.startswith("word/media/")])
