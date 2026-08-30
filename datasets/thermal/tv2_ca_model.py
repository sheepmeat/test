"""Candidate A architecture family: REVISED COMPACT CONVENTIONAL CNN.

Both variants share one convolutional trunk and differ only in how spatial structure is
collapsed before the classifier. This is deliberately *not* the B6R pooled-MLP family, and it is
deliberately *not* a recreation of the historical 312k Flatten-heavy model.

Permitted operations only: ``Conv2D``, ``ReLU``, ``MaxPool2D``, ``AveragePooling2D``,
``GlobalAveragePooling2D``, ``Dense``, ``Softmax``. No attention, no transformer, no GPU-only op.
"""

from __future__ import annotations

from typing import Final

CANONICAL_INPUT_SHAPE: Final[tuple[int, int, int]] = (62, 80, 1)
NUM_CLASSES: Final[int] = 3

HEAD_GAP: Final[str] = "GAP_DENSE_V1"
HEAD_SPATIAL: Final[str] = "COARSE_SPATIAL_RETAIN_FLATTEN_V1"
HEAD_VARIANTS: Final[tuple[str, str]] = (HEAD_GAP, HEAD_SPATIAL)

ARCHITECTURE_FAMILY: Final[str] = "REVISED_COMPACT_CONVENTIONAL_CNN"


def build_model(head_variant: str, seed: int):
    """Build one Candidate A variant.

    Trunk (identical for both variants)::

        [62,80,1]
        Conv2D(16,3x3,same) + ReLU -> MaxPool2x2 -> [31,40,16]
        Conv2D(32,3x3,same) + ReLU -> MaxPool2x2 -> [15,20,32]
        Conv2D(64,3x3,same) + ReLU -> MaxPool2x2 -> [ 7,10,64]

    ``GAP_DENSE_V1``                    GAP -> Dense(64) + ReLU -> Dense(3) + Softmax
    ``COARSE_SPATIAL_RETAIN_FLATTEN_V1`` AvgPool2x2 -> [4,5,64] -> Flatten -> Dense(32) + ReLU
                                        -> Dense(3) + Softmax
    """
    import tensorflow as tf
    from tensorflow import keras

    if head_variant not in HEAD_VARIANTS:
        raise ValueError(f"unsupported head variant {head_variant!r}")

    initializer = keras.initializers.GlorotUniform(seed=seed)
    layers = [
        keras.layers.Input(shape=CANONICAL_INPUT_SHAPE, name="relative_thermal_appearance"),
        keras.layers.Conv2D(16, 3, padding="same", activation="relu",
                            kernel_initializer=initializer, name="conv1"),
        keras.layers.MaxPooling2D(2, name="pool1"),
        keras.layers.Conv2D(32, 3, padding="same", activation="relu",
                            kernel_initializer=initializer, name="conv2"),
        keras.layers.MaxPooling2D(2, name="pool2"),
        keras.layers.Conv2D(64, 3, padding="same", activation="relu",
                            kernel_initializer=initializer, name="conv3"),
        keras.layers.MaxPooling2D(2, name="pool3"),
    ]
    if head_variant == HEAD_GAP:
        layers += [
            keras.layers.GlobalAveragePooling2D(name="gap"),
            keras.layers.Dense(64, activation="relu", kernel_initializer=initializer, name="dense1"),
        ]
    else:
        layers += [
            keras.layers.AveragePooling2D(2, padding="same", name="coarse_spatial_retain"),
            keras.layers.Flatten(name="flatten"),
            keras.layers.Dense(32, activation="relu", kernel_initializer=initializer, name="dense1"),
        ]
    layers.append(
        keras.layers.Dense(NUM_CLASSES, activation="softmax",
                           kernel_initializer=initializer, name="safenest_class")
    )

    model = keras.Sequential(layers, name=f"tv2_candidate_a_{head_variant.lower()}")
    model.build((None, *CANONICAL_INPUT_SHAPE))
    del tf
    return model


def architecture_contract(head_variant: str, param_count: int) -> dict:
    return {
        "architecture_family": ARCHITECTURE_FAMILY,
        "head_variant": head_variant,
        "canonical_input_shape": [1, *CANONICAL_INPUT_SHAPE],
        "num_classes": NUM_CLASSES,
        "parameter_count": int(param_count),
        "permitted_ops_only": [
            "Conv2D", "ReLU", "MaxPool2D", "AveragePooling2D",
            "GlobalAveragePooling2D", "Dense", "Softmax",
        ],
        "pooled_mlp_reuse": "FORBIDDEN_NOT_CANDIDATE_A",
        "historical_312k_flatten_model_recreated": False,
        "attention_or_transformer": "NONE",
    }
