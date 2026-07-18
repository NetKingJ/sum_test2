#!/usr/bin/env python3
from __future__ import annotations
import io,json,urllib.parse
from pathlib import Path
import cv2,numpy as np,requests
from PIL import Image
ROOT=Path(__file__).resolve().parent
Q=ROOT/'whereami-original.jpg'
UA={'User-Agent':'Mozilla/5.0','Referer':'https://artsandculture.google.com/asset/rashaan-khad-monument-complex/PwHfeS1womJbxw?hl=en'}
urls=[
'https://tourmongolia.com/file/2018/03/Rashaan-khad-ancestors-wall-Tour-Mongolia-4.jpg',
'https://tourmongolia.com/file/2018/03/Rashaan-khad-ancestors-wall-Tour-Mongolia-2.jpg',
'https://lh3.googleusercontent.com/ci/AL18g_SE0QFha9ZyjgfJyB5VHpB-5E8dz-8pX0pOMhWLAk2yIhUh543oXQMrh9NUL1whyCpDeLr_umY']
q=cv2.imread(str(Q),cv2.IMREAD_GRAYSCALE)
sift=cv2.SIFT_create(nfeatures=5000,contrastThreshold=.015)
qkp,qdes=sift.detectAndCompute(q,None)
def comp(data):
 im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_GRAYSCALE)
 if im is None:return {'decode':False}
 kp,des=sift.detectAndCompute(im,None);good=[];inl=0
 if des is not None:
  for p in cv2.BFMatcher().knnMatch(qdes,des,k=2):
   if len(p)==2 and p[0].distance<.72*p[1].distance:good.append(p[0])
  if len(good)>=4:
   a=np.float32([qkp[m.queryIdx].pt for m in good]).reshape(-1,1,2);b=np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1,1,2)
   H,mask=cv2.findHomography(a,b,cv2.RANSAC,5)
   if mask is not None:inl=int(mask.sum())
 return {'decode':True,'width':im.shape[1],'height':im.shape[0],'sift_good':len(good),'inliers':inl}
out=[]
s=requests.Session()
for idx,u in enumerate(urls):
 ent={'url':u,'direct':{},'archives':[]}
 try:
  r=s.get(u,headers=UA,timeout=90)
  c=comp(r.content)
  ent['direct']={'status':r.status_code,'length':len(r.content),'final_url':r.url,'content_type':r.headers.get('content-type'),**c}
  if c.get('decode'):
   (ROOT/f'rashaan-direct-{idx}.jpg').write_bytes(r.content)
 except Exception as e:ent['direct']={'error':repr(e)}
 if 'tourmongolia.com/file/' in u:
  cdx='https://web.archive.org/cdx/search/cdx?'+urllib.parse.urlencode({'url':u,'output':'json','filter':'statuscode:200','fl':'timestamp,original,statuscode,mimetype','collapse':'digest','limit':'20'})
  try:
   cr=s.get(cdx,timeout=90);ent['cdx_status']=cr.status_code;ent['cdx_preview']=cr.text[:2000]
   arr=cr.json()
   for j,row in enumerate(arr[1:8]):
    ts,orig=row[0],row[1];au=f'https://web.archive.org/web/{ts}id_/{orig}'
    try:
     ar=s.get(au,headers={'User-Agent':'Mozilla/5.0'},timeout=120)
     ae={'timestamp':ts,'archive_url':au,'status':ar.status_code,'length':len(ar.content),'final_url':ar.url,'content_type':ar.headers.get('content-type'),**comp(ar.content)}
     ent['archives'].append(ae)
     if ae.get('decode'):(ROOT/f'rashaan-archive-{idx}-{j}.jpg').write_bytes(ar.content)
    except Exception as e:ent['archives'].append({'timestamp':ts,'error':repr(e)})
  except Exception as e:ent['cdx_error']=repr(e)
 out.append(ent)
(ROOT/'rashaan-image-check.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(out,indent=2,ensure_ascii=False))
