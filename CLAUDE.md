# DEMRE – Rechnungsverwaltungssystem

## Projektübersicht
Buchhaltungs- und Rechnungsverwaltungssystem für **Demme Immobilien Verwaltung GmbH**.
Verwaltet Kunden, Artikel, Abo-Rechnungen (Verträge), Ausgangsrechnungen (ZUGFeRD/Factur-X),
Kreditoren, Eingangsrechnungen und Belege.

**GitHub:** `git@github.com:patrikerfurt-creator/DEMRE.git`

---

## Tech-Stack
| Komponente | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic, Pydantic v2 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| Datenbank | PostgreSQL 16 |
| PDF/XML | ReportLab, drafthorse (ZUGFeRD EN16931 / Factur-X) |
| Deployment | Docker, Docker Compose |

---

## Projektstruktur
```
DEMRE/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI-Router (invoices, contracts, customers, ...)
│   │   ├── models/          # SQLAlchemy-Modelle
│   │   ├── schemas/         # Pydantic-Schemas
│   │   ├── services/
│   │   │   ├── invoice_service.py    # Rechnungslauf-Logik
│   │   │   └── zugferd_service.py    # PDF + ZUGFeRD-XML
│   │   └── config.py        # Einstellungen (Firmendaten, Pfade)
│   ├── alembic/versions/    # DB-Migrationen
│   ├── .env.example         # Vorlage für Umgebungsvariablen
│   └── create_admin.py      # Admin-User anlegen (interaktiv)
├── frontend/
│   ├── src/
│   │   ├── pages/           # Seitenkomponenten
│   │   ├── components/ui/   # shadcn/ui-Komponenten
│   │   ├── lib/api.ts       # Axios-Client (baseURL: /api/v1, relative URLs)
│   │   └── lib/utils.ts     # Hilfsfunktionen, Label-Maps
│   ├── Dockerfile           # Entwicklung (Vite Dev Server)
│   ├── Dockerfile.prod      # Produktion (nginx, Multi-Stage Build)
│   └── nginx.conf           # nginx: SPA-Routing + /api/ Proxy zum Backend
├── docker-compose.yml       # Entwicklung (Ports: 5173, 8000, 5432)
├── docker-compose.prod.yml  # Produktion (nur Port 80 nach außen)
├── .env.prod.example        # Vorlage Produktions-Umgebungsvariablen
└── storage/invoices/        # Generierte PDFs (in .gitignore)
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

## Produktions-Deployment (Server: appsrv)
```bash
# 1. Repository klonen
cd /opt && git clone git@github.com:patrikerfurt-creator/DEMRE.git && cd DEMRE

# 2. Umgebungsvariablen setzen
cp .env.prod.example .env.prod
# Pflichtfelder: POSTGRES_PASSWORD, DATABASE_URL, DATABASE_URL_SYNC, SECRET_KEY
# SECRET_KEY erzeugen: openssl rand -hex 32

# 3. Ordner anlegen und starten
mkdir -p storage/invoices Eingangsrechnungen
docker compose -f docker-compose.prod.yml up -d --build

# 4. Admin-User anlegen
docker compose -f docker-compose.prod.yml exec backend python create_admin.py

# 5. Als Systemdienst (auto-start nach Reboot)
# Datei: /etc/systemd/system/demre.service  (siehe unten)
systemctl enable demre && systemctl start demre
```

### systemd-Service `/etc/systemd/system/demre.service`
```ini
[Unit]
Description=DEMRE Rechnungsverwaltung
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=/opt/DEMRE
ExecStart=docker compose -f docker-compose.prod.yml up
ExecStop=docker compose -f docker-compose.prod.yml down
Restart=always

[Install]
WantedBy=multi-user.target
```

### URL im Netz
- Produktion: `http://192.168.161.108/` (Port 80, kein Port im URL nötig)
- Kein IP-Hardcoding im Code nötig — Frontend nutzt relative URLs (`/api/v1`)

---

## Wichtige Backend-Endpunkte
| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/v1/auth/login` | Login (JSON: email, password) |
| GET/POST | `/api/v1/invoices` | Rechnungen |
| POST | `/api/v1/invoices/generate` | Rechnungslauf (period_from, period_to, auto_issue) |
| PUT | `/api/v1/invoices/{id}` | Rechnung bearbeiten (**nur Entwurf**) |
| POST/PUT/DELETE | `/api/v1/invoices/{id}/items/{item_id}` | Positionen (**nur Entwurf**) |
| GET/POST | `/api/v1/contracts` | Abo-Rechnungen/Verträge |
| GET/POST | `/api/v1/contracts/{id}/items` | Vertragspositionen |
| GET | `/api/v1/invoices/{id}/pdf` | PDF herunterladen |

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
- **Decimal-Serialisierung**: `format(Decimal.normalize(), "f")` verwenden, sonst erscheint `1E+1` statt `10`
- **Radix UI Dialog + Seitenpanel**: Drawer muss via `createPortal` in `document.body` gerendert werden; Dialog braucht `modal={!drawerOpen}` und `onInteractOutside` mit `useRef` (kein State, wegen async)
- **Rechnungen bearbeiten**: Nur im Status `draft` — Backend wirft HTTP 400 bei anderen Status
- **Vite Dev-Server**: Nur für Entwicklung. Produktion nutzt `Dockerfile.prod` (nginx + statischer Build)
- **PDF-Speicherort**: `storage/invoices/*.pdf` — in `.gitignore`, nicht im Repository

---

## Updates einspielen (Produktion)
```bash
cd /opt/DEMRE
git pull
docker compose -f docker-compose.prod.yml up -d --build
```
