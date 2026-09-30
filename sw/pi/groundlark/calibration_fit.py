"""Offline static affine calibration from bounded, intact SSREC intervals.

Reference values and acceptance limits come from the operator. This does not
estimate mechanical response, phase, cross-axis alignment or clock accuracy.
"""
import hashlib
import json
import math
from pathlib import Path

from groundlark_contract.validation import require
from .calibration import Calibrations, VECTORS, canonical, configuration_hash, raw_values
from .recording import Reader, is_acquisition_metadata
from .session import Sessions

SUPPORTED = {1: {"acceleration_m_s2", "angular_rate_rad_s", "temperature_k"},
             2: {"acceleration_m_s2", "angular_rate_rad_s", "temperature_k"},
             3: {"acceleration_m_s2", "angular_rate_rad_s", "temperature_k"},
             9: {"geophone_input_v"}}


def digest(path):
    require(path.stat().st_size <= 256 * 1024 * 1024, "calibration recording exceeds 256 MiB")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def numbers(value, count, name, positive=False):
    require(isinstance(value, list) and len(value) == count and
            all(type(x) in (int, float) and math.isfinite(x) and
                (not positive or x > 0) for x in value), name)
    return value


def observe(path, device, sensor, field, first, last, allow_simulation=False):
    require(type(first) is int and type(last) is int and 0 <= first <= last and
            32 <= last - first + 1 <= 100000, "select 32..100000 consecutive sequences")
    before = digest(path)
    count, mean, m2, binding, previous = 0, [], [], None, None
    with path.open("rb") as stream:
        reader = Reader(stream)
        require(is_acquisition_metadata(reader.metadata), "acquisition recording required")
        simulated = reader.metadata.get("source") == "simulation"
        require(allow_simulation or not simulated, "simulation requires --allow-simulation")
        sessions = Sessions(Calibrations(reader.metadata.get("calibrations", [])))
        completed = False
        for _, item in reader:
            completed = isinstance(item, dict) and item.get("code") == "acquisition_summary"
            if isinstance(item, dict):
                if item.get("code") == "usb_disconnected": sessions.disconnect(item.get("device"))
                continue
            kind = sessions.accept(item)
            if kind != "batch" or item.device_id != device or item.batch.sensor_id != sensor:
                continue
            cfg = sessions.devices[device].settings[sensor]
            for index, sample in enumerate(item.batch.samples):
                if not first <= sample.sequence <= last: continue
                current = (item.boot_id, configuration_hash(cfg))
                require(binding is None or binding == current, "boot/configuration changed in calibration interval")
                binding = current
                require(sample.quality == 1, "calibration interval contains missing, saturated or faulty data")
                require(previous is None or sample.sequence == previous + 1, "calibration interval has sequence loss")
                if index == 0:
                    require(item.batch.HasField("dropped_before") and item.batch.dropped_before == 0,
                            "calibration interval has known or unknown loss")
                values = raw_values(sample, field)
                if not count: mean, m2 = [0.] * len(values), [0.] * len(values)
                count += 1
                for i, x in enumerate(values):
                    delta = x - mean[i]
                    mean[i] += delta / count
                    m2[i] += delta * (x - mean[i])
                previous = sample.sequence
        require(completed, "recording has no final acquisition summary")
    require(count == last - first + 1, "requested interval incomplete or ambiguous")
    require(digest(path) == before, "recording changed during calibration")
    return dict(recording_sha256=before, first_sequence=first, last_sequence=last,
                boot_id=binding[0], configuration_sha256=binding[1], samples=count,
                raw_mean=mean, raw_stddev=[math.sqrt(max(0, x) / (count - 1)) for x in m2],
                simulation=simulated)


