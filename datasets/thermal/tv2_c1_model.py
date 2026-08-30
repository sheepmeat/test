"""C1 matched pooled-MLP control for the Thermal V2 architecture comparison.

This is the operational B6R pooled-MLP family trained under the *current* Candidate A
representation and training policy. It is a control, not a prototype winner.

Architecture::

    Input [62,80,1]
    -> AdaptiveMeanPoolP1 integer-linspace [8,10] flatten 80
    -> Dense(32, ReLU)
    -> Dense(3, Softmax)

Expected trainable parameter count: 2691.
"""

from __future__ import annotations

from typing import Final

CANONICAL_INPUT_SHAPE: Final[tuple[int, int, int]] = (62, 80, 1)
NUM_CLASSES: Final[int] = 3
ARCHITECTURE_FAMILY: Final[str] = "MATCHED_POOLED_MLP_CONTROL"
ARCHITECTURE_ID: Final[str] = "C1_MATCHED_POOLED_MLP"
HEIGHT_EDGES: Final[tuple[int, ...]] = (0, 7, 15, 23, 31, 38, 46, 54, 62)
WIDTH_EDGES: Final[tuple[int, ...]] = (0, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80)


def _adaptive_mean_pool_layer():
    import tensorflow as tf
    from tensorflow import keras

    @keras.utils.register_keras_serializable(package="tv2_c1", name="AdaptiveMeanPoolP1")
    class AdaptiveMeanPoolP1(keras.layers.Layer):
        """B6R-P1/P2 integer-linspace adaptive mean pool to 80 features."""

        def call(self, inputs):
            cells = []
            for row in range(8):
                for column in range(10):
                    block = inputs[
                        :,
                        HEIGHT_EDGES[row]:HEIGHT_EDGES[row + 1],
                        WIDTH_EDGES[column]:WIDTH_EDGES[column + 1],
                        0,
                    ]
                    cells.append(tf.reduce_mean(block, axis=(1, 2)))
            return tf.stack(cells, axis=1)

        def compute_output_shape(self, input_shape):
            return input_shape[0], 80

        def get_config(self):
            return super().get_config()

    return AdaptiveMeanPoolP1


def build_model(seed: int):
    from tensorflow import keras

    initializer = keras.initializers.GlorotUniform(seed=seed)
    pool_cls = _adaptive_mean_pool_layer()
    inputs = keras.Input(shape=CANONICAL_INPUT_SHAPE, name="relative_thermal_appearance")
    pooled = pool_cls(name="adaptive_mean_pool_p1")(inputs)
    hidden = keras.layers.Dense(
        32, activation="relu", kernel_initializer=initializer, name="hidden_relu",
    )(pooled)
    outputs = keras.layers.Dense(
        NUM_CLASSES, activation="softmax", kernel_initializer=initializer, name="safenest_class",
    )(hidden)
    model = keras.Model(inputs=inputs, outputs=outputs, name="tv2_c1_matched_pooled_mlp")
    model.build((None, *CANONICAL_INPUT_SHAPE))
    return model


def architecture_contract(param_count: int) -> dict:
    return {
        "architecture_family": ARCHITECTURE_FAMILY,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_input_shape": [1, *CANONICAL_INPUT_SHAPE],
        "num_classes": NUM_CLASSES,
        "parameter_count": int(param_count),
        "pooling": {
            "operation": "adaptive_mean_pool",
            "edge_policy": "numpy_linspace_integer_boundaries",
            "height_edges": list(HEIGHT_EDGES),
            "width_edges": list(WIDTH_EDGES),
            "output_hw": [8, 10],
            "feature_count": 80,
            "source_family": "B6R_PUBLIC_SDT_POOLED_MLP",
        },
        "hidden_units": 32,
        "batch_norm": "NONE",
        "dropout": "NONE",
        "attention_or_transformer": "NONE",
        "role": "MATCHED_CONTROL_NOT_PROTOTYPE_WINNER",
    }
