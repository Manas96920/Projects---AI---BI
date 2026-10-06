"""Execute the main notebook using this process's global Python 3.12 kernel.

Writes the main notebook only after all cells complete successfully. This is a
manual verification utility; Task Scheduler uses run_report.py instead.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

if sys.version_info[:2] != (3, 12) or sys.prefix != sys.base_prefix:
    raise SystemExit("Run with the global Python 3.12 interpreter")

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ai', choices=['off', 'auto', 'required'], default='off',
                    help='Default off runs locally without any external API request.')
args = parser.parse_args()
os.environ['IPYTHONDIR'] = str(root / 'tmp' / 'ipython')
os.environ['JUPYTER_RUNTIME_DIR'] = str(root / 'tmp' / 'jupyter_runtime')
target = root / "automated_recurring_report_generator.ipynb"
notebook = nbformat.read(target, as_version=4)
for i, cell in enumerate(notebook.cells):
    if cell.cell_type == "code":
        if 'configuration' in cell.metadata.get('tags', []):
            cell.source = re.sub(r'^AI_MODE = "[^"]+"', f'AI_MODE = "{args.ai}"',
                                 cell.source, flags=re.MULTILINE)
        compile(cell.source, f"notebook_cell_{i}", "exec")

# The generic python3 kernelspec can point to a different PATH interpreter.
# Pin its launch command to the exact interpreter running this utility.
manager = KernelManager(kernel_name="python3")
manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
client = NotebookClient(notebook, km=manager, timeout=300,
                        resources={"metadata": {"path": str(root)}})
try:
    client.execute()
except Exception as exc:
    print(f"Notebook failed ({type(exc).__name__}); the existing notebook was not replaced.")
    raise SystemExit(1) from None
finally:
    if manager.has_kernel:
        manager.shutdown_kernel(now=True)

nbformat.validate(notebook)
nbformat.write(notebook, target)
executed = [c for c in notebook.cells if c.cell_type == "code"]
errors = [o for c in executed for o in c.get("outputs", []) if o.output_type == "error"]
if errors:
    raise SystemExit("Notebook contains execution errors")
print(f"Executed and saved {len(executed)} code cells with Python {sys.version.split()[0]}.")
print("Notebook:", target)
# Only report provenance/path data; don't print raw notebook streams or API errors.
streams = '\n'.join(o.get('text', '') for c in executed for o in c.get('outputs', [])
                    if o.output_type == 'stream')
match = re.search(r'^PDF created: (.+)$', streams, flags=re.MULTILINE)
if match:
    path = Path(match.group(1).strip()).parent / 'manifest.json'
    result = json.loads(path.read_text(encoding="utf-8"))
    print("Summary source:", result["summary_source"])
    print("PDF:", path.parent / result["pdf"])
