"""解压已有 Vitis 组件并填写本机路径；不重建、不编译、不启动任何工具。"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import zipfile

HERE = Path(__file__).resolve().parent


def unpack(workspace, vitis_root, archive=HERE / "vitis_workspace.zip"):
    workspace = Path(workspace).resolve()
    vitis_root = Path(vitis_root).resolve()
    if workspace.exists():
        raise ValueError("目标目录已经存在，请选择一个尚不存在的新工作区；不会覆盖原工程")
    if not (vitis_root / "data/embeddedsw").is_dir():
        raise ValueError("Vitis 安装目录应包含 data/embeddedsw")

    # 先在内存中验证所有条目和路径，再创建目标目录。
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("ZIP 内容损坏")
        files = {}
        for item in z.infolist():
            name = PurePosixPath(item.filename)
            if (not name.parts or name.parts[0] != "Vitis" or
                    ".." in name.parts or "\\" in item.filename or ":" in item.filename):
                raise ValueError("ZIP 中存在不安全路径")
            if item.is_dir():
                continue
            rel = PurePosixPath(*name.parts[1:]).as_posix()
            if rel in files or rel == ".":
                raise ValueError("ZIP 中存在重复/无效文件名")
            files[rel] = z.read(item)

    mapping = json.loads(files["path-bases.json"])
    changed = set()
    for entry in mapping["paths"]:
        rel = PurePosixPath(entry["relative"])
        if rel.is_absolute() or ".." in rel.parts or ":" in str(rel) or "\\" in str(rel):
            raise ValueError("元数据必须使用包内或安装目录内的相对路径")
        if entry["base"] == "workspace":
            if str(rel) not in files and not any(n.startswith(str(rel) + "/") for n in files):
                raise FileNotFoundError("交接包缺少依赖: " + str(rel))
            absolute = workspace / str(rel)
        elif entry["base"] == "vitis":
            absolute = vitis_root / str(rel)
            if not absolute.exists():
                raise FileNotFoundError("本机 Vitis 缺少依赖: " + str(absolute))
        else:
            raise ValueError("未知路径基准")
        name = entry["file"]
        text = files[name].decode("utf-8")
        if entry["format"] == "json":
            obj = json.loads(text)
            target = obj
            for key in entry["field"][:-1]:
                target = target[key]
            key = entry["field"][-1]
            if target[key] != entry["relative"]:
                raise ValueError("JSON 相对路径与清单不符: " + name)
            target[key] = absolute.as_posix()
            text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
        elif entry["format"] == "yaml-line":
            old = entry["prefix"] + entry["relative"]
            lines = text.splitlines()
            if old not in lines:
                raise ValueError("YAML 相对路径与清单不符: " + name)
            text = "\n".join(entry["prefix"] + absolute.as_posix() if line == old else line
                             for line in lines) + "\n"
        else:
            raise ValueError("未知元数据格式")
        files[name] = text.encode("utf-8")
        changed.add(name)

    workspace.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        output = workspace / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
    return {"workspace": str(workspace), "files": len(files),
            "local_metadata_files": len(changed), "eda_started": False,
            "project_recreated": False, "build_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="尚不存在的新工作区目录")
    parser.add_argument("--vitis-root", help="接收方 Vitis 2025.2 安装目录；也可用 VITIS_ROOT/XILINX_VITIS")
    args = parser.parse_args()
    root = args.vitis_root or os.environ.get("VITIS_ROOT") or os.environ.get("XILINX_VITIS")
    if not root:
        executable = shutil.which("vitis.bat") or shutil.which("vitis")
        if executable:
            root = str(Path(executable).resolve().parent.parent)
    if not root:
        parser.error("请填写 --vitis-root，或设置本机 VITIS_ROOT/XILINX_VITIS/PATH")
    print(json.dumps(unpack(args.workspace, root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
