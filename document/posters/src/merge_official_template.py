"""Preserve official PPTX furniture; add editable artifact-tool authored content.

No sample-project photos, labels or results are retained. No raster flattening.
"""
from copy import deepcopy
from pathlib import Path
import posixpath
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E

NS = {'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
def xml(b): return E.fromstring(b)
def serial(r): return E.tostring(r, xml_declaration=True, encoding='UTF-8', standalone=True)
def read(p):
    with ZipFile(p) as z: return {n:z.read(n) for n in z.namelist()}

def merge(template, donor, output, language='zh'):
    base, new = read(template), read(donor)
    root = xml(base['ppt/slides/slide1.xml'])
    tree = root.find('p:cSld/p:spTree', NS)
    # Preserve exact geometry, color, line styling and layering of template furniture.
    keep = {'8','10','12','13','14','32','39','45','46'}
    for node in list(tree):
        if node.tag.rsplit('}',1)[-1] in ('nvGrpSpPr','grpSpPr'):continue
        nv = node.find('.//p:cNvPr', NS)
        if nv is None: continue
        if nv.get('id') not in keep:
            tree.remove(node)
        else:
            tx = node.find('p:txBody', NS)
            if tx is not None:
                for child in list(tx): tx.remove(child)
                E.SubElement(tx, '{'+NS['a']+'}bodyPr')
                E.SubElement(tx, '{'+NS['a']+'}lstStyle')
                E.SubElement(tx, '{'+NS['a']+'}p')
            # Keep the reference rectangle, but remove its empty title placeholder semantics.
            for ph in node.findall('.//p:ph', NS): ph.getparent().remove(ph)
            sp=node.find('p:spPr',NS)
            if nv.get('id')=='8' and sp.find('a:prstGeom',NS) is None:
                geom=E.Element('{'+NS['a']+'}prstGeom',prst='rect')
                E.SubElement(geom,'{'+NS['a']+'}avLst');sp.insert(1,geom)
            if nv.get('id') in ('45','46'):
                fill=E.SubElement(sp,'{'+NS['a']+'}solidFill')
                E.SubElement(fill,'{'+NS['a']+'}srgbClr',val='FFFFFF')
                ln=E.SubElement(sp,'{'+NS['a']+'}ln',w='12700')
                f=E.SubElement(ln,'{'+NS['a']+'}solidFill')
                E.SubElement(f,'{'+NS['a']+'}srgbClr',val='000000')
    relpath = 'ppt/slides/_rels/slide1.xml.rels'
    rels = xml(base[relpath])
    for r in list(rels):
        if r.get('Type').endswith('/image') and r.get('Id') != 'rId4':
            rels.remove(r)
    newrels = xml(new[relpath])
    mapping = {}
    # Donor charts/notes live in a private namespace, so no source-layout/theme collision occurs.
    partmap = {}
    def copy_part(name):
        if name in partmap: return partmap[name]
        target = 'ppt/soundsight/' + name.removeprefix('ppt/')
        partmap[name] = target
        data = new[name]
        base[target] = data
        directory, filename = posixpath.split(name)
        relname = directory + '/_rels/' + filename + '.rels'
        if relname in new:
            rr = xml(new[relname])
            for rel in rr:
                if rel.get('TargetMode') == 'External': continue
                resolved = posixpath.normpath(posixpath.join(directory, rel.get('Target'))).lstrip('/')
                if rel.get('Type').endswith('/slide'):
                    resolved_target = 'ppt/slides/slide1.xml'
                else:
                    resolved_target = copy_part(resolved)
                rel.set('Target', posixpath.relpath(resolved_target, posixpath.dirname(target)))
            target_rel = posixpath.dirname(target)+'/_rels/'+filename+'.rels'
            base[target_rel] = serial(rr)
        return target
    for i,r in enumerate(newrels,100):
        typ = r.get('Type')
        if not (typ.endswith('/chart') or typ.endswith('/notesSlide')): continue
        rid='rId'+str(i);mapping[r.get('Id')]=rid
        n=deepcopy(r);n.set('Id',rid)
        resolved=posixpath.normpath(posixpath.join('ppt/slides',r.get('Target'))).lstrip('/')
        n.set('Target',posixpath.relpath(copy_part(resolved),'ppt/slides'))
        rels.append(n)
    donor_tree=xml(new['ppt/slides/slide1.xml']).find('p:cSld/p:spTree',NS)
    for i,node in enumerate(donor_tree,1000):
        if node.tag.rsplit('}',1)[-1] in ('nvGrpSpPr','grpSpPr'): continue
        node=deepcopy(node)
        for nv in node.findall('.//p:cNvPr',NS): nv.set('id',str(i))
        for el in node.iter():
            for attr,value in list(el.attrib.items()):
                if attr.startswith('{'+NS['r']+'}') and value in mapping: el.set(attr,mapping[value])
        tree.append(node)
    base['ppt/slides/slide1.xml']=serial(root)
    base[relpath]=serial(rels)
    # Corporate template automation/SharePoint form metadata is not part of the poster.
    presentation_rels='ppt/_rels/presentation.xml.rels'
    pr=xml(base[presentation_rels])
    for r in list(pr):
        if r.get('Type').endswith('/customXml'):pr.remove(r)
    base[presentation_rels]=serial(pr)
    for n in list(base):
        if n.startswith('customXml/'):base.pop(n)
    master='ppt/slideMasters/slideMaster1.xml'
    m=xml(base[master])
    for node in m.findall('.//p:sp',NS):
        if any('Copyright' in (t.text or '') for t in node.findall('.//a:t',NS)):
            for t in node.findall('.//a:t',NS): t.text='INTERNAL DRAFT · 2026' if language=='en' else '内部预写稿 · 2026'
            # Preserve the source top-left green note; widen it for Chinese.
            node.find('p:spPr/a:xfrm/a:ext',NS).set('cx',str(180*9525))
            for rp in node.findall('.//a:rPr',NS):
                for fam in ('latin','ea','cs'):
                    e=rp.find('a:'+fam,NS)
                    if e is None:e=E.SubElement(rp,'{'+NS['a']+'}'+fam)
                    e.set('typeface','Calibri' if language=='en' else 'Microsoft YaHei')
    base[master]=serial(m)
    # Drop removed sample illustrations from the package as well as the visible slide.
    for name in ['image3.png','image4.png','image5.emf','image6.emf']:
        base.pop('ppt/media/'+name,None)
    types=xml(base['[Content_Types].xml']); ntypes=xml(new['[Content_Types].xml'])
    for n in list(types):
        if n.tag.endswith('Override') and n.get('PartName').lstrip('/') not in base:types.remove(n)
    existing_default={n.get('Extension') for n in types if n.tag.endswith('Default')}
    for n in ntypes:
        if n.tag.endswith('Override') and n.get('PartName').lstrip('/') in partmap:
            nn=deepcopy(n);nn.set('PartName','/'+partmap[n.get('PartName').lstrip('/')]);types.append(nn)
        elif n.tag.endswith('Default') and n.get('Extension') not in existing_default:
            types.append(deepcopy(n));existing_default.add(n.get('Extension'))
    base['[Content_Types].xml']=serial(types)
    # Source preview and document metadata must not retain sample-project identities.
    base.pop('docProps/thumbnail.jpeg',None)
    for n in ('docProps/core.xml','docProps/app.xml'):
        if n in base:
            rr=xml(base[n])
            for e in rr.iter():
                if e.tag.rsplit('}',1)[-1] in ('creator','lastModifiedBy','Company','Manager','title','subject'):
                    e.text='SoundSight' if e.tag.rsplit('}',1)[-1]=='title' else ''
            base[n]=serial(rr)
    # Remove the optional thumbnail relationship if the package has one.
    rr=xml(base['_rels/.rels'])
    for r in list(rr):
        if r.get('Type').endswith('/thumbnail'):
            base.pop(r.get('Target'),None);rr.remove(r)
    base['_rels/.rels']=serial(rr)
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        for n,b in base.items():z.writestr(n,b)
    print('Preserved official template furniture; added editable SoundSight content.')

if __name__=='__main__': merge(*map(Path,sys.argv[1:4]),language=sys.argv[4] if len(sys.argv)>4 else 'zh')
