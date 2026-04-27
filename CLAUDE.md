# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektübersicht
Buchhaltungs- und Rechnungsverwaltungssystem für **Demme Immobilien Verwaltung GmbH**.
Verwaltet Kunden, Artikel, Abo-Rechnungen (Verträge), Ausgangsrechnungen (ZUGFeRD/Factur-X),
Kreditoren, Eingangsrechnungen und Belege (Mitarbeiter-Ausgaben).

**GitHub:** `git@github.com:patrikerfurt-creator/DEMRE.git`

---

## Tech-Stack
| Komponente | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic, Pydantic v2 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| Datenbank | PostgreSQL 16 |
| PDF/XML | ReportLab, drafthorse (ZUGFeRD EN16931 / Factur-X) |
| KI-Extraktion | Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) via `anthropic` SDK |
| Scheduler | APScheduler (AsyncIOScheduler, Jobs in PostgreSQL gespeichert) |
| Deployment | Docker, Docker Compose |

---

## Projektstruktur
```
DEMRE/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # FastAPI-Router
│   │   ├── models/              # SQLAlchemy-Modelle
│   │   ├── schemas/             # Pydantic-Schemas
│   │   ├── services/
│   │   │   ├── invoice_service.py       # Rechnungslauf-Logik
│   │   │   ├── invoice_extractor.py     # KI-Extraktion (Rechnungen + Belege)
│   │   │   ├── sepa_service.py          # SEPA pain.001 XML-Generierung
│   │   │   └── zugferd_service.py       # PDF + ZUGFeRD-XML
│   │   ├── scheduler/
│   │   │   ├── setup.py                 # APScheduler-Initialisierung
│   │   │   └── jobs/
│   │   │       ├── monthly_invoicing.py         # Monatlicher Rechnungslauf
│   │   │       ├── incoming_invoices_watcher.py # Watcher: Eingangsrechnungen
│   │   │       └── expense_receipts_watcher.py  # Watcher: Belege
│   │   └── config.py            # Einstellungen (Firmendaten, Pfade, API-Keys)
│   ├── alembic/versions/        # DB-Migrationen (0001–0008)
│   └── create_admin.py          # Admin-User anlegen (interaktiv)
├── frontend/
│   ├── src/
│   │   ├── pages/               # Seitenkomponenten
│   │   ├── components/ui/       # shadcn/ui-Komponenten
│   │   ├── types/index.ts       # Alle TypeScript-Typen
│   │   ├── lib/api.ts           # Axios-Client (baseURL: /api/v1, relative URLs)
│   │   └── lib/utils.ts         # Hilfsfunktionen, Label-Maps
│   ├── Dockerfile               # Entwicklung (Vite Dev Server)
│   ├── Dockerfile.prod          # Produktion (nginx, Multi-Stage Build)
│   └── nginx.conf               # SPA-Routing + /api/ Proxy zum Backend
├── docker-compose.yml           # Entwicklung (Ports: 5173, 8000, 5432)
├── docker-compose.prod.yml      # Produktion (Port 8081 nach außen)
├── Eingangsrechnungen/          # Eingangsordner: Kreditoren-Rechnungen (→ /app/incoming_invoices)
├── Belege/                      # Eingangsordner: Mitarbeiter-Belege (→ /app/expense_receipts)
└── storage/                     # Generierte Dateien (in .gitignore)
    ├── invoices/
    │   ├── *.pdf                        # Ausgangsrechnungen
    │   └── incoming/pending/            # Staging: Eingangsrechnungen
    ├── receipts/pending/                # Staging: Belege
    └── uploads/
        ├── incoming-invoices/           # Verarbeitete Eingangsrechnungen
        └── expense-receipts/            # Verarbeitete Belege
```

---

## Lokale Entwicklung starten
```bash
# Alle Container starten
docker compose up -d

# Backend-Logs
docker logs demre-backend-1 -f

# Admin-User anlegen (einmalig)
docker exec -it demre-backend-1 python create_admin.py

# Standard-Zugangsdaten (Entwicklung)
# E-Mail: admin@demre.de  |  Passwort: admin123

# URLs
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API-Docs:  http://localhost:8000/docs
```

---

## Produktions-Deployment (Linux Cloud-Server)

