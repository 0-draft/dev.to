"""Independent check: re-encode the demo RequestPayload with a 30-line encoder
that sorts map keys bytewise (RFC 8949 Section 4.2.1) and compare with cbor2."""
import sys, importlib.util
spec = importlib.util.spec_from_file_location("d", sys.argv[1]); d = importlib.util.module_from_spec(spec)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(d)
def head(mt, n):
    if n < 24: return bytes([mt<<5|n])
    for ai, l in ((24,1),(25,2),(26,4),(27,8)):
        if n < 1<<(8*l): return bytes([mt<<5|ai]) + n.to_bytes(l,'big')
def e(x):
    if x is True: return b'\xf5'
    if x is False: return b'\xf4'
    if isinstance(x,int): return head(0,x) if x>=0 else head(1,-1-x)
    if isinstance(x,bytes): return head(2,len(x))+x
    if isinstance(x,str): b=x.encode(); return head(3,len(b))+b
    if isinstance(x,list): return head(4,len(x))+b''.join(e(i) for i in x)
    if isinstance(x,dict):
        items=sorted((e(k),e(v)) for k,v in x.items())  # RFC 8949 4.2.1: bytewise order of encoded keys
        return head(5,len(x))+b''.join(k+v for k,v in items)
print("payload match:", e(d.request_payload) == d.payload_bytes)
