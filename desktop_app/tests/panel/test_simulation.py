import os
from pathlib import Path
import subprocess
import sys


def test_simulation_command_runs_end_to_end_without_hardware():
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "dj_poltorashka.panel.simulation"],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Подключение: connected" in result.stdout
    assert "Отправлено кадров подсветки после heartbeat: 1" in result.stdout
    assert "После потери связи: closed" in result.stdout
    assert "Периметр: (128, 128, 128)" in result.stdout
    assert "Через 500 мс: (0, 0, 0)" in result.stdout
    assert "Переподключение: connected" in result.stdout
    assert "Ложных нажатий при переподключении: 0" in result.stdout
