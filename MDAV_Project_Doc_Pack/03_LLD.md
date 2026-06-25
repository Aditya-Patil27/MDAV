# Low-Level Design (LLD)
## MDAV: Multimodal Government Document Verification and Automated Authentication

---

### 1. Backend Services

#### 1.1 Upload Service
- Accept image/PDF uploads (JPEG, PNG, PDF)
- Validate size (max 20MB) and file type
- Store original file in object storage
- Create verification job record in DB
- Return job ID for status tracking

#### 1.2 Preprocessing Service
- Deskew image using Hough transform
- Normalize resolution to standard DPI
- Convert PDF pages to images (300 DPI)
- Split multi-page PDFs into processing units
- Apply denoising and contrast enhancement

#### 1.3 OCR Service
- Extract text blocks and bounding boxes
- Return raw text, coordinates, and confidence scores
- Normalize dates (DD/MM/YYYY, YYYY-MM-DD)
- Normalize ID numbers (Aadhaar, PAN)
- Handle multi-language documents

#### 1.4 Semantic Validation Service

| Validator | Rule | Implementation |
|-----------|------|----------------|
| Aadhaar | 12 digits, Verhoeff checksum | Verhoeff algorithm |
| PAN | 5 letters + 4 digits + 1 letter | Regex: `^[A-Z]{5}[0-9]{4}[A-Z]$` |
| DOB | Valid date, age 0-150 years | datetime parsing |
| Issue Date | <= current date | datetime comparison |
| Expiry Date | > issue date (if present) | datetime comparison |
| Field Presence | Required fields exist | Null/empty checks |
| Cross-field | DOB vs age consistency | Rule engine |

#### 1.5 Visual Analysis Service
- Load trained CNN model (EfficientNet-B0 / ResNet18)
- Run inference on preprocessed document image
- Output tamper probability (0-1)
- Optionally generate Grad-CAM heatmap
- Return confidence score and explanation

#### 1.6 Signature Verification Service
- Detect embedded digital signatures (PKCS#7/CMS)
- Parse CMS signed-data structure
- Validate certificate chain against trusted CAs
- Verify document hash matches signature hash
- Return pass/fail with detailed reason

#### 1.7 Fusion Service
- Collect outputs from all branches
- Apply weighted scoring:
  - Visual score: 0.40
  - Semantic score: 0.35
  - Signature score: 0.25
- Generate human-readable reason summary
- Determine final state: APPROVED / FLAGGED / REVIEW_REQUIRED

#### 1.8 Audit Service
- Store document hash (SHA-256) in blockchain audit log
- Record verification timestamp
- Log all branch outputs
- Store final verification decision
- Provide audit trail query API

### 2. API Endpoints

```
POST   /api/auth/register          - Register new user
POST   /api/auth/login             - Login and get JWT

POST   /api/documents/upload       - Upload document for verification
GET    /api/documents/{id}         - Get document metadata
GET    /api/documents/{id}/results - Get verification results
GET    /api/documents/{id}/audit   - Get audit trail
GET    /api/history                - Get verification history
POST   /api/verify/retry           - Retry verification

GET    /api/dashboard/stats        - Get dashboard statistics
GET    /api/dashboard/recent       - Get recent verifications
```

### 3. Database Schema

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    doc_type VARCHAR(50), -- 'aadhaar', 'pan', 'passport', 'other'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Verification jobs table
CREATE TABLE verification_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- OCR results table
CREATE TABLE ocr_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES verification_jobs(id),
    raw_text TEXT,
    extracted_fields JSONB,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Semantic results table
CREATE TABLE semantic_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES verification_jobs(id),
    aadhaar_valid BOOLEAN,
    pan_valid BOOLEAN,
    dates_valid BOOLEAN,
    field_presence_valid BOOLEAN,
    consistency_score FLOAT,
    validation_details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vision results table
CREATE TABLE vision_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES verification_jobs(id),
    tamper_probability FLOAT,
    confidence FLOAT,
    heatmap_path VARCHAR(500),
    explanation TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Signature results table
CREATE TABLE signature_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES verification_jobs(id),
    signature_detected BOOLEAN,
    certificate_valid BOOLEAN,
    hash_valid BOOLEAN,
    validation_result VARCHAR(50),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Fused results table
CREATE TABLE fused_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES verification_jobs(id),
    visual_score FLOAT,
    semantic_score FLOAT,
    signature_score FLOAT,
    final_score FLOAT,
    decision VARCHAR(50), -- APPROVED, FLAGGED, REVIEW_REQUIRED
    reason_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit logs table (blockchain-backed)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES verification_jobs(id),
    document_hash VARCHAR(255),
    verification_timestamp TIMESTAMP DEFAULT NOW(),
    verification_status VARCHAR(50),
    authenticity_score FLOAT,
    previous_hash VARCHAR(255), -- blockchain link
    block_hash VARCHAR(255),
    details JSONB
);
```

### 4. Fusion Logic

```python
WEIGHTS = {
    "visual": 0.40,
    "semantic": 0.35,
    "signature": 0.25
}

def compute_final_score(visual, semantic, signature):
    if signature is None:  # No signature detected
        return 0.60 * visual + 0.40 * semantic
    
    return (
        WEIGHTS["visual"] * visual +
        WEIGHTS["semantic"] * semantic +
        WEIGHTS["signature"] * signature
    )

def determine_decision(score):
    if score >= 0.8:
        return "APPROVED"
    elif score >= 0.5:
        return "FLAGGED"
    else:
        return "REVIEW_REQUIRED"
```

### 5. Error Handling

| Error | Response | Action |
|-------|----------|--------|
| Unsupported file type | 400 + message | Reject upload |
| Corrupt PDF/image | 422 + message | Reject with reason |
| OCR failure | 500 + message | Log error, continue other branches |
| Signature missing | 200 + null signature | Skip signature branch |
| Model inference failure | 500 + message | Log error, return partial results |

### 6. Logging

- Job ID, document ID, timestamps at every stage
- Branch outputs (OCR, semantic, vision, signature)
- Final decision and confidence score
- Error details for failed processing
- Audit trail for compliance and traceability