### Server-Infos
- **IP:** `87.106.219.148`
- **User:** `patrik` (sudo-Rechte)
- **Pfad:** `/opt/DEMRE`
- **URL:** `http://87.106.219.148:8081/` (Port 8081)
- Docker-Befehle benötigen `sudo`

### Erstinstallation
```bash
# 1. Repository klonen
cd /opt && sudo git clone https://github.com/patrikerfurt-creator/DEMRE.git && cd DEMRE

# 2. Umgebungsvariablen setzen
sudo cp .env.prod.example .env.prod
sudo nano .env.prod
# Pflichtfelder: POSTGRES_PASSWORD, DATABASE_URL, DATABASE_URL_SYNC, SECRET_KEY
# SECRET_KEY erzeugen: openssl rand -hex 32
# DATABASE_URL=postgresql+asyncpg://demre:PASSWORT@db:5432/demre
# DATABASE_URL_SYNC=postgresql+psycopg2://demre:PASSWORT@db:5432/demre
# Optional: ANTHROPIC_API_KEY für KI-Extraktion

# 3. Ordner anlegen und starten
sudo mkdir -p storage/invoices Eingangsrechnungen Belege
sudo docker compose -f docker-compose.prod.yml up -d --build

# 4. Admin-User anlegen
sudo docker compose -f docker-compose.prod.yml exec backend python create_admin.py
```

### Updates einspielen
```bash
cd /opt/DEMRE
sudo git pull
sudo docker compose -f docker-compose.prod.yml up -d --build
```

### Logs prüfen
```bash
sudo docker compose -f docker-compose.prod.yml logs backend --tail=40
sudo docker compose -f docker-compose.prod.yml logs db --tail=20
sudo docker compose -f docker-compose.prod.yml ps
```

---

## Ordnerüberwachung (Folder Watcher)

Das System überwacht zwei Eingangsordner via APScheduler (jede 60 Sekunden):

### Eingangsrechnungen (`Eingangsrechnungen/` → `/app/incoming_invoices`)
**Job:** `incoming_invoices_watcher.py`
- Datei landet im Ordner → wird nach `storage/invoices/incoming/pending/` verschoben
- KI extrahiert: Kreditor-Daten, Beträge, Datum, Fälligkeit, **`is_direct_debit`** (Lastschrift-Erkennung)
- Kreditor wird automatisch in der DB gesucht oder neu angelegt
- Eingangsrechnung wird sofort als DB-Datensatz (Status `open`) angelegt
- Bei Extraktionsfehler: Datei bleibt im Staging mit Error-Sidecar

### Belege (`Belege/` → `/app/expense_receipts`)
**Job:** `expense_receipts_watcher.py`
- Datei landet im Ordner → wird nach `storage/receipts/pending/` verschoben
- KI extrahiert: Händler, Betrag, Datum, Kategorie, Zahlungsart
- **Kein DB-Datensatz** wird automatisch angelegt — Admin-Review erforderlich
- Admin sieht Belege im Frontend-Banner und übernimmt sie manuell (mit Mitarbeiter-Auswahl)

### Sidecar-Muster
Jede Staging-Datei `YYYYMMDD_HHMMSS_originalname.pdf` bekommt eine gleichnamige JSON-Datei `*.json` mit:
- `extracted_at`, `source_file`, `extraction_error`
- `data`: alle extrahierten Felder
- Eingangsrechnungen zusätzlich: `matched_creditor`, `is_direct_debit`

### KI-Extraktion (`services/invoice_extractor.py`)
- `extract_invoice_data(filepath)` → für Eingangsrechnungen (inkl. `is_direct_debit`)
- `extract_receipt_data(filepath)` → für Belege
- Modell: `claude-haiku-4-5-20251001`; benötigt `ANTHROPIC_API_KEY` in `.env`
- Unterstützt: `.pdf`, `.jpg`, `.jpeg`, `.png` (`.tif`/`.tiff` nur im Watcher, nicht KI)
- Ohne API-Key: `extraction_error`-Sidecar, Workflow funktioniert weiter ohne KI

---

