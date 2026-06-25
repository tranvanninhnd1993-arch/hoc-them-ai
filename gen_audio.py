# -*- coding: utf-8 -*-
"""Trích lời giảng từ RICH (index.html) -> thu MP3 giọng nữ tiếng Việt CÓ ĐIỂM NHẤN (edge-tts).

Mỗi bài tách thành các đoạn theo mức quan trọng (emph):
  0 = câu thường            -> rate -8%,  pitch +0Hz
  1 = tiêu đề / công thức    -> rate -13%, pitch +10Hz
  2 = Ghi nhớ / Lỗi hay gặp  -> rate -19%, pitch +22Hz  (chậm & cao -> nổi bật)
Các đoạn được nối liền thành 1 file mp3/bài, nên giọng lên xuống tự nhiên.
"""
import re, os, asyncio, edge_tts
from html.parser import HTMLParser

BASE = os.path.dirname(os.path.abspath(__file__))
VOICE = "vi-VN-HoaiMyNeural"
PROSODY = {0: ("-8%", "+0Hz"), 1: ("-13%", "+10Hz"), 2: ("-19%", "+22Hz")}
VOID = {"br","hr","img","input","meta","link","area","base","col","embed","source","track","wbr"}

REPL = [("×"," nhân "),("÷"," chia "),("−"," trừ "),("+"," cộng "),("="," bằng "),
        ("²"," vuông "),("%"," phần trăm "),("/"," phần "),("≥"," lớn hơn "),("≤"," nhỏ hơn ")]

def clean(t):
    t = (t.replace("&gt;"," lớn hơn ").replace("&lt;"," nhỏ hơn ")
           .replace("&amp;"," và ").replace("&nbsp;"," "))
    for a,b in REPL: t = t.replace(a,b)
    t = re.sub(r"[\U0001F000-\U0001FAFF←-⇿⌀-➿⬀-⯿︀-️]", " ", t)
    for d in ["—","–","·","•"]: t = t.replace(d, ", ")
    return re.sub(r"\s+"," ", t).strip()

class Seg(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth=0; self.in_viz=False; self.viz_depth=0
        self.cur=None; self.cur_emph=0; self.skip_depth=None; self.segs=[]
    def _emph(self, cls):
        c=cls.split()
        if "keybox" in c or "warnbox" in c: return 2
        if "tipbox" in c or "sec-label" in c or "exbox" in c: return 1
        return 0
    def handle_starttag(self, tag, attrs):
        cls=dict(attrs).get("class","") or ""
        if tag in VOID:
            if self.in_viz and self.skip_depth is None and self.cur is not None:
                self.cur.append(" ")
            return
        self.depth+=1
        if not self.in_viz:
            if "viz" in cls.split():
                self.in_viz=True; self.viz_depth=self.depth
            return
        if self.skip_depth is not None: return
        if tag=="svg" or tag=="details" or any(c in cls.split() for c in ["tenframe","viz-emoji","colcalc"]):
            self.skip_depth=self.depth; return
        if self.depth==self.viz_depth+1:
            self._flush()
            self.cur=[]; self.cur_emph=self._emph(cls)
    def handle_startendtag(self, tag, attrs):
        # <rect/>, <line/>... : khong anh huong depth
        pass
    def handle_endtag(self, tag):
        if tag in VOID: return
        if self.skip_depth is not None and self.depth==self.skip_depth:
            self.skip_depth=None; self.depth-=1; return
        if self.in_viz and self.depth==self.viz_depth+1: self._flush()
        if self.in_viz and self.depth==self.viz_depth: self.in_viz=False
        self.depth-=1
    def handle_data(self, data):
        if self.in_viz and self.skip_depth is None and self.cur is not None:
            self.cur.append(data)
    def handle_entityref(self, name):
        if self.in_viz and self.skip_depth is None and self.cur is not None:
            self.cur.append("&"+name+";")
    def _flush(self):
        if self.cur is not None:
            txt=clean("".join(self.cur))
            if txt: self.segs.append([txt, self.cur_emph])
        self.cur=None

def lesson_segments(html_str):
    p=Seg(); p.feed(html_str); p.close()
    # gop cac doan lien tiep cung muc nhan
    merged=[]
    for txt,emph in p.segs:
        if merged and merged[-1][1]==emph:
            merged[-1][0]+=". "+txt
        else:
            merged.append([txt,emph])
    return merged

# ----- doc index.html, lay tung bai -----
html = open(os.path.join(BASE,"index.html"), encoding="utf-8").read()
rich = html[html.index("const RICH="):html.index("/* ===== ACTIVE CURRICULUM")]
rich = re.sub(r"\$\{[^}]*\}", " ", rich)
chunks = re.split(r"/\*\s*\d+\s*-[^*]*\*/", rich)[1:]
lessons=[]
for ch in chunks:
    frags=re.findall(r"`([^`]*)`", ch, re.S)
    h=" ".join(frags).strip()
    if not h: continue
    lessons.append(lesson_segments(h))
print("So bai trich duoc:", len(lessons))

async def synth(path, segs):
    with open(path,"wb") as f:
        for txt,emph in segs:
            if not txt.strip(): continue
            rate,pitch=PROSODY.get(emph,PROSODY[0])
            c=edge_tts.Communicate(txt, VOICE, rate=rate, pitch=pitch)
            async for ch in c.stream():
                if ch["type"]=="audio": f.write(ch["data"])

async def main():
    os.makedirs(os.path.join(BASE,"audio"), exist_ok=True)
    i=0
    for g in (2,3,4,5):
        for l in range(10):
            if i>=len(lessons): break
            segs=lessons[i]; i+=1
            fn=os.path.join(BASE,"audio",f"g{g}_l{l}.mp3")
            try:
                await synth(fn, segs)
                kb=round(os.path.getsize(fn)/1024,1)
                print(f"  OK g{g}_l{l}.mp3  ({kb} KB, {len(segs)} doan)")
            except Exception as e:
                print(f"  LOI g{g}_l{l}: {e}")
    print("XONG.")

asyncio.run(main())
