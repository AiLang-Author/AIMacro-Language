import os as _os
import sys as _sys
print(_os.name)
print(_sys.platform)
print(_os.O_RDWR | _os.O_CREAT | _os.O_EXCL)
print(hasattr(_os, "O_NOFOLLOW"))
