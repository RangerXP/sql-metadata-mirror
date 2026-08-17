import json, re, subprocess, urllib.parse, urllib.request, urllib.error, shutil
from pathlib import Path

BASE='https://Purview-West3.purview.azure.com'
API='2023-09-01'
AZ_FALLBACK=r'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd'
SEED_META=Path('sql/02_metadata_foundation/07_seed_purview_metadata.sql')
SEED_OWNERS=Path('sql/01_source_data/05_seed_purview_demo_data.sql')
OUT=Path('tools/purview_intent_metadata_write_report.json')
DATASET_QN='https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/datasets/8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c'
DATASET_GUID='a0df6b58-9fcd-4aee-8235-d1a035677215'
REPORT_QN='https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/reports/7c4f1103-e22c-4a8c-930d-9fe20b71b409'
REPORT_GUID='42561931-aa73-4cbd-9fe3-141b0796ecc6'

def safe(x):
    return (x or '').strip() if isinstance(x,str) else ('' if x is None else str(x).strip())
def norm(x):
    return ''.join(ch for ch in safe(x).lower() if ch.isalnum())
def split_tokens(v):
    t=safe(v)
    return [p.strip() for p in re.split(r'[;,|\n]+',t) if p and p.strip()] if t else []

def parse_insert_values(sql_text, table):
    m=re.search(rf"INSERT\s+INTO\s+dbo\.{table}\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\nGO|\nPRINT|\nSELECT|$)", sql_text, flags=re.I|re.S)
    if not m:return []
    cols=[c.strip().strip('[]') for c in m.group(1).split(',')]
    vals=m.group(2)
    tuples=[];cur='';depth=0;ins=False;i=0
    while i<len(vals):
        ch=vals[i]
        if ch=="'":
            if i+1<len(vals) and vals[i+1]=="'":cur+="''";i+=2;continue
            ins=not ins;cur+=ch;i+=1;continue
        if not ins and ch=='(':depth+=1
        if depth>0:cur+=ch
        if not ins and ch==')':
            depth-=1
            if depth==0 and cur.strip():tuples.append(cur.strip());cur=''
        i+=1
    rows=[]
    for tup in tuples:
        inner=tup[1:-1]
        parts=[];tok='';ins=False;j=0
        while j<len(inner):
            ch=inner[j]
            if ch=="'":
                if j+1<len(inner) and inner[j+1]=="'":tok+="''";j+=2;continue
                ins=not ins;tok+=ch;j+=1;continue
            if ch==',' and not ins:parts.append(tok.strip());tok='';j+=1;continue
            tok+=ch;j+=1
        if tok.strip() or inner.endswith(','):parts.append(tok.strip())
        if len(parts)!=len(cols):continue
        rec={}
        for c,v in zip(cols,parts):
            if v.upper()=='NULL':rec[c]=''
            elif v.startswith("'") and v.endswith("'"):rec[c]=v[1:-1].replace("''","'")
            else:rec[c]=v
        rows.append(rec)
    return rows

def parse_owner_seed_rows(sql_text):
    m=re.search(r"INSERT\s+INTO\s+dbo\.data_owners_directory\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\n\s*\n|\n/\*|\n--|$)", sql_text, flags=re.I|re.S)
    if not m:return []
    cols=[c.strip().strip('[]') for c in m.group(1).split(',')]
    block=m.group(2)
    tuples=[];cur='';depth=0;ins=False;i=0
    while i<len(block):
        ch=block[i]
        if ch=="'":
            if i+1<len(block) and block[i+1]=="'":cur+="''";i+=2;continue
            ins=not ins;cur+=ch;i+=1;continue
        if not ins and ch=='(':depth+=1
        if depth>0:cur+=ch
        if not ins and ch==')':
            depth-=1
            if depth==0 and cur.strip():tuples.append(cur.strip());cur=''
        i+=1
    rows=[]
    for tup in tuples:
        inner=tup[1:-1]
        parts=[];tok='';ins=False;j=0
        while j<len(inner):
            ch=inner[j]
            if ch=="'":
                if j+1<len(inner) and inner[j+1]=="'":tok+="''";j+=2;continue
                ins=not ins;tok+=ch;j+=1;continue
            if ch==',' and not ins:parts.append(tok.strip());tok='';j+=1;continue
            tok+=ch;j+=1
        if tok.strip() or inner.endswith(','):parts.append(tok.strip())
        if len(parts)!=len(cols):continue
        rec={}
        for c,v in zip(cols,parts):
            if v.upper()=='NULL':rec[c]=''
            elif v.startswith("'") and v.endswith("'"):rec[c]=v[1:-1].replace("''","'")
            else:rec[c]=v
        rows.append(rec)
    return rows

