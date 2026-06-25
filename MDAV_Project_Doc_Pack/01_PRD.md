# Product Requirements Document (PRD)
## MDAV: Multimodal Government Document Verification and Automated Authentication

**Project 45 (Governance) | Group 25**

---

### 1. Problem Statement

Government documents are verified manually, which is slow, inconsistent, and hard to scale. Existing verification systems rely on a single modality (visual inspection, OCR validation, or cryptographic verification) and cannot handle both digitally signed documents and conventional scanned documents within a unified pipeline. MDAV addresses this by combining AI-based forgery detection, semantic validation, digital signature verification, and blockchain-backed auditability into a single framework.

### 2. Goals

- Verify uploaded government documents from scans, photos, and digitally signed PDFs
- Detect obvious tampering, AI-generated modifications, inpainting, text replacement, and copy-move attacks
- Validate document-specific fields: Aadhaar (Verhoeff checksum), PAN (regex), dates, mandatory fields
- Verify PKCS#7/CMS digital signatures embedded in signed documents
- Produce a single authenticity score with explainable verification results
- Maintain an immutable audit log of all verification actions on a blockchain-backed layer

### 3. Non-Goals

- Replacing official government identity systems (DigiLocker, UIDAI)
- Building a large-scale production fraud platform in v1
- Training heavyweight foundation models from scratch
- Real-time document processing at government scale

### 4. Users

- **Primary**: College project evaluators, demo users, system admins
- **Secondary**: Future government-office operators and document reviewers

### 5. Core Features

| Feature | Description |
|---------|-------------|
| Document Upload | Accept scanned images (JPEG/PNG) and digitally signed PDFs |
| Preprocessing | Deskew, normalize, denoise, resize, document-type classification |
| OCR Text Extraction | PaddleOCR pipeline for text block and field extraction |
| Semantic Validation | Aadhaar checksum, PAN regex, date logic, cross-field consistency |
| Visual Tamper Detection | CNN-based classifier for clean vs tampered documents with heatmap |
| Digital Signature Verification | PKCS#7/CMS validation, certificate chain, hash verification |
| Confidence Fusion | Weighted scoring combining all branch outputs |
| Audit Logging | Blockchain-backed immutable verification records |
| Dashboard | Verification results, authenticity scores, anomaly reports, history |

### 6. Feature Categories

#### A. Visual Forensic Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| Texture Inconsistency Score | Local texture irregularities indicating splicing/copy-move | Float (0-1) |
| Noise Residual Features | SRM high-pass maps exposing manipulation traces | Float array |
| Compression Artifact Indicators | ELA/DCT double-compression cues | Float array |
| Tamper Mask | Pixel-level binary mask localizing forged region | Binary image (HxW) |
| Suspicious Region Coordinates | Bounding-box of detected tampered areas | Integer tuples |
| Heatmap Confidence Score | Per-region probability of manipulation | Float (0-1) |

#### B. OCR & Semantic Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| OCR Extracted Text | Raw text from document fields | String |
| Aadhaar Number | 12-digit ID validated via Verhoeff checksum | String |
| PAN Number | 10-char alphanumeric validated via format rules | String |
| Date of Birth | Parsed and range-checked | Date |
| Issue Date | Checked <= current date | Date |
| Expiry Date | Validity date, chronological order check | Date |
| Field Consistency Score | Cross-field agreement (DOB vs age, issue < expiry) | Float (0-1) |
| Validation Status | Aggregated pass/fail of semantic checks | Categorical |

#### C. Digital Signature Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| Signature Presence | Whether PKCS#7 block is detected | Boolean |
| PKCS#7 Metadata | Parsed CMS signed-data structure | JSON |
| SHA-256 Hash | Cryptographic digest for integrity | Hex string |
| Certificate Status | Valid / expired / revoked | Categorical |
| Issuer Information | Certificate issuer/CA details | String |
| Signature Validation Result | PKCS#7/CMS verification outcome | Categorical |

#### D. Audit & Verification Features

| Feature | Description | Data Type |
|---------|-------------|-----------|
| Document Hash | SHA-256 hash anchored to audit record | Hex string |
| Verification Timestamp | When verification event was logged | Datetime |
| Verification Status | Final authenticity decision | Categorical |
| Authenticity Score | Fused confidence from all branches | Float (0-1) |
| Audit Record ID | Unique identifier of audit entry | String |

### 7. Success Criteria

- End-to-end upload-to-result flow works reliably
- OCR extracts key fields with acceptable accuracy on sample documents
- Signature validation passes/fails correctly on test PDFs
- Visual detector separates clean vs tampered samples on DocTamper dataset
- Dashboard clearly explains why a document was accepted or flagged
- Blockchain audit trail is immutable and queryable

### 8. Constraints

- Two-week delivery window
- Limited/no budget for paid software
- No reliance on high-end local GPU
- Must remain demo-friendly and maintainable

### 9. Risks

| Risk | Mitigation |
|------|------------|
| Too many datasets and model branches | Focus on one trained visual model + OCR/signature rules |
| Poor OCR on low-quality scans | Preprocess with deskew/denoise; fallback to manual review |
| Over-scoping blockchain component | Use simple hash-chain instead of full blockchain |
| Integration delays | Modular architecture; each branch demoed independently |
| AI-generated forgeries evade detection | Include AIForge-Doc stress testing in evaluation |

### 10. Delivery Strategy

Use one trained visual model, OCR libraries, signature verification libraries, and rule-based validation. Keep the pipeline modular so each branch can be demoed independently. Fuse outputs into one score for the final authenticity decision.

### 11. Datasets Used

| Dataset | Purpose | Domain |
|---------|---------|--------|
| DocTamper | Visual tamper classification/localization | Document forgery detection |
| MIDV-2020 | OCR and identity-document validation | Identity document analysis |
| CORD | OCR and key-information extraction | Receipt understanding |
| WildReceipt | Real-world receipt OCR | Receipt KIE in the wild |
| SROIE | Scanned-receipt OCR baseline | Scanned receipt OCR |
| XFUND | Multilingual form understanding | Form key-value extraction |
| AIForge-Doc methodology | AI-generated forgery stress testing | Diffusion-based forgery detection |

### 12. Weekly Execution Plan

| Week | Activities | Outcome |
|------|-----------|---------|
| Week 1 | Literature survey, research gaps, dataset study, architecture | Research analysis and planning complete |
| Week 2 | Dataset collection, preprocessing, OCR pipeline, semantic validation, signature verification | Functional document processing pipeline |
| Week 3 | Visual forgery model training, integration, confidence fusion | Working multimodal verification system |
| Week 4 | Dashboard, blockchain audit, evaluation, IEEE paper draft, demo | Complete MDAV prototype |
