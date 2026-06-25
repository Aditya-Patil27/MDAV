# ML Design Document
## MDAV: Multimodal Government Document Verification and Automated Authentication

---

### 1. ML Scope

The practical 2-week plan focuses on:
- Train one lightweight visual tamper classifier
- Use OCR and rule-based validation for document semantics
- Use cryptographic verification for signatures
- Fuse outputs into one score

### 2. Dataset Usage Plan

| Dataset | Purpose | Records | Features |
|---------|---------|---------|----------|
| DocTamper | Visual tamper classification/localization | ~170K images | 512x512 RGB + pixel masks |
| MIDV-2020 | OCR and identity-document validation | 1K mock IDs, 72K images | Document images + field annotations |
| CORD | OCR and key-information extraction | ~11K receipts | Receipt images + field labels |
| WildReceipt | Real-world receipt OCR | ~1,740 receipts | Text boxes + 25 key categories |
| SROIE | Scanned-receipt OCR baseline | ~973 receipts | Receipt images + 4 key fields |
| XFUND | Multilingual form understanding | 1,393 forms (7 languages) | Form images + entities |
| AIForge-Doc methodology | AI-generated forgery stress testing | ~4,061 forged images | Diffusion-inpainted + masks |

### 3. Recommended Trainable Model

| Model | Parameters | Pros | Cons |
|-------|-----------|------|------|
| EfficientNet-B0 | 5.3M | Best accuracy/size tradeoff | Slightly complex |
| ResNet18 | 11.7M | Simple, well-understood | Larger than needed |
| MobileNetV3 | 5.4M | Fastest inference | Lower accuracy |

**Preferred**: EfficientNet-B0 for binary classification (clean vs tampered)

### 4. Input Pipeline

```
Raw Document Image
       ↓
Resize to 224x224 (or 512x512 for DocTamper)
       ↓
Normalize: mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
       ↓
Optional Augmentation:
  - Rotation (±15°)
  - Gaussian blur
  - Brightness/contrast shift
  - JPEG compression artifacts
  - Random crop/scale
       ↓
Tensor ready for inference
```

### 5. Training Strategy

| Aspect | Decision |
|--------|----------|
| Dataset subset | 20K balanced (10K clean + 10K tampered) from DocTamper |
| Train/val/test | 70/15/15 split |
| Optimizer | Adam, lr=1e-4 |
| Loss | Binary Cross-Entropy |
| Early stopping | Patience=5 on validation loss |
| Checkpointing | Save best model only |
| Hardware | Colab/Kaggle GPU (T4 or equivalent) |
| Epochs | 15-20 max |

### 6. Metrics

| Metric | Target |
|--------|--------|
| Accuracy | > 90% |
| Precision | > 85% |
| Recall | > 85% |
| F1 Score | > 85% |
| ROC-AUC | > 0.90 |
| Inference Latency | < 2s on CPU |

### 7. Non-ML Components (Rule-Based)

| Component | Implementation |
|-----------|---------------|
| Aadhaar validation | Verhoeff checksum algorithm |
| PAN validation | Regex pattern matching |
| Date logic checks | datetime parsing + comparison |
| Signature verification | pyHanko PKCS#7/CMS |
| Final fusion scoring | Weighted average with thresholds |

### 8. Recommended Output

The model should return:
- `tamper_probability`: float (0-1)
- `confidence_score`: float (0-1)
- `heatmap`: optional Grad-CAM visualization
- `explanation`: human-readable reason

### 9. Practical Recommendation

For the final demo, one trained model plus strong OCR/signature/rule logic is better than multiple unfinished models. Focus on:
1. A working visual classifier trained on DocTamper
2. Robust OCR extraction with PaddleOCR
3. Solid signature verification with pyHanko
4. Clean fusion logic that explains decisions

### 10. Feature Descriptions

#### A. Visual Forensic Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| Texture Inconsistency Score | Local texture irregularities indicating splicing/copy-move | Float (0-1) |
| Noise Residual Features | SRM high-pass maps exposing manipulation traces | Float array/tensor |
| Compression Artifact Indicators | ELA/DCT double-compression cues | Float array |
| Tamper Mask | Pixel-level binary mask localizing forged region | Binary image (HxW) |
| Suspicious Region Coordinates | Bounding-box of detected tampered areas | Integer tuples (x,y,w,h) |
| Heatmap Confidence Score | Per-region probability of manipulation | Float (0-1) |

#### B. OCR & Semantic Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| OCR Extracted Text | Raw text from document fields | String |
| Aadhaar Number | 12-digit ID validated via Verhoeff checksum | String/Numeric |
| PAN Number | 10-char alphanumeric validated via format rules | String |
| Date of Birth | Parsed and range-checked | Date |
| Issue Date | Checked <= current date | Date |
| Expiry Date | Validity date, chronological order check | Date |
| Field Consistency Score | Cross-field agreement (DOB vs age, issue < expiry) | Float (0-1) |
| Validation Status | Aggregated pass/fail of semantic checks | Categorical (Valid/Invalid) |

#### C. Digital Signature Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| Signature Presence | Whether PKCS#7 block is detected | Boolean |
| PKCS#7 Metadata | Parsed CMS signed-data structure | JSON |
| SHA-256 Hash | Cryptographic digest for integrity | Hex string (256-bit) |
| Certificate Status | Valid / expired / revoked | Categorical |
| Issuer Information | Certificate issuer/CA details | String |
| Signature Validation Result | PKCS#7/CMS verification outcome | Categorical (Pass/Fail) |

#### D. Audit & Verification Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| Document Hash | SHA-256 hash anchored to audit record | Hex string |
| Verification Timestamp | When verification event was logged | Datetime |
| Verification Status | Final authenticity decision | Categorical |
| Authenticity Score | Fused confidence from all branches | Float (0-1) |
| Audit Record ID | Unique identifier of audit entry | String/Hash |
