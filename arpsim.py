from typing import List, Dict
import ctypes
from os import path
from typing import Tuple

class ScanResult(ctypes.Structure):
    _fields_ = [
        ("ipAdress", ctypes.c_char_p),
        ("resultCode", ctypes.c_uint32),
        ("resultAddress", (ctypes.c_uint32 * 2))
    ]

    def get_address(self) -> Tuple[str, str]:
        size = 6
        matrix = ctypes.cast(ctypes.pointer(self.resultAddress), ctypes.POINTER(ctypes.c_ubyte))
        return (":".join([f"{matrix[i]:02X}" for i in range(size)]), self.ipAdress.decode())

module_name = "arp.dll"
arp = ctypes.CDLL(path.join(path.dirname(__file__), "C", module_name))

scan_all = arp.scanAll
scan_all.restype = ctypes.POINTER(ScanResult)
scan_all.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_size_t]

def arp_scan_all(adresses: List[str]) -> Dict[str, str]:
    list_size = len(adresses)
    arr = (ctypes.c_char_p * list_size)()
    arr[:] = [x.encode() for x in adresses]
    scan_result = scan_all(arr, list_size)
    result = {}

    for i in range(list_size):
        (key, value) = scan_result[i].get_address()
        if value == "00:00:00:00:00:00": continue
        result[key] = value

    return result

def scan_local(ip_address: str, limit: int) -> Dict[str, str]:
    limit = min(limit, 254)
    base = ".".join(ip_address.split(".")[:3])
    adresses = []

    for x in range(2, limit):
        adresses.append(".".join([base, str(x)]))

    return arp_scan_all(adresses)

    return arp_scan_all(adresses)
