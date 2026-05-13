import os
import sys
import jpype

__all__ = []

def get_resource_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # In PyInstaller bundle, __file__ is relative to _MEIPASS or absolute
        _base = os.path.dirname(__file__)
        if not os.path.isabs(_base):
            return os.path.join(sys._MEIPASS, _base, filename)
        return os.path.join(_base, filename)
    # In development
    return os.path.abspath(os.path.join(os.path.dirname(__file__), filename))

PLAYERGLOBAL = get_resource_path("playerglobal32_0.swc")
FFDEC_LIB = get_resource_path("ffdec_lib.jar")
CMYKJPEG_LIB = get_resource_path("cmykjpeg.jar")
JL_LIB = get_resource_path("jl1.0.1.jar")

assert os.path.exists(FFDEC_LIB), f"ffdec_lib.jar doesn't exist at {FFDEC_LIB}"
assert os.path.exists(CMYKJPEG_LIB), f"cmykjpeg.jar doesn't exist at {CMYKJPEG_LIB}"
assert os.path.exists(JL_LIB), f"jl1.0.1.jar doesn't exist at {JL_LIB}"

jvmpath = None

if sys.platform.startswith("win"):
    try:
        jvmpath = jpype._jvmfinder.getDefaultJVMPath()
    except jpype._jvmfinder.JVMNotFoundException:
        pass

    flashlibFolder = os.path.join(os.getenv("APPDATA"), "JPEXS", "FFDec", "flashlib")
    flashlibFile = os.path.join(flashlibFolder, "playerglobal32_0.swc")

    if not os.path.exists(flashlibFile):
        if not os.path.exists(flashlibFolder):
            os.makedirs(flashlibFolder, exist_ok=True)

        with open(PLAYERGLOBAL, "rb") as orig:
            with open(flashlibFile, "wb") as new:
                new.write(orig.read())

elif sys.platform == "darwin":
    jvmpath = "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/lib/jli/libjli.dylib"

else:
    pass

if jvmpath is None:
    raise ImportError("Java not found!")

jpype.startJVM(jvmpath, "-Xmx2048m", "-Xms32m", classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB])



from .classes import *
