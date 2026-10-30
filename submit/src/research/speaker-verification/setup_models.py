"""从官方仓库固定模型版本并校验权重；唯一需要联网的模型准备入口。"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
REPO = "speechbrain/spkrec-ecapa-voxceleb"
REVISION = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "SoundSight-speaker-research/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--smoke-assets", action="store_true", help="下载官方示例，仅供流程冒烟，不能作为独立身份评价")
    args = parser.parse_args()
    lock_path = ROOT / "model-lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        revision = lock["revision"]
    else:
        meta = json.loads(fetch(f"https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true"))
        revision = meta["sha"]
        if args.inspect:
            print(json.dumps(meta, indent=2))
            return
        if meta.get("cardData", {}).get("license") != "apache-2.0":
            raise RuntimeError("Model card license changed: review before download")
        lock = {"repository": REPO, "revision": revision, "license": "apache-2.0",
                "source": f"https://huggingface.co/{REPO}/tree/{revision}", "files": {}}
        for item in meta["siblings"]:
            if item["rfilename"] == "embedding_model.ckpt":
                lock["expected_embedding_sha256"] = item["lfs"]["sha256"]
    folder = ROOT / "models" / "ecapa"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ["embedding_model.ckpt", "hyperparams.yaml", "README.md"]:
        target = folder / name
        expected = lock.get("files", {}).get(name, {}).get("sha256")
        if name == "embedding_model.ckpt":
            expected = lock["expected_embedding_sha256"]
        if target.exists():
            data = target.read_bytes()
        else:
            data = fetch(f"https://huggingface.co/{REPO}/resolve/{revision}/{name}")
        digest = sha256(data)
        if expected and digest != expected:
            raise RuntimeError(f"Hash mismatch: {name}; existing evidence retained")
        if not target.exists():
            target.write_bytes(data)
        lock["files"][name] = {"sha256": digest, "bytes": len(data)}
        print(f"Verified {name}: {digest}", flush=True)
    if not lock_path.exists():
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned revision: {revision}")
    if args.smoke_assets:
        sample_dir = ROOT / "private" / "official-smoke"
        sample_dir.mkdir(parents=True, exist_ok=True)
        provenance = {"usage": "pipeline smoke only; no independent speaker ground truth", "source_license": "model repository declares Apache-2.0", "files": []}
        for name in ["example1.wav", "example2.flac"]:
            url = f"https://huggingface.co/{REPO}/resolve/{revision}/{name}"
            target = sample_dir / name
            data = target.read_bytes() if target.exists() else fetch(url)
            if not target.exists():
                target.write_bytes(data)
            provenance["files"].append({"name": name, "url": url, "sha256": sha256(data)})
        (sample_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
