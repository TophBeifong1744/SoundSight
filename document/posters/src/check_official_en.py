"""Verify English translation coverage, numeric parity, template and rendered bounds."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re
import sys
import unicodedata
from lxml import etree as E
import pdfplumber

ROOT = Path(__file__).resolve().parents[3]
REV = sys.argv[1] if len(sys.argv) > 1 else 'content-v3'
BASE = ROOT / f'document/posters/output/SoundSight-poster-en-{REV}'
ZH = ROOT / 'document/posters/output/SoundSight-poster-zh-content-v3.pptx'
EV = ROOT / 'document/evidence/posters-en-20261102'
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_json(p):
    return json.loads(p.read_text(encoding='utf-8'))


def norm(s):
    return ''.join(unicodedata.normalize('NFKC', s).split())


def shape_texts(slide):
    return {s.find('.//p:cNvPr', NS).get('name'):
            ''.join(s.xpath('.//a:t/text()', namespaces=NS))
            for s in slide.findall('.//p:sp', NS)}


def rows(slide):
    tables = slide.findall('.//a:tbl', NS)
    assert len(tables) == 1
    return [[''.join(c.xpath('.//a:t/text()', namespaces=NS))
             for c in r.findall('a:tc', NS)] for r in tables[0].findall('a:tr', NS)]


source = ROOT / 'document/posters/assets/reference/poster-reference.pptx'
assert sha(source) == 'b99946c7443efd2a169035159185ed45b0021272e03d180786c2718ec40259df'
receipt = read_json(EV / f'{REV}-validation.json')
assert receipt['finalSha256'] == sha(BASE.with_suffix('.pptx'))
assert receipt['packageIntegrity']['status'] == 'pass'
assert receipt['presentationLayout']['finding_count'] == 0
assert receipt['firstPartyImport']['passed']
zh_record = read_json(ROOT / 'document/evidence/posters-content-20261101/delivery-check.json')
for f in zh_record['outputs']:
    assert sha(ROOT / 'document/posters/output' / f['name']) == f['sha256'], f['name']
facts = read_json(ROOT / 'document/posters/assets/joint-run-facts.json')
for src in facts['sources']:
    assert sha(ROOT / src['path']) == src['sha256'], src['path']
copy = read_json(ROOT / 'document/posters/assets/copy-en.json')
translations = read_json(EV / 'translation-map.json')
assert {t['name'] for t in translations} == set(copy['elements'])
with ZipFile(source) as old, ZipFile(BASE.with_suffix('.pptx')) as new, ZipFile(ZH) as zh:
    before = E.fromstring(old.read('ppt/slides/slide1.xml'))
    after = E.fromstring(new.read('ppt/slides/slide1.xml'))
    chinese = E.fromstring(zh.read('ppt/slides/slide1.xml'))
    preserved = []
    for sid in ('8', '10', '12', '13', '14', '32', '39', '45', '46'):
        a = before.xpath("//*[@id='" + sid + "']/../..", namespaces=NS)[0].find('p:spPr/a:xfrm', NS)
        b = after.xpath("//*[@id='" + sid + "']/../..", namespaces=NS)[0].find('p:spPr/a:xfrm', NS)
        assert E.tostring(a, method='c14n') == E.tostring(b, method='c14n'), sid
        preserved.append(sid)
    for name in ('ppt/media/image1.png', 'ppt/media/image2.png'):
        assert old.read(name) == new.read(name)
    assert not any('ppt/media/' + n in new.namelist()
                   for n in ('image3.png', 'image4.png', 'image5.emf', 'image6.emf'))
    assert not any('/charts/chart' in n or n.endswith('.xlsx') for n in new.namelist())
    en_text, zh_text = shape_texts(after), shape_texts(chinese)
    for t in translations:
        assert norm(t['zh']) == norm(zh_text[t['name']]), t['name']
        assert norm(t['en']) == norm(en_text[t['name']]), t['name']
        assert t['en'] == copy['elements'][t['name']]['text'], t['name']
    english_rows, chinese_rows = rows(after), rows(chinese)
    assert english_rows[0] == copy['table_headers']
    expected_values = [[f"{r['seconds']:.3f}" for r in facts['runs']]]
    for field in ('frames', 'speaker_before_stop', 'commits', 'runtime_fault', 'drops'):
        expected_values.append([str(r[field]) for r in facts['runs']])
    assert [r[1:] for r in english_rows[1:]] == expected_values
    assert [r[1:] for r in english_rows[1:]] == [r[1:] for r in chinese_rows[1:]]
    assert [r[0] for r in english_rows[1:]] == copy['table_rows']
    visible = ''.join(after.xpath('//a:t/text()', namespaces=NS))
    master = E.fromstring(new.read('ppt/slideMasters/slideMaster1.xml'))
    mastertext = ''.join(master.xpath('//a:t/text()', namespaces=NS))
    assert 'INTERNAL DRAFT' in mastertext
    assert not re.search(r'[\u3400-\u9fff]', visible + mastertext)
    for forbidden in ('Three Gorges', 'Hao Zhang', 'radio telescope', 'Optical Communication',
                      'High-speed Acquisition', '40.55%', 'Size:11', 'Font:'):
        assert forbidden not in visible
    native_shapes = len(after.findall('.//p:sp', NS))
    assert native_shapes > 50

elements = read_json(EV / 'authored-elements.json')
table = read_json(EV / 'table-layout.json')
assert table['values'] == english_rows
for r, row in enumerate(english_rows):
    for c, value in enumerate(row):
        elements.append(dict(name=f'table-{r}-{c}', text=value,
                             x=table['x'] + sum(table['widths'][:c]),
                             y=table['y'] + r * table['rowHeight'],
                             w=table['widths'][c], h=table['rowHeight']))
bounds, failures, overlap_pairs = [], [], []
with pdfplumber.open(BASE.with_suffix('.pdf')) as pdf:
    assert len(pdf.pages) == 1
    page = pdf.pages[0]
    sx, sy = page.width / 1280, page.height / 720
    chars = [(t, ch) for ch in page.chars for t in norm(ch['text'])]
    flat = ''.join(c for c, _ in chars)
    for item in elements:
        needle, starts, pos = norm(item['text']), [], 0
        while (hit := flat.find(needle, pos)) >= 0:
            starts.append(hit)
            pos = hit + 1
        assert starts, ('Rendered text missing', item['name'])
        start = min(starts, key=lambda k: abs(chars[k][1]['top'] / sy - item['y']) +
                    abs(chars[k][1]['x0'] / sx - item['x']))
        selected = [ch for _, ch in chars[start:start + len(needle)]]
        actual = [min(c['x0'] for c in selected) / sx, min(c['top'] for c in selected) / sy,
                  max(c['x1'] for c in selected) / sx, max(c['bottom'] for c in selected) / sy]
        expected = [item['x'], item['y'], item['x'] + item['w'], item['y'] + item['h']]
        ok = (actual[0] >= expected[0] - 2 and actual[1] >= expected[1] - 2 and
              actual[2] <= expected[2] + 2 and actual[3] <= expected[3] + 2)
        bounds.append(dict(name=item['name'], glyph_bounds_css=actual,
                           textbox_css=expected, within_box=ok))
        if not ok:
            failures.append(bounds[-1])
    for i, a in enumerate(bounds):
        for b in bounds[i + 1:]:
            ax, ay, ar, ab = a['glyph_bounds_css']
            bx, by, br, bb = b['glyph_bounds_css']
            if min(ar, br) - max(ax, bx) > 0.5 and min(ab, bb) - max(ay, by) > 0.5:
                overlap_pairs.append([a['name'], b['name']])
    # The footer mark is inherited from the official master, outside authored elements.
    outlook = next(b['glyph_bounds_css'] for b in bounds if b['name'] == 'outlook')
    assert outlook[2] < 1198, 'Outlook intrudes into the reserved AMD footer strip'
    alltext = norm(page.extract_text())
    for value in ('32.159', '27.254', '3012', '2552', '117', '94', '0.45', '12000', '48kHz', '10s'):
        assert value in alltext, value
report = dict(status='FAIL' if failures or overlap_pairs else 'PASS', revision=REV,
              source_sha256=sha(source), original_furniture_geometry_ids=preserved,
              original_AMD_images_unchanged=True, sample_project_images_removed=True,
              native_shapes=native_shapes, native_tables=1, translated_textboxes=len(translations),
              numeric_cells_equal_to_chinese_and_evidence=True, chinese_pptx_pdf_png_unchanged=True,
              authored_textboxes_checked=len(bounds), all_rendered_text_within_textboxes=not failures,
              rendered_glyph_bounds=bounds, text_overlap_pairs=overlap_pairs,
              outputs=[dict(name=BASE.with_suffix(e).name, sha256=sha(BASE.with_suffix(e)))
                       for e in ('.pptx', '.pdf', '.png')],
              limitations=['No Microsoft PowerPoint edit/save test', 'No independent reviewer',
                           'Identity, device photograph and print size pending', 'No new hardware or EDA test'])
(EV / 'delivery-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(status=report['status'], translated_textboxes=len(translations),
                     checked_elements=len(bounds), bounds_failures=failures, overlaps=overlap_pairs,
                     chinese_unchanged=True), ensure_ascii=False))
sys.exit(1 if failures or overlap_pairs else 0)