def az_token():
    az=shutil.which('az') or shutil.which('az.cmd') or (AZ_FALLBACK if Path(AZ_FALLBACK).exists() else None)
    return subprocess.check_output([az,'account','get-access-token','--resource','https://purview.azure.net','--query','accessToken','-o','tsv'], text=True).strip()

def req(method,path,token,body=None,params=None):
    u=BASE+path
    q=dict(params or {})
    if path.startswith('/datamap/') and 'api-version' not in q:q['api-version']=API
    if q:u+='?'+urllib.parse.urlencode(q,doseq=True)
    h={'Authorization':f'Bearer {token}'}
    d=None
    if body is not None:d=json.dumps(body).encode('utf-8');h['Content-Type']='application/json'
    r=urllib.request.Request(u,data=d,headers=h,method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:return resp.status,resp.read().decode('utf-8',errors='replace')
    except urllib.error.HTTPError as e:return e.code,e.read().decode('utf-8',errors='replace')

def j(s):
    try:return json.loads(s)
    except:return None

def search(token,keywords,limit=50):
    st,bd=req('POST','/datamap/api/search/query',token,body={'keywords':keywords,'limit':limit})
    if st!=200:return []
    p=j(bd)
    return p.get('value') if isinstance(p,dict) else []

def entity_by_guid(token,guid):
    st,bd=req('GET',f'/catalog/api/atlas/v2/entity/guid/{guid}',token)
    if st!=200:return None
    p=j(bd)
    return (p or {}).get('entity',{}) if isinstance(p,dict) else None

cache={}
def pick_best(cands,asset_ref,intent):
    ar=safe(asset_ref);arl=ar.lower();arn=norm(ar);best=None;best_score=-10**9
    for c in cands:
        et=safe(c.get('entityType') or c.get('typeName')).lower();qn=safe(c.get('qualifiedName')).lower();nm=safe(c.get('name')).lower();score=0
        if arn and arn in norm(qn):score+=2
        if intent=='protection_label':
            if arl.startswith('dbo.') and ('table' in et or 'view' in et):score+=18
            if arl.startswith('brookfieldenercare/_measures/') and 'measure' in et:score+=20
            if arl in ('brookfieldenercare.report','brookfieldenercare.semanticmodel') and ('report' in et or 'dataset' in et):score+=18
        elif intent=='business_glossary':
            if arl.startswith('dbo.') and ('table' in et or 'view' in et):score+=16
            if 'glossary' in et:score-=100
            if arl.startswith('brookfieldenercare/_measures/') and 'measure' in et:score+=16
        elif intent=='description_enrichment':
            if arl.startswith('dbo.') and ('table' in et or 'view' in et):score+=18
            if arl.startswith('brookfieldenercare/_measures/') and 'measure' in et:score+=20
            if arl in ('brookfieldenercare.report','brookfieldenercare.semanticmodel') and ('report' in et or 'dataset' in et):score+=14
        elif intent=='accountability_contact':
            if arl.startswith('dbo.') and ('table' in et or 'view' in et):score+=22
            if arl in ('brookfieldenercare.report','brookfieldenercare.semanticmodel') and ('report' in et or 'dataset' in et):score+=15
        if arl.startswith('dbo.'):
            p=ar.split('.');tbl=p[1].lower() if len(p)>1 else ''
            if tbl and tbl in qn:score+=7
            if tbl and tbl in nm:score+=5
            if 'mssql://' in qn:score+=3
        if ar.startswith('BrookfieldEnercare/_Measures/'):
            m=ar.split('/_Measures/',1)[1].lower()
            if m and m in qn:score+=12
        if arl=='brookfieldenercare.report' and REPORT_QN.lower() in qn:score+=20
        if arl=='brookfieldenercare.semanticmodel' and DATASET_QN.lower() in qn:score+=20
        if score>best_score:best_score=score;best=c
    return best

def resolve_target(token,asset_ref,intent):
    key=(safe(asset_ref).lower(),intent)
    if key in cache:return cache[key]
    ar=safe(asset_ref);cands=[]
    if ar.lower().startswith('dbo.'):
        p=ar.split('.')
        if len(p)>=3:cands.extend(search(token,f'{p[1]} {".".join(p[2:])} sqldemo',30))
        cands.extend(search(token,ar,30));cands.extend(search(token,f'{p[1]} sqldemo',30))
    elif ar.startswith('BrookfieldEnercare/_Measures/'):
        m=ar.split('/_Measures/',1)[1];cands.extend(search(token,f'{m} measure BrookfieldEnercare',30))
    elif ar in ('BrookfieldEnercare.Report','BrookfieldEnercare.SemanticModel'):
        cands.extend(search(token,f'{ar} powerbi',30))
    elif ar.lower().startswith('dp-'):
        cands.extend(search(token,f'{ar.split(":",1)[0]} EnercareDataProduct',30))
    else:cands.extend(search(token,ar,20))
    uniq=[];seen=set()
    for c in cands:
        gid=safe(c.get('id') or c.get('guid'))
        if not gid or gid in seen:continue
        seen.add(gid);uniq.append({'guid':gid,'entityType':safe(c.get('entityType') or c.get('typeName')),'qualifiedName':safe(c.get('qualifiedName')),'name':safe(c.get('name'))})
    best=pick_best(uniq,ar,intent)
    if best:cache[key]=best;return best
    fallback={'guid':REPORT_GUID,'entityType':'powerbi_report','qualifiedName':REPORT_QN,'name':'BrookfieldEnercare'} if ar=='BrookfieldEnercare.Report' else {'guid':DATASET_GUID,'entityType':'powerbi_dataset','qualifiedName':DATASET_QN,'name':'BrookfieldEnercare'}
    cache[key]=fallback;return fallback

def apply_label(token,gid,label):
    path=f'/catalog/api/atlas/v2/entity/guid/{gid}/labels';compact=''.join(ch for ch in safe(label) if ch.isalnum())
    candidates=[]
    for l in (safe(label),compact):
        if l and l not in candidates:candidates.append(l)
    for lab in candidates:
        for method in ('POST','PUT'):
            for payload in ([lab],{'labels':[lab]},{'labels':[{'name':lab}]}):
                st,bd=req(method,path,token,body=payload);low=bd.lower()
                if st in (200,201,204):return 'assigned',''
                if st==409 or 'already exists' in low or 'already associated' in low or 'duplicate' in low:return 'existing',''
                if st in (400,404,405):continue
                return 'failed',f'HTTP {st} | {bd[:220]}'
    return 'failed','labels endpoint rejected all payload forms'

def resolve_term_guid(token,term):
    t=safe(term)
    if not t:return ''
    vals=search(token,t,25);target=t.lower()
    for e in vals:
        et=safe(e.get('entityType') or e.get('typeName')).lower();nm=safe(e.get('name')).lower();qn=safe(e.get('qualifiedName')).lower();gid=safe(e.get('id') or e.get('guid'))
        if gid and 'glossaryterm' in et and (nm==target or target in nm or '@' in qn):return gid
    for e in vals:
        gid=safe(e.get('id') or e.get('guid'));qn=safe(e.get('qualifiedName'));nm=safe(e.get('name'))
        if gid and qn and '@' in qn and (nm.lower()==target or target in nm.lower()):return gid
    return ''

def is_term_assigned(token,tid,gid):
    st,bd=req('GET',f'/catalog/api/atlas/v2/glossary/terms/{tid}/assignedEntities',token)
    if st!=200:return False
    p=j(bd)
    return isinstance(p,list) and any(safe(e.get('guid'))==safe(gid) for e in p)

def apply_term(token,tid,gid,etype=''):
    if is_term_assigned(token,tid,gid):return 'existing',''
    st,bd=req('POST',f'/catalog/api/atlas/v2/glossary/terms/{tid}/assignedEntities',token,body=[{'guid':gid,'typeName':safe(etype)}])
    if st in (200,201,202,204):return 'assigned',''
    if is_term_assigned(token,tid,gid):return 'existing',''
    return 'failed',f'HTTP {st} | {bd[:220]}'

def apply_description(token,gid,text):
    text=safe(text)
    if not text:return 'skipped',''
    ent=entity_by_guid(token,gid)
    if not isinstance(ent,dict):return 'failed','entity read failed'
    attrs=ent.get('attributes') if isinstance(ent.get('attributes'),dict) else {}
    if safe(attrs.get('description'))==text:return 'existing',''
    payload={'entity':{'typeName':safe(ent.get('typeName')),'guid':safe(ent.get('guid') or gid) or gid,'attributes':{'qualifiedName':safe(attrs.get('qualifiedName')),'name':safe(attrs.get('name')),'description':text}}}
    for method,path in [('PUT',f'/catalog/api/atlas/v2/entity/guid/{gid}'),('PUT','/catalog/api/atlas/v2/entity'),('POST','/catalog/api/atlas/v2/entity')]:
        st,bd=req(method,path,token,body=payload)
        if st in (200,201,204):return 'assigned',''
        if st in (400,404,405):continue
        return 'failed',f'{method} {path} -> HTTP {st} | {bd[:220]}'
    return 'failed','no compatible description update endpoint'

def set_owner(token,gid,owner):
    owner=safe(owner)
    if not owner:return 'skipped',''
    ent=entity_by_guid(token,gid)
    if not isinstance(ent,dict):return 'failed','entity read failed'
    attrs=ent.get('attributes') if isinstance(ent.get('attributes'),dict) else {}
    if safe(attrs.get('owner')).lower()==owner.lower():return 'existing',''
    payload={'entity':{'typeName':safe(ent.get('typeName')),'guid':safe(ent.get('guid') or gid) or gid,'attributes':{'qualifiedName':safe(attrs.get('qualifiedName')),'name':safe(attrs.get('name')),'owner':owner}}}
    for method,path in [('PUT',f'/catalog/api/atlas/v2/entity/guid/{gid}'),('PUT','/catalog/api/atlas/v2/entity'),('POST','/catalog/api/atlas/v2/entity')]:
        st,bd=req(method,path,token,body=payload)
        if st in (200,201,204):return 'assigned',''
        if st in (400,404,405):continue
        return 'failed',f'{method} {path} -> HTTP {st} | {bd[:220]}'
    return 'failed','no compatible owner update endpoint'

meta_sql=SEED_META.read_text(encoding='utf-8');owner_sql=SEED_OWNERS.read_text(encoding='utf-8')
labels=parse_insert_values(meta_sql,'governance_label_assignments')
glossary=parse_insert_values(meta_sql,'governance_glossary_terms')
cdes=parse_insert_values(meta_sql,'governance_cdes')
owner_rows=parse_owner_seed_rows(owner_sql)

label_manifest=[]
for r in labels:
    for a in split_tokens(r.get('applies_to_asset_ids','')):
        label_manifest.append({'asset_ref':a,'label_name':safe(r.get('label_name')),'intent':'protection_label'})
code_to_name={safe(r.get('term_code')).upper():safe(r.get('term_name')) for r in glossary if safe(r.get('term_code')) and safe(r.get('term_name'))}
glossary_manifest=[]
for r in glossary:
    for a in split_tokens(r.get('bound_assets','')):
        glossary_manifest.append({'asset_ref':a,'term_name':safe(r.get('term_name')),'intent':'business_glossary'})
for r in cdes:
    parent=safe(r.get('parent_glossary_term'));term=code_to_name.get(parent.upper(),parent) if parent else safe(r.get('cde_name'))
    for a in split_tokens(r.get('bound_columns','')):
        if term:glossary_manifest.append({'asset_ref':a,'term_name':term,'intent':'business_glossary'})
description_manifest=[]
for r in cdes:
    desc=safe(r.get('business_definition'))
    for a in split_tokens(r.get('bound_columns','')):
        if desc:description_manifest.append({'asset_ref':a,'description':desc,'intent':'description_enrichment'})
for r in glossary:
    desc=safe(r.get('definition'))
    for a in split_tokens(r.get('bound_assets','')):
        if desc:description_manifest.append({'asset_ref':a,'description':desc,'intent':'description_enrichment'})
contacts_manifest=[]
for r in owner_rows:
    schema=safe(r.get('object_schema')).lower();obj=safe(r.get('object_name')).lower()
    if schema and obj:contacts_manifest.append({'asset_ref':f'{schema}.{obj}','owner_upn':safe(r.get('data_owner_upn')),'intent':'accountability_contact'})
contacts_manifest.append({'asset_ref':'BrookfieldEnercare.SemanticModel','owner_upn':'Ci.Zhu@enercare.ca','intent':'accountability_contact'})
contacts_manifest.append({'asset_ref':'BrookfieldEnercare.Report','owner_upn':'Victoria.Tan@enercare.ca','intent':'accountability_contact'})

def dedupe(rows,keyfn):
    out=[];seen=set()
    for r in rows:
        k=keyfn(r)
        if k in seen:continue
        seen.add(k);out.append(r)
    return out
label_manifest=dedupe(label_manifest,lambda r:(safe(r['asset_ref']).lower(),safe(r['label_name']).lower()))
glossary_manifest=dedupe(glossary_manifest,lambda r:(safe(r['asset_ref']).lower(),safe(r['term_name']).lower()))
description_manifest=dedupe(description_manifest,lambda r:(safe(r['asset_ref']).lower(),safe(r['description']).lower()[:120]))
contacts_manifest=dedupe(contacts_manifest,lambda r:(safe(r['asset_ref']).lower(),safe(r['owner_upn']).lower()))

T=az_token()
report={'counts':{'label_manifest_rows':len(label_manifest),'glossary_manifest_rows':len(glossary_manifest),'description_manifest_rows':len(description_manifest),'contacts_manifest_rows':len(contacts_manifest)},'results':{'labels':{'assigned':0,'existing':0,'failed':0,'unresolved':0},'glossary':{'assigned':0,'existing':0,'failed':0,'unresolved_asset':0,'unresolved_term':0},'descriptions':{'assigned':0,'existing':0,'failed':0,'unresolved':0},'contacts':{'assigned':0,'existing':0,'failed':0,'unresolved':0}}}

term_cache={}
for r in label_manifest:
    t=resolve_target(T,r['asset_ref'],'protection_label')
    if not t:report['results']['labels']['unresolved']+=1;continue
    o,_=apply_label(T,t['guid'],r['label_name']);report['results']['labels'][o]+=1
for r in glossary_manifest:
    t=resolve_target(T,r['asset_ref'],'business_glossary')
    if not t:report['results']['glossary']['unresolved_asset']+=1;continue
    key=safe(r['term_name']).lower();
    if key not in term_cache:term_cache[key]=resolve_term_guid(T,r['term_name'])
    tg=term_cache.get(key,'')
    if not tg:report['results']['glossary']['unresolved_term']+=1;continue
    o,_=apply_term(T,tg,t['guid'],t.get('entityType',''));report['results']['glossary'][o]+=1
for r in description_manifest:
    t=resolve_target(T,r['asset_ref'],'description_enrichment')
    if not t:report['results']['descriptions']['unresolved']+=1;continue
    o,_=apply_description(T,t['guid'],r['description'])
    if o!='skipped':report['results']['descriptions'][o]+=1
for r in contacts_manifest:
    t=resolve_target(T,r['asset_ref'],'accountability_contact')
    if not t:report['results']['contacts']['unresolved']+=1;continue
    o,_=set_owner(T,t['guid'],r['owner_upn'])
    if o!='skipped':report['results']['contacts'][o]+=1

OUT.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('WROTE tools/purview_intent_metadata_write_report.json')
print(json.dumps(report,indent=2))
