import sys
sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2\Python\3.9")

import powerfactory as pf

app = pf.GetApplication()
if app is None:
    raise RuntimeError("Could not start PowerFactory (check license / close other instances)")

print("Connected to PowerFactory")
print("User:", app.GetCurrentUser().loc_name)

project = app.GetActiveProject()
print("Active project:", project.loc_name if project else None)
