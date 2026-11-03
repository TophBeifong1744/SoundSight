"""Recompute report statistics from supplied XLSX cells without editing originals.

The source owner's corrections are documented beside the workbook. This reads
stored numeric cells, never invents observations or treats summaries as raw data.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import posixpath
import re
from statistics import mean
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def sheets(path):
    with ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {x.attrib['Id']: x.attrib['Target'] for x in
                ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        output = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS):
            rel = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = rels[rel]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows = []
            for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row', NS):
                values = {}
                for cell in row:
                    value = cell.find('s:v', NS)
                    kind = cell.attrib.get('t')
                    if kind == 'inlineStr':
                        value = ''.join(cell.find('s:is', NS).itertext())
                    elif value is not None:
                        value = value.text
                        value = shared[int(value)] if kind == 's' else float(value) if kind not in ('str','e') else value
                    else:
                        continue
                    values[re.sub(r'\d+', '', cell.attrib['r'])] = value
                if values:
                    rows.append(values)
            output[sheet.attrib['name']] = rows
        return output


def errors(values):
    return dict(n=len(values), mae_deg=mean(abs(v) for v in values),
                rmse_deg=math.sqrt(mean(v*v for v in values)), max_abs_deg=max(map(abs, values)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workbook', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    data = sheets(args.workbook)
    angle = [r for r in data['角度准确性-原始'] if str(r.get('A','')).startswith('P') and isinstance(r.get('F'), float)]
    mechanical = [r for r in data['双轴指向与响应'] if isinstance(r.get('A'), float)]
    speaker = [r for r in data['声纹评价-原始'] if str(r.get('A','')).startswith('S') and isinstance(r.get('G'), float)]
    longrun = [r for r in data['四功能联合长稳'] if isinstance(r.get('C'), float)]
    joint = [r for r in data['声纹双轴联合日志'] if isinstance(r.get('A'), float)]
    assert (len(angle), len(mechanical), len(speaker), len(longrun), len(joint)) == (75,10,60,13,30)
    # Recompute errors from reference and measured values, not rounded summaries.
    for r in angle:
        r['az_error_deg'] = (r['F']-r['C']+180) % 360-180
        r['el_error_deg'] = r['G']-r['D']
        assert abs(r['az_error_deg']-r['H']) < 1e-8
        assert abs(r['el_error_deg']-r['I']) < 1e-8
    genuine = [r for r in speaker if r['D'].startswith('本人')]
    impostor = [r for r in speaker if r['D'].startswith('冒认')]
    fr = sum(r['G'] < r['F'] for r in genuine)
    fa = sum(r['G'] >= r['F'] for r in impostor)
    for r in speaker:
        assert (r['G'] >= r['F']) == (r['H'] == '通过')
    timings = [r[c] for r in mechanical for c in ('I','J','K')]
    group_means = [mean(r[c] for c in ('I','J','K')) for r in mechanical]
    result = dict(provenance='User-supplied measured workbook; owner corrections in provenance.md',
        geometry='40 mm regular tetrahedron; owner corrected the square-array description',
        angle=dict(points=len({r['A'] for r in angle}), repeats_per_point=5,
            azimuth=errors([r['az_error_deg'] for r in angle]), elevation=errors([r['el_error_deg'] for r in angle])),
        mechanical=dict(targets=10, azimuth=errors([r['D']-r['B'] for r in mechanical]),
            elevation=errors([r['E']-r['C'] for r in mechanical]), timing_trials=len(timings),
            timing_mean_seconds=mean(timings), trial_range_seconds=[min(timings),max(timings)],
            group_mean_range_seconds=[min(group_means),max(group_means)]),
        speaker=dict(subjects=5, genuine=len(genuine), impostor=len(impostor), false_rejects=fr,
            false_accepts=fa, false_reject_rate=fr/len(genuine), false_accept_rate=fa/len(impostor),
            observed_decision_accuracy=(len(speaker)-fr-fa)/len(speaker),
            thresholds={r['B']:r['F'] for r in speaker}),
        longrun=dict(duration_minutes=max(r['C'] for r in longrun), sample_records=len(longrun),
            temperature_start_c=longrun[0]['N'], temperature_end_c=longrun[-1]['N'],
            temperature_max_c=max(r['N'] for r in longrun),
            observations=[dict(minute=r['C'],note=r['O']) for r in longrun if r['O'] != '无']),
        joint=dict(rounds=len({r['A'] for r in joint}), events=len(joint)))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'measurement-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name, rows in (('angle',angle),('mechanical',mechanical),('speaker',speaker),('longrun',longrun),('joint',joint)):
        # Column letters map exactly to the original sheet's row-2 headings.
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (args.output/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
