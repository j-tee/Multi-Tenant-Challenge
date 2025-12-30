# Multi-Tenant Invoice Reconciliation API

A production-ready multi-tenant invoice reconciliation system built with FastAPI, Strawberry GraphQL, and SQLAlchemy 2.0.

## Features

- **Multi-tenancy**: Complete data isolation between organizations
- **REST & GraphQL APIs**: Dual API support with shared service layer
- **Fully Async**: Async SQLAlchemy 2.0 with async/await throughout
- **Automated Reconciliation**: Deterministic matching with scoring algorithm
- **AI Integration**: Natural language explanations with graceful fallback
- **Idempotency**: Safe bulk operations with idempotency key support
- **Type Safety**: Full Python type hints and Pydantic validation

## Quick Start

### Prerequisites

- Python 3.13+
- pip or uv package manager

### Installation

```bash
# Clone the repository
cd invoice-reconciliation-api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Or using uv
uv sync --all-extras
```

### Configuration

Copy the example environment file and configure as needed:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./reconciliation.db` |
| `OPENAI_API_KEY` | OpenAI API key for AI explanations | `None` (fallback mode) |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` |
| `AI_ENABLED` | Enable/disable AI features | `true` |
| `DEBUG` | Enable debug mode | `false` |

### Running the Server

```bash
# Development server with hot reload
uvicorn app.main:app --reload

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- REST API: `http://localhost:8000/docs` (Swagger UI)
- GraphQL: `http://localhost:8000/graphql` (GraphiQL)

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_reconciliation.py -v
```

---

## Architecture

### Project Structure

```
├── app/
│   ├── api/
│   │   ├── graphql/        # GraphQL schema and resolvers
│   │   │   ├── schema.py   # Query and Mutation definitions
│   │   │   ├── types.py    # GraphQL types
│   │   │   └── resolvers.py
│   │   ├── rest/           # REST API endpoints
│   │   │   ├── tenants.py
│   │   │   ├── invoices.py
│   │   │   ├── bank_transactions.py
│   │   │   └── reconciliation.py
│   │   └── exception_handlers.py
│   ├── core/
│   │   ├── config.py       # Application settings
│   │   ├── database.py     # Database configuration
│   │   └── exceptions.py   # Custom exceptions
│   ├── models/             # SQLAlchemy models
│   │   ├── tenant.py
│   │   ├── invoice.py
│   │   ├── bank_transaction.py
│   │   ├── match.py
│   │   └── idempotency.py
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   │   ├── tenant.py
│   │   ├── invoice.py
│   │   ├── bank_transaction.py
│   │   ├── reconciliation.py
│   │   ├── match.py
│   │   ├── ai_explanation.py
│   │   └── idempotency.py
│   └── main.py
└── tests/
```

### Design Decisions

#### 1. Clean Architecture

The application follows clean architecture principles with clear separation:

- **API Layer** (`app/api/`): Handles HTTP requests, validation, and response formatting
- **Service Layer** (`app/services/`): Contains all business logic
- **Data Layer** (`app/models/`): SQLAlchemy models and database operations

**Benefit**: Both REST and GraphQL APIs share the same service layer, ensuring consistent business logic and eliminating code duplication.

#### 2. Multi-Tenancy Strategy

Every tenant-scoped table includes a `tenant_id` column. All queries are filtered by tenant at the service layer.

```python
# Example: Every query enforces tenant isolation
def get_by_id(self, tenant_id: str, invoice_id: str) -> Invoice:
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant_id,  # Always filtered
    )
```

**Tradeoff**: This adds overhead to every query but provides strong isolation guarantees without complex database-level policies.

#### 3. Transaction Boundaries

Database sessions are managed per-request with commit at the API layer:

```python
@router.post("/invoices")
def create_invoice(..., db: Session = Depends(get_db)):
    invoice = service.create(tenant_id, data)
    db.commit()  # Explicit commit at API boundary
    return invoice
```

**Rationale**: This gives explicit control over transaction scope and makes testing easier.

---

## Reconciliation Scoring Algorithm

The reconciliation engine uses a weighted scoring system to match invoices with bank transactions.

### Score Components

| Factor | Weight | Description |
|--------|--------|-------------|
| **Amount Match** | 40% | Exact match = 1.0, within 1% tolerance = 0.8 |
| **Date Proximity** | 30% | Same day = 1.0, within 3 days = 0.7, within 7 days = 0.4 |
| **Text Similarity** | 20% | Token matching between descriptions |
| **Currency Match** | 10% | Same currency = 1.0 |

### Formula

```
Final Score = (amount_score × 0.4) + (date_score × 0.3) + 
              (text_score × 0.2) + (currency_score × 0.1)
```

### Match Threshold

- Candidates with score ≥ 0.5 are considered viable matches
- Results are ranked by score in descending order
- The `min_score` parameter allows customization

### Example Scoring

| Scenario | Amount | Date | Text | Currency | Final |
|----------|--------|------|------|----------|-------|
| Perfect match | 1.0 (40%) | 1.0 (30%) | 0.8 (20%) | 1.0 (10%) | **0.86** |
| Amount + date | 1.0 (40%) | 0.7 (30%) | 0.0 (20%) | 1.0 (10%) | **0.71** |
| Amount only | 1.0 (40%) | 0.0 (30%) | 0.0 (20%) | 1.0 (10%) | **0.50** |

**Design Choice**: Amount is weighted highest (40%) because financial matching relies primarily on monetary accuracy. Text similarity is lower (20%) because bank memos are often inconsistent.

---

## Idempotency Implementation

### Mechanism

The bank transaction import endpoint supports idempotency via the `Idempotency-Key` header.

```http
POST /tenants/{tenant_id}/bank-transactions/import
Idempotency-Key: unique-request-id-123
Content-Type: application/json

