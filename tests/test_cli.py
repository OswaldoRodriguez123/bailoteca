import subprocess
import sys


def test_module_help_lists_commands():
    result = subprocess.run(
        [sys.executable, "-m", "bailoteca", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for command in ("run", "review", "approve", "add", "refresh"):
        assert command in result.stdout
