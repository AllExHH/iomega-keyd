import struct,sys
# Find NEC-Codetabellen (Adresse/Befehl mit Pruefbyte) in Binaerdateien.
# Aufruf: python3 find_nec_codes.py <datei> [...]
def nec(w):
    b=w.to_bytes(4,'little')
    return w!=0 and ((b[2]^b[3])==0xff or (b[0]^b[1])==0xff) and w not in (0xffff0000,0x0000ffff,0xff00ff00,0x00ff00ff)
for f in sys.argv[1:]:
    d=open(f,'rb').read()
    for stride in (4,8,12,16):
      i=0
      while i+4<=len(d):
        run=[];j=i
        while j+4<=len(d):
            w=struct.unpack_from('<I',d,j)[0]
            if nec(w): run.append(w); j+=stride
            else: break
        if len(run)>=8 and len(set(run))>=6:
            hi=set(x>>16 for x in run); lo=set(x&0xffff for x in run)
            print(f,hex(i),'stride',stride,len(run),'hi',[hex(h) for h in list(hi)[:4]],'lo',[hex(l) for l in list(lo)[:4]])
            i=j
        else: i+=4
