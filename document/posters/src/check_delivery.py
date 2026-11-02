"""Audit final bilingual values, editable objects, source image and PDF text."""
from pathlib import Path
import hashlib
import json
import sys
import unicodedata
import zipfile
from xml.etree import ElementTree as ET
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
REV=sys.argv[1] if len(sys.argv)>1 else 'review-v4'
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(s): return ''.join(unicodedata.normalize('NFKC',s).split())
facts=json.loads((ROOT/'document/posters/assets/facts.json').read_text(encoding='utf-8'))
reports=[]
numbers=[]
for lang in ('zh','en'):
    base=ROOT/f'document/posters/output/SoundSight-poster-{lang}-{REV}'
    ppt=base.with_suffix('.pptx')
    receipt=json.loads((ROOT/f'document/evidence/posters-20261031/{lang}-{REV}-validation.json').read_text())
    assert receipt['finalSha256']==sha(ppt)
    assert receipt['presentationLayout']['finding_count']==0
    assert receipt['presentationLayout']['warnings']==[]
    with zipfile.ZipFile(ppt) as z:
        slide=ET.fromstring(z.read('ppt/slides/slide1.xml'))
        values=[n.text for n in slide.findall('.//a:tbl//a:t',ns)]
        numeric=[s for s in values if s.replace('.','',1).isdigit()]
        numbers.append(numeric)
        assert numeric==['32.159','27.254','3012','2552','117','94','0','0','0','1'],numeric
        charts=[n for n in z.namelist() if '/charts/chart' in n and n.endswith('.xml')]
        assert len(charts)==1
        chart=ET.fromstring(z.read(charts[0]))
        assert [float(e.text) for e in chart.findall('.//c:val/c:numRef/c:numCache/c:pt/c:v',ns)]==[7.333,4.36]
        assert len([n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')])==1
        table_count=len(slide.findall('.//a:tbl',ns))
        shape_count=len(slide.findall('.//p:sp',ns))
        assert table_count==1 and shape_count>40
        image_bytes=(ROOT/'document/posters/assets/fpga-implementation-original.png').read_bytes()
        assert any(z.read(n)==image_bytes for n in z.namelist() if n.startswith('ppt/media/'))
    pdf=PdfReader(base.with_suffix('.pdf'))
    assert len(pdf.pages)==1
    text=clean(pdf.pages[0].extract_text())
    required=['40.55%','7.333','4.360','32.159','27.254','3012','2552','117','94','0.45','10.912']
    assert all(clean(v) in text for v in required)
    texts=json.loads((ROOT/f'document/evidence/posters-20261031/{lang}-authored-elements.json').read_text(encoding='utf-8'))
    missing=[]
    for item in texts:
        for ln in item['text'].splitlines():
            if clean(ln) not in text: missing.append({'name':item['name'],'line':ln})
    assert not missing,missing
    reports.append({'language':lang,'pptx_sha256':sha(ppt),'pages':1,'native_chart_count':1,
                    'embedded_workbooks':1,'native_tables':table_count,'native_shapes':shape_count,
                    'all_authored_text_found_in_pdf':True,'structural_layout_warnings':0,
                    'files':[{'name':base.with_suffix(ext).name,'sha256':sha(base.with_suffix(ext))} for ext in ('.pptx','.pdf','.png')]})
assert numbers[0]==numbers[1]
original=ROOT/'project/reports/ps_3d/latest_result/user-export/imp_schematic.png'
assert sha(original)==sha(ROOT/'document/posters/assets/fpga-implementation-original.png')
report={'status':'PASS','revision':REV,'bilingual_numeric_parity':True,'image_original_preserved':True,
        'outputs':reports,'limitations':['Not a Microsoft PowerPoint edit/save test','No new hardware or system acceptance','Print dimensions and pending evidence unresolved']}
target=ROOT/'document/evidence/posters-20261031/delivery-check.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','languages':2,'numeric_parity':True,'all_pdf_text_found':True}))
