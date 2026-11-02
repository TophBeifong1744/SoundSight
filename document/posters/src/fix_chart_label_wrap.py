"""Keep numeric native-chart labels on one line across PPTX renderers."""
from pathlib import Path
import sys
import zipfile
from lxml import etree as ET

p = Path(sys.argv[1])
ns = {'c':'http://schemas.openxmlformats.org/drawingml/2006/chart',
      'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with zipfile.ZipFile(p) as z:
    contents = {i.filename:(i,z.read(i.filename)) for i in z.infolist()}
changes = 0
for name,(info,data) in list(contents.items()):
    if '/charts/chart' in name and name.endswith('.xml'):
        tree = ET.fromstring(data)
        for body in tree.findall('.//c:dLbls/c:txPr/a:bodyPr',ns):
            body.set('wrap','none')
            changes += 1
        contents[name] = info,ET.tostring(tree,xml_declaration=True,encoding='UTF-8')
assert changes == 1, changes
with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for info,data in contents.values():
        z.writestr(info,data)
