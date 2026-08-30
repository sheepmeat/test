"""Evaluation metrics for the Thermal V2 Candidate A prototype.

The primary practical metric is the ``HUMAN_NORMAL -> HUMAN_FALL_PROXY`` confusion count and rate
on PUBLIC_SDT DEVELOPMENT. The mandatory guardrails exist so that a candidate cannot look good
merely by predicting ``HUMAN_NORMAL`` more often.
"""

from __future__ import annotations

from typing import Final

import numpy as np

CLASS_NAMES: Final[tuple[str, str, str]] = ("NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY")
NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY = 0, 1, 2

# Frozen historical C0 diagnostic anchor from the B6R-P2 SDT DEVELOPMENT error slice.
C0_NORMAL_TO_FALL_COUNT: Final[int] = 174
C0_NORMAL_TO_FALL_DENOMINATOR: Final[int] = 4000


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    matrix = np.zeros((3, 3), dtype=np.int64)
    for true_class, pred_class in zip(y_true, y_pred):
        matrix[int(true_class), int(pred_class)] += 1
    return matrix


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Full guardrail metric set for one SDT DEVELOPMENT (or comparable) evaluation."""
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    matrix = confusion_matrix(y_true, y_pred)

    per_class: dict[str, dict] = {}
    f1_scores: list[float] = []
    for index, name in enumerate(CLASS_NAMES):
        true_positive = int(matrix[index, index])
        support = int(matrix[index, :].sum())
        predicted = int(matrix[:, index].sum())
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        f1_scores.append(f1)
        per_class[name] = {
            "support": support,
            "predicted": predicted,
            "true_positive": true_positive,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    normal_support = int(matrix[HUMAN_NORMAL, :].sum())
    fall_support = int(matrix[HUMAN_FALL_PROXY, :].sum())
    not_human_support = int(matrix[NOT_HUMAN, :].sum())
    normal_to_fall = int(matrix[HUMAN_NORMAL, HUMAN_FALL_PROXY])
    fall_to_normal = int(matrix[HUMAN_FALL_PROXY, HUMAN_NORMAL])
    not_human_to_fall = int(matrix[NOT_HUMAN, HUMAN_FALL_PROXY])

    return {
        "sample_count": int(y_true.size),
        "accuracy": float((y_true == y_pred).mean()) if y_true.size else 0.0,
        "macro_f1": float(np.mean(f1_scores)),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_layout": "rows=true, cols=pred, order=(NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY)",
        "primary_metric": {
            "name": "HUMAN_NORMAL_TO_HUMAN_FALL_PROXY",
            "count": normal_to_fall,
            "denominator": normal_support,
            "rate": (normal_to_fall / normal_support) if normal_support else 0.0,
        },
        "guardrails": {
            "HUMAN_NORMAL_TO_HUMAN_FALL_PROXY": {
                "count": normal_to_fall,
                "denominator": normal_support,
                "rate": (normal_to_fall / normal_support) if normal_support else 0.0,
            },
            "HUMAN_FALL_PROXY_TO_HUMAN_NORMAL": {
                "count": fall_to_normal,
                "denominator": fall_support,
                "rate": (fall_to_normal / fall_support) if fall_support else 0.0,
            },
            "NOT_HUMAN_TO_HUMAN_FALL_PROXY": {
                "count": not_human_to_fall,
                "denominator": not_human_support,
                "rate": (not_human_to_fall / not_human_support) if not_human_support else 0.0,
            },
            "HUMAN_FALL_PROXY_RECALL": per_class["HUMAN_FALL_PROXY"]["recall"],
            "HUMAN_NORMAL_RECALL": per_class["HUMAN_NORMAL"]["recall"],
            "MACRO_F1": float(np.mean(f1_scores)),
        },
        "c0_historical_anchor": {
            "identity": "B6R-P2_PUBLIC_SDT_POOLED_MLP_FP32",
            "normal_to_fall_count": C0_NORMAL_TO_FALL_COUNT,
            "normal_to_fall_denominator": C0_NORMAL_TO_FALL_DENOMINATOR,
            "normal_to_fall_rate": C0_NORMAL_TO_FALL_COUNT / C0_NORMAL_TO_FALL_DENOMINATOR,
            "comparability": "DIFFERENT_REPRESENTATION_AND_ARCHITECTURE_DIAGNOSTIC_ANCHOR_ONLY",
        },
    }


def evaluate_hard_negatives(y_pred: np.ndarray) -> dict:
    """Supplemental Thermal-IM held-out hard-negative evaluation.

    Every frame here is a verified seated ``HUMAN_NORMAL`` hard negative, so there is no
    ``HUMAN_FALL_PROXY`` ground truth and no macro F1. These numbers must never be merged into the
    PUBLIC_SDT metric set.
    """
    y_pred = np.asarray(y_pred, dtype=np.int64)
    total = int(y_pred.size)
    predicted_normal = int((y_pred == HUMAN_NORMAL).sum())
    predicted_fall = int((y_pred == HUMAN_FALL_PROXY).sum())
    predicted_not_human = int((y_pred == NOT_HUMAN).sum())
    return {
        "domain": "Thermal-IM_HELD_OUT_SEATED_HARD_NEGATIVE",
        "domain_separation": "MUST_NOT_BE_MERGED_INTO_SDT_MACRO_F1",
        "ground_truth_class": "HUMAN_NORMAL_ONLY",
        "hard_negative_frame_count": total,
        "predicted_HUMAN_NORMAL": predicted_normal,
        "predicted_HUMAN_FALL_PROXY": predicted_fall,
        "predicted_NOT_HUMAN": predicted_not_human,
        "normal_acceptance_rate": (predicted_normal / total) if total else 0.0,
        "fall_proxy_false_positive_rate": (predicted_fall / total) if total else 0.0,
        "not_human_rate": (predicted_not_human / total) if total else 0.0,
    }
