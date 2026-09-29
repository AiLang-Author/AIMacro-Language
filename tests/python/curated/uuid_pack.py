print(int("10", 16))
class U:
    def __init__(self, hex=None, bytes=None, bytes_le=None, fields=None, n=None, version=None, is_safe=None):
        print([hex, bytes, bytes_le, fields, n].count(None))
        print(hex.strip("{}"))
U("{ok}")
