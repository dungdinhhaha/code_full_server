import zipfile
from xml.dom.minidom import parseString
from collections import Counter

path = r"outputs\submission_word\SMIOT_03_Observability_Datadog.docx"
with zipfile.ZipFile(path) as z:
    names = z.namelist()
    data = z.read("word/document.xml")

dom = parseString(data)
print("XML parse OK, length:", len(data))

styles = [n.getAttribute("w:val") for n in dom.getElementsByTagName("w:pStyle")]
c = Counter(styles)
print("Style counts (all):", dict(c))

drawings = dom.getElementsByTagName("w:drawing")
print("w:drawing count (images):", len(drawings))

tbls = dom.getElementsByTagName("w:tbl")
print("w:tbl count (tables):", len(tbls))

print("Total files in docx package:", len(names))
