"""通过实际子进程检查CLI生命周期；示例分数不作为真实识别指标。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
RUN = Path(tempfile.mkdtemp(prefix="cli-smoke-", dir=ROOT / "runs"))
TARGET = "CLI_SMOKE_" + uuid.uuid4().hex[:8]
sample1 = ROOT / "private" / "official-smoke" / "example1.wav"
sample2 = ROOT / "private" / "official-smoke" / "example2.flac"
results = []


def run(name, args, expected_code=0):
    command = [sys.executable, "-X", "utf8", str(ROOT / "speaker_verify.py"), *map(str, args)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=90)
    (RUN / f"{name}.stdout.json").write_text(completed.stdout, encoding="utf-8")
    (RUN / f"{name}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    results.append({"name": name, "command": command, "exit_code": completed.returncode})
    if completed.returncode != expected_code:
        raise AssertionError(f"{name}: exit {completed.returncode}, see {RUN}")
    return json.loads(completed.stdout) if expected_code == 0 else None


try:
    run("01-enroll", ["enroll", "--id", TARGET, "--session", "SMOKE_ONLY", sample1])
    assert TARGET in run("02-list", ["list"])["templates"]
    result = run("03-uncalibrated", ["verify", "--id", TARGET, sample2])
    assert result["state"] == "insufficient" and result["reason"] == "THRESHOLDS_NOT_CALIBRATED"
    score = result["score"]
    # 根据已知分数造三个演示分支，只验证路由，不评估说话人准确率。
    for state, low, high in [("target", score-.2, score-.1), ("non_target", score+.1, score+.2), ("insufficient", score-.1, score+.1)]:
        result = run("04-demo-" + state, ["verify", "--id", TARGET, "--demo-thresholds", low, high, sample2])
        assert result["state"] == state and result["demo_only"] is True
    run("05-invalid-threshold", ["verify", "--id", TARGET, "--demo-thresholds", .8, .2, sample2], 2)
    result = run("06-delete", ["delete", "--id", TARGET, "--yes"])
    assert result["original_audio_deleted"] is False and sample1.exists() and sample2.exists()
    assert TARGET not in run("07-list-after", ["list"])["templates"]
    status = "PASS_FUNCTIONAL_ONLY"
finally:
    (RUN / "result.json").write_text(json.dumps({"status": locals().get("status", "FAILED"),
        "claim": "CLI functional smoke only; thresholds deliberately constructed, no accuracy evidence",
        "calls": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(RUN)