def fit(spec, base, allow_simulation=False):
    require(set(spec) == {"version", "device_id", "sensor_id", "provenance", "conditions", "fields"}, "fit specification keys")
    require(spec["version"] == 1 and type(spec["sensor_id"]) is int and spec["sensor_id"] in SUPPORTED, "fit version/sensor")
    require(isinstance(spec["conditions"], str) and 0 < len(spec["conditions"]) <= 1024, "record temperature, fixture and reference identification in conditions")
    require(isinstance(spec["fields"], dict) and 1 <= len(spec["fields"]) <= 3, "fit fields")
    evidence = dict(format="groundlark-static-calibration-v1", specification=spec, fields={})
    coefficients, ranges, hashes, simulated = {}, {}, set(), set()
    for field, request in spec["fields"].items():
        require(field in SUPPORTED[spec["sensor_id"]], "unsupported static calibration field")
        require(set(request) == {"max_stddev_counts", "max_residual_si", "observations"}, "field specification keys")
        n = 3 if field in VECTORS else 1
        limits = numbers(request["max_stddev_counts"], n, "positive count stability limits required", True)
        residual_limits = numbers(request["max_residual_si"], n, "positive SI residual limits required", True)
        observations = request["observations"]
        require(isinstance(observations, list) and 3 <= len(observations) <= 12, "use 3..12 reference observations")
        rows = []
        intervals = {}
        for point in observations:
            require(set(point) == {"recording", "first_sequence", "last_sequence", "reference_si", "reference_uncertainty_si"}, "observation keys")
            reference = numbers(point["reference_si"], n, "finite SI references required")
            uncertainty = numbers(point["reference_uncertainty_si"], n, "positive reference uncertainties required", True)
            require(isinstance(point["recording"], str) and bool(point["recording"]), "recording path required")
            path = Path(base) / point["recording"]
            row = observe(path, spec["device_id"], spec["sensor_id"], field,
                          point["first_sequence"], point["last_sequence"], allow_simulation)
            key = (row["recording_sha256"], row["boot_id"])
            interval = (point["first_sequence"], point["last_sequence"])
            require(all(interval[1] < a or interval[0] > b for a, b in intervals.get(key, [])), "reference intervals overlap")
            intervals.setdefault(key, []).append(interval)
            require(all(x <= limit for x, limit in zip(row["raw_stddev"], limits)), "reference interval exceeds stability limit")
            row.update(reference_si=reference, reference_uncertainty_si=uncertainty)
            rows.append(row)
            hashes.add(row["configuration_sha256"])
            simulated.add(row["simulation"])
        scales, offsets, residuals = [], [], []
        for axis in range(n):
            xs = [r["raw_mean"][axis] for r in rows]
            ys = [r["reference_si"][axis] for r in rows]
            require(len(set(ys)) >= 3 and min(ys) < 0 < max(ys) if field != "temperature_k" else len(set(ys)) >= 3,
                    "each axis needs three distinct references spanning negative, zero and positive (temperature: three temperatures)")
            xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
            xx = sum((x - xm) ** 2 for x in xs)
            require(xx > 0, "zero raw reference span")
            scale = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / xx
            offset = ym - scale * xm
            residual = [y - (scale * x + offset) for x, y in zip(xs, ys)]
            require(math.isfinite(scale) and scale != 0 and math.isfinite(offset), "invalid fitted coefficients")
            require(max(abs(x) for x in residual) <= residual_limits[axis], "affine fit exceeds residual limit")
            scales.append(scale); offsets.append(offset); residuals.append(residual)
        coefficients[field] = dict(scale=scales, offset=offsets)
        ranges[field] = [[min(r["raw_mean"][i] for r in rows), max(r["raw_mean"][i] for r in rows)] for i in range(n)]
        evidence["fields"][field] = dict(observations=rows, residual_si_by_axis=residuals,
                                       raw_min=[min(r["raw_mean"][i] for r in rows) for i in range(n)],
                                       raw_max=[max(r["raw_mean"][i] for r in rows) for i in range(n)])
    require(len(hashes) == 1, "all references must use identical effective sensor configuration")
    require(len(simulated) == 1, "cannot mix simulated and physical observations")
    evidence["simulation"] = simulated.pop()
    evidence["limits"] = "Static affine fit only. Residuals and sample scatter are not a combined uncertainty budget. Validity outside the measured range and conditions is unqualified."
    record = dict(version=2, device_id=spec["device_id"], sensor_id=spec["sensor_id"],
                  configuration_sha256=hashes.pop(), provenance=spec["provenance"],
                  fields=coefficients, raw_limits=ranges, method="static-affine",
                  evidence_sha256=hashlib.sha256(canonical(evidence)).hexdigest())
    Calibrations([record])
    return record, evidence


def write_fit(spec_path, output, allow_simulation=False):
    from .cli import load_json
    output = Path(output)
    evidence_path = output.with_suffix(output.suffix + ".evidence.json")
    require(not output.exists() and not evidence_path.exists(), "calibration output already exists")
    record, evidence = fit(load_json(spec_path, 65536), Path(spec_path).parent, allow_simulation)
    # Evidence first: an interrupted write never leaves a usable calibration
    # referring to evidence that was not successfully written.
    with evidence_path.open("x", encoding="utf8") as stream:
        stream.write(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    with output.open("x", encoding="utf8") as stream:
        stream.write(json.dumps([record], indent=2, allow_nan=False) + "\n")
    return dict(calibration=str(output), evidence=str(evidence_path),
                calibration_id=Calibrations().add(record), simulation=evidence["simulation"])
