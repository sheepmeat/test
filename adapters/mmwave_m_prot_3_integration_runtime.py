"""M-PROT-3 integration runtime wiring.

Composes (does not reimplement):
  SW-01 source validation
    → causal temporal composer (30 s / past-only)
    → NativeTraceInput
    → R1 adapt_native_trace
    → M-PROT-2 B23 runtime

Semantics:
  PROTOTYPE_INTEGRATION_ONLY / NOT_FINAL_SELECTED_MODEL / SUBJECT_TO_REPLACEMENT
  PROVISIONAL_INTEGRATION_FREEZE = true
  No M-N9 fallback. No UART protocol invention.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from adapters.mmwave_m_prot_2_b23_runtime import (
    CANONICAL_PARAMETER_SHA256,
    CANDIDATE_ID,
    PANEL_ID,
    PRIMARY_REPRESENTATION,
    SAMPLE_RATE_HZ,
    SCALER_CONTENT_SHA256,
    SOURCE_ARTIFACT_REL,
    SOURCE_ARTIFACT_SHA256,
    TRACE_SAMPLES,
    WINDOW_DURATION_S,
    PrototypeFailClosed,
    PrototypeReceipt,
    resolve_verified_runtime,
    run_prototype_inference,
)
from adapters.mmwave_r1_sensor_independent_trace import (
    R1_PROFILE_ID,
    NativeTraceInput,
    R1TraceError,
    adapt_native_trace,
)
from adapters.mmwave_sw01_interface_checker import (
    STATUS_PASS,
    Sample,
    StreamBundle,
    evaluate_stream,
)

PHASE_ID = "M-PROT-3"
RUNTIME_MODULE = "adapters/mmwave_m_prot_3_integration_runtime.py"
WINDOW_CONTRACT = "M_PROT_3_CAUSAL_30S_10HZ_300_V1"
PRODUCTION_INFERENCE_CADENCE = "NOT_GOVERNED_IN_M_PROT_3"

MANDATORY_SEMANTICS = (
    "PROTOTYPE_INTEGRATION_ONLY",
    "NOT_FINAL_SELECTED_MODEL",
    "NOT_DEPLOYMENT_VALIDATED",
    "NOT_SAFETY_VALIDATED",
    "NOT_CLINICAL_VALIDATION",
    "SUBJECT_TO_REPLACEMENT",
)

# Composer: max gap aligned with SW-01 default.
DEFAULT_MAX_GAP_S = 0.5
TARGET_SPAN_S = (TRACE_SAMPLES - 1) / SAMPLE_RATE_HZ  # 29.9 s for samples 0..299


class MProt3FailClosed(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


@dataclass
class WiringReceipt:
    """Portable M-PROT-3 composition receipt (one inference attempt)."""

    schema_version: str = "M-PROT-3-WIRING-RECEIPT-V1"
    phase: str = PHASE_ID
    status: str = "UNAVAILABLE"
    fail_closed_code: str | None = None
    panel_id: str = PANEL_ID
    candidate_id: str = CANDIDATE_ID
    artifact_rel: str = SOURCE_ARTIFACT_REL
    artifact_sha256: str = SOURCE_ARTIFACT_SHA256
    parameter_sha256: str = CANONICAL_PARAMETER_SHA256
    scaler_content_sha256: str = SCALER_CONTENT_SHA256
    representation: str = PRIMARY_REPRESENTATION
    r1_profile: str = R1_PROFILE_ID
    window_contract: str = WINDOW_CONTRACT
    source_validation_status: str | None = None
    window_ready: bool = False
    window_start_s: float | None = None
    window_end_s: float | None = None
    source_sample_count: int | None = None
    r1_sample_count: int | None = None
    assembled_dim: int | None = None
    session_id: str | None = None
    presence_status: str = "PRESENCE_UNAVAILABLE"
    presence_available: bool = False
    lineage_class: str = "FIXTURE_NON_CAMPAIGN"
    provisional_integration_freeze: bool = True
    replacement_requires_control_tower_decision: bool = True
    mandatory_semantics: tuple[str, ...] = MANDATORY_SEMANTICS
    production_inference_cadence: str = PRODUCTION_INFERENCE_CADENCE
    m_n9_fallback: bool = False
    prototype_receipt: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mandatory_semantics"] = list(self.mandatory_semantics)
        payload["PROTOTYPE_INTEGRATION_ONLY"] = True
        payload["NOT_FINAL_SELECTED_MODEL"] = True
        payload["FINAL_GOVERNED_EVALUATION"] = False
        return payload


@dataclass
class _BufferedSample:
    t: float
    phase: float
    session_id: str | None


@dataclass
class CausalTemporalComposer:
    """Past-only causal composer for 30 s / 10 Hz / 300-sample B23 context."""

    max_gap_s: float = DEFAULT_MAX_GAP_S
    target_rate_hz: float = SAMPLE_RATE_HZ
    target_samples: int = TRACE_SAMPLES
    _buf: list[_BufferedSample] = field(default_factory=list)
    _session_id: str | None = None

    def flush(self) -> None:
        self._buf.clear()

    @property
    def buffered_count(self) -> int:
        return len(self._buf)

    def push(self, sample: Sample) -> str | None:
        """Push one SW-01 sample. Returns a flush reason if state was cleared."""
        if sample.reset_flag:
            self.flush()
            self._session_id = sample.session_id
            # Reset sample itself may still be admitted after flush
        if sample.session_id is not None and self._session_id is not None:
            if sample.session_id != self._session_id:
                self.flush()
                self._session_id = sample.session_id
        elif sample.session_id is not None:
            self._session_id = sample.session_id

        if sample.t is None or not np.isfinite(sample.t):
            return "TIMESTAMP_INVALID"
        if sample.phase is None or not np.isfinite(sample.phase):
            return "PHASE_MISSING"
        # scalar_rr alone is never admitted
        t = float(sample.t)
        phase = float(sample.phase)
        if self._buf:
            prev = self._buf[-1]
            dt = t - prev.t
            if dt <= 0:
                self.flush()
                return "TIMESTAMP_NON_MONOTONIC"
            if dt > self.max_gap_s:
                self.flush()
                # Do not bridge; start fresh with current sample after flush
                self._buf.append(_BufferedSample(t=t, phase=phase, session_id=sample.session_id))
                return "LARGE_GAP_FLUSH"
        self._buf.append(_BufferedSample(t=t, phase=phase, session_id=sample.session_id))
        return None

    def ready(self) -> bool:
        return len(self._buf) >= self.target_samples

    def compose_native_window(self) -> NativeTraceInput:
        if not self.ready():
            raise MProt3FailClosed("WINDOW_NOT_READY", f"have={len(self._buf)} need={self.target_samples}")
        window = self._buf[-self.target_samples :]
        # Reject mixed sessions inside the window
        sessions = {s.session_id for s in window if s.session_id is not None}
        if len(sessions) > 1:
            raise MProt3FailClosed("CROSS_SESSION_WINDOW", str(sessions))
        # Gap check inside window
        for i in range(1, len(window)):
            dt = window[i].t - window[i - 1].t
            if dt <= 0 or dt > self.max_gap_s:
                raise MProt3FailClosed("WINDOW_INTERNAL_GAP", f"index={i} dt={dt}")
        times = np.asarray([s.t for s in window], dtype=np.float64)
        phases = np.asarray([s.phase for s in window], dtype=np.float64)
        # Relative time for R1: preserve deltas, start at 0
        t0 = float(times[0])
        time_s = times - t0
        span = float(time_s[-1] - time_s[0])
        # Nominal span for 300 @ 10 Hz is 29.9 s
        if span + 1e-9 < TARGET_SPAN_S * 0.98:
            raise MProt3FailClosed("WINDOW_SPAN_TOO_SHORT", f"span={span}")
        # Estimate source rate from median dt
        dts = np.diff(time_s)
        med_dt = float(np.median(dts)) if dts.size else 0.1
        rate = 1.0 / med_dt if med_dt > 0 else self.target_rate_hz
        session = window[-1].session_id or "UNKNOWN_SESSION"
        return NativeTraceInput(
            source_id="M_PROT_3_SW01",
            dataset_id="m_prot_3_integration",
            subject_id="PROTOTYPE",
            recording_id=str(session),
            condition="FIXTURE_NON_CAMPAIGN",
            trace=phases,
            time_s=time_s,
            sampling_rate_hz=float(rate),
            native_trace_semantics="phase_like_radian",
            native_trace_unit="radian_like",
            source_scale_metadata={"composer": WINDOW_CONTRACT},
            provenance={
                "m_prot_3": True,
                "window_contract": WINDOW_CONTRACT,
                "source_sample_count": len(window),
                "window_start_s": float(times[0]),
                "window_end_s": float(times[-1]),
                "session_id": session,
            },
            validity_mask=np.ones(len(window), dtype=bool),
            source_quality_flags=("M_PROT_3_CAUSAL_WINDOW",),
        )


class MProt3IntegrationRuntime:
    """SW-01 → composer → R1 → M-PROT-2 B23 composition."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
        self.composer = CausalTemporalComposer()
        self._model = None
        self._scaler = None
        self._last_source_status: str | None = None

    def ensure_runtime(self) -> None:
        if self._model is None or self._scaler is None:
            self._model, self._scaler = resolve_verified_runtime(root=self.root)

    def validate_source(self, bundle: StreamBundle, *, mode: str = "FIXTURE_OFFLINE_VALIDATION") -> dict[str, Any]:
        receipt = evaluate_stream(bundle, mode=mode, check_source="m_prot_3")
        self._last_source_status = receipt.get("overall_status")
        return receipt

    def reset(self) -> None:
        self.composer.flush()

    def push_sample(self, sample: Sample) -> str | None:
        return self.composer.push(sample)

    def ingest_bundle(self, bundle: StreamBundle, *, require_sw01_pass: bool = True) -> dict[str, Any]:
        """Validate then push samples. Does not run inference."""
        source_receipt = self.validate_source(bundle)
        if require_sw01_pass and source_receipt.get("overall_status") != STATUS_PASS:
            raise MProt3FailClosed(
                "SOURCE_VALIDATION_FAILED",
                str(source_receipt.get("overall_status")),
            )
        # Reject scalar-only observation kinds even if somehow passed
        if (bundle.observation_kind or "") == "scalar_vendor_rr":
            raise MProt3FailClosed("SCALAR_RR_NOT_MODEL_INPUT", "scalar_rr cannot feed B23")
        for sample in bundle.samples:
            if sample.phase is None and sample.scalar_rr is not None:
                raise MProt3FailClosed("SCALAR_RR_NOT_MODEL_INPUT", "missing phase; scalar_rr ignored")
            self.composer.push(sample)
        return source_receipt

    def try_infer(
        self,
        *,
        presence_available: bool | None = None,
        lineage_class: str = "FIXTURE_NON_CAMPAIGN",
    ) -> WiringReceipt:
        """Caller-triggered inference when window ready.

        Presence is NOT inferred from physiology. If the caller does not supply
        an explicit governed presence flag, presence_available defaults to False
        → PRESENCE_UNAVAILABLE (fail closed).
        """
        self.ensure_runtime()
        base = WiringReceipt(
            source_validation_status=self._last_source_status,
            lineage_class=lineage_class,
            session_id=self.composer._session_id,
            source_sample_count=self.composer.buffered_count,
        )

        # Explicit presence gate — no inference from B23
        if presence_available is None:
            presence_available = False
        base.presence_available = bool(presence_available)
        base.presence_status = "PRESENCE_AVAILABLE" if presence_available else "PRESENCE_UNAVAILABLE"

        if not self.composer.ready():
            base.status = "WINDOW_NOT_READY"
            base.fail_closed_code = "WINDOW_NOT_READY"
            base.window_ready = False
            return base

        try:
            native = self.composer.compose_native_window()
        except MProt3FailClosed as exc:
            base.status = "UNAVAILABLE"
            base.fail_closed_code = exc.code
            return base

        base.window_ready = True
        base.window_start_s = float(native.provenance.get("window_start_s"))
        base.window_end_s = float(native.provenance.get("window_end_s"))
        base.session_id = str(native.provenance.get("session_id"))

        if not presence_available:
            base.status = "UNAVAILABLE"
            base.fail_closed_code = "PRESENCE_UNAVAILABLE"
            return base

        try:
            common = adapt_native_trace(native)
        except R1TraceError as exc:
            base.status = "UNAVAILABLE"
            base.fail_closed_code = f"R1_{exc.code}"
            return base

        r1_n = int(np.asarray(common.trace).shape[0])
        base.r1_sample_count = r1_n
        if r1_n < TRACE_SAMPLES:
            base.status = "UNAVAILABLE"
            base.fail_closed_code = "R1_INSUFFICIENT_SAMPLES"
            return base
        if r1_n > TRACE_SAMPLES:
            # Take the most recent 300 causal samples (past-only tail)
            common = type(common)(
                trace=np.asarray(common.trace, dtype=np.float64)[-TRACE_SAMPLES:],
                time_s=np.asarray(common.time_s, dtype=np.float64)[-TRACE_SAMPLES:],
                validity_mask=np.asarray(common.validity_mask, dtype=bool)[-TRACE_SAMPLES:],
                metadata=dict(common.metadata),
            )
            base.r1_sample_count = TRACE_SAMPLES
        elif r1_n != TRACE_SAMPLES:
            base.status = "UNAVAILABLE"
            base.fail_closed_code = "R1_SAMPLE_COUNT_MISMATCH"
            return base

        try:
            proto = run_prototype_inference(
                {
                    "common_trace": common,
                    "presence_available": True,
                    "lineage_class": lineage_class,
                },
                root=self.root,
                model=self._model,
                scaler=self._scaler,
            )
        except PrototypeFailClosed as exc:
            base.status = "UNAVAILABLE"
            base.fail_closed_code = exc.code
            return base

        base.status = proto.status
        base.fail_closed_code = proto.fail_closed_code
        base.assembled_dim = TRACE_SAMPLES + TRACE_SAMPLES + 12 + 9  # 621
        base.prototype_receipt = proto.to_json()
        return base


def assert_no_mn9_imports() -> None:
    """Static guard used by tests — M-PROT-3 must not depend on M-N9."""
    import ast

    tree = ast.parse(Path(__file__).read_text())
    forbidden_modules = {"inference.mmwave_interpreter", "tensorflow.lite"}
    forbidden_names = {"MMWaveInterpreter", "MN9Interpreter"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules or alias.name.startswith("tensorflow.lite"):
                    raise RuntimeError(f"forbidden_import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in forbidden_modules or mod.startswith("inference.mmwave"):
                raise RuntimeError(f"forbidden_import_from:{mod}")
            for alias in node.names:
                if alias.name in forbidden_names:
                    raise RuntimeError(f"forbidden_import_name:{alias.name}")


__all__ = [
    "CausalTemporalComposer",
    "MProt3FailClosed",
    "MProt3IntegrationRuntime",
    "WiringReceipt",
    "PHASE_ID",
    "WINDOW_CONTRACT",
    "PRODUCTION_INFERENCE_CADENCE",
    "assert_no_mn9_imports",
]
