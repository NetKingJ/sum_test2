#!/usr/bin/env python3
from __future__ import annotations
import json, re, urllib.parse
from collections import Counter
from pathlib import Path

root=Path(__file__).resolve().parent
src=json.loads((root/'other-engine-summary.json').read_text(encoding='utf-8'))
keys=['mongol','kazakh','kyrgyz','uzbek','tajik','turkmen','central asia','tamga','tamgha','tamgaly','tanbaly','petroglyph','archaeolog','clan','tribe','rashaan','rashan','khentii','kherlen','shambhala','khamar','stone','rock','monument','museum','heritage','almaty','astana','bishkek','ulaanbaatar','ulan bator','turkic','nomad']
out={}
for name,res in src.get('results',{}).items():
    links=res.get('links',[]) if isinstance(res,dict) else []
    visible=res.get('visible_text',[]) if isinstance(res,dict) else []
    hosts=Counter()
    interesting=[]
    for item in links:
        url=item.get('url','')
        text=item.get('text','')
        host=urllib.parse.urlparse(url).netloc.lower()
        hosts[host]+=1
        blob=(url+' '+text).lower()
        if any(k in blob for k in keys) or host.endswith(('.mn','.kz','.kg','.uz','.tj','.tm','.ru')):
            interesting.append(item)
    interesting_text=[x for x in visible if any(k in x.lower() for k in keys)]
    out[name]={
        'title':res.get('title','') if isinstance(res,dict) else '',
        'url':res.get('url','') if isinstance(res,dict) else '',
        'length':res.get('length',0) if isinstance(res,dict) else 0,
        'link_count':len(links),
        'top_hosts':hosts.most_common(50),
        'interesting_links':interesting[:300],
        'interesting_visible_text':interesting_text[:300],
        'visible_text_head':visible[:250],
    }
(root/'compact-engine-summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print((root/'compact-engine-summary.json').read_text(encoding='utf-8'))
