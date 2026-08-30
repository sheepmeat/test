"""Candidate B: capacity-corrected depthwise-separable CNN.

This is not the historical 347-parameter under-capacity depthwise instance.

Architecture::

    Input [62,80,1]
    Conv2D(16, 3x3, same, ReLU)
    MaxPool2D(2)
    SeparableConv2D(32, 3x3, same, ReLU)
    MaxPool2D(2)
    SeparableConv2D(48, 3x3, same, ReLU)
    GlobalAveragePooling2D
    Dense(32, ReLU)
    Dense(3, Softmax)
"""

from __future__ import annotations

from typing import Final

CANONICAL_INPUT_SHAPE: Final[tuple[int, int, int]] = (62, 80, 1)
NUM_CLASSES: Final[int] = 3
ARCHITECTURE_FAMILY: Final[str] = "CAPACITY_MATCHED_DEPTHWISE_SEPARABLE_CNN"
ARCHITECTURE_ID: Final[str] = "B_DEPTHWISE_SEPARABLE"


def build_model(seed: int):
    from tensorflow import keras

    initializer = keras.initializers.GlorotUniform(seed=seed)
    layers = [
        keras.layers.Input(shape=CANONICAL_INPUT_SHAPE, name="relative_thermal_appearance"),
        keras.layers.Conv2D(
            16, 3, padding="same", activation="relu",
            kernel_initializer=initializer, name="conv1",
        ),
        keras.layers.MaxPooling2D(2, name="pool1"),
        keras.layers.SeparableConv2D(
            32, 3, padding="same", activation="relu",
            depthwise_initializer=initializer, pointwise_initializer=initializer, name="sep_conv2",
        ),
        keras.layers.MaxPooling2D(2, name="pool2"),
        keras.layers.SeparableConv2D(
            48, 3, padding="same", activation="relu",
            depthwise_initializer=initializer, pointwise_initializer=initializer, name="sep_conv3",
        ),
        keras.layers.GlobalAveragePooling2D(name="gap"),
        keras.layers.Dense(
            32, activation="relu", kernel_initializer=initializer, name="dense1",
        ),
        keras.layers.Dense(
            NUM_CLASSES, activation="softmax", kernel_initializer=initializer, name="safenest_class",
        ),
    ]
    model = keras.Sequential(layers, name="tv2_candidate_b_depthwise_separable")
    model.build((None, *CANONICAL_INPUT_SHAPE))
    return model


def architecture_contract(param_count: int) -> dict:
    return {
        "architecture_family": ARCHITECTURE_FAMILY,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_input_shape": [1, *CANONICAL_INPUT_SHAPE],
        "num_classes": NUM_CLASSES,
        "parameter_count": int(param_count),
        "permitted_ops_only": [
            "Conv2D", "SeparableConv2D", "ReLU", "MaxPool2D",
            "GlobalAveragePooling2D", "Dense", "Softmax",
        ],
        "historical_347_param_depthwise_recreated": False,
        "batch_norm": "NONE",
        "dropout": "NONE",
        "attention_or_transformer": "NONE",
        "parameter_parity_with_candidate_a": "NOT_REQUIRED",
    }
