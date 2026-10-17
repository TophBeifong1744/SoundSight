#!/usr/bin/env python3
"""Fail-closed validation for a profile-driven PYNQ Overlay/DMA evidence set."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEX64 = re.compile(r"^[0-9a-f]{64}$")
ACCESS = {"ro", "rw", "wo", "w1c", "rc"}
PATTERNS = {"counter8", "alternating", "xorshift32"}
EVIDENCE_LEVELS = {"static", "mock", "hardware"}


class Result:
    def __init__(self, mode: str, profile_id: str = "unknown") -> None:
        self.mode = mode
        self.profile_id = profile_id
        self.checks: list[dict[str, Any]] = []
        self.issues: list[dict[str, str]] = []
        self.artifact_hashes: dict[str, str] = {}

    def check(self, code: str, ok: bool, message: str) -> None:
        self.checks.append({"code": code, "status": "PASS" if ok else "FAIL", "message": message})
        if not ok:
            self.error(code, message)

    def error(self, code: str, message: str) -> None:
        self.issues.append({"severity": "ERROR", "code": code, "message": message})

    def warn(self, code: str, message: str) -> None:
        self.issues.append({"severity": "WARNING", "code": code, "message": message})

    @property
    def failed(self) -> bool:
        return any(item["severity"] == "ERROR" for item in self.issues)

    def report(self, evidence_level: str) -> dict[str, Any]:
        return {
            "tool": "pynq-overlay-dma-validation/validate_profile.py",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "profile_id": self.profile_id,
            "evidence_level": evidence_level,
            "status": "FAIL" if self.failed else "PASS",
            "artifact_hashes": self.artifact_hashes,
            "checks": self.checks,
            "issues": self.issues,
        }


def read_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value is forbidden: {value}")
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve(profile_path: Path, raw: Any, result: Result, field: str) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        result.error("PATH_MISSING", f"{field} must be a non-empty path")
        return None
    path = Path(raw)
    if path.is_absolute():
        result.warn("ABSOLUTE_PATH", f"{field} is absolute and reduces portability: {path}")
    else:
        path = profile_path.parent / path
    return path.resolve()


def required_object(parent: dict[str, Any], name: str, result: Result) -> dict[str, Any]:
    value = parent.get(name)
    if not isinstance(value, dict):
        result.error("FIELD_REQUIRED", f"{name} must be an object")
        return {}
    return value


def required_text(parent: dict[str, Any], name: str, result: Result, scope: str) -> str:
    value = parent.get(name)
    if not isinstance(value, str) or not value.strip() or value.startswith("replace-with-"):
        result.error("FIELD_REQUIRED", f"{scope}.{name} must be resolved")
        return ""
    return value


def hwh_inventory(path: Path, result: Result) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    values: set[str] = set()
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        result.error("HWH_PARSE", f"cannot parse HWH XML: {exc}")
        return names, values
    for element in root.iter():
        for key, value in element.attrib.items():
            if value:
                values.add(value.strip())
            if key.upper() in {"INSTANCE", "FULLNAME", "NAME", "MODULENAME"} and value:
                names.add(value.strip().lstrip("/"))
    return names, values


def validate_overlay(profile_path: Path, profile: dict[str, Any], result: Result) -> None:
    board = required_object(profile, "board", result)
    overlay = required_object(profile, "overlay", result)
    for field in ("board_name", "board_revision", "device_part", "pynq_image"):
        required_text(board, field, result, "board")
    compatibility = board.get("compatibility_contains")
    if not isinstance(compatibility, list) or not compatibility or not all(isinstance(item, str) and item for item in compatibility):
        result.error("BOARD_COMPATIBILITY", "board.compatibility_contains must be a non-empty string list")
    for field in ("build_id", "vivado_version"):
        required_text(overlay, field, result, "overlay")
    if not isinstance(overlay.get("interface_version"), int):
        result.error("FIELD_REQUIRED", "overlay.interface_version must be an integer")

    paths: dict[str, Path] = {}
    for field in ("bit", "hwh", "manifest"):
        path = resolve(profile_path, overlay.get(field), result, f"overlay.{field}")
        if path is None:
            continue
        paths[field] = path
        if not path.is_file():
            result.error("ARTIFACT_MISSING", f"overlay.{field} not found: {path}")
        else:
            result.artifact_hashes[field] = sha256(path)

    if "bit" in paths and "hwh" in paths:
        result.check("OVERLAY_STEM", paths["bit"].stem == paths["hwh"].stem, ".bit and .hwh must share a basename for PYNQ")
        result.check("OVERLAY_DIRECTORY", paths["bit"].parent == paths["hwh"].parent,
                     ".bit and .hwh must be adjacent so PYNQ loads the validated HWH")

    if "manifest" not in paths or not paths["manifest"].is_file():
        return
    try:
        manifest = read_json(paths["manifest"])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result.error("MANIFEST_PARSE", str(exc))
        return
    for field in ("build_id", "interface_version", "vivado_version"):
        result.check(
            f"MANIFEST_{field.upper()}",
            manifest.get(field) == overlay.get(field),
            f"manifest {field} must equal profile overlay {field}",
        )
    result.check(
        "MANIFEST_DEVICE_PART",
        manifest.get("device_part") == board.get("device_part"),
        "manifest device_part must equal board.device_part",
    )
    for field in ("bit", "hwh"):
        key = f"{field}_sha256"
        expected = manifest.get(key)
        if not isinstance(expected, str) or not HEX64.fullmatch(expected):
            result.error("MANIFEST_HASH", f"manifest {key} must be 64 lowercase hex characters")
        elif field in result.artifact_hashes:
            result.check(
                f"{field.upper()}_HASH",
                result.artifact_hashes[field] == expected,
                f"actual {field} SHA-256 must match manifest",
            )

    if "hwh" in paths and paths["hwh"].is_file():
        inventory, hwh_values = hwh_inventory(paths["hwh"], result)
        device_part = board.get("device_part")
        result.check(
            "HWH_DEVICE_PART",
            isinstance(device_part, str) and any(device_part.lower() in value.lower() for value in hwh_values),
            "HWH metadata must contain board.device_part",
        )
        required_ip = overlay.get("required_ip")
        if not isinstance(required_ip, list) or not required_ip:
            result.error("HWH_REQUIRED_IP", "overlay.required_ip must be a non-empty list")
        else:
            for name in required_ip:
                ok = isinstance(name, str) and any(
                    item == name or item.endswith("/" + name) for item in inventory
                )
                result.check("HWH_IP", ok, f"HWH must expose required IP {name!r}")
        required_interrupts = overlay.get("required_interrupts", [])
        if not isinstance(required_interrupts, list) or not all(isinstance(name, str) and name for name in required_interrupts):
            result.error("HWH_INTERRUPTS", "overlay.required_interrupts must be a string list when present")
        else:
            for name in required_interrupts:
                ok = any(name == item or item.endswith("/" + name) or name in item for item in inventory | hwh_values)
                result.check("HWH_INTERRUPT", ok, f"HWH must expose required interrupt {name!r}")


def validate_registers(profile: dict[str, Any], result: Result) -> None:
    contract = required_object(profile, "register_contract", result)
    required_text(contract, "ip_name", result, "register_contract")
    span = contract.get("address_span_bytes")
    if not isinstance(span, int) or span <= 0:
        result.error("REGISTER_SPAN", "register_contract.address_span_bytes must be positive")
        span = 0
    registers = contract.get("registers")
    if not isinstance(registers, list) or not registers:
        result.error("REGISTER_LIST", "register_contract.registers must be non-empty")
        registers = []
    names: set[str] = set()
    offsets: set[int] = set()
    for index, reg in enumerate(registers):
        if not isinstance(reg, dict):
            result.error("REGISTER_ENTRY", f"register {index} must be an object")
            continue
        name = reg.get("name")
        offset = reg.get("offset")
        width = reg.get("width_bits")
        access = reg.get("access")
        if type(width) is not int or width != 32:
            result.error("REGISTER_WIDTH", "v0 supports only 32-bit registers; wider access needs a reviewed adapter")
        if not isinstance(name, str) or not name:
            result.error("REGISTER_NAME", f"register {index} has no name")
        elif name in names:
            result.error("REGISTER_DUPLICATE", f"duplicate register name {name}")
        else:
            names.add(name)
        if not isinstance(offset, int) or offset < 0 or offset % 4:
            result.error("REGISTER_OFFSET", f"register {name!r} offset must be a non-negative 4-byte multiple")
        else:
            if offset in offsets:
                result.error("REGISTER_DUPLICATE", f"duplicate register offset {offset}")
            offsets.add(offset)
            if span and (not isinstance(width, int) or width <= 0 or offset + (width + 7) // 8 > span):
                result.error("REGISTER_RANGE", f"register {name!r} exceeds the address span")
        if access not in ACCESS:
            result.error("REGISTER_ACCESS", f"register {name!r} access must be one of {sorted(ACCESS)}")
    identity = contract.get("identity")
    if not isinstance(identity, list) or not identity:
        result.error("IDENTITY_REQUIRED", "register_contract.identity must be non-empty")
    else:
        for item in identity:
            if not isinstance(item, dict) or item.get("register") not in names:
                result.error("IDENTITY_REGISTER", "identity entry must reference a declared register")
                continue
            register = next(reg for reg in registers if isinstance(reg, dict) and reg.get("name") == item["register"])
            if register.get("access") != "ro":
                result.error("IDENTITY_ACCESS", "identity registers must be side-effect-free read-only registers")
            if not isinstance(item.get("expected"), int) or not isinstance(item.get("mask", 0xFFFFFFFF), int):
                result.error("IDENTITY_VALUE", f"identity {item.get('register')!r} needs integer expected/mask")
            elif not (0 <= item["expected"] <= 0xFFFFFFFF and 0 < item.get("mask", 0xFFFFFFFF) <= 0xFFFFFFFF):
                result.error("IDENTITY_VALUE", "identity expected/mask must fit 32 bits and mask must not be zero")


def validate_dma(profile: dict[str, Any], result: Result) -> None:
    dma = required_object(profile, "dma_contract", result)
    for field in ("ip_name", "mm2s_channel", "s2mm_channel"):
        required_text(dma, field, result, "dma_contract")
    if dma.get("mode") not in {"simple", "sg"}:
        result.error("DMA_MODE", "dma_contract.mode must be simple or sg")
    width = dma.get("stream_data_width_bits")
    alignment = dma.get("buffer_alignment_bytes")
    maximum = dma.get("max_transfer_bytes")
    if type(width) is not int or width <= 0 or width % 8:
        result.error("DMA_WIDTH", "stream_data_width_bits must be a positive multiple of 8")
        width = 0
    if type(alignment) is not int or alignment <= 0:
        result.error("DMA_ALIGNMENT", "buffer_alignment_bytes must be positive")
        alignment = 0
    if type(maximum) is not int or maximum <= 0:
        result.error("DMA_MAX", "max_transfer_bytes must be positive")
        maximum = 0
    # Buffer-address alignment does not impose a packet-length multiple.
    granularity = dma.get("length_granularity_bytes", width // 8 if width else 0)
    if type(granularity) is not int or granularity <= 0:
        result.error("DMA_GRANULARITY", "length_granularity_bytes must be positive")
        granularity = 0
    cache = dma.get("cache_policy")
    if not isinstance(cache, dict) or cache.get("tx") not in {"flush", "coherent"} or cache.get("rx") not in {"invalidate", "coherent"}:
        result.error("DMA_CACHE", "cache_policy must declare tx flush/coherent and rx invalidate/coherent")
    if not isinstance(dma.get("tlast_required"), bool):
        result.error("DMA_TLAST", "tlast_required must be boolean")

    tests = profile.get("self_tests")
    if not isinstance(tests, list) or not tests:
        result.error("SELF_TESTS", "self_tests must be non-empty")
        return
    ids: set[str] = set()
    beat = width // 8 if width else 0
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            result.error("SELF_TEST_ENTRY", f"self test {index} must be an object")
            continue
        test_id = test.get("id")
        if not isinstance(test_id, str) or not test_id or test_id in ids:
            result.error("SELF_TEST_ID", f"self test {index} needs a unique id")
        else:
            ids.add(test_id)
        if test.get("kind") != "loopback":
            result.error("SELF_TEST_KIND", f"self test {test_id!r} kind must be loopback")
        length = test.get("length_bytes")
        if type(length) is not int or length <= 0:
            result.error("DMA_LENGTH", f"self test {test_id!r} length must be positive")
        else:
            if beat and length % beat:
                result.error("DMA_LENGTH_BEAT", f"self test {test_id!r} length is not a stream-beat multiple")
            if granularity and length % granularity:
                result.error("DMA_LENGTH_GRANULARITY", f"self test {test_id!r} length violates transfer granularity")
            if maximum and length > maximum:
                result.error("DMA_LENGTH_MAX", f"self test {test_id!r} exceeds max_transfer_bytes")
        if test.get("pattern") not in PATTERNS:
            result.error("SELF_TEST_PATTERN", f"self test {test_id!r} uses an unsupported pattern")
        timeout = test.get("timeout_seconds")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
            result.error("SELF_TEST_TIMEOUT", f"self test {test_id!r} timeout must be in (0, 60]")
        if test.get("golden") != "exact":
            result.error("SELF_TEST_GOLDEN", f"self test {test_id!r} currently requires golden=exact")


def validate_acceptance(profile: dict[str, Any], evidence: dict[str, Any] | None, result: Result) -> None:
    acceptance = required_object(profile, "acceptance", result)
    numeric_positive = ("minimum_throughput_bytes_per_second", "maximum_latency_seconds")
    for key in numeric_positive:
        value = acceptance.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            result.error("ACCEPTANCE_VALUE", f"acceptance.{key} must be non-negative")
    if evidence is None:
        result.warn("NO_RUN_EVIDENCE", "profile/artifacts validated without run evidence")
        return

    performance = evidence.get("performance")
    if not isinstance(performance, dict):
        result.error("PERFORMANCE_EVIDENCE", "run evidence must contain performance")
    else:
        throughput = performance.get("minimum_throughput_bytes_per_second")
        latency = performance.get("maximum_latency_seconds")
        result.check(
            "THROUGHPUT",
            isinstance(throughput, (int, float)) and throughput >= acceptance.get("minimum_throughput_bytes_per_second", 0),
            "measured minimum throughput must meet acceptance",
        )
        result.check(
            "LATENCY",
            isinstance(latency, (int, float)) and latency <= acceptance.get("maximum_latency_seconds", 0),
            "measured maximum latency must meet acceptance",
        )

    timing_limit = acceptance.get("timing", {}).get("minimum_wns_ns") if isinstance(acceptance.get("timing"), dict) else None
    if timing_limit is not None:
        timing = evidence.get("timing")
        result.check(
            "TIMING_WNS",
            isinstance(timing, dict) and isinstance(timing.get("wns_ns"), (int, float)) and timing["wns_ns"] >= timing_limit and bool(timing.get("source")),
            "timing evidence must meet WNS limit and name its source",
        )
    resource_limits = acceptance.get("resources")
    if isinstance(resource_limits, dict):
        resources = evidence.get("resources")
        if not isinstance(resources, dict) or not resources.get("source"):
            result.error("RESOURCE_EVIDENCE", "resource evidence must name its source")
        else:
            for key, limit in resource_limits.items():
                metric = key[:-4] if key.endswith("_max") else key
                value = resources.get(metric)
                result.check(
                    f"RESOURCE_{metric.upper()}",
                    isinstance(limit, (int, float)) and isinstance(value, (int, float)) and value <= limit,
                    f"resource {metric} must not exceed {limit}",
                )


def validate_run_evidence(profile: dict[str, Any], evidence: dict[str, Any], mode: str, result: Result) -> str:
    level = evidence.get("evidence_level")
    if level not in EVIDENCE_LEVELS:
        result.error("EVIDENCE_LEVEL", f"evidence_level must be one of {sorted(EVIDENCE_LEVELS)}")
        level = "static"
    if mode == "hardware" and level != "hardware":
        result.error("FALSE_HARDWARE_CLAIM", "hardware mode requires evidence_level=hardware")
    if mode == "offline" and level == "hardware":
        result.warn("HARDWARE_IN_OFFLINE_MODE", "hardware evidence was supplied but only offline checks were requested")

    if mode == "hardware":
        if evidence.get("overlay_downloaded") is not True:
            result.error("OVERLAY_NOT_DOWNLOADED", "hardware evidence must record overlay_downloaded=true")
        board_observation = evidence.get("board_observation")
        if not isinstance(board_observation, dict) or not board_observation.get("model") or not board_observation.get("compatible"):
            result.error("BOARD_OBSERVATION", "hardware evidence needs observed model and compatible strings")
        else:
            observed = f"{board_observation.get('model')} {board_observation.get('compatible')}"
            for token in profile.get("board", {}).get("compatibility_contains", []):
                result.check("BOARD_COMPATIBILITY", token in observed, f"board observation must contain compatibility token {token!r}")
        interrupt_inventory = evidence.get("interrupt_inventory", [])
        for required in profile.get("overlay", {}).get("required_interrupts", []):
            ok = isinstance(interrupt_inventory, list) and any(
                isinstance(item, str) and (item == required or item.endswith("/" + required) or required in item)
                for item in interrupt_inventory
            )
            result.check("HARDWARE_INTERRUPT", ok, f"PYNQ inventory must expose required interrupt {required!r}")

    supplied_hashes = evidence.get("artifact_hashes")
    if not isinstance(supplied_hashes, dict):
        result.error("EVIDENCE_HASHES", "run evidence must contain artifact_hashes")
    else:
        for name in ("bit", "hwh"):
            result.check(
                f"EVIDENCE_{name.upper()}_HASH",
                supplied_hashes.get(name) == result.artifact_hashes.get(name),
                f"evidence {name} hash must match validated artifact",
            )

    reads = evidence.get("register_reads")
    identities = profile.get("register_contract", {}).get("identity", [])
    if not isinstance(reads, dict):
        result.error("REGISTER_READS", "run evidence must contain register_reads")
    else:
        for item in identities:
            name = item.get("register")
            actual = reads.get(name)
            mask = item.get("mask", 0xFFFFFFFF)
            expected = item.get("expected")
            ok = isinstance(actual, int) and isinstance(expected, int) and (actual & mask) == (expected & mask)
            result.check("IDENTITY_READ", ok, f"identity register {name!r} must match expected value")

    runs = evidence.get("dma_runs")
    by_id = {item.get("id"): item for item in runs if isinstance(item, dict)} if isinstance(runs, list) else {}
    dma = profile.get("dma_contract", {})
    for test in profile.get("self_tests", []):
        test_id = test.get("id")
        run = by_id.get(test_id)
        if not isinstance(run, dict):
            result.error("DMA_RUN_MISSING", f"no evidence for self test {test_id!r}")
            continue
        result.check("DMA_LENGTH", run.get("length_bytes") == test.get("length_bytes"), f"DMA run {test_id!r} length must match")
        result.check("DMA_TIMEOUT", run.get("timed_out") is False, f"DMA run {test_id!r} must not time out")
        result.check("DMA_ERROR", run.get("dma_error") is False, f"DMA run {test_id!r} must have no DMA error")
        result.check("DMA_COMPLETE", run.get("mm2s_completed") is True and run.get("s2mm_completed") is True, f"DMA run {test_id!r} must complete both channels")
        if dma.get("tlast_required") is True:
            result.check("DMA_TLAST", run.get("tlast_observed") is True, f"DMA run {test_id!r} must observe TLAST completion")
        operations = set(run.get("cache_operations", [])) if isinstance(run.get("cache_operations"), list) else set()
        if dma.get("cache_policy", {}).get("tx") == "flush":
            result.check("CACHE_TX", "tx.flush" in operations, f"DMA run {test_id!r} must record tx.flush")
        if dma.get("cache_policy", {}).get("rx") == "invalidate":
            result.check("CACHE_RX", "rx.invalidate" in operations, f"DMA run {test_id!r} must record rx.invalidate")
        result.check("GOLDEN_EXACT", run.get("mismatch_count") == 0, f"DMA run {test_id!r} must exactly match golden")
    return str(level)


def validate(profile_path: Path, evidence_path: Path | None, mode: str) -> tuple[dict[str, Any], int]:
    # Malformed nested contracts must produce a failure report, not a traceback.
    try:
        return _validate(profile_path, evidence_path, mode)
    except (TypeError, ValueError, KeyError, AttributeError, OSError, OverflowError) as exc:
        result = Result(mode)
        result.error("INVALID_INPUT", f"{type(exc).__name__}: {exc}")
        return result.report("static"), 2


def _validate(profile_path: Path, evidence_path: Path | None, mode: str) -> tuple[dict[str, Any], int]:
    result = Result(mode)
    evidence: dict[str, Any] | None = None
    try:
        profile = read_json(profile_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result.error("PROFILE_PARSE", str(exc))
        return result.report("static"), 2
    result.profile_id = str(profile.get("profile_id", "unknown"))
    if profile.get("schema_version") != 1:
        result.error("SCHEMA_VERSION", "schema_version must be 1")
    required_text(profile, "profile_id", result, "profile")
    validate_overlay(profile_path, profile, result)
    validate_registers(profile, result)
    validate_dma(profile, result)

    if evidence_path is not None:
        try:
            evidence = read_json(evidence_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result.error("EVIDENCE_PARSE", str(exc))
    evidence_level = "static"
    if evidence is not None:
        evidence_level = validate_run_evidence(profile, evidence, mode, result)
    elif mode == "hardware":
        result.error("HARDWARE_EVIDENCE_REQUIRED", "hardware mode requires --evidence")
    validate_acceptance(profile, evidence, result)
    report = result.report(evidence_level)
    return report, 1 if result.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--mode", choices=("offline", "hardware"), default="offline")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report, exit_code = validate(args.profile.resolve(), args.evidence.resolve() if args.evidence else None, args.mode)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
