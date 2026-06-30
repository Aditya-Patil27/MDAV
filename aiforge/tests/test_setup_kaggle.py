from __future__ import annotations

import unittest

from setup_kaggle import model_snapshot_specs


class KaggleSetupTest(unittest.TestCase):
    def test_model_snapshots_exclude_full_precision_base_weights(self) -> None:
        specs = model_snapshot_specs()

        self.assertEqual(specs[0][0], "diffusers/FLUX.1-Fill-dev-nf4")
        self.assertIsNone(specs[0][1])
        self.assertEqual(specs[1][0], "black-forest-labs/FLUX.1-Fill-dev")
        self.assertEqual(
            specs[1][1],
            [
                "model_index.json",
                "scheduler/**",
                "text_encoder/**",
                "tokenizer/**",
                "tokenizer_2/**",
                "vae/**",
            ],
        )
        flattened = " ".join(specs[1][1])
        self.assertNotIn("transformer", flattened)
        self.assertNotIn("text_encoder_2", flattened)


if __name__ == "__main__":
    unittest.main()
