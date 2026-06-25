# Deployment Plan
## MDAV: Multimodal Government Document Verification and Automated Authentication

---

### 1. Deployment Architecture

| Component | Target | Notes |
|-----------|--------|-------|
| Frontend | Vercel / Netlify | Static Next.js export |
| Backend | Render / Railway / local Docker | FastAPI Python service |
| DB | PostgreSQL / Supabase | Managed database |
| Storage | Supabase Storage / local | Document file storage |
| ML Model | Packaged with backend or separate service | FastAPI route |

### 2. Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/mdav

# Authentication
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# Storage
STORAGE_BUCKET=mdav-documents
STORAGE_PATH=./storage

# ML Models
OCR_MODEL_PATH=./models/ocr
VISION_MODEL_PATH=./models/vision_best.pt

# App
APP_BASE_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000
NODE_ENV=production
```

### 3. Recommended Runtime Layout

```
mdav/
├── frontend/           # Next.js app
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── next.config.js
├── backend/            # FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── services/
│   │   └── models/
│   ├── requirements.txt
│   └── Dockerfile
├── ml_service/         # ML inference (optional separate service)
│   ├── models/
│   ├── inference.py
│   └── Dockerfile
├── docs/               # Documentation
├── models/             # Trained model weights
│   └── vision_best.pt
├── docker-compose.yml
└── README.md
```

### 4. Docker Strategy

```yaml
# docker-compose.yml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
  
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/mdav
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=mdav
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### 5. CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy MDAV
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run backend tests
        run: cd backend && pip install -r requirements.txt && pytest
      - name: Run frontend tests
        run: cd frontend && npm install && npm test
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy frontend to Vercel
      - name: Deploy backend to Render
```

### 6. Monitoring

| Metric | Tool | Purpose |
|--------|------|---------|
| Request logs | FastAPI middleware | Track API usage |
| Error logs | Python logging | Debug issues |
| Model inference timing | Custom metrics | Performance monitoring |
| Failed upload counters | Database queries | Reliability tracking |

### 7. Demo Mode

If cloud deployment is too complex:

```bash
# One-command local setup
docker-compose up --build

# Or manual setup
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

**Demo checklist:**
- [ ] Preloaded test files in /test_samples/
- [ ] Live upload and result flow working
- [ ] Fallback sample result for presentation
- [ ] Dashboard showing all features
- [ ] Audit trail visible

### 8. Demo File Structure

```
test_samples/
├── clean_aadhaar.jpg          # Clean document
├── tampered_aadhaar.jpg       # Tampered document
├── signed_document.pdf        # Signed PDF
├── invalid_pan.txt            # Invalid PAN
└── ai_inpainted.jpg           # AI-forged document
```
