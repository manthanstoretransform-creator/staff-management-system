import ctypes
import ctypes.wintypes
from ctypes import Structure, c_ulong, c_ushort, c_byte, c_void_p, byref

class GUID(Structure):
    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_byte * 8)
    ]

def make_guid(l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8):
    g = GUID()
    g.Data1 = l
    g.Data2 = w1
    g.Data3 = w2
    g.Data4 = (c_byte * 8)(b1, b2, b3, b4, b5, b6, b7, b8)
    return g

CLSID_CUIAutomation = make_guid(0xff48dba4, 0x6056, 0x4e01, 0x84, 0x0b, 0x43, 0x94, 0x46, 0xd5, 0x3b, 0x61)
IID_IUIAutomation = make_guid(0x30cbe57d, 0xd9d0, 0x452a, 0xab, 0x13, 0x7a, 0xc5, 0xac, 0x48, 0x25, 0xee)

ole32 = ctypes.windll.ole32
ole32.CoInitialize(None)

p_uia = c_void_p()
hr = ole32.CoCreateInstance(
    byref(CLSID_CUIAutomation),
    None,
    1, # CLSCTX_INPROC_SERVER
    byref(IID_IUIAutomation),
    byref(p_uia)
)
print("CoCreateInstance hr:", hex(hr if hr >= 0 else hr & 0xffffffff), "p_uia:", p_uia.value)
