#!/usr/bin/env python3
import io,json,math,urllib.parse
from pathlib import Path
import cv2, numpy as np, requests
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
query=cv2.imread(str(ROOT/'whereami-original.jpg'))
qg=cv2.cvtColor(query,cv2.COLOR_BGR2GRAY)
sift=cv2.SIFT_create(nfeatures=5000,contrastThreshold=.015)
qkp,qdes=sift.detectAndCompute(qg,None)
data=json.loads((ROOT/'yandex-exact-results.json').read_text())
urls=[]
for req in data['requests']:
 for u in req.get('found',[]):
  p=urllib.parse.urlparse(u)
  if any(x in p.path.lower() for x in ['.jpg','.jpeg','.png','.webp']) or 'googleusercontent.com' in p.netloc or 'pinimg.com' in p.netloc:
   if u not in urls: urls.append(u)
s=requests.Session();s.headers['User-Agent']='Mozilla/5.0 Chrome/124 Safari/537.36'
rows=[]
for rank,u in enumerate(urls[:180]):
 try:
  r=s.get(u,timeout=20); b=r.content
  if r.status_code!=200 or len(b)<1000 or len(b)>15000000: continue
  im=cv2.imdecode(np.frombuffer(b,np.uint8),cv2.IMREAD_COLOR)
  if im is None or min(im.shape[:2])<80: continue
  scale=min(1,1800/max(im.shape[:2])); test=cv2.resize(im,None,fx=scale,fy=scale) if scale<1 else im
  g=cv2.cvtColor(test,cv2.COLOR_BGR2GRAY); kp,des=sift.detectAndCompute(g,None)
  good=[];inl=0
  if des is not None and len(des)>1:
   for pair in cv2.BFMatcher().knnMatch(qdes,des,k=2):
    if len(pair)==2 and pair[0].distance<.72*pair[1].distance:good.append(pair[0])
   if len(good)>=4:
    a=np.float32([qkp[m.queryIdx].pt for m in good]).reshape(-1,1,2); d=np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1,1,2)
    H,mask=cv2.findHomography(a,d,cv2.RANSAC,5)
    if mask is not None:inl=int(mask.sum())
  pil=Image.open(io.BytesIO(b)).convert('RGB');pil.thumbnail((400,260))
  rows.append({'rank':rank,'url':u,'good':len(good),'inliers':inl,'w':im.shape[1],'h':im.shape[0],'pil':pil})
 except Exception:pass
rows.sort(key=lambda x:(x['inliers'],x['good'],-x['rank']),reverse=True)
for i,r in enumerate(rows[:40]):r['pil'].save(ROOT/f'yandex-match-{i:02d}.jpg',quality=88)
cellw,cellh=440,320; top=rows[:40]
sheet=Image.new('RGB',(cellw*4,cellh*math.ceil(len(top)/4)),'white');draw=ImageDraw.Draw(sheet)
for n,r in enumerate(top):
 x=n%4*cellw;y=n//4*cellh;im=r['pil'];sheet.paste(im,(x+(cellw-im.width)//2,y+45));draw.text((x+5,y+5),f"#{n} rank={r['rank']} inl={r['inliers']} good={r['good']}",fill='black');draw.text((x+5,y+22),urllib.parse.urlparse(r['url']).netloc[:55],fill='black')
sheet.save(ROOT/'yandex-contact.jpg',quality=90)
out=[{k:v for k,v in r.items() if k!='pil'} for r in rows]
(ROOT/'yandex-ranked.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out[:50],indent=2,ensure_ascii=False))
