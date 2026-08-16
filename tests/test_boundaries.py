import subprocess
import sys


def test_core_import_pulls_no_server():
    code = (
        "import sys; import papercli; "
        "assert 'papercli.server' not in sys.modules; "
        "assert 'fastapi' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
