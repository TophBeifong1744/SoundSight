"""Host-only test launcher: Linux resource import shim, never fake measurements."""
import os
import runpy
import sys
import types
from pathlib import Path
if os.name == 'nt':
    sys.modules['resource'] = types.ModuleType('resource')
path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(path.parent))
sys.argv = [str(path)] + sys.argv[2:]
runpy.run_path(str(path), run_name='__main__')
