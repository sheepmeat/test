"""Deterministic M-PROT-4 replay fixtures.

This module owns only fixture construction.  It imports the canonical SW-01
``Sample`` and ``StreamBundle`` classes and never recreates or bypasses the
M-PROT-3 runtime.  A fixture is a compact specification plus a deterministic
materialisation of the samples that Grok1's tests can pass to
``MProt3IntegrationRuntime.ingest_bundle`` and ``try_infer``.

The generated timestamps are semantic source timestamps in seconds.  Replay
is offline and never sleeps, claims transport timing, or mutates runtime code.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from adapters.mmwave_sw01_interface_checker import Sample, StreamBundle


SCHEMA_VERSION = "M_PROT_4_DETERMINISTIC_REPLAY_FIXTURE_SPEC_V1"
FIXTURE_MATERIALIZATION_VERSION = "M_PROT_4_DETERMINISTIC_REPLAY_MATERIALIZATION_V1"
DEFAULT_START_TIMESTAMP_S = 1_000.0
DEFAULT_START_SEQ = 10_000
DEFAULT_SESSION_ID = "M_PROT_4_SESSION_A"
DEFAULT_DEVICE_IDENTITY = "M_PROT_4_FIXTURE_DEVICE"
DEFAULT_INTERFACE_IDENTITY = "fixture:m-prot-4"
DEFAULT_CONFIGURATION_IDENTITY = "M_PROT_4_CFG_V1"
DEFAULT_OBSERVATION_KIND = "near_raw_phase"
DEFAULT_WAVEFORM_PROFILE = "sine"
DEFAULT_FREQUENCY_HZ = 0.25
DEFAULT_AMPLITUDE = 1.0
DEFAULT_SEED = 11

SUPPORTED_CASES = frozenset(
    {
        "VALID_10HZ_30S",
        "VALID_20HZ_30S_MULTIBUNDLE",
        "VALID_LONGER_THAN_WINDOW",
        "INSUFFICIENT_DURATION",
        "SEQ_GAP",
        "SEQ_REGRESSION",
        "TIMESTAMP_REGRESSION",
        "LARGE_TIMESTAMP_GAP",
        "SESSION_TRANSITION",
        "RESET",
        "HEALTH_FAILURE",
        "MISSING_PHASE",
        "SCALAR_RR_ONLY",
        "IDENTITY_CHANGE",
        "CONFIGURATION_CHANGE",
        "BELOW_10HZ",
    }
)

SUPPORTED_MUTATIONS = frozenset(
    {
        "seq_gap",
        "seq_regression",
        "timestamp_regression",
        "large_timestamp_gap",
        "session_transition",
        "reset",
        "health_failure",
        "missing_phase",
        "scalar_rr_only",
        "identity_change",
        "configuration_change",
        "insufficient_duration",
        "low_sample_rate",
    }
)


def _canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON without path-dependent or insertion-order-dependent data."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _finite_float(value: Any, *, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _as_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if float(value) != float(result):
        raise ValueError(f"{name} must be an integer")
    return result


@dataclass(frozen=True)
class Mutation:
    """One explicit semantic mutation applied in declaration order."""

    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Mutation":
        if not isinstance(value, Mapping):
            raise ValueError("mutation must be an object")
        kind = str(value.get("type", value.get("kind", ""))).strip()
        if kind not in SUPPORTED_MUTATIONS:
            raise ValueError(f"unsupported M-PROT-4 mutation: {kind!r}")
        params = {str(k): copy.deepcopy(v) for k, v in value.items() if k not in {"type", "kind"}}
        # Fail early if a future caller attempts to put non-JSON objects in a
        # fixture spec.  This also keeps the checksum representation stable.
        _canonical_json_bytes(params)
        return cls(kind=kind, params=params)

    def to_mapping(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.kind}
        payload.update(copy.deepcopy(dict(self.params)))
        return payload


@dataclass(frozen=True)
class FixtureSpec:
    """Compact, JSON-compatible replay specification."""

    fixture_id: str
    case: str
    sample_rate_hz: float
    duration_s: float
    waveform_profile: str = DEFAULT_WAVEFORM_PROFILE
    frequency_hz: float = DEFAULT_FREQUENCY_HZ
    amplitude: float = DEFAULT_AMPLITUDE
    seed: int = DEFAULT_SEED
    bundle_partition: tuple[int, ...] = ()
    start_timestamp_s: float = DEFAULT_START_TIMESTAMP_S
    start_seq: int = DEFAULT_START_SEQ
    session_id: str = DEFAULT_SESSION_ID
    device_identity: str = DEFAULT_DEVICE_IDENTITY
    interface_identity: str = DEFAULT_INTERFACE_IDENTITY
    configuration_identity: str = DEFAULT_CONFIGURATION_IDENTITY
    observation_kind: str = DEFAULT_OBSERVATION_KIND
    health_ok: bool = True
    mutations: tuple[Mutation, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FixtureSpec":
        if not isinstance(value, Mapping):
            raise ValueError("fixture spec must be an object")
        mutations = tuple(
            Mutation.from_mapping(item) for item in (value.get("mutations") or ())
        )
        partition = tuple(
            _as_int(item, name="bundle_partition entry")
            for item in (value.get("bundle_partition") or ())
        )
        spec = cls(
            fixture_id=str(value.get("fixture_id", "")).strip(),
            case=str(value.get("case", "")).strip(),
            sample_rate_hz=_finite_float(value.get("sample_rate_hz"), name="sample_rate_hz"),
            duration_s=_finite_float(value.get("duration_s"), name="duration_s"),
            waveform_profile=str(value.get("waveform_profile", DEFAULT_WAVEFORM_PROFILE)),
            frequency_hz=_finite_float(value.get("frequency_hz", DEFAULT_FREQUENCY_HZ), name="frequency_hz"),
            amplitude=_finite_float(value.get("amplitude", DEFAULT_AMPLITUDE), name="amplitude"),
            seed=_as_int(value.get("seed", DEFAULT_SEED), name="seed"),
            bundle_partition=partition,
            start_timestamp_s=_finite_float(
                value.get("start_timestamp_s", DEFAULT_START_TIMESTAMP_S),
                name="start_timestamp_s",
            ),
            start_seq=_as_int(value.get("start_seq", DEFAULT_START_SEQ), name="start_seq"),
            session_id=str(value.get("session_id", DEFAULT_SESSION_ID)),
            device_identity=str(value.get("device_identity", DEFAULT_DEVICE_IDENTITY)),
            interface_identity=str(value.get("interface_identity", DEFAULT_INTERFACE_IDENTITY)),
            configuration_identity=str(
                value.get("configuration_identity", DEFAULT_CONFIGURATION_IDENTITY)
            ),
            observation_kind=str(value.get("observation_kind", DEFAULT_OBSERVATION_KIND)),
            health_ok=bool(value.get("health_ok", True)),
            mutations=mutations,
        )
        _validate_spec_shape(spec)
        return spec

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "fixture_id": self.fixture_id,
            "case": self.case,
            "sample_rate_hz": self.sample_rate_hz,
            "duration_s": self.duration_s,
            "waveform_profile": self.waveform_profile,
            "frequency_hz": self.frequency_hz,
            "amplitude": self.amplitude,
            "seed": self.seed,
            "bundle_partition": list(self.bundle_partition),
            "start_timestamp_s": self.start_timestamp_s,
            "start_seq": self.start_seq,
            "session_id": self.session_id,
            "device_identity": self.device_identity,
            "interface_identity": self.interface_identity,
            "configuration_identity": self.configuration_identity,
            "observation_kind": self.observation_kind,
            "health_ok": self.health_ok,
            "mutations": [mutation.to_mapping() for mutation in self.mutations],
        }

    def effective_sample_rate_hz(self) -> float:
        rate = self.sample_rate_hz
        for mutation in self.mutations:
            if mutation.kind == "low_sample_rate":
                rate = _finite_float(
                    mutation.params.get("sample_rate_hz", 5.0),
                    name="low_sample_rate.sample_rate_hz",
                )
        return rate

    def effective_duration_s(self) -> float:
        duration = self.duration_s
        for mutation in self.mutations:
            if mutation.kind == "insufficient_duration":
                duration = _finite_float(
                    mutation.params.get("duration_s", 2.0),
                    name="insufficient_duration.duration_s",
                )
        return duration


@dataclass(frozen=True)
class ReplayResult:
    """Receipts produced by replaying a fixture through a caller-owned runtime."""

    sw01_receipts: tuple[dict[str, Any], ...]
    inference_receipt: Any | None


@dataclass(frozen=True)
class ReplayFixture:
    """Materialised SW-01 bundles and their deterministic content hash."""

    spec: FixtureSpec
    bundles: tuple[StreamBundle, ...]
    sample_rate_hz: float
    duration_s: float
    sample_count: int
    canonical_bytes: bytes
    fixture_sha256: str

    @property
    def samples(self) -> tuple[Sample, ...]:
        return tuple(sample for bundle in self.bundles for sample in bundle.samples)

    @property
    def bundle_partition(self) -> tuple[int, ...]:
        return tuple(len(bundle.samples) for bundle in self.bundles)

    def replay_into(
        self,
        runtime: Any,
        *,
        infer: bool = True,
        mode: str = "FIXTURE_OFFLINE_VALIDATION",
        infer_kwargs: Mapping[str, Any] | None = None,
    ) -> ReplayResult:
        """Replay through the real runtime methods without sleeping or bypassing SW-01."""

        receipts: list[dict[str, Any]] = []
        for bundle in self.bundles:
            receipts.append(runtime.ingest_bundle(bundle, mode=mode))
        inference = None
        if infer:
            inference = runtime.try_infer(**dict(infer_kwargs or {}))
        return ReplayResult(tuple(receipts), inference)


def _validate_spec_shape(spec: FixtureSpec) -> None:
    if not spec.fixture_id:
        raise ValueError("fixture_id is required")
    if spec.case not in SUPPORTED_CASES:
        raise ValueError(f"unsupported M-PROT-4 fixture case: {spec.case!r}")
    if spec.waveform_profile != DEFAULT_WAVEFORM_PROFILE:
        raise ValueError(f"unsupported waveform_profile: {spec.waveform_profile!r}")
    if spec.effective_sample_rate_hz() <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if spec.effective_duration_s() <= 0.0:
        raise ValueError("duration_s must be positive")
    if spec.frequency_hz < 0.0:
        raise ValueError("frequency_hz must be non-negative")
    if not spec.session_id or not spec.device_identity or not spec.interface_identity:
        raise ValueError("session and identity fields must be non-empty")
    if not spec.configuration_identity:
        raise ValueError("configuration_identity must be non-empty")
    if not isinstance(spec.health_ok, bool):
        raise ValueError("health_ok must be boolean")


def _sample_count(spec: FixtureSpec) -> int:
    count = int(round(spec.effective_sample_rate_hz() * spec.effective_duration_s())) + 1
    if count < 2:
        raise ValueError("fixture must contain at least two samples")
    return count


def _partition(spec: FixtureSpec, count: int) -> tuple[int, ...]:
    if spec.bundle_partition:
        partition = tuple(spec.bundle_partition)
        if any(size <= 0 for size in partition):
            raise ValueError("bundle_partition entries must be positive")
        if sum(partition) != count:
            raise ValueError(
                f"bundle_partition sum {sum(partition)} does not equal sample count {count}"
            )
        return partition
    return (count,)


def _starts(partition: Sequence[int]) -> tuple[int, ...]:
    starts: list[int] = []
    cursor = 0
    for size in partition:
        starts.append(cursor)
        cursor += size
    return tuple(starts)


def _mutation_index(
    mutation: Mutation,
    *,
    count: int,
    partition: Sequence[int],
    default: int = 0,
) -> int:
    if "index" in mutation.params:
        index = _as_int(mutation.params["index"], name=f"{mutation.kind}.index")
    elif "bundle_index" in mutation.params:
        bundle_index = _as_int(
            mutation.params["bundle_index"], name=f"{mutation.kind}.bundle_index"
        )
        if bundle_index < 0 or bundle_index >= len(partition):
            raise ValueError(f"{mutation.kind}.bundle_index is outside bundle partition")
        index = _starts(partition)[bundle_index]
    else:
        index = default
    if index < 0 or index >= count:
        raise ValueError(f"{mutation.kind}.index is outside sample range")
    return index


def _seed_phase_offset(seed: int) -> float:
    """Map an explicit integer seed to a stable phase offset without RNG state."""

    # The modulo operation is intentional: no platform-specific PRNG or
    # uncontrolled entropy enters a fixture.  The seed remains in metadata.
    return (seed % 360) * math.pi / 180.0


def _apply_mutations(
    spec: FixtureSpec,
    *,
    count: int,
    sample_rate_hz: float,
    partition: Sequence[int],
) -> tuple[
    list[float],
    list[int],
    list[str | None],
    list[float | None],
    list[float | None],
    list[bool],
    list[bool],
    list[str | None],
    str,
    dict[int, dict[str, str]],
]:
    times = [
        spec.start_timestamp_s + float(index) / sample_rate_hz
        for index in range(count)
    ]
    seqs = [spec.start_seq + index for index in range(count)]
    sessions: list[str | None] = [spec.session_id for _ in range(count)]
    phase_offset = _seed_phase_offset(spec.seed)
    phases: list[float | None] = [
        spec.amplitude
        * math.sin(2.0 * math.pi * spec.frequency_hz * (index / sample_rate_hz) + phase_offset)
        for index in range(count)
    ]
    scalar_rrs: list[float | None] = [None for _ in range(count)]
    health: list[bool] = [spec.health_ok for _ in range(count)]
    resets: list[bool] = [False for _ in range(count)]
    fault_codes: list[str | None] = [None for _ in range(count)]
    observation_kind = spec.observation_kind
    bundle_overrides: dict[int, dict[str, str]] = {}

    for mutation in spec.mutations:
        kind = mutation.kind
        if kind in {"insufficient_duration", "low_sample_rate"}:
            # These two cases are parameterised at FixtureSpec level before
            # materialisation; retaining the mutation in the spec preserves
            # the requested provenance without a second post-hoc rewrite.
            continue
        if kind in {"seq_gap", "seq_regression"}:
            index = _mutation_index(mutation, count=count, partition=partition, default=0)
            default_delta = 2 if kind == "seq_gap" else -2
            delta = _as_int(mutation.params.get("delta", default_delta), name=f"{kind}.delta")
            for i in range(index, count):
                seqs[i] += delta
            continue
        if kind in {"timestamp_regression", "large_timestamp_gap"}:
            index = _mutation_index(mutation, count=count, partition=partition, default=0)
            default_delta = -0.2 if kind == "timestamp_regression" else 1.0
            delta = _finite_float(mutation.params.get("delta_s", default_delta), name=f"{kind}.delta_s")
            for i in range(index, count):
                times[i] += delta
            continue
        if kind == "session_transition":
            index = _mutation_index(mutation, count=count, partition=partition, default=0)
            new_session = str(mutation.params.get("session_id", f"{spec.session_id}_B"))
            if not new_session:
                raise ValueError("session_transition.session_id must be non-empty")
            for i in range(index, count):
                sessions[i] = new_session
            continue
        if kind == "reset":
            index = _mutation_index(mutation, count=count, partition=partition, default=0)
            resets[index] = True
            continue
        if kind == "health_failure":
            index = _mutation_index(mutation, count=count, partition=partition, default=0)
            health[index] = False
            fault_codes[index] = str(mutation.params.get("fault_code", "FIXTURE_HEALTH_FAILURE"))
            continue
        if kind == "missing_phase":
            indices = mutation.params.get("indices")
            if indices is None:
                indices = [_mutation_index(mutation, count=count, partition=partition, default=0)]
            for raw_index in indices:
                index = _as_int(raw_index, name="missing_phase.index")
                if index < 0 or index >= count:
                    raise ValueError("missing_phase.index is outside sample range")
                phases[index] = None
            continue
        if kind == "scalar_rr_only":
            observation_kind = "scalar_vendor_rr"
            scalar_value = _finite_float(
                mutation.params.get("rr_bpm", 16.0), name="scalar_rr_only.rr_bpm"
            )
            phases = [None for _ in range(count)]
            scalar_rrs = [scalar_value for _ in range(count)]
            continue
        if kind in {"identity_change", "configuration_change"}:
            field_name = "device_identity" if kind == "identity_change" else "configuration_identity"
            bundle_index = _as_int(mutation.params.get("bundle_index", 1), name=f"{kind}.bundle_index")
            if bundle_index <= 0 or bundle_index >= len(partition):
                raise ValueError(f"{kind} requires a non-first bundle_index")
            value = str(
                mutation.params.get(
                    "value",
                    f"{getattr(spec, field_name)}_CHANGED",
                )
            )
            if not value:
                raise ValueError(f"{kind}.value must be non-empty")
            bundle_overrides.setdefault(bundle_index, {})[field_name] = value
            continue
        raise ValueError(f"unhandled M-PROT-4 mutation: {kind}")

    return (
        times,
        seqs,
        sessions,
        phases,
        scalar_rrs,
        health,
        resets,
        fault_codes,
        observation_kind,
        bundle_overrides,
    )


def _sample_payload(sample: Sample) -> dict[str, Any]:
    return {
        "t": sample.t,
        "phase": sample.phase,
        "seq": sample.seq,
        "health_ok": sample.health_ok,
        "fault_code": sample.fault_code,
        "session_id": sample.session_id,
        "reset_flag": sample.reset_flag,
        "scalar_rr": sample.scalar_rr,
    }


def _bundle_payload(bundle: StreamBundle) -> dict[str, Any]:
    return {
        "device_identity": bundle.device_identity,
        "interface_identity": bundle.interface_identity,
        "configuration_identity": bundle.configuration_identity,
        "observation_kind": bundle.observation_kind,
        "backend_error": bundle.backend_error,
        "source_faults": list(bundle.source_faults),
        "samples": [_sample_payload(sample) for sample in bundle.samples],
    }


def _validate_materialized(spec: FixtureSpec, fixture: ReplayFixture) -> None:
    if len(fixture.samples) != fixture.sample_count:
        raise AssertionError("materialized sample count mismatch")
    if fixture.bundle_partition != _partition(spec, fixture.sample_count):
        raise AssertionError("materialized bundle partition mismatch")
    if fixture.samples[0].t != spec.start_timestamp_s:
        raise AssertionError("start timestamp was not preserved")
    if fixture.samples[0].seq != spec.start_seq:
        raise AssertionError("start sequence was not preserved")
    if any(not isinstance(bundle, StreamBundle) for bundle in fixture.bundles):
        raise AssertionError("fixture did not produce SW-01 StreamBundle objects")
    if any(not isinstance(sample, Sample) for sample in fixture.samples):
        raise AssertionError("fixture did not produce SW-01 Sample objects")


def generate_fixture(spec: FixtureSpec) -> ReplayFixture:
    """Materialise one spec into real SW-01-compatible bundles."""

    _validate_spec_shape(spec)
    sample_rate_hz = spec.effective_sample_rate_hz()
    duration_s = spec.effective_duration_s()
    count = _sample_count(spec)
    partition = _partition(spec, count)
    (
        times,
        seqs,
        sessions,
        phases,
        scalar_rrs,
        health,
        resets,
        fault_codes,
        observation_kind,
        bundle_overrides,
    ) = _apply_mutations(
        spec,
        count=count,
        sample_rate_hz=sample_rate_hz,
        partition=partition,
    )

    samples = [
        Sample(
            t=float(times[index]),
            phase=None if phases[index] is None else float(phases[index]),
            seq=int(seqs[index]),
            health_ok=bool(health[index]),
            fault_code=fault_codes[index],
            session_id=sessions[index],
            reset_flag=bool(resets[index]),
            scalar_rr=None if scalar_rrs[index] is None else float(scalar_rrs[index]),
        )
        for index in range(count)
    ]

    bundles: list[StreamBundle] = []
    cursor = 0
    for bundle_index, size in enumerate(partition):
        metadata: dict[str, str | None] = {
            "device_identity": spec.device_identity,
            "interface_identity": spec.interface_identity,
            "configuration_identity": spec.configuration_identity,
            "observation_kind": observation_kind,
        }
        metadata.update(bundle_overrides.get(bundle_index, {}))
        bundles.append(
            StreamBundle(
                device_identity=metadata["device_identity"],
                interface_identity=metadata["interface_identity"],
                configuration_identity=metadata["configuration_identity"],
                observation_kind=metadata["observation_kind"],
                samples=samples[cursor : cursor + size],
            )
        )
        cursor += size

    payload = {
        "materialization_version": FIXTURE_MATERIALIZATION_VERSION,
        "spec": spec.to_mapping(),
        "effective": {
            "sample_rate_hz": sample_rate_hz,
            "duration_s": duration_s,
            "sample_count": count,
            "bundle_partition": list(partition),
        },
        "bundles": [_bundle_payload(bundle) for bundle in bundles],
    }
    canonical_bytes = _canonical_json_bytes(payload)
    fixture = ReplayFixture(
        spec=spec,
        bundles=tuple(bundles),
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        sample_count=count,
        canonical_bytes=canonical_bytes,
        fixture_sha256=hashlib.sha256(canonical_bytes).hexdigest(),
    )
    _validate_materialized(spec, fixture)
    return fixture


def fixture_spec_sha256(spec: FixtureSpec) -> str:
    """Hash the compact spec itself, independent of its materialisation."""

    return hashlib.sha256(_canonical_json_bytes(spec.to_mapping())).hexdigest()


def load_fixture_catalog(path: Path) -> tuple[FixtureSpec, ...]:
    """Load a catalog containing ``{"fixtures": [...]}`` specs."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unexpected fixture catalog schema: {raw.get('schema_version')!r}")
    fixtures = tuple(FixtureSpec.from_mapping(item) for item in (raw.get("fixtures") or ()))
    if not fixtures:
        raise ValueError("fixture catalog is empty")
    ids = [fixture.fixture_id for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("fixture_id values must be unique")
    return fixtures


def load_fixture(path: Path, *, fixture_id: str | None = None) -> ReplayFixture:
    """Load one compact spec or select one item from a catalog."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if "fixtures" in raw:
        candidates = load_fixture_catalog(path)
        if fixture_id is None:
            if len(candidates) != 1:
                raise ValueError("fixture_id is required when loading a multi-fixture catalog")
            spec = candidates[0]
        else:
            matches = [candidate for candidate in candidates if candidate.fixture_id == fixture_id]
            if len(matches) != 1:
                raise KeyError(f"unknown fixture_id: {fixture_id}")
            spec = matches[0]
    else:
        spec = FixtureSpec.from_mapping(raw)
    return generate_fixture(spec)


__all__ = [
    "DEFAULT_OBSERVATION_KIND",
    "FIXTURE_MATERIALIZATION_VERSION",
    "FixtureSpec",
    "Mutation",
    "ReplayFixture",
    "ReplayResult",
    "SCHEMA_VERSION",
    "SUPPORTED_CASES",
    "SUPPORTED_MUTATIONS",
    "Sample",
    "StreamBundle",
    "fixture_spec_sha256",
    "generate_fixture",
    "load_fixture",
    "load_fixture_catalog",
]
