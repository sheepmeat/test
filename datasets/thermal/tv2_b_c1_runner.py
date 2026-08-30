"""PUBLIC_SDT-only runner for the Thermal V2 C1 vs Candidate B matched comparison.

Reuses Candidate A representation, SDT loader, A0 membership, training policy, and metrics.
Thermal-IM is not loaded. LOCKED_PUBLIC_TEST is never referenced.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from datasets.thermal import tv2_ca_metrics as metrics
from datasets.thermal import tv2_ca_runner as ca
from datasets.thermal import tv2_ca_sdt_source as sdt
from datasets.thermal import tv2_c1_model as c1
from datasets.thermal import tv2_candidate_b_model as cand_b

FAMILY_C1 = "C1"
FAMILY_B = "B"
NORMALIZATION = "FRAME_ROBUST_P2_P98_V1"
SEEDS = (42, 7, 1337)


def build_model(family: str, seed: int):
    if family == FAMILY_C1:
        return c1.build_model(seed)
    if family == FAMILY_B:
        return cand_b.build_model(seed)
    raise ValueError(f"unsupported family {family!r}")


def architecture_contract(family: str, param_count: int) -> dict:
    if family == FAMILY_C1:
        return c1.architecture_contract(param_count)
    if family == FAMILY_B:
        return cand_b.architecture_contract(param_count)
    raise ValueError(f"unsupported family {family!r}")


def run_id(family: str, seed: int) -> str:
    if family == FAMILY_C1:
        return f"C1_MATCHED_POOLED_MLP_seed{seed}"
    if family == FAMILY_B:
        return f"B_DEPTHWISE_SEPARABLE_seed{seed}"
    raise ValueError(f"unsupported family {family!r}")


def train_and_evaluate(arm_data: dict, sdt_train_frames, dev_frames, dev_labels,
                       family: str, seed: int):
    from tensorflow import keras

    keras.utils.set_random_seed(seed)
    model = build_model(family, seed)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=ca.TRAINING_POLICY["learning_rate"]),
        loss=ca.TRAINING_POLICY["loss"],
        metrics=["accuracy"],
    )
    sequence = ca.make_sequence(
        arm_data, sdt_train_frames, None, ca.TRAINING_POLICY["batch_size"], seed,
    )
    dev_input = np.asarray(dev_frames, dtype=np.float32).reshape(dev_frames.shape[0], 62, 80, 1)
    history = model.fit(
        sequence,
        validation_data=(dev_input, dev_labels),
        epochs=ca.TRAINING_POLICY["max_epochs"],
        verbose=0,
        callbacks=[keras.callbacks.EarlyStopping(
            monitor=ca.TRAINING_POLICY["early_stopping_monitor"],
            patience=ca.TRAINING_POLICY["early_stopping_patience"],
            restore_best_weights=True,
        )],
    )
    dev_pred = np.argmax(model.predict(dev_input, batch_size=512, verbose=0), axis=1)
    result = {
        "family": family,
        "seed": seed,
        "parameter_count": int(model.count_params()),
        "epochs_run": len(history.history["loss"]),
        "best_val_loss": float(min(history.history["val_loss"])),
        "sdt_development": metrics.evaluate(dev_labels, dev_pred),
    }
    del dev_input
    return result, model


def smoke_family(family: str) -> dict:
    import tensorflow as tf
    from tensorflow import keras

    keras.utils.set_random_seed(42)
    model = build_model(family, 42)
    x = tf.zeros((4, 62, 80, 1), dtype=tf.float32)
    y = tf.constant([0, 1, 2, 1], dtype=tf.int64)
    out = model(x, training=False)
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy")
    loss = float(model.train_on_batch(x, y, return_dict=True)["loss"])
    params = int(model.count_params())
    out_np = np.asarray(out)
    if tuple(out_np.shape) != (4, 3):
        raise RuntimeError(f"{family} output shape {out_np.shape} != (4, 3)")
    if not np.isfinite(out_np).all():
        raise RuntimeError(f"{family} forward pass produced non-finite values")
    if not np.isfinite(loss):
        raise RuntimeError(f"{family} loss is non-finite")
    in_shape = [None if d is None else int(d) for d in model.inputs[0].shape]
    out_shape = [None if d is None else int(d) for d in model.outputs[0].shape]
    return {
        "family": family,
        "parameter_count": params,
        "input_shape": in_shape,
        "output_shape": out_shape,
        "forward_finite": True,
        "loss_finite": True,
        "status": "PASS",
    }
