from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from src.builder import generate_forged_sample
from src.cord_loader import _parse_cord_json
from src.crop_paste import paste_crop_back
from src.diffusers_generator import DiffusersGenerator
from src.field_selector import select_fields_for_variants
from src.mask_generator import generate_tamper_mask
from src.metadata_writer import append_metadata_row, get_metadata_index
from src.prompt_builder import build_inpainting_prompt
from src.schema import UnifiedDocument, UnifiedField
from src.statistics import StatsTracker
from src.utils import pad_to_multiple, unpad_to_box


class PipelineContractsTest(unittest.TestCase):
    def test_cord_loader_uses_value_words_for_geometry_and_preserves_full_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            annotation = tmp_path / "cord.json"
            annotation.write_text(
                json.dumps(
                    {
                        "meta": {"image_size": {"width": 200, "height": 100}},
                        "valid_line": [
                            {
                                "category": "sub_total.subtotal_price",
                                "words": [
                                    {
                                        "text": "Sub-Total",
                                        "is_key": 1,
                                        "quad": {"x1": 10, "y1": 20, "x2": 70, "y2": 20, "x3": 70, "y3": 40, "x4": 10, "y4": 40},
                                    },
                                    {
                                        "text": "1,346,000",
                                        "is_key": 0,
                                        "quad": {"x1": 90, "y1": 20, "x2": 160, "y2": 20, "x3": 160, "y3": 40, "x4": 90, "y4": 40},
                                    },
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            doc = _parse_cord_json(annotation, "cord_test", "train", tmp_path / "image.png")

        self.assertIsNotNone(doc)
        field = doc.fields[0]
        self.assertEqual(field.text, "Sub-Total 1,346,000")
        self.assertEqual(field.bbox, [90, 20, 160, 40])
        self.assertEqual(field.extra["label_text"], "Sub-Total")
        self.assertEqual(field.extra["value_text"], "1,346,000")
        self.assertEqual(field.extra["value_bbox_source"], "cord_is_key")

    def test_diffusers_generator_uses_separate_base_and_nf4_repositories(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            generator = DiffusersGenerator.from_env()

        self.assertEqual(
            generator.base_model_id,
            "black-forest-labs/FLUX.1-Fill-dev",
        )
        self.assertEqual(
            generator.quantized_model_id,
            "diffusers/FLUX.1-Fill-dev-nf4",
        )

    def test_diffusers_generator_reads_kaggle_model_cache(self) -> None:
        with patch.dict(
            os.environ,
            {"KAGGLE_MODEL_CACHE": "/kaggle/working/hf-cache"},
            clear=True,
        ):
            generator = DiffusersGenerator.from_env()

        self.assertEqual(generator.cache_dir, Path("/kaggle/working/hf-cache"))

    def test_diffusers_mask_uses_bbox_margin_without_modifying_pixels(self) -> None:
        generator = DiffusersGenerator(mask_margin=2)
        crop = Image.new("RGB", (12, 14), "white")
        before = crop.tobytes()

        mask = generator._build_mask(crop.size, [3, 4, 8, 10])

        self.assertEqual(crop.tobytes(), before)
        self.assertEqual(mask.getpixel((0, 0)), 0)
        self.assertEqual(mask.getpixel((1, 2)), 255)
        self.assertEqual(mask.getpixel((9, 11)), 255)
        self.assertEqual(mask.getpixel((10, 12)), 0)

    def test_pad_to_multiple_uses_source_pixels_and_unpads_exactly(self) -> None:
        source = Image.new("RGB", (100, 100))
        source.putdata([(x, y, (x + y) % 256) for y in range(100) for x in range(100)])
        source_box = (20, 20, 70, 50)
        crop = source.crop(source_box)

        padded, original_box = pad_to_multiple(
            crop,
            multiple=64,
            source_image=source,
            source_box=source_box,
        )

        self.assertEqual(padded.size, (64, 64))
        self.assertEqual(original_box, (7, 17, 57, 47))
        self.assertEqual(padded.getpixel((0, 0)), source.getpixel((13, 3)))
        restored = unpad_to_box(padded, original_box)
        self.assertEqual(restored.size, crop.size)
        self.assertEqual(restored.tobytes(), crop.tobytes())

    def test_pad_to_multiple_edge_replicates_only_beyond_source(self) -> None:
        source = Image.new("RGB", (40, 40), "black")
        source.putpixel((0, 0), (12, 34, 56))
        crop = source.crop((0, 0, 33, 33))

        padded, original_box = pad_to_multiple(
            crop,
            multiple=64,
            source_image=source,
            source_box=(0, 0, 33, 33),
        )

        self.assertEqual(padded.size, (64, 64))
        self.assertEqual(padded.getpixel((0, 0)), (12, 34, 56))
        self.assertEqual(unpad_to_box(padded, original_box).tobytes(), crop.tobytes())

    def test_prompt_is_semantic_and_has_no_visual_marker(self) -> None:
        prompt = build_inpainting_prompt("10.00", "12.00", "total")
        self.assertIn('original value "10.00"', prompt)
        self.assertIn('new value "12.00"', prompt)
        self.assertIn('field type "total"', prompt)
        self.assertNotIn("rectangle", prompt.lower())
        self.assertNotIn("highlight", prompt.lower())
        self.assertNotIn("border", prompt.lower())
        self.assertLessEqual(len(prompt.split()), 70)

    def test_feathered_paste_blends_expanded_region(self) -> None:
        original = Image.new("RGB", (32, 32), "black")
        edited = Image.new("RGB", (32, 32), "white")
        result = paste_crop_back(
            original,
            edited,
            [10, 10, 20, 20],
            (0, 0, 32, 32),
            margin=2,
            blur_radius=1,
        )
        self.assertEqual(result.getpixel((16, 16)), (255, 255, 255))
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))
        self.assertTrue(0 < result.getpixel((8, 10))[0] < 255)

    def test_variant_selection_prefers_distinct_labels_then_wraps(self) -> None:
        doc = UnifiedDocument(
            image_id="doc_variants",
            dataset="CORD",
            split="train",
            language="en",
            document_type="receipt",
            width=100,
            height=100,
            image_path=Path("source.png"),
            fields=[
                UnifiedField("total", "total", "10.00", [1, 1, 20, 10], []),
                UnifiedField("price", "price", "2.00", [1, 20, 20, 30], []),
            ],
        )
        selected = select_fields_for_variants(doc, 3)
        self.assertEqual([field.field_id for field in selected], ["total", "price", "total"])

    def test_generate_forged_sample_uses_injected_image_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.png"
            Image.new("RGB", (160, 120), "white").save(source_path)
            doc = UnifiedDocument(
                image_id="doc_backend",
                dataset="CORD",
                split="train",
                language="ko",
                document_type="receipt",
                width=160,
                height=120,
                image_path=source_path,
                fields=[
                    UnifiedField(
                        field_id="field_total",
                        label="total",
                        text="10.00",
                        bbox=[20, 20, 70, 40],
                        polygon=[],
                    )
                ],
            )

            class FakeGenerator:
                name = "diffusers"

                def __init__(self) -> None:
                    self.calls: list[tuple[tuple[int, int], str, tuple[int, int, int, int], int | None]] = []

                def generate(self, crop, prompt, bbox, seed=None):
                    self.calls.append((crop.size, prompt, tuple(bbox), seed))
                    return crop.copy()

            fake = FakeGenerator()
            stats = StatsTracker()
            with patch("src.builder.locate_substring_bbox", return_value=[20, 20, 70, 40]), \
                    patch("src.builder.verify_edited_region_text", return_value=True):
                result = generate_forged_sample(
                    doc=doc,
                    output_dir=tmp_path / "out",
                    stats=stats,
                    seed=7,
                    max_retries=1,
                    image_generator=fake,
                )

            self.assertIsNotNone(result)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(fake.calls[0][0][0] % 64, 0)
            self.assertEqual(fake.calls[0][0][1] % 64, 0)
            self.assertEqual(fake.calls[0][3], 7)
            self.assertEqual(result[1].name, "doc_backend_v0_forged.png")

    def test_builder_fails_closed_when_value_cannot_be_located(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.png"
            Image.new("RGB", (160, 120), "white").save(source_path)
            doc = UnifiedDocument(
                "doc_missing_value", "CORD", "train", "ko", "receipt", 160, 120,
                source_path,
                [UnifiedField("field_total", "total", "Total 10.00", [20, 20, 100, 40], [])],
            )
            generator = SimpleNamespace(name="diffusers", generate=unittest.mock.Mock())
            tracker = SimpleNamespace(mark_failed=unittest.mock.Mock())
            stats = StatsTracker()

            with patch("src.builder.locate_substring_bbox", return_value=None):
                result = generate_forged_sample(
                    doc, tmp_path / "out", stats, 7, max_retries=1,
                    image_generator=generator, progress_tracker=tracker,
                )

        self.assertIsNone(result)
        generator.generate.assert_not_called()
        tracker.mark_failed.assert_called_once_with("doc_missing_value_v0_forged")
        self.assertEqual(stats.failed_generations, 1)

    def test_builder_uses_logged_cord_is_key_bbox_when_locator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.png"
            Image.new("RGB", (160, 120), "white").save(source_path)
            doc = UnifiedDocument(
                "doc_cord_fallback", "CORD", "train", "ko", "receipt", 160, 120,
                source_path,
                [
                    UnifiedField(
                        "field_total",
                        "total",
                        "SUBTOTAL 503,000",
                        [60, 20, 110, 40],
                        [],
                        extra={
                            "value_text": "503,000",
                            "label_text": "SUBTOTAL",
                            "value_bbox_source": "cord_is_key",
                        },
                    )
                ],
            )

            class FakeGenerator:
                name = "diffusers"
                mask_margin = 0

                def __init__(self) -> None:
                    self.bbox = None

                def generate(self, crop, prompt, bbox, seed=None):
                    self.bbox = list(bbox)
                    return crop.copy()

            generator = FakeGenerator()
            with patch("src.builder.locate_substring_bbox", return_value=None), \
                    patch("src.builder.verify_edited_region_text", return_value=True) as verifier, \
                    patch("src.builder.logger.warning") as warning:
                result = generate_forged_sample(
                    doc, tmp_path / "out", StatsTracker(), 7, max_retries=1,
                    image_generator=generator,
                )

        self.assertIsNotNone(result)
        self.assertIsNotNone(generator.bbox)
        verifier.assert_called_once()
        self.assertEqual(verifier.call_args.args[1], [60, 20, 110, 40])
        self.assertNotEqual(verifier.call_args.args[2], "503,000")
        warning.assert_any_call(
            "Using trusted CORD is_key value bbox after OCR localization failure. "
            "field=%s reason=%s",
            "field_total",
            "no confidence-qualified exact OCR match",
        )

    def test_builder_passes_narrowed_value_bbox_to_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.png"
            Image.new("RGB", (160, 120), "white").save(source_path)
            doc = UnifiedDocument(
                "doc_narrow", "CORD", "train", "ko", "receipt", 160, 120,
                source_path,
                [UnifiedField("field_total", "total", "Total 10.00", [20, 20, 100, 40], [], extra={"value_text": "10.00"})],
            )

            class FakeGenerator:
                name = "diffusers"
                mask_margin = 0

                def __init__(self) -> None:
                    self.bbox = None

                def generate(self, crop, prompt, bbox, seed=None):
                    self.bbox = list(bbox)
                    return crop.copy()

            generator = FakeGenerator()
            with patch("src.builder.locate_substring_bbox", return_value=[60, 20, 100, 40]), \
                    patch("src.builder.verify_edited_region_text", return_value=True):
                result = generate_forged_sample(
                    doc, tmp_path / "out", StatsTracker(), 7, max_retries=1,
                    image_generator=generator,
                )

        self.assertIsNotNone(result)
        self.assertEqual(generator.bbox, [76, 24, 116, 44])

    def test_mask_uses_exclusive_bbox_edges_matching_crop_and_paste(self) -> None:
        mask = generate_tamper_mask(10, 10, [2, 3, 5, 7])
        pixels = mask.get_flattened_data() if hasattr(mask, "get_flattened_data") else mask.getdata()
        white_pixels = sum(1 for value in pixels if value == 255)
        self.assertEqual(white_pixels, (5 - 2) * (7 - 3))

    def test_metadata_append_is_duplicate_safe_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            forged = tmp_path / "forged.png"
            mask = tmp_path / "mask.png"
            for path in (source, forged, mask):
                path.write_bytes(b"x")

            csv_path = tmp_path / "metadata.csv"
            kwargs = dict(
                csv_path=csv_path,
                image_id="doc_1_v0_forged",
                dataset="CORD",
                split="train",
                language="ko",
                document_type="receipt",
                source_image=source,
                forged_image=forged,
                mask_path=mask,
                edited_field="field_1",
                original_text="10.00",
                forged_text="12.00",
            )

            append_metadata_row(**kwargs)
            append_metadata_row(**kwargs)

            with csv_path.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([row["image_id"] for row in rows], ["doc_1_v0_forged"])
            self.assertIs(get_metadata_index(csv_path), get_metadata_index(csv_path))

    def test_run_pipeline_continues_after_document_failure(self) -> None:
        import main as cli

        docs = [
            SimpleNamespace(image_id="bad_doc"),
            SimpleNamespace(image_id="good_doc"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sample = (tmp_path / "source.png", tmp_path / "forged.png", tmp_path / "mask.png")
            fake_generator = SimpleNamespace(name="diffusers")

            def fake_generate_forged_sample(
                doc,
                output_dir,
                stats,
                seed,
                max_retries,
                image_generator,
                progress_tracker=None,
                variant_index=0,
                num_variants=1,
            ):
                if doc.image_id == "bad_doc":
                    raise RuntimeError("boom")
                return sample

            with patch.object(cli, "generate_forged_sample", fake_generate_forged_sample), \
                    patch.object(cli, "generate_visualizations") as fake_visuals, \
                    patch.object(cli, "write_readme"), \
                    patch.object(cli.logger, "error"):
                stats, sample_paths = cli.run_pipeline(
                    documents=docs,
                    output_dir=tmp_path,
                    seed=100,
                    max_retries=2,
                    image_generator=fake_generator,
                    variants_per_doc=1,
                )

            self.assertEqual(sample_paths, [sample])
            self.assertEqual(stats.failed_generations, 1)
            fake_visuals.assert_called_once()

    def test_run_pipeline_uses_sorted_global_indices_before_sharding(self) -> None:
        import main as cli

        docs = [
            SimpleNamespace(image_id="z_doc", dataset="CORD"),
            SimpleNamespace(image_id="a_doc", dataset="CORD"),
        ]
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_generate_forged_sample(**kwargs):
                calls.append(
                    (
                        kwargs["doc"].image_id,
                        kwargs["variant_index"],
                        kwargs["seed"],
                    )
                )
                return None

            with patch.object(cli, "generate_forged_sample", fake_generate_forged_sample), \
                    patch.object(cli, "write_readme"):
                cli.run_pipeline(
                    documents=docs,
                    output_dir=tmp_path,
                    seed=100,
                    max_retries=1,
                    image_generator=SimpleNamespace(name="diffusers"),
                    variants_per_doc=2,
                    shard_count=2,
                    shard_index=1,
                )

        self.assertEqual(calls, [("a_doc", 1, 101), ("z_doc", 1, 103)])

    def test_run_pipeline_preserves_retry_count_in_final_statistics(self) -> None:
        import main as cli

        doc = SimpleNamespace(image_id="retry_doc", dataset="CORD")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_generate_forged_sample(**kwargs):
                kwargs["stats"].record_retry()
                return None

            with patch.object(cli, "generate_forged_sample", fake_generate_forged_sample), \
                    patch.object(cli, "write_readme"):
                final_stats, _ = cli.run_pipeline(
                    documents=[doc],
                    output_dir=tmp_path,
                    seed=42,
                    max_retries=1,
                    image_generator=SimpleNamespace(name="diffusers"),
                    variants_per_doc=1,
                )

        self.assertEqual(final_stats.retry_count, 1)

    def test_main_constructs_diffusers_generator_before_loading_documents(self) -> None:
        import main as cli

        with patch.object(cli, "setup_logging"), \
                patch.object(cli, "reset_rng"), \
                patch.object(cli, "resolve_output_root", return_value=Path(".")), \
                patch.object(cli, "load_all_datasets", return_value=[]), \
                patch.object(cli, "DiffusersGenerator") as fake_generator_cls:
            fake_generator_cls.from_env.return_value = SimpleNamespace(name="diffusers")
            with self.assertRaises(SystemExit):
                with patch("sys.argv", ["main.py"]):
                    cli.main()

        fake_generator_cls.from_env.assert_called_once()

    def test_builder_retries_when_ocr_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.png"
            Image.new("RGB", (120, 80), "white").save(source_path)
            doc = UnifiedDocument(
                image_id="doc_ocr",
                dataset="CORD",
                split="train",
                language="ko",
                document_type="receipt",
                width=120,
                height=80,
                image_path=source_path,
                fields=[
                    UnifiedField(
                        field_id="field_total",
                        label="total",
                        text="10.00",
                        bbox=[10, 10, 40, 25],
                        polygon=[],
                    )
                ],
            )
            stats = StatsTracker()
            fake_generator = SimpleNamespace(
                name="diffusers",
                generate=lambda img, prompt, bbox, seed=None: img.copy(),
            )

            with patch("src.builder.locate_substring_bbox", return_value=[10, 10, 40, 25]), \
                    patch("src.builder.verify_edited_region_text", side_effect=[False, True]):
                result = generate_forged_sample(
                    doc=doc,
                    output_dir=tmp_path / "out",
                    stats=stats,
                    seed=5,
                    max_retries=2,
                    image_generator=fake_generator,
                )

            self.assertIsNotNone(result)
            self.assertEqual(stats.retry_count, 1)

    def test_builder_fails_when_ocr_verification_never_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.png"
            Image.new("RGB", (120, 80), "white").save(source_path)
            doc = UnifiedDocument(
                image_id="doc_ocr_fail",
                dataset="CORD",
                split="train",
                language="ko",
                document_type="receipt",
                width=120,
                height=80,
                image_path=source_path,
                fields=[
                    UnifiedField(
                        field_id="field_total",
                        label="total",
                        text="10.00",
                        bbox=[10, 10, 40, 25],
                        polygon=[],
                    )
                ],
            )
            stats = StatsTracker()
            fake_generator = SimpleNamespace(
                name="diffusers",
                generate=lambda img, prompt, bbox, seed=None: img.copy(),
            )

            with patch("src.builder.locate_substring_bbox", return_value=[10, 10, 40, 25]), \
                    patch("src.builder.verify_edited_region_text", side_effect=[False, False]):
                result = generate_forged_sample(
                    doc=doc,
                    output_dir=tmp_path / "out",
                    stats=stats,
                    seed=5,
                    max_retries=2,
                    image_generator=fake_generator,
                )

            self.assertIsNone(result)
            self.assertEqual(stats.failed_generations, 1)

    def test_no_obsolete_backend_imports_remain(self) -> None:
        builder_text = Path("src/builder.py").read_text(encoding="utf-8")
        main_text = Path("main.py").read_text(encoding="utf-8")
        combined = (builder_text + main_text).lower()
        obsolete_prefix = "comfy"
        self.assertNotIn(obsolete_prefix + "generator", combined)
        self.assertNotIn(obsolete_prefix + "_generator", combined)
        self.assertNotIn(obsolete_prefix + "ui", combined)
        self.assertFalse((Path("src") / (obsolete_prefix + "_generator.py")).exists())
        self.assertFalse((Path("workflows") / ("flux_" + "fill.json")).exists())
        self.assertFalse(Path("run_" + "colab.py").exists())
        self.assertFalse(Path("src/puter_generator.py").exists())


if __name__ == "__main__":
    unittest.main()
