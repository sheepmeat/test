"""M-PROT-4 system-level offline / replay / synthetic smoke harness.

Exercises the merged M-PROT-3 public API only:

  StreamBundle fixture
    → MProt3IntegrationRuntime.ingest_bundle()
    → try_infer()
    → WiringReceipt V3
    → SmokeReceipt (thin system evidence)

Does not reimplement R1/R2/B23. No M-N9. No direct B23 bypass.
Luna1 may later own richer fixture helpers; Luna2 may own a stricter
standalone SmokeReceipt validator. This module stays independently functional.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from adapters.mmwave_m_prot_2_b23_runtime import (
    CANONICAL_PARAMETER_SHA256,
    SCALER_CONTENT_SHA256,
    SOURCE_ARTIFACT_SHA256,
    TRACE_SAMPLES,
)
from adapters.mmwave_m_prot_3_integration_runtime import (
    TARGET_SPAN_S,
    MProt3FailClosed,
    MProt3IntegrationRuntime,
    WiringReceipt,
)
from adapters.mmwave_sw01_interface_checker import Sample, StreamBundle

PHASE_ID = "M-PROT-4"
SMOKE_RECEIPT_SCHEMA = "M-PROT-4-SMOKE-RECEIPT-V1"
LINEAGE_CLASS = "FIXTURE_NON_CAMPAIGN"
KNOWN_LIMITATIONS = (
    "MR60_UART_PROTOCOL_UNPROVEN",
    "PI_TORCH_NOT_LIVE_VERIFIED",
    "PI_LATENCY_NOT_MEASURED",
    "LIVE_PRESENCE_SOURCE_NOT_PROVEN",
    "PRODUCTION_INFERENCE_CADENCE_NOT_GOVERNED",
    "LIVE_HARDWARE_NOT_EXECUTED",
)

# Explicit fixture presence gate exercises the frozen path; does NOT prove live presence.
FIXTURE_PRESENCE_GATE_NOTE = (
    "FIXTURE_EXPLICIT_PRESENCE_GATE_ONLY; LIVE_PRESENCE_SOURCE_NOT_PROVEN"
)


@dataclass
class SmokeReceipt:
    """Thin M-PROT-4 system-smoke evidence (not final evaluation)."""

    schema_version: str = SMOKE_RECEIPT_SCHEMA
    phase: str = PHASE_ID
    case_id: str = ""
    fixture_id: str = ""
    deterministic_pass: bool = False
    expected_system_state: str = ""
    observed_system_state: str = ""
    fail_closed_code: str | None = None
    sw01_overall_status: str | None = None
    device_identity: str | None = None
    interface_identity: str | None = None
    configuration_identity: str | None = None
    observation_kind: str | None = None
    session_id: str | None = None
    r1_sample_count: int | None = None
    assembled_dim: int | None = None
    sw01_receipt_sha256: str | None = None
    sw01_receipt_sha256_chain: tuple[str, ...] = ()
    artifact_sha256: str = SOURCE_ARTIFACT_SHA256
    scaler_content_sha256: str = SCALER_CONTENT_SHA256
    parameter_sha256: str = CANONICAL_PARAMETER_SHA256
    wiring_receipt_summary: dict[str, Any] | None = None
    lineage_class: str = LINEAGE_CLASS
    not_final_evaluation: bool = True
    live_hardware: bool = False
    presence_limitation: str = FIXTURE_PRESENCE_GATE_NOTE
    known_limitations: tuple[str, ...] = KNOWN_LIMITATIONS
    m_n9_fallback: bool = False
    direct_b23_bypass: bool = False
    notes: str = ""

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sw01_receipt_sha256_chain"] = list(self.sw01_receipt_sha256_chain)
        payload["known_limitations"] = list(self.known_limitations)
        payload["FINAL_GOVERNED_EVALUATION"] = False
        payload["NOT_FINAL_EVALUATION"] = True
        payload["PROTOTYPE_INTEGRATION_ONLY"] = True
        return payload


def phase_samples(
    n: int,
    *,
    rate: float = 10.0,
    session: str = "A",
    t0: float = 0.0,
    seq0: int = 0,
    reset_at: int | None = None,
) -> list[Sample]:
    """Minimal deterministic phase fixture builder (Luna1 may supersede later)."""
    samples: list[Sample] = []
    for i in range(n):
        t = t0 + i / rate
        samples.append(
            Sample(
                t=t,
                phase=float(np.sin(2 * np.pi * 0.25 * t)),
                seq=seq0 + i,
                health_ok=True,
                session_id=session,
                reset_flag=(reset_at is not None and i == reset_at),
            )
        )
    return samples


def samples_covering_span(
    rate: float,
    *,
    span_s: float = TARGET_SPAN_S,
    session: str = "A",
    t0: float = 0.0,
    seq0: int = 0,
) -> list[Sample]:
    n = int(round(span_s * rate)) + 1
    return phase_samples(n, rate=rate, session=session, t0=t0, seq0=seq0)


def make_bundle(
    samples: Sequence[Sample],
    *,
    device_identity: str = "M_PROT_4_FIXTURE_DEVICE",
    interface_identity: str = "fixture:json",
    configuration_identity: str = "M_PROT_4_CFG",
    observation_kind: str = "near_raw_phase",
) -> StreamBundle:
    return StreamBundle(
        device_identity=device_identity,
        interface_identity=interface_identity,
        configuration_identity=configuration_identity,
        observation_kind=observation_kind,
        samples=list(samples),
    )


def _summarize_wiring(receipt: WiringReceipt | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    return {
        "schema_version": receipt.schema_version,
        "status": receipt.status,
        "fail_closed_code": receipt.fail_closed_code,
        "window_ready": receipt.window_ready,
        "r1_sample_count": receipt.r1_sample_count,
        "assembled_dim": receipt.assembled_dim,
        "sw01_receipt_sha256": receipt.sw01_receipt_sha256,
        "sw01_receipt_sha256_chain": list(receipt.sw01_receipt_sha256_chain),
        "presence_status": receipt.presence_status,
        "session_id": receipt.session_id,
        "prototype_status": None
        if receipt.prototype_receipt is None
        else receipt.prototype_receipt.get("status"),
        "panel_id": None
        if receipt.prototype_receipt is None
        else receipt.prototype_receipt.get("panel_id"),
    }


@dataclass
class MProt4SystemSmokeHarness:
    """System smoke driver over the real M-PROT-3 public API."""

    root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])
    runtime: MProt3IntegrationRuntime = field(init=False)

    def __post_init__(self) -> None:
        self.runtime = MProt3IntegrationRuntime(root=self.root)

    def reset(self) -> None:
        self.runtime.reset()

    def run_case(
        self,
        *,
        case_id: str,
        fixture_id: str,
        bundles: Sequence[StreamBundle],
        expected_system_state: str,
        presence_gate_satisfied: bool = True,
        expect_ingest_fail_code: str | None = None,
        accept_observed: Sequence[str] | None = None,
        after_ingest_hook: Any = None,
    ) -> SmokeReceipt:
        """Ingest ordered bundles then try_infer once (unless ingest fails as expected)."""
        self.reset()
        last_sw01: str | None = None
        wiring: WiringReceipt | None = None
        ingest_fail: str | None = None

        try:
            for bundle in bundles:
                src = self.runtime.ingest_bundle(bundle)
                last_sw01 = str(src.get("overall_status"))
            if after_ingest_hook is not None:
                after_ingest_hook(self)
            if expect_ingest_fail_code is not None:
                # Expected failure did not occur.
                observed = "UNEXPECTED_INGEST_SUCCESS"
            else:
                wiring = self.runtime.try_infer(
                    presence_gate_satisfied=presence_gate_satisfied,
                    lineage_class=LINEAGE_CLASS,
                )
                observed = wiring.fail_closed_code or wiring.status
        except MProt3FailClosed as exc:
            ingest_fail = exc.code
            observed = exc.code
            if expect_ingest_fail_code is None:
                # Unexpected ingest failure — still emit smoke receipt.
                pass

        accepted = list(accept_observed or [expected_system_state])
        if expect_ingest_fail_code is not None:
            observed = ingest_fail or observed
            if accept_observed:
                accepted = list(accept_observed)
            else:
                accepted = [expect_ingest_fail_code]
            expected_system_state = expect_ingest_fail_code
            deterministic_pass = observed in accepted
        else:
            deterministic_pass = observed in accepted

        return SmokeReceipt(
            case_id=case_id,
            fixture_id=fixture_id,
            deterministic_pass=deterministic_pass,
            expected_system_state=expected_system_state,
            observed_system_state=str(observed),
            fail_closed_code=None if wiring is None else wiring.fail_closed_code,
            sw01_overall_status=last_sw01,
            device_identity=None if wiring is None else wiring.device_identity,
            interface_identity=None if wiring is None else wiring.interface_identity,
            configuration_identity=None if wiring is None else wiring.configuration_identity,
            observation_kind=None if wiring is None else wiring.observation_kind,
            session_id=None if wiring is None else wiring.session_id,
            r1_sample_count=None if wiring is None else wiring.r1_sample_count,
            assembled_dim=None if wiring is None else wiring.assembled_dim,
            sw01_receipt_sha256=None if wiring is None else wiring.sw01_receipt_sha256,
            sw01_receipt_sha256_chain=()
            if wiring is None
            else tuple(wiring.sw01_receipt_sha256_chain),
            wiring_receipt_summary=_summarize_wiring(wiring),
            notes="" if deterministic_pass else f"expected_one_of={accepted}",
        )


def assert_no_mn9_or_direct_b23_bypass() -> None:
    """Static guard: M-PROT-4 harness must not import M-N9 or call B23 directly."""
    import ast

    tree = ast.parse(Path(__file__).read_text())
    forbidden_names = {
        "MMWaveInterpreter",
        "MN9Interpreter",
        "run_prototype_inference",
        "resolve_verified_runtime",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("inference.mmwave") or "mmwave_interpreter" in mod:
                raise RuntimeError(f"forbidden_import_from:{mod}")
            for alias in node.names:
                if alias.name in forbidden_names:
                    raise RuntimeError(f"forbidden_import_name:{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "mmwave_interpreter" in alias.name:
                    raise RuntimeError(f"forbidden_import:{alias.name}")


__all__ = [
    "FIXTURE_PRESENCE_GATE_NOTE",
    "KNOWN_LIMITATIONS",
    "LINEAGE_CLASS",
    "MProt4SystemSmokeHarness",
    "PHASE_ID",
    "SMOKE_RECEIPT_SCHEMA",
    "SmokeReceipt",
    "TARGET_SPAN_S",
    "TRACE_SAMPLES",
    "assert_no_mn9_or_direct_b23_bypass",
    "make_bundle",
    "phase_samples",
    "samples_covering_span",
]
