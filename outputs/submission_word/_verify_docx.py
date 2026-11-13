import zipfile
import re
from xml.dom.minidom import parseString

PATH = r"outputs\submission_word\SMIOT_01_Kien_truc_giai_phap.docx"

with zipfile.ZipFile(PATH) as z:
    xml_bytes = z.read("word/document.xml")

try:
    parseString(xml_bytes)
    print("XML_VALID: pass")
except Exception as e:
    print("XML_VALID: fail:", e)
    raise SystemExit(1)

text = xml_bytes.decode("utf-8")


def count(pattern):
    return len(re.findall(pattern, text))


h1 = count(r'w:pStyle w:val="Heading1"')
h2 = count(r'w:pStyle w:val="Heading2"')
h3 = count(r'w:pStyle w:val="Heading3"')
tbl = count(r"<w:tbl>")
img = count(r"<pic:pic ")

print("Heading1 paragraphs:", h1)
print("Heading2 paragraphs:", h2)
print("Heading3 paragraphs:", h3)
print("Tables <w:tbl>:", tbl)
print("Images <pic:pic>:", img)
