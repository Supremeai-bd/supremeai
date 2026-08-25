import py_compile
from pathlib import Path

p = Path(__file__).parents[1] / "tools" / "solution_synthesizer.py"
py_compile.compile(str(p), doraise=True)
print("solution_synthesizer.py: compile OK")
