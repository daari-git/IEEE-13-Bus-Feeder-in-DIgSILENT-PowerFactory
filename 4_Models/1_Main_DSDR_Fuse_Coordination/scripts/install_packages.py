"""
Installs the two Python packages that the scripts need (matplotlib and reportlab).

Run it ONCE, as the script file of a Python Script object in PowerFactory (see the guide); the messages appear
in the Output Window.  Needs an internet connection.  It can also be run with any normal Python 3.9.
"""
import os
import subprocess
import sys

PACKAGES = ["matplotlib", "reportlab"]


def say(msg=""):
    print(msg)
    try:
        import powerfactory
        app = powerfactory.GetApplication()
        if app is not None:
            app.PrintPlain(msg)
    except Exception:
        pass


def python_exe():
    """python.exe of the Python 3.9 that PowerFactory uses (it sits two folders above os.py)."""
    exe = os.path.join(os.path.dirname(os.path.dirname(os.__file__)), "python.exe")
    if os.path.isfile(exe):
        return exe
    return sys.executable


exe = python_exe()
say("Python used: " + exe)
say("Installing: " + ", ".join(PACKAGES) + "  (this may take a minute)")
try:
    p = subprocess.run([exe, "-m", "pip", "install"] + PACKAGES, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        say("  " + line)
    if p.returncode == 0:
        say("DONE. The packages are installed.")
    else:
        say("The installation FAILED (exit code %d). Check the internet connection and run this script again." % p.returncode)
except Exception as e:
    say("The installation FAILED: %s" % e)
