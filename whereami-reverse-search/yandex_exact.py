#!/usr/bin/env python3
import html,json,re,urllib.parse
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent
IMAGE=ROOT/'whereami-original.jpg'
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'en-US,en;q=0.9'})
params={'rpt':'imageview','format':'json','request':'{"blocks":[{"block":"b-page_type_search-by-image__link"}]}' }
with IMAGE.open('rb') as f:
    up=s.post('https://yandex.com/images/search',params=params,files={'upfile':('blob',f,'image/jpeg')},headers={'Referer':'https://yandex.com/images/'},timeout=90)
obj=up.json(); p=obj['blocks'][0]['params']; cbir=p['cbirId']; orig=p['originalImageUrl']
urls=[
 'https://yandex.com/images/search?'+urllib.parse.urlencode({'rpt':'imageview','cbir_id':cbir}),
 'https://yandex.com/images/search?'+urllib.parse.urlencode({'rpt':'imageview','url':orig}),
 'https://yandex.com/images/search?'+urllib.parse.urlencode({'rpt':'imageview','cbir_id':cbir,'cbir_page':'similar'}),
]
out={'cbirId':cbir,'originalImageUrl':orig,'requests':[]}
for u in urls:
    r=s.get(u,headers={'Referer':'https://yandex.com/images/'},timeout=90)
    text=html.unescape(r.text).replace('\\/','/').replace('\\u0026','&').replace('\\u003d','=')
    found=[]
    for pat in [r'https?://[^"\'<>\\\s]+',r'"url"\s*:\s*"([^"]+)"',r'"origin"\s*:\s*\{[^}]*"url"\s*:\s*"([^"]+)"']:
        for x in re.findall(pat,text):
            x=urllib.parse.unquote(x).rstrip('),.;]')
            if x.startswith('http') and not any(h in x.lower() for h in ['yandex.','yastatic.','ya.ru']) and x not in found: found.append(x)
    hits=[k for k in ['Mongol','Kazakh','Kyrgyz','Turkmen','Uzbek','tamga','petroglyph','Rashaan','Tamgaly','Khuduu','Shambhala','seal','monument'] if k.lower() in text.lower()]
    out['requests'].append({'url':u,'status':r.status_code,'length':len(r.content),'found':found[:500],'hits':hits,'head':text[:2000]})
    (ROOT/f'yandex-result-{len(out["requests"])}.html').write_text(r.text,encoding='utf-8',errors='replace')
(ROOT/'yandex-exact-results.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(out,indent=2,ensure_ascii=False))
