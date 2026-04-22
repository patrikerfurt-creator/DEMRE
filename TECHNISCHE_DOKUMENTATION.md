# DEMRE – Technische Dokumentation

Buchhaltungs- und Rechnungsverwaltungssystem für **Demme Immobilien Verwaltung GmbH**.

---

## Inhaltsverzeichnis

1. [Systemübersicht](#1-systemübersicht)
2. [Tech-Stack](#2-tech-stack)
3. [Architektur & Deployment](#3-architektur--deployment)
4. [Datenbankmodell](#4-datenbankmodell)
5. [Backend – Module & Services](#5-backend--module--services)
6. [API-Endpunkte](#6-api-endpunkte)
7. [Geschäftslogik](#7-geschäftslogik)
8. [Ordnerüberwachung & Datei-Workflows](#8-ordnerüberwachung--datei-workflows)
9. [Windows-Dienst (SFTP-Uploader)](#9-windows-dienst-sftp-uploader)
10. [Frontend](#10-frontend)
11. [Authentifizierung & Rollen](#11-authentifizierung--rollen)
12. [Konfiguration](#12-konfiguration)
13. [Datenbankmigrationen](#13-datenbankmigrationen)
14. [Bekannte Besonderheiten](#14-bekannte-besonderheiten)

---

## 1. Systemübersicht

DEMRE verwaltet den vollständigen Buchhaltungskreislauf einer Immobilienverwaltung:

| Bereich | Funktion |
|---|---|
| **Ausgangsrechnungen** | Automatischer Monatslauf aus Verträgen, PDF + ZUGFeRD/Factur-X |
| **Eingangsrechnungen** | Kreditoren-Verwaltung, KI-Extraktion, SEPA-Überweisung |
| **Belege** | Mitarbeiter-Ausgaben, KI-Extraktion, SEPA-Erstattung |
| **STB-Export** | Genehmigte Dokumente für den Steuerberater bündeln |
| **SFTP-Uploader** | Windows-Dienst überträgt Dokumente vom Büro-PC auf den Server |

---

## 2. Tech-Stack

| Komponente | Technologie | Version |
|---|---|---|
| Backend | Python, FastAPI, SQLAlchemy (async), Alembic, Pydantic v2 | Python 3.12 |
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query | React 18 |
| Datenbank | PostgreSQL | 16 |
| PDF-Generierung | ReportLab | – |
| ZUGFeRD/Factur-X | drafthorse | – |
| KI-Extraktion | Anthropic Claude Haiku | `claude-haiku-4-5-20251001` |
| Scheduler | APScheduler (AsyncIOScheduler) | – |
| Deployment | Docker, Docker Compose | – |
| SFTP-Uploader | Python, paramiko, pywin32, watchdog | Windows-Dienst |

---

## 3. Architektur & Deployment

### Entwicklung

```
docker compose up -d
# Frontend: http://localhost:5173  (Vite Dev Server)
# Backend:  http://localhost:8000
# API-Docs: http://localhost:8000/docs
# DB:       localhost:5432
```

### Produktion

```
# Server: 87.106.219.148, User: patrik, Pfad: /opt/DEMRE
# Extern erreichbar unter: http://87.106.219.148:8081/

sudo git pull
sudo docker compose -f docker-compose.prod.yml up -d --build
```

Produktion nutzt `Dockerfile.prod` (Multi-Stage: Vite-Build → nginx). Der nginx-Container übernimmt:
- Statisches Serving des React-Builds
- Reverse Proxy `/api/` → Backend-Container auf Port 8000
- CSP-Header (inkl. `unsafe-eval` für den Vite-Produktionsbuild)

### Container-Übersicht

| Container | Image | Ports |
|---|---|---|
| `frontend` | nginx (Multi-Stage) | 8081 → 80 (Produktion) |
| `backend` | Python 3.12-slim | 8000 (intern) |
| `db` | postgres:16 | 5432 (intern) |

---

## 4. Datenbankmodell

Alle Tabellen verwenden UUID als Primärschlüssel und ein `TimestampMixin` mit `created_at`/`updated_at`.

### Kernentitäten

```
users
  id, email, full_name, role (admin/user/readonly), is_active
  iban, bic                          ← Bankverbindung für Mitarbeiter-Erstattungen

customers
  id, customer_number, customer_type (weg/company/person)
  company_name, salutation, first_name, last_name
  address_*, vat_id, iban, bic, ...

articles
  id, article_number, name, description
  unit_price_net, vat_rate, billing_period (monthly/annual/one-time)

contracts                            ← Abo-Rechnungen
  id, contract_number, customer_id
  billing_day, payment_terms_days, property_ref
  status (active/terminated/suspended)

  contract_items
    contract_id, article_id, quantity
    override_price, override_vat_rate, billing_period
    is_active, valid_from, valid_until

invoices                             ← Ausgangsrechnungen
  id, invoice_number (Format: RE-YYYY-NNNN), customer_id, contract_id
  invoice_date, due_date, billing_period_from/to
  subtotal_net, total_vat, total_gross
  status (draft/issued/sent/paid/overdue/cancelled)
  pdf_path, zugferd_xml

  invoice_items
    invoice_id, article_id, position
    description, quantity, unit, unit_price_net, vat_rate
    total_net, total_vat, total_gross

creditors
  id, creditor_number, company_name / last_name, first_name
  address_*, vat_id, tax_number, iban, bic, is_active

incoming_invoices                    ← Eingangsrechnungen (Kreditoren)
  id, document_number (Format: ER-YYYY-NNNN), creditor_id
  external_invoice_number, invoice_date, receipt_date, due_date
  total_net, total_vat, total_gross, currency
  is_direct_debit                    ← true = Lastschrift, kein SEPA-Export
  status (open/approved/scheduled/paid/rejected/cancelled)
  document_path, approved_by, approved_at, paid_at

expense_receipts                     ← Mitarbeiter-Belege
  id, receipt_number (Format: BL-YYYY-NNNN), submitted_by (→ users)
  receipt_date, merchant, category, description, payment_method
  amount_gross, vat_amount, amount_net, vat_rate
  reimbursement_iban, reimbursement_account_holder
  status (submitted/approved/paid/rejected)
  document_path, approved_by, approved_at, paid_at

payment_runs
  id, run_type, status, triggered_by
  invoice_count, total_amount, started_at, completed_at

status_change_log
  entity_type (incoming_invoice/expense_receipt), entity_id
  from_status, to_status, changed_by_id, changed_at, note
```

### Dokumentnummern

Generiert durch `backend/app/core/number_generator.py`:
- Format: `{PREFIX}-{YYYY}-{NNNN}` (z.B. `RE-2025-0042`)
- Präfixe: `RE` Ausgangsrechnungen, `ER` Eingangsrechnungen, `BL` Belege
- Zähler wird jährlich zurückgesetzt

---

## 5. Backend – Module & Services

```
backend/app/
├── api/v1/                  # FastAPI-Router (ein File pro Domäne)
├── models/                  # SQLAlchemy-ORM-Modelle
├── schemas/                 # Pydantic v2 Request/Response-Schemas
├── services/
│   ├── invoice_service.py   # Rechnungslauf-Logik
│   ├── invoice_extractor.py # KI-Extraktion via Claude Haiku
│   ├── sepa_service.py      # SEPA pain.001 XML-Generierung
│   └── zugferd_service.py   # PDF + ZUGFeRD/Factur-X XML
├── scheduler/
│   ├── setup.py             # APScheduler-Initialisierung
│   └── jobs/
│       ├── monthly_invoicing.py         # Automatischer Monatslauf
│       ├── incoming_invoices_watcher.py # Watcher: Eingangsrechnungen
│       └── expense_receipts_watcher.py  # Watcher: Belege (Staging only)
├── core/
│   └── number_generator.py  # Dokumentnummern (RE/ER/BL)
├── api/deps.py              # FastAPI-Abhängigkeiten (Auth, DB)
├── config.py                # Konfiguration (pydantic-settings)
└── database.py              # AsyncSessionLocal, Engine
```

### `invoice_extractor.py` – KI-Extraktion

Nutzt Claude Haiku mit Vision (PDF → base64 oder Bild). Zwei Funktionen:

- `extract_invoice_data(filepath)` → Eingangsrechnung-Felder inkl. `is_direct_debit`
- `extract_receipt_data(filepath)` → Beleg-Felder (Händler, Betrag, Datum, Kategorie)

Ohne `ANTHROPIC_API_KEY`: Datei bleibt im Staging mit `extraction_error`-Sidecar. Workflow läuft weiter.

### `sepa_service.py` – SEPA pain.001

Generiert SEPA-Überweisungsdateien (XML pain.001) für:
- Eingangsrechnungen: `generate_incoming_pain001(invoices, execution_date)` – schließt Lastschriften aus
- Belege: `generate_expense_pain001(receipts, execution_date)` – schließt Belege ohne IBAN aus

### `zugferd_service.py` – PDF + E-Rechnung

Erstellt ZUGFeRD EN16931 / Factur-X konforme PDFs mit eingebettetem XML.

---

## 6. API-Endpunkte

Alle Endpunkte unter `/api/v1/`. Auth via JWT Bearer Token.

### Authentifizierung

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/auth/login` | Login → `access_token`, `refresh_token`, `user` |
| POST | `/auth/refresh` | Token erneuern |

### Ausgangsrechnungen

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET/POST | `/invoices` | Liste / Anlegen |
| POST | `/invoices/generate` | Rechnungslauf (`period_from`, `period_to`, `auto_issue`) |
| GET/PUT | `/invoices/{id}` | Detail / Bearbeiten (nur Status `draft`) |
| GET | `/invoices/{id}/pdf` | PDF herunterladen |
| POST/PUT/DELETE | `/invoices/{id}/items/{item_id}` | Positionen (nur `draft`) |

### Eingangsrechnungen

| Methode | Pfad | Zugriff | Beschreibung |
|---|---|---|---|
| GET | `/incoming-invoices/pending` | Admin | Staging-Dateien |
| POST | `/incoming-invoices/pending/{filename}/extract` | Admin | KI-Extraktion |
| GET | `/incoming-invoices/pending/{filename}/download` | Admin | Vorschau |
| DELETE | `/incoming-invoices/pending/{filename}` | Admin | Löschen |
| GET/POST | `/incoming-invoices` | Auth | Liste / Anlegen |
| GET/PUT | `/incoming-invoices/{id}` | Auth | Detail / Bearbeiten |
| PUT | `/incoming-invoices/{id}/status` | Admin | Statuswechsel |
| POST | `/incoming-invoices/sepa-export` | Admin | SEPA pain.001 (ohne Lastschriften) |

### Belege

| Methode | Pfad | Zugriff | Beschreibung |
|---|---|---|---|
| GET | `/expense-receipts/pending` | Auth (nicht readonly) | Staging-Dateien |
| POST | `/expense-receipts/pending/{filename}/extract` | Auth (nicht readonly) | KI-Extraktion |
| GET | `/expense-receipts/pending/{filename}/download` | Auth (nicht readonly) | Vorschau |
| DELETE | `/expense-receipts/pending/{filename}` | Admin | Löschen |
| GET | `/expense-receipts` | Auth | Eigene Belege (Admin sieht alle) |
| POST | `/expense-receipts` | Auth (nicht readonly) | Anlegen; IBAN automatisch aus Mitarbeiterstamm |
| GET/PUT | `/expense-receipts/{id}` | Auth (eigene oder Admin) | Detail / Bearbeiten |
| PUT | `/expense-receipts/{id}/status` | Admin | Genehmigen / Ablehnen / Bezahlt |
| POST | `/expense-receipts/sepa-export` | Admin | SEPA pain.001 (nur Belege mit IBAN) |

### STB-Export

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/stb-export/count` | Anzahl bereitstehender Dateien |
| GET | `/stb-export/download` | ZIP mit allen genehmigten Belegen/Rechnungen |
| GET | `/stb-export/files` | Dateiliste (für stb_downloader.py) |
| GET | `/stb-export/files/{filename}` | Einzelne Datei herunterladen |
| DELETE | `/stb-export/files/{filename}` | Datei als abgeholt markieren (löschen) |

---

## 7. Geschäftslogik

### Rechnungslauf (`invoice_service.py`)

- **Auslöser:** Manuell via API oder automatisch durch `monthly_invoicing.py` (APScheduler)
- **Pro Vertragsposition eine eigene Rechnung** (nicht eine pro Vertrag)
- **Monatliche Positionen:** Leistungszeitraum = übergebene Periode (z.B. 01.03.–31.03.)
- **Jährliche Positionen:** Leistungszeitraum = 01.01.–31.12., nur 1× pro Kalenderjahr
- **Doppellaufschutz:**
  - Monatlich: übersprungen wenn `article_id + exakter Zeitraum` bereits existiert
  - Jährlich: übersprungen wenn `article_id` im selben Kalenderjahr bereits abgerechnet
  - Stornierte Rechnungen zählen nicht für den Doppellaufschutz

### Statusfluss Eingangsrechnungen

```
open → approved → scheduled → paid
     → rejected
     → cancelled  (jederzeit durch Admin)
```

Beim SEPA-Export (`/sepa-export`) werden automatisch alle `approved`-Rechnungen ohne `is_direct_debit` exportiert und auf `paid` gesetzt.

### Statusfluss Belege

```
submitted → approved → paid
          → rejected
```

Beim SEPA-Export werden alle `approved`-Belege **mit hinterlegter IBAN** exportiert und auf `paid` gesetzt.

### IBAN-Automatik bei Belegen

Beim Anlegen eines Belegs (`POST /expense-receipts`) wird die IBAN automatisch aus dem Mitarbeiterstamm übernommen, wenn im Request keine IBAN angegeben ist:
1. Ist `submitted_by_id` gesetzt (Admin reicht für Mitarbeiter ein): IBAN des benannten Mitarbeiters
2. Sonst: IBAN des eingeloggten Nutzers

### STB-Export-Workflow

Genehmigte Rechnungen/Belege werden per `_copy_to_stb_export()` in `settings.stb_export_dir` kopiert. Der Steuerberater lädt diese via `stb_downloader.py` (polling per HTTP-API) oder der SFTP-Uploader-Dienst lädt sie direkt per SFTP herunter.

### is_direct_debit (Lastschrift-Flag)

- `incoming_invoices.is_direct_debit: bool` (Standard: `false`)
- KI erkennt automatisch Begriffe wie „Lastschrift", „Bankeinzug", „SEPA-Mandat"
- Rechnungen mit `is_direct_debit = true` werden beim SEPA-Export übersprungen
- Manuell änderbar über Checkbox im Bearbeitungsdialog

---

## 8. Ordnerüberwachung & Datei-Workflows

### Eingangsrechnungen

```
Eingangsrechnungen/     ← Büro-PC (via SFTP-Uploader hochgeladen)
        ↓  APScheduler alle 60s
storage/invoices/incoming/pending/
  YYYYMMDD_HHMMSS_original.pdf   ← Staging-Datei
  YYYYMMDD_HHMMSS_original.json  ← Sidecar mit KI-Extraktion
        ↓  Nach Admin-Übernahme oder automatisch
storage/uploads/incoming-invoices/
  ER-2025-0042.pdf               ← Finale Ablage, Pfad in DB gespeichert
```

**Sidecar-Format:**
```json
{
  "extracted_at": "2025-03-01T10:00:00Z",
  "source_file": "original.pdf",
  "extraction_error": null,
  "data": {
    "creditor_name": "...", "invoice_date": "2025-02-28",
    "total_gross": "119.00", "is_direct_debit": false, ...
  }
}
```

### Belege (Mitarbeiter-Ausgaben)

```
Belege/                 ← Büro-PC (via SFTP-Uploader hochgeladen)
        ↓  APScheduler alle 60s
storage/receipts/pending/
  YYYYMMDD_HHMMSS_original.pdf   ← Staging (kein DB-Datensatz!)
  YYYYMMDD_HHMMSS_original.json  ← Sidecar
        ↓  Wenn Mitarbeiter/Admin „Übernehmen" klickt
storage/uploads/expense-receipts/
  BL-2025-0007.pdf               ← Finale Ablage, DB-Datensatz angelegt
```

**Unterschied zu Eingangsrechnungen:** Belege im Staging werden **nicht** automatisch als DB-Datensatz angelegt. Der Mitarbeiter (oder Admin) muss den Beleg aktiv über die UI übernehmen und dabei bestätigen/korrigieren.

---

## 9. Windows-Dienst (SFTP-Uploader)

**Datei:** `uploader/demre_uploader_service.py`

### Funktion

| Richtung | Was | Wie |
|---|---|---|
| Upload ↑ | Neue Dateien aus `Eingangsrechnungen/` und `Belege/` | Watchdog (Dateisystem-Events) |
| Upload ↑ | Dateien die beim Neustart bereits vorhanden sind | `scan_existing()` beim Start |
| Download ↓ | Neue Ausgangsrechnungen (PDFs) vom Server | Polling alle 10 min |
| Download ↓ | STB-Export-Dateien vom Server | Polling alle 10 min |

### Konfiguration (`config.json` neben der .exe)

```json
{
  "sftp_host": "87.106.219.148",
  "sftp_port": 22,
  "sftp_user": "patrik",
  "sftp_key_file": "C:\\...\\demre_sftp_key",
  "local_incoming_invoices_folder": "C:\\...\\Eingangsrechnungen",
  "remote_incoming_invoices_dir": "/opt/DEMRE/Eingangsrechnungen",
  "local_expense_receipts_folder": "C:\\...\\Belege",
  "remote_expense_receipts_dir": "/opt/DEMRE/Belege",
  "local_outgoing_invoices_folder": "C:\\...\\Ausgangsrechnungen",
  "remote_outgoing_invoices_dir": "/opt/DEMRE/storage/outgoing_invoices",
  "local_stb_folder": "C:\\...\\STB",
  "remote_stb_export_dir": "/opt/DEMRE/storage/stb_export"
}
```

`local_outgoing_invoices_folder` und `local_stb_folder` akzeptieren auch Arrays (mehrere Zielordner).

### Datei-Stabilität

`wait_for_stable()` wartet bis die Dateigröße sich 2 Sekunden lang nicht mehr verändert (max. 30s). Wichtig für Netzlaufwerke, die beim Schreiben kurzzeitig `OSError` werfen.

### Archivierung

Nach erfolgreichem Upload wird die Datei nach `{lokaler_Ordner}/Hochgeladen/YYYY-MM-DD/` verschoben.

### Dienst verwalten (Windows)

```cmd
# Als Administrator:
demre_uploader_service.exe install
demre_uploader_service.exe start
demre_uploader_service.exe stop
demre_uploader_service.exe remove

# Log: uploader.log (neben der .exe)
```

---

## 10. Frontend

```
frontend/src/
├── pages/                        # Seitenkomponenten (eine pro Modul)
│   ├── DashboardPage.tsx
│   ├── CustomerListPage.tsx
│   ├── ArticleListPage.tsx
│   ├── ContractListPage.tsx / ContractDetailPage.tsx
│   ├── InvoiceListPage.tsx
│   ├── IncomingInvoiceListPage.tsx
│   ├── ExpenseReceiptListPage.tsx
│   └── UserListPage.tsx
├── components/ui/                # shadcn/ui-Basiskomponenten
├── store/
│   └── authStore.ts              # Zustand: JWT-Token + User (zustand + persist)
├── lib/
│   ├── api.ts                    # Axios-Client (baseURL: /api/v1)
│   └── utils.ts                  # formatCurrency, Label-Maps
└── types/index.ts                # Alle TypeScript-Interfaces
```

### Wichtige Konventionen

**Preisfelder:** `type="text"` mit `inputMode="decimal"`, Komma wird vor `parseFloat` zu Punkt normalisiert (`normalizeDecimal()`).

**Dialog-Scrollbarkeit:** Lange Dialoge nutzen `flex flex-col` mit `shrink-0` Header/Footer und `flex-1 overflow-y-auto` Innenbereich. Inline-`style={{ display: 'flex' }}` ist nötig, da Tailwind `flex` gegenüber dem shadcn-Standard `grid` verliert.

**Fehlerbehandlung:** `formatApiError(err)` konvertiert sowohl String-`detail` als auch Pydantic-v2-Array-`detail` in einen anzeigbaren String.

**PDF-Vorschau:** `openDocument(path)` öffnet die URL in einem neuen Tab (verhindert Browser-Download).

**Rollen-Prüfung:**
```typescript
const { user } = useAuthStore()
const isAdmin = user?.role === 'admin'
```

---

## 11. Authentifizierung & Rollen

JWT-basiert. Token-Lebensdauer: 60 Minuten Access, 30 Tage Refresh.

| Rolle | Rechte |
|---|---|
| `admin` | Vollzugriff: Genehmigen, Ablehnen, SEPA-Export, alle Belege sehen, Pending löschen |
| `user` | Eigene Belege einreichen, Pending-Belege sehen und übernehmen, eigene Eingangsrechnungen |
| `readonly` | Nur lesend; kann keine Belege anlegen oder Pending-Endpunkte nutzen |

### Backend-Abhängigkeiten (`api/deps.py`)

| Funktion | Bedeutung |
|---|---|
| `get_current_user` | Beliebiger eingeloggter Nutzer |
| `require_not_readonly` | `user` oder `admin` |
| `require_admin` | Nur `admin` |

---

## 12. Konfiguration

### Umgebungsvariablen (`.env` / `.env.prod`)

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `DATABASE_URL` | Ja | `postgresql+asyncpg://user:pw@host:5432/db` |
| `DATABASE_URL_SYNC` | Ja | `postgresql+psycopg2://...` (für Alembic) |
| `SECRET_KEY` | Ja | JWT-Signatur (`openssl rand -hex 32`) |
| `POSTGRES_PASSWORD` | Ja | Für `start.sh` DB-Wartelogik |
| `ANTHROPIC_API_KEY` | Nein | KI-Extraktion; ohne Key: Fehler-Sidecar |
| `STB_EXPORT_DIR` | Nein | Pfad zum STB-Ordner auf dem Server |
| `COMPANY_*` | Nein | Firmenname, Adresse, IBAN, BIC für ZUGFeRD |

### Firmendaten in `config.py`

```python
company_name = "Demme Immobilien Verwaltung GmbH"
company_street = "Coventrystraße 32"
company_zip = "65934"
company_city = "Frankfurt am Main"
```

Werden in ZUGFeRD-XMLs und SEPA-Dateien als Auftraggeber eingesetzt.

---

## 13. Datenbankmigrationen

Alembic, Migrationsdateien unter `backend/alembic/versions/`.

```bash
# Im Backend-Container ausführen:
alembic upgrade head

# Neue Migration erstellen:
alembic revision --autogenerate -m "beschreibung"
```

| Migration | Inhalt |
|---|---|
| `0001` | Initiales Schema: users, customers, articles, contracts, invoices |
| `0002` | customer_type Enum |
| `0003` | creditors, incoming_invoices, expense_receipts |
| `0004` | Stub (leer, Platzhalter) |
| `0005` | `incoming_invoices.is_direct_debit` (idempotent: `ADD COLUMN IF NOT EXISTS`) |
| `0006` | `users.iban`, `users.bic` |
| `0007` | `status_change_log`-Tabelle |

---

## 14. Bekannte Besonderheiten

### Backend

- **Decimal-Serialisierung:** `format(Decimal.normalize(), "f")` verwenden, sonst `1E+1` statt `10`
- **Rechnungen bearbeiten:** Nur im Status `draft` — HTTP 400 bei anderen Status
- **Watcher + DB-Session:** Eigene `AsyncSessionLocal`-Session pro Job, nicht die FastAPI-Request-Session
- **`env_file` vs. YAML-Interpolation:** `env_file` lädt Variablen in den Container; `${VAR}` im YAML kommt aus der Host-Umgebung — deshalb keine Variablen in Healthcheck-Befehlen

### Frontend

- **`crypto.randomUUID()` nur HTTPS:** Auf HTTP nicht verfügbar → `Date.now().toString(36) + Math.random().toString(36).slice(2)` als Fallback
- **shadcn/ui Checkbox nicht installiert:** Stattdessen natives `<input type="checkbox">` verwenden
- **Tailwind-Spezifität:** `flex` überschreibt nicht zuverlässig `grid` aus shadcn-Basisklassen → Inline-`style` verwenden

### Deployment

- **`.env.prod` niemals committen** — steht in `.gitignore`, Vorlage ist `.env.prod.example`
- **Nur Frontend rebuild:** `docker compose ... up -d --build frontend` (spart Zeit wenn Backend unverändert)
- **Nur Backend rebuild:** `docker compose ... up -d --build backend`
