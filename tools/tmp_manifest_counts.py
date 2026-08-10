import json, re
from pathlib import Path

def safe(x):
    return (x or '').strip() if isinstance(x,str) else ('' if x is None else str(x).strip())

def split_tokens(v):
    t=safe(v)
    return [p.strip() for p in re.split(r'[;,|\n]+', t) if p and p.strip()] if t else []

def parse_insert_values(sql_text, table):
    m=re.search(rf"INSERT\s+INTO\s+dbo\.{table}\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\nGO|\nPRINT|\nSELECT|$)", sql_text, flags=re.I|re.S)
    if not m:
        return []
    cols=[c.strip().strip('[]') for c in m.group(1).split(',')]
    vals=m.group(2)
    tuples=[];cur='';depth=0;ins=False;i=0
    while i<len(vals):
        ch=vals[i]
        if ch=="'":
            if i+1<len(vals) and vals[i+1]=="'":
                cur+="''";i+=2;continue
            ins=not ins;cur+=ch;i+=1;continue
        if not ins and ch=='(': depth+=1
        if depth>0: cur+=ch
        if not ins and ch==')':
            depth-=1
            if depth==0 and cur.strip():
                tuples.append(cur.strip());cur=''
        i+=1
    rows=[]
    for tup in tuples:
        inner=tup[1:-1]
        parts=[];tok='';ins=False;j=0
        while j<len(inner):
            ch=inner[j]
            if ch=="'":
                if j+1<len(inner) and inner[j+1]=="'":
                    tok+="''";j+=2;continue
                ins=not ins;tok+=ch;j+=1;continue
            if ch==',' and not ins:
                parts.append(tok.strip());tok='';j+=1;continue
            tok+=ch;j+=1
        if tok.strip() or inner.endswith(','):
            parts.append(tok.strip())
        if len(parts)!=len(cols):
            continue
        rec={}
        for c,v in zip(cols,parts):
            if v.upper()=='NULL': rec[c]=''
            elif v.startswith("'") and v.endswith("'"): rec[c]=v[1:-1].replace("''","'")
            else: rec[c]=v
        rows.append(rec)
    return rows

meta=Path('sql/07_seed_purview_metadata.sql').read_text(encoding='utf-8')
labels=parse_insert_values(meta,'governance_label_assignments')
glossary=parse_insert_values(meta,'governance_glossary_terms')
cdes=parse_insert_values(meta,'governance_cdes')

label_manifest=[]
for r in labels:
    for a in split_tokens(r.get('applies_to_asset_ids','')):
        label_manifest.append((safe(a).lower(), safe(r.get('label_name')).lower()))

glossary_manifest=[]
code_to_name={safe(r.get('term_code')).upper():safe(r.get('term_name')) for r in glossary if safe(r.get('term_code')) and safe(r.get('term_name'))}
for r in glossary:
    for a in split_tokens(r.get('bound_assets','')):
        glossary_manifest.append((safe(a).lower(), safe(r.get('term_name')).lower()))
for r in cdes:
    parent=safe(r.get('parent_glossary_term'))
    term=code_to_name.get(parent.upper(), parent) if parent else safe(r.get('cde_name'))
    for a in split_tokens(r.get('bound_columns','')):
        if term:
            glossary_manifest.append((safe(a).lower(), safe(term).lower()))

description_manifest=[]
for r in cdes:
    d=safe(r.get('business_definition'))
    for a in split_tokens(r.get('bound_columns','')):
        if d:
            description_manifest.append((safe(a).lower(), d[:120].lower()))
for r in glossary:
    d=safe(r.get('definition'))
    for a in split_tokens(r.get('bound_assets','')):
        if d:
            description_manifest.append((safe(a).lower(), d[:120].lower()))

print(json.dumps({
    'label_manifest_rows': len(dict.fromkeys(label_manifest)),
    'glossary_manifest_rows': len(dict.fromkeys(glossary_manifest)),
    'description_manifest_rows': len(dict.fromkeys(description_manifest))
}, indent=2))