## Wichtige Backend-Endpunkte
| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/v1/auth/login` | Login (JSON: email, password) |
| GET/POST | `/api/v1/invoices` | Ausgangsrechnungen |
| POST | `/api/v1/invoices/generate` | Rechnungslauf (period_from, period_to, auto_issue) |
| PUT | `/api/v1/invoices/{id}` | Rechnung bearbeiten (**nur Status `draft`**) |
| POST/PUT/DELETE | `/api/v1/invoices/{id}/items/{item_id}` | Positionen (**nur `draft`**) |
| GET/POST | `/api/v1/contracts` | Abo-Rechnungen/Verträge |
| GET | `/api/v1/invoices/{id}/pdf` | PDF herunterladen |
| GET | `/api/v1/incoming-invoices/pending` | Staging-Dateien aus Eingangsordner |
| POST | `/api/v1/incoming-invoices/pending/{filename}/extract` | KI-Extraktion (manuell) |
| GET | `/api/v1/incoming-invoices/pending/{filename}/download` | Staging-Datei Vorschau |
| DELETE | `/api/v1/incoming-invoices/pending/{filename}` | Staging-Datei löschen |
| GET | `/api/v1/expense-receipts/pending` | Staging-Belege aus Beleg-Ordner (Admin) |
| POST | `/api/v1/expense-receipts/pending/{filename}/extract` | KI-Extraktion für Beleg |
| GET | `/api/v1/expense-receipts/pending/{filename}/download` | Beleg-Staging Vorschau |
| DELETE | `/api/v1/expense-receipts/pending/{filename}` | Staging-Beleg löschen |
| POST | `/api/v1/incoming-invoices/sepa-export` | SEPA pain.001 für genehmigte Eingangsrechnungen |
| POST | `/api/v1/expense-receipts/sepa-export` | SEPA pain.001 für genehmigte Belege mit IBAN |

---

## Rechnungslauf-Logik (`backend/app/services/invoice_service.py`)
- **Pro Vertragsposition eine eigene Rechnung** (nicht eine pro Vertrag)
- **Monatliche Positionen**: Leistungszeitraum = übergebene Periode (z.B. 01.03.–31.03.)
- **Jährliche Positionen**: Leistungszeitraum = 01.01.–31.12. des laufenden Jahres, nur 1× pro Jahr
- **Doppellaufschutz**:
  - Monatlich: übersprungen wenn article_id + exakter Zeitraum bereits existiert (nicht storniert)
  - Jährlich: übersprungen wenn article_id im selben Kalenderjahr bereits abgerechnet
- Stornierte Rechnungen zählen **nicht** für die Doppellauf-Prüfung

### Rechnungslauf aufrufen
```bash
curl -X POST http://localhost:8000/api/v1/invoices/generate \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"period_from":"2026-03-01","period_to":"2026-03-31","auto_issue":true}'
```

---

## is_direct_debit (SEPA-Lastschrift-Flag)
- `incoming_invoices.is_direct_debit: bool` — Standard: `false`
- KI erkennt automatisch aus Rechnungstext: Begriffe „Lastschrift", „Bankeinzug", „wird abgebucht", „SEPA-Mandat", „Einzugsermächtigung"
- Rechnungen mit `is_direct_debit = true` werden beim SEPA-Export **nicht** in die Überweisung aufgenommen
- Manuell anpassbar: Checkbox im Anlegen/Bearbeiten-Dialog der Eingangsrechnungen
- Anzeige in der Tabelle: Lastschrift-Icon (CreditCard) oder Überweisungs-Icon (Banknote)

---

## Datenbank-Operationen
```bash
# Verbindung zur DB
docker exec -it demre-db-1 psql -U demre -d demre

# Tabellen anzeigen
\dt

# Alle Rechnungsdaten leeren (Entwicklung/Test)
docker exec demre-db-1 psql -U demre -d demre -c \
  "TRUNCATE TABLE invoice_items, invoices, contract_items, contracts RESTART IDENTITY CASCADE;"

# Komplett leeren (alle Daten inkl. Benutzer)
docker exec demre-db-1 psql -U demre -d demre -c \
  "TRUNCATE TABLE invoice_items, invoices, contract_items, contracts,
   expense_receipts, incoming_invoices, payment_runs,
   customers, articles, creditors, users RESTART IDENTITY CASCADE;"
