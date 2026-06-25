# Testing Plan
## MDAV: Multimodal Government Document Verification and Automated Authentication

---

### 1. Unit Tests

| Component | Test Cases |
|-----------|-----------|
| Upload Service | File type validation, size limits, storage creation |
| Preprocessing | Deskew accuracy, normalization, PDF-to-image conversion |
| OCR Parser | Text extraction, field normalization, confidence parsing |
| Aadhaar Validator | Verhoeff checksum, format validation, edge cases |
| PAN Validator | Regex matching, valid/invalid formats |
| Date Validator | Format parsing, range checks, chronological order |
| Signature Wrapper | CMS parsing, certificate validation, hash verification |
| Fusion Score | Weighted computation, edge cases (missing branches) |

### 2. Integration Tests

| Flow | Verification |
|------|-------------|
| Upload → Preprocess → OCR | Text extracted correctly from uploaded document |
| OCR → Semantic Validation | Fields validated against rules |
| Upload → Visual Model | Tamper score returned for document |
| Upload → Signature Check | Signature detected/validated for signed PDFs |
| All Branches → Fusion | Final score computed and decision made |
| Fusion → Audit Log | Results stored in blockchain audit layer |
| Audit → Dashboard | History and audit pages load correctly |

### 3. ML Tests

| Test | Description |
|------|-------------|
| Class Balance | Verify equal distribution of clean/tampered samples |
| Train/Val Split | Ensure no data leakage between splits |
| Accuracy on Held-out | Achieve >90% accuracy on test set |
| Inference Speed | < 2s per document on CPU |
| Robustness: Blur | Performance on blurred documents |
| Robustness: Rotation | Performance on rotated documents |
| Robustness: JPEG | Performance on compressed documents |
| Failure Cases | Identify and document misclassifications |

### 4. Security Tests

| Test | Description |
|------|-------------|
| File Type Enforcement | Only JPEG/PNG/PDF accepted |
| Oversized Rejection | Files > 20MB rejected |
| Corrupt File Handling | Corrupt files rejected gracefully |
| Path Traversal | No directory traversal in file storage |
| Rate Limiting | Upload rate limiting enforced |
| Auth Enforcement | Unauthenticated requests rejected |
| SQL Injection | Parameterized queries prevent injection |

### 5. UX Tests

| Test | Description |
|------|-------------|
| Upload Flow | User can upload document without confusion |
| Results Readability | Verification result clearly displayed |
| Risk Reason | Explanation of why document was flagged |
| History Screen | Loads quickly, shows all past verifications |
| Audit Trail | Complete verification history visible |

### 6. Demo Test Cases

| Case | Expected Result |
|------|-----------------|
| Clean signed PDF | APPROVED with valid signature |
| Tampered scanned image | FLAGGED with tamper heatmap |
| OCR mismatch example | FLAGGED with field inconsistency |
| Invalid Aadhaar/PAN | FLAGGED with validation error |
| Missing signature | REVIEW_REQUIRED with no signature info |
| AI-inpainted document | FLAGGED with visual anomalies |

### 7. Exit Criteria

- [ ] Core flow works end-to-end without crashes
- [ ] Each branch returns a meaningful result
- [ ] Final score and decision are displayed correctly
- [ ] Audit trail is immutable and queryable
- [ ] Dashboard explains verification decisions
- [ ] No major security vulnerabilities
- [ ] Demo can be presented without manual intervention

### 8. Test Data Requirements

| Type | Count | Source |
|------|-------|--------|
| Clean scanned documents | 20 | MIDV-2020, CORD |
| Tampered documents | 20 | DocTamper |
| Signed PDFs | 10 | Sample DigiLocker-style |
| Invalid Aadhaar/PAN | 10 | Synthetic |
| AI-inpainted documents | 10 | AIForge-Doc methodology |
