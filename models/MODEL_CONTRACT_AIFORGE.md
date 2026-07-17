# MDAVNet AIForge Segmentation Model Contract

## Identity

- **Model name:** MDAVNet AIForge segmentation model
- **Checkpoint:** `models/best_diffusion.pth`
- **Backend branch:** `diffusion` / AIForge
- **Consumer:** `backend/app/services/diffusion_service.py`
- **Task:** pixel-level localization of AI-generated or diffusion-inpainted document regions

## Architecture

The checkpoint stores weights under the `model` key and includes an
`architecture` dictionary. The loader reads this metadata before constructing
the network.

- Model class: `MDAVNet`
- Segmentation implementation: `segmentation_models_pytorch.Unet`
- Encoder: `resnet18`
- Encoder initialization: `encoder_weights=None`; learned weights come from the checkpoint
- RGB channels: 3
- DCT bins: 21 (`0..20`)
- DCT embedding dimension: 16
- Combined network input: 19 channels
- Output classes: 2
- Output shape: `[B, 2, H, W]`
- Class 0: authentic/background
- Class 1: AI-forged/tampered
- Activation: `torch.softmax(logits, dim=1)[:, 1]`

## Input and Preprocessing

The input is represented as aligned RGB and DCT streams:

1. Open the document and convert it to grayscale.
2. Save a temporary JPEG at checkpoint `jpeg_quality` (95 for this checkpoint).
3. Read the JPEG luminance coefficient array with `jpegio`.
4. Take absolute coefficient values and clip them to `0..dct_bins-1`.
5. Decode the same temporary JPEG as RGB.
6. Crop RGB and DCT to a common 8-pixel-aligned region.
7. Normalize RGB with mean `[0.485, 0.456, 0.406]` and standard deviation
   `[0.229, 0.224, 0.225]`.
8. Pad the right and bottom edges to checkpoint stride 32, then crop the output
   probability map back to the valid region.

The DCT map contains integer embedding indices, not normalized floating-point
pixels. Backend preprocessing must change whenever the training contract changes.

## Operating Threshold and Aggregation

- Recommended pixel threshold: **0.95**
- Resolution order: `MDAV_DIFFUSION_THRESHOLD`, checkpoint `best_threshold`, then `0.95`
- Pixel statistics: thresholded area, maximum probability, 0.995 quantile,
  and connected-component measurements.
- A document receives forged evidence only when at least one connected region
  crosses the pixel threshold and contains at least
  `MDAV_DIFFUSION_MIN_COMPONENT_PIXELS` pixels (default: 16). A map with no
  such region is **inconclusive/vacuous**, even if its high quantile is large.
- For a valid region, the branch uses that region's 95th-percentile pixel score
  and derives confidence from its margin above the operating threshold and its
  relative area. These values are model evidence, not calibrated probabilities.
- On Aadhaar, PAN, passports, and driving licences the committed confidence is
  capped by `MDAV_IDENTITY_FORENSICS_CONFIDENCE_CAP` (default: 0.25) until a
  dedicated identity-document calibration is promoted.

## Validation at Threshold 0.95

| Metric | Value |
|---|---:|
| Accuracy | 0.9867 |
| Precision | 0.9827 |
| Recall | 0.5863 |
| F1 / Dice | 0.7345 |
| IoU | 0.5804 |
| Specificity | 0.9997 |

Confusion matrix:

| | Predicted forged | Predicted authentic |
|---|---:|---:|
| Actually forged | TP = 5,163,147 | FN = 3,642,559 |
| Actually authentic | FP = 90,880 | TN = 271,073,206 |

The selected threshold is conservative: precision and specificity are high,
false positives are rare, and recall is moderate. A low branch score does not
prove authenticity; it represents limited localized AIForge evidence.

## Backend Integration Contract

```python
ai_forgery_prob, confidence = service._predict(image_path)
```

Both values are in `[0, 1]`. `analyze()` maps them to evidence as:

```python
from_probability(
    1.0 - ai_forgery_prob,
    confidence=confidence,
    source="diffusion",
    details=segmentation_diagnostics,
)
```

Missing weights, missing ML dependencies, invalid checkpoints, and unreadable
images produce a vacuous belief and do not stop the remaining MDAV branches.

## Limitations

- Training and validation cover AIForge-style edits in receipt and form images.
- Generalization to Aadhaar, PAN, passports, driving licences, unseen generation
  models, photographed documents, and adversarial recompression requires a
  separate cross-domain evaluation.
- The operating threshold favors low false-positive rate over recall.
- Full-page inference can downscale very large inputs through
  `MDAV_DIFFUSION_MAX_SIDE`; report this setting in evaluations.
