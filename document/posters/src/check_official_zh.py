"""Check official-template geometry, rendered text, numeric evidence and English immutability."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import sys
import unicodedata
from lxml import etree as E
import pdfplumber

ROOT=Path(__file__).resolve().parents[3]
REV=sys.argv[1] if len(sys.argv)>1 else 'content-v3'
CONTENT_MODE=REV.startswith('content-')
BASE=ROOT/f'document/posters/output/SoundSight-poster-zh-{REV}'
EV=ROOT/('document/evidence/posters-content-20261101' if CONTENT_MODE else 'document/evidence/posters-official-20261101')
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return ''.join(unicodedata.normalize('NFKC',s).split())
source=ROOT/'document/posters/assets/reference/poster-reference.pptx'
assert sha(source)=='b99946c7443efd2a169035159185ed45b0021272e03d180786c2718ec40259df'
receipt=json.loads((EV/f'{REV}-validation.json').read_text(encoding='utf-8'))
assert receipt['finalSha256']==sha(BASE.with_suffix('.pptx'))
assert receipt['packageIntegrity']['status']=='pass'
assert receipt['presentationLayout']['finding_count']==0
with ZipFile(source) as old, ZipFile(BASE.with_suffix('.pptx')) as new:
    before=E.fromstring(old.read('ppt/slides/slide1.xml'))
    after=E.fromstring(new.read('ppt/slides/slide1.xml'))
    preserved=[]
    for sid in ('8','10','12','13','14','32','39','45','46'):
        a=before.xpath("//*[@id='"+sid+"']/../..",namespaces=NS)[0].find('p:spPr/a:xfrm',NS)
        b=after.xpath("//*[@id='"+sid+"']/../..",namespaces=NS)[0].find('p:spPr/a:xfrm',NS)
        assert E.tostring(a,method='c14n')==E.tostring(b,method='c14n'),sid
        preserved.append(sid)
    for name in ('ppt/media/image1.png','ppt/media/image2.png'):
        assert old.read(name)==new.read(name)
    assert not any('ppt/media/'+n in new.namelist() for n in ('image3.png','image4.png','image5.emf','image6.emf'))
    chartparts=[n for n in new.namelist() if '/charts/chart' in n and n.endswith('.xml')]
    assert len(chartparts)==(0 if CONTENT_MODE else 1)
    if not CONTENT_MODE:
        chart=E.fromstring(new.read(chartparts[0]))
        assert [float(v.text) for v in chart.findall('.//c:val/c:numRef/c:numCache/c:pt/c:v',NS)]==[7.333,4.360]
    workbooks=[n for n in new.namelist() if n.endswith('.xlsx')]
    assert len(workbooks)==(0 if CONTENT_MODE else 1)
    if CONTENT_MODE:
        facts=json.loads((ROOT/'document/posters/assets/joint-run-facts.json').read_text(encoding='utf-8'))
        for src in facts['sources']:assert sha(ROOT/src['path'])==src['sha256']
        tables=after.findall('.//a:tbl',NS)
        assert len(tables)==1
        table_rows=[[''.join(c.xpath('.//a:t/text()',namespaces=NS)) for c in row.findall('a:tc',NS)] for row in tables[0].findall('a:tr',NS)]
        expected=[['指标','第一轮','第二轮'],['日志运行时间 / s',*[f"{r['seconds']:.3f}" for r in facts['runs']]],
                  ['读取定位帧 / 帧',*[str(r['frames']) for r in facts['runs']]],
                  ['停止前声纹计算 / 次',*[str(r['speaker_before_stop']) for r in facts['runs']]],
                  ['双轴目标提交 / 次',*[str(r['commits']) for r in facts['runs']]],
                  ['运行故障值',*[str(r['runtime_fault']) for r in facts['runs']]],
                  ['旧定位结果淘汰 / 帧',*[str(r['drops']) for r in facts['runs']]]]
        assert table_rows==expected,table_rows
    native_shapes=len(after.findall('.//p:sp',NS))
    assert native_shapes>50
    text=''.join(after.xpath('//a:t/text()',namespaces=NS))
    for forbidden in ('Three Gorges','Hao Zhang','radio telescope','Optical Communication','High-speed Acquisition','Size:11','Font:'):
        assert forbidden not in text
elements=json.loads((EV/'authored-elements.json').read_text(encoding='utf-8'))
if CONTENT_MODE:
    for r,row in enumerate(table_rows):
        for c,value in enumerate(row):
            elements.append(dict(name=f'table-{r}-{c}',text=value,x=[948,1131,1196][c],y=251+r*21,w=[183,65,65][c],h=21))
with pdfplumber.open(BASE.with_suffix('.pdf')) as pdf:
    assert len(pdf.pages)==1
    page=pdf.pages[0]
    chars=[]
    for char in page.chars:
        for token in norm(char['text']):chars.append((token,char))
    flat=''.join(c for c,_ in chars)
    alltext=norm(page.extract_text())
    bounds=[]
    for item in elements:
        needle=norm(item['text']);starts=[];search_from=0
        while True:
            hit=flat.find(needle,search_from)
            if hit<0:break
            starts.append(hit);search_from=hit+1
        assert starts,('Rendered text missing',item['name'])
        # Repeated words (e.g. RGB touchscreen) occur in both prose and diagram labels.
        start=min(starts,key=lambda k:abs(chars[k][1]['top']/(page.height/720)-item['y'])+abs(chars[k][1]['x0']/(page.width/1280)-item['x']))
        selected=[ch for _,ch in chars[start:start+len(needle)]]
        x0,y0,x1,y1=min(c['x0'] for c in selected),min(c['top'] for c in selected),max(c['x1'] for c in selected),max(c['bottom'] for c in selected)
        sx,sy=page.width/1280,page.height/720
        actual=[x0/sx,y0/sy,x1/sx,y1/sy]
        expected=[item['x'],item['y'],item['x']+item['w'],item['y']+item['h']]
        # 2 CSS px tolerance for PDF font ascent/descent metrics.
        ok=actual[0]>=expected[0]-2 and actual[1]>=expected[1]-2 and actual[2]<=expected[2]+2 and actual[3]<=expected[3]+2
        bounds.append({'name':item['name'],'glyph_bounds_css':actual,'textbox_css':expected,'within_box':ok})
    assert all(x['within_box'] for x in bounds),[x for x in bounds if not x['within_box']]
    required=('32.159','27.254','3012','2552','117','94','0.45','12000','48kHz') if CONTENT_MODE else ('40.55%','7.333','4.360','32.159','27.254','3012','2552','117','94','0.45','10.912')
    for value in required:
        assert value in alltext,value
prior=json.loads((ROOT/'document/evidence/posters-20261031/delivery-check.json').read_text(encoding='utf-8'))
english=next(o for o in prior['outputs'] if o['language']=='en')
for f in english['files']:
    assert sha(ROOT/'document/posters/output'/f['name'])==f['sha256'],f['name']
report={'status':'PASS','revision':REV,'source_sha256':sha(source),'original_furniture_geometry_ids':preserved,
        'original_AMD_images_unchanged':True,'sample_project_images_removed':True,
        'native_shapes':native_shapes,'native_charts':len(chartparts),'embedded_workbooks':len(workbooks),'native_tables':1 if CONTENT_MODE else 0,
        'authored_textboxes_checked':len(bounds),'all_rendered_text_within_textboxes':True,
        'rendered_glyph_bounds':bounds,'english_pptx_pdf_png_unchanged':True,
        'outputs':[{'name':BASE.with_suffix(e).name,'sha256':sha(BASE.with_suffix(e))} for e in ('.pptx','.pdf','.png')],
        'limitations':['No Microsoft PowerPoint edit/save test','Device photo and official identity pending','Print size pending','No new hardware or EDA test']}
(EV/'delivery-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','textboxes':len(bounds),'template_geometry':len(preserved),'english_unchanged':True}))
