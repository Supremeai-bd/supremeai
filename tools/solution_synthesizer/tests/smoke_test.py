from pathlib import Path
import py_compile

p = Path(__file__).parents[1] / "tools" / "solution_synthesizer.py"
py_compile.compile(str(p), doraise=True)
print("solution_synthesizer.py: compile OK")