```

---

## Bekannte Besonderheiten / Pitfalls

### Backend
- **Decimal-Serialisierung**: `format(Decimal.normalize(), "f")` verwenden, sonst erscheint `1E+1` statt `10`
- **Rechnungen bearbeiten**: Nur im Status `draft` — Backend wirft HTTP 400 bei anderen Status
- **Docker Compose `env_file` vs YAML-Interpolation**: `env_file` lädt Variablen in den Container, aber `${VAR}` im YAML wird aus der Host-Umgebung gelesen — deshalb keine `${POSTGRES_USER}` im Healthcheck verwenden, sondern Werte hardcoden
- **`start.sh` DB-Verbindung**: Nutzt `os.environ.get('POSTGRES_PASSWORD', '')` — `POSTGRES_PASSWORD` muss explizit in `backend/.env` gesetzt sein, auch wenn das Passwort bereits in `DATABASE_URL` steht
- **`.env.prod` niemals committen**: Steht in `.gitignore`; Vorlage ist `.env.prod.example`
- **Migrationen**: Aktueller Stand ist `0005`. Migration `0004` existiert als Stub (bereits in DB angewendet, enthielt `is_direct_debit`-Spalte). Migration `0005` nutzt `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (idempotent).
- **Watcher + DB-Session**: Jeder Watcher-Job öffnet eine eigene `AsyncSessionLocal`-Session und committed selbst — nicht die Request-Session von FastAPI verwenden.

### Frontend
- **`crypto.randomUUID()` nur HTTPS**: Auf HTTP (Produktion ohne TLS) nicht verfügbar → `Date.now().toString(36) + Math.random().toString(36).slice(2)` verwenden
- **Radix UI Dialog + Seitenpanel**: Drawer muss via `createPortal` in `document.body` gerendert werden; Dialog braucht `modal={!drawerOpen}` und `onInteractOutside` mit `useRef` (kein State, wegen async)
- **Vite Dev-Server**: Nur für Entwicklung. Produktion nutzt `Dockerfile.prod` (nginx + statischer Build)
- **PDF-Speicherort**: `storage/invoices/*.pdf` — in `.gitignore`, nicht im Repository
- **shadcn/ui Checkbox**: Nicht installiert — native `<input type="checkbox">` verwenden

### Dezimalzahlen (Preise, Mengen)
Alle Preis- und Mengenfelder verwenden `type="text"` mit `inputMode="decimal"` statt `type="number"`. Die Hilfsfunktion `normalizeDecimal(v)` (in `ArticleListPage.tsx`) ersetzt `,` durch `.` vor dem `parseFloat`.

### Dialog-Struktur (scrollbare Formulare)
Lange Dialoge nutzen `flex flex-col`-Layout mit `DialogHeader`/`DialogFooter` als `shrink-0` und einem scrollbaren `flex-1 overflow-y-auto`-Innenbereich. Verhindert, dass der Speichern-Button außerhalb des sichtbaren Bereichs liegt.

### Fehlerbehandlung in Mutationen
Alle `onError`-Handler nutzen `formatApiError(err)` (definiert in `CustomerListPage.tsx` und `ArticleListPage.tsx`), das sowohl String-`detail` als auch Pydantic-v2-Array-`detail` korrekt anzeigt.

### Vertragsbearbeitung (`ContractDetailPage.tsx`)
- **Vertragskopf bearbeiten**: Button „Bearbeiten" (Pencil-Icon) öffnet Dialog für start_date, end_date, billing_day, payment_terms_days, property_ref, notes
- **Vertragsposition bearbeiten**: Pencil-Icon in der Aktionsspalte
- `is_active` einer Position kann im Bearbeitungs-Dialog auf Aktiv/Inaktiv gesetzt werden

### Beleg-Workflow (Staging)
- `POST /expense-receipts` akzeptiert optionale Felder `source_pending_file` (Staging-Dateiname) und `submitted_by_id` (UUID des einreichenden Nutzers, Standard: aktueller User)
- Beim Anlegen aus Staging wird die Datei von `storage/receipts/pending/` nach `storage/uploads/expense-receipts/` verschoben und der Sidecar gelöscht
- Der Pending-Endpunkt `/expense-receipts/pending` ist nur für Admins zugänglich; normale Nutzer sehen ihre eigenen Belege nur über `GET /expense-receipts`