{"transactions": [...]}
```

### How It Works

1. **First Request**: 
   - Payload is hashed (SHA-256)
   - Operation executes
   - Result stored with key + hash

2. **Subsequent Request (Same Key + Same Payload)**:
   - Returns cached result immediately
   - No duplicate processing

3. **Subsequent Request (Same Key + Different Payload)**:
   - Returns `409 Conflict`
   - Prevents accidental reuse

### Data Model

```sql
CREATE TABLE idempotency_records (
    id VARCHAR(36) PRIMARY KEY,
    idempotency_key VARCHAR(255) UNIQUE,
    tenant_id VARCHAR(36),
    operation VARCHAR(100),
    payload_hash VARCHAR(64),  -- SHA-256 hash
    response TEXT,             -- Cached JSON response
    created_at TIMESTAMP,
    expires_at TIMESTAMP       -- TTL (24 hours default)
);
```

### Tradeoffs

| Approach | Pros | Cons |
|----------|------|------|
| **Payload Hash** (chosen) | Detects changed payloads | Requires storing hash |
| **Timestamp-based** | Simple | No payload change detection |
| **Full payload storage** | Can compare exactly | Storage overhead |

**Decision**: Payload hashing provides a good balance of security and storage efficiency.

---

## AI Integration

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  API Request    │────▶│ AI Explanation  │────▶│   OpenAI API    │
│                 │     │    Service      │     │  (if available) │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │                        │
                                 │ fallback               │ error/timeout
                                 ▼                        ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Deterministic  │◀────│  Catch & Log    │
                        │   Explanation   │     │                 │
                        └─────────────────┘     └─────────────────┘
```

### Data Sent to AI

Only tenant-authorized data is included:

- Invoice: amount, date, description, vendor name
- Transaction: amount, posted date, description
- Computed: match score breakdown

**No sensitive identifiers or API keys are sent.**

### Fallback Explanations

When AI is unavailable, the system generates deterministic explanations:

```python
# Example fallback output
"The amounts match exactly ($1000.00 USD). The dates are very close or matching. 
There is some textual overlap between the descriptions. 
This appears to be a strong match."
```

### Configuration

```bash
# Enable AI (default)
AI_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=10

# Disable AI (always use fallback)
AI_ENABLED=false
```

---

## API Reference

### REST Endpoints

#### Tenants
- `POST /tenants` - Create tenant
- `GET /tenants` - List tenants
- `GET /tenants/{tenant_id}` - Get tenant

#### Invoices
- `POST /tenants/{tenant_id}/invoices` - Create invoice
- `GET /tenants/{tenant_id}/invoices` - List invoices (with filters)
- `GET /tenants/{tenant_id}/invoices/{id}` - Get invoice
- `DELETE /tenants/{tenant_id}/invoices/{id}` - Delete invoice

**Filters**: `status`, `vendor_id`, `date_from`, `date_to`, `amount_min`, `amount_max`

#### Bank Transactions
- `POST /tenants/{tenant_id}/bank-transactions/import` - Bulk import
- `GET /tenants/{tenant_id}/bank-transactions` - List transactions

#### Reconciliation
- `POST /tenants/{tenant_id}/reconcile` - Run reconciliation
- `GET /tenants/{tenant_id}/matches` - List matches
- `POST /tenants/{tenant_id}/matches/{id}/confirm` - Confirm match
- `GET /tenants/{tenant_id}/reconcile/explain` - AI explanation

### GraphQL Schema

```graphql
type Query {
  tenants: [Tenant!]!
  invoices(tenantId: ID!, filters: InvoiceFilters, pagination: Pagination): InvoiceConnection!
  bankTransactions(tenantId: ID!, filters: TransactionFilters): TransactionConnection!
  matches(tenantId: ID!, filters: MatchFilters): [Match!]!
  explainReconciliation(tenantId: ID!, invoiceId: ID!, transactionId: ID!): Explanation!
}

type Mutation {
  createTenant(input: TenantInput!): Tenant!
  createInvoice(tenantId: ID!, input: InvoiceInput!): Invoice!
  deleteInvoice(tenantId: ID!, invoiceId: ID!): Boolean!
  importBankTransactions(tenantId: ID!, input: ImportInput!, idempotencyKey: String): ImportResult!
  reconcile(tenantId: ID!, input: ReconcileInput): ReconciliationResult!
  confirmMatch(tenantId: ID!, matchId: ID!): Match!
}
```

---

## Testing Strategy

### Test Categories

1. **Unit Tests**: Service layer logic
2. **Integration Tests**: API endpoints with test database
3. **Isolation Tests**: Multi-tenant data separation
4. **Idempotency Tests**: Duplicate request handling
5. **AI Tests**: Mocked AI + fallback behavior

### Test Coverage

```
tests/
├── conftest.py              # Fixtures and test database
├── test_invoices.py         # Invoice CRUD and filtering
├── test_bank_transactions.py # Import and idempotency
├── test_reconciliation.py   # Matching and confirmation
├── test_ai_explanation.py   # AI and fallback
└── test_tenant_isolation.py # Multi-tenant security
```

### Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing

# Specific category
pytest tests/test_tenant_isolation.py -v
```

---

## Future Improvements

1. **Database Migrations**: Add Alembic for schema migrations
2. **Caching**: Add Redis caching for frequent queries
3. **Audit Logging**: Track all data changes per tenant
4. **Rate Limiting**: Per-tenant rate limiting
5. **Background Jobs**: Async reconciliation for large datasets
6. **Webhooks**: Notify on match confirmations

---

## License

MIT License - See LICENSE file for details.
