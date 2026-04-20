# PROJEKTSTAND – DEMRE Rechnungsverwaltungssystem

> Stand: 20. April 2026 | Branch: `master`

---

## 1. Überblick

Buchhaltungs- und Rechnungsverwaltungssystem für **Demme Immobilien Verwaltung GmbH**.  
Das System verwaltet Kunden, Verträge, Artikel, Ausgangsrechnungen (ZUGFeRD/Factur-X),
Kreditoren, Eingangsrechnungen, Mitarbeiter-Belege sowie SEPA- und DATEV-Exporte.
KI-gestützte Datenextraktion (Claude Haiku) verarbeitet eingehende Rechnungen und Belege automatisch.

**Produktion:** `http://87.106.219.148:8081/`  
**Repository:** `git@github.com:patrikerfurt-creator/DEMRE.git`

---

## 2. Architektur & Tech-Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React 18 + TypeScript + Vite + Tailwind/shadcn)   │
│  Port 5173 (dev) / Port 8081 via nginx (prod)               │
└────────────────────────┬────────────────────────────────────┘
                         │ /api/v1/* (Axios)
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI Backend (Python 3.12)                              │
│  ├── API-Router: 10 Router-Module                           │
│  ├── SQLAlchemy (async) + Pydantic v2                       │
│  ├── APScheduler (monatlicher Rechnungslauf + 2 Watcher)    │
│  ├── ReportLab + drafthorse (PDF + ZUGFeRD XML)             │
│  ├── Anthropic Claude Haiku (KI-Extraktion)                 │
│  └── sepaxml / manual XML (SEPA pain.001)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│  PostgreSQL 16                                              │
│  9 Tabellen + Alembic Migrationen 0001–0006                 │
└─────────────────────────────────────────────────────────────┘
```

**Deployment:** Docker Compose  
- Entwicklung: `docker-compose.yml` (Hot-Reload, Port 5173 + 8000 + 5432)  
- Produktion: `docker-compose.prod.yml` (nginx Multi-Stage Build, Port 8081 extern)

---

## 3. Datenbankmodell

| Tabelle | Beschreibung |
|---|---|
| `users` | Mitarbeiter (Admin / User / Readonly), mit IBAN/BIC für Erstattung |
| `customers` | Kunden (WEG / Firma / Person) mit SEPA-Mandatsdaten |
| `creditors` | Kreditoren mit IBAN/BIC für Überweisungen |
| `articles` | Leistungsartikel mit Preis + MwSt.-Satz |
| `contracts` | Verträge (1 Vertrag → n Positionen) |
| `contract_items` | Vertragspositionen (monatlich / jährlich / einmalig) |
| `invoices` + `invoice_items` | Ausgangsrechnungen mit Positionen (ZUGFeRD) |
| `incoming_invoices` | Eingangsrechnungen mit Status + Lastschrift-Flag |
| `expense_receipts` | Mitarbeiter-Belege mit Status + Erstattungs-IBAN |
| `payment_runs` | Protokoll aller Läufe (Rechnungslauf, SEPA, DATEV) |

Aktuelle Migrationsversion: **0006** (`iban`/`bic` an User-Tabelle)

---

## 4. Backend-API (FastAPI `/api/v1`)

| Router | Endpunkte | Beschreibung |
|---|---|---|
| `auth` | 3 | Login (JWT), Refresh-Token, eigenes Profil |
| `users` | 5 | Benutzerverwaltung (Admin only) |
| `customers` | 7 | CRUD + CSV-Import |
| `creditors` | 5 | CRUD |
| `articles` | 7 | CRUD + CSV-Import |
| `contracts` | 9 | CRUD + Kündigung + Positionen |
| `invoices` | 11 | CRUD + Rechnungslauf + PDF/XML-Download |
| `incoming_invoices` | 10 | CRUD + Staging + KI-Extraktion + SEPA-Export |
| `expense_receipts` | 11 | CRUD + Staging + KI-Extraktion + SEPA-Export |
| `payment_runs` | 5 | Liste + SEPA + DATEV + Download |
| `settings` | 2 | Firmendaten lesen/schreiben |

---

## 5. Frontend-Seiten

| Seite | Funktion |
|---|---|
| `DashboardPage` | Startseite |
| `CustomerListPage` / `CustomerDetailPage` | Kunden (Liste + Detail + CSV-Import) |
| `CreditorListPage` / `CreditorDetailPage` | Kreditoren |
| `ArticleListPage` | Artikel (+ CSV-Import) |
| `ContractListPage` / `ContractDetailPage` | Verträge + Positionen bearbeiten |
| `InvoiceListPage` / `InvoiceCreatePage` / `InvoiceDetailPage` | Ausgangsrechnungen |
| `IncomingInvoiceListPage` | Eingangsrechnungen + Staging-Verwaltung + SEPA |
| `ExpenseReceiptListPage` | Mitarbeiter-Belege + Staging + SEPA |
| `MitarbeiterListPage` | Benutzerverwaltung |
| `ExportsPage` | DATEV-/SEPA-Export-Oberfläche |
| `SettingsPage` | Firmendaten-Einstellungen |
| `LoginPage` | Authentifizierung |

---

## 6. Hintergrundprozesse (APScheduler)

| Job | Trigger | Beschreibung |
|---|---|---|
| `monthly_invoicing` | 1. jeden Monats 02:00 (Europe/Berlin) | Rechnungslauf für alle aktiven Verträge des Vormonats, auto-issue + ZUGFeRD-PDF |
| `incoming_invoices_watcher` | Alle 60 Sekunden | Ordner `/app/incoming_invoices` → KI-Extraktion → Kreditor anlegen → IncomingInvoice (Status `open`) |
| `expense_receipts_watcher` | Alle 60 Sekunden | Ordner `/app/expense_receipts` → KI-Extraktion → Staging (kein DB-Datensatz; Admin-Review erforderlich) |

---

## 7. Automatisierung & Besonderheiten

### KI-Extraktion (Claude Haiku Vision)
- Verarbeitet PDF und Bilder (JPG, PNG, TIFF)
- Eingangsrechnungen: Kreditorname, Beträge, Datum, Fälligkeit, IBAN, MwSt., `is_direct_debit`
- Belege: Händler, Betrag, Kategorie, Zahlungsart, MwSt.
- Ohne API-Key: Fehler-Sidecar, Workflow läuft weiter
- Manuelles Nachextrahieren über UI möglich

### SFTP-Uploader (Windows-Dienst)
- Läuft als Windows-Dienst auf einem Scanner-PC
- Schiebt eingescannte Dokumente per SSH/SFTP in die Eingangsordner
- Zuletzt migriert auf SSH-Key-Authentifizierung

### SEPA pain.001
- Ausgangsrechnungen: separate Seite in `ExportsPage` / `payment_runs`
- Eingangsrechnungen + Belege: je eigener Export-Button in den Listenseiten
- `is_direct_debit = true` → wird **nicht** in Überweisungsdatei aufgenommen
- Fallback: manuelle XML-Generierung wenn sepaxml-Library fehlt

### DATEV-Export
- Buchungsstapel EXTF CSV (Format 700)
- Gegenkonto-Mapping: MwSt. 19 % → 8400, 7 % → 8300, 0 % → 8200

### Rechnungsnummern
- Ausgangsrechnungen: Format `YYYY-NNNN` (z. B. `2026-0012`)
- Eingangsrechnungen: internes `document_number`, externes `external_invoice_number`

---

## 8. Was funktioniert (produktionsreif)

- [x] Komplette Kundenverwaltung (CRUD, CSV-Import, WEG/Firma/Person)
- [x] Kreditorenverwaltung (CRUD, Zahlungsbedingungen)
- [x] Artikelverwaltung (CRUD, CSV-Import)
- [x] Verträge + Positionen (monatlich, jährlich, einmalig; Kündigung)
- [x] Automatischer monatlicher Rechnungslauf (APScheduler)
- [x] ZUGFeRD EN16931 / Factur-X PDF-Generierung
- [x] DATEV Buchungsstapel Export
- [x] SEPA pain.001 Export (Kunden- & Kreditorenzahlungen)
- [x] Eingangsrechnungen: Staging-Workflow + KI-Extraktion + DB-Datensatz
- [x] Belege: Staging-Workflow + KI-Extraktion + Admin-Review + Erstattungs-SEPA
- [x] `is_direct_debit`-Erkennung (KI + manuelle Checkbox)
- [x] SFTP-Uploader (Windows-Dienst, SSH-Key-Auth)
- [x] JWT-Authentifizierung (Access + Refresh Token)
- [x] Rollensystem (Admin / User / Readonly)
- [x] Firmendaten über UI konfigurierbar
- [x] Produktions-Deployment (Docker, nginx, Port 8081)

---

## 9. Offene Punkte / bekannte Lücken

### Funktional
- [ ] **E-Mail-Versand**: Ausgangsrechnungen können heruntergeladen, aber nicht direkt per E-Mail verschickt werden
- [ ] **Mahnwesen**: Kein automatisches Überfälligkeits-Tracking / Mahnlauf
- [ ] **Dashboard**: Noch keine aussagekräftigen Kennzahlen / Charts (offene Beträge, überfällige Rechnungen, Umsatz)
- [ ] **Suche/Filter Eingangsrechnungen**: Filterung nach Kreditor / Zeitraum / Status noch rudimentär
- [ ] **SEPA-Lastschrift (Einzug)**: Nur Überweisungs-Export (pain.001); kein SEPA-Lastschrift-Export (pain.008) für Kundenzahlungen mit SEPA-Mandat
- [ ] **Belegkategorien**: Feste Kategorienliste; keine Konfiguration über UI
- [ ] **Quartalliche Abrechnung**: `billing_period = quarterly` im Modell vorhanden, aber Rechnungslauf-Logik behandelt es wie monatlich
- [ ] **Benutzer-Passwort ändern**: Kein Self-Service für Passwortänderung
- [ ] **Mehrsprachigkeit**: System ist Deutsch-only; keine Internationalisierungsstrategie

### Technisch
- [ ] **Tests**: Keine automatisierten Tests (Unit / Integration / E2E)
- [ ] **HTTPS / TLS**: Produktion läuft auf HTTP (Port 8081 ohne TLS); `crypto.randomUUID()` als Workaround nötig
- [ ] **Backup-Strategie**: Keine dokumentierte / automatisierte DB-Sicherung
- [ ] **Logging**: Backend nutzt structlog für Jobs; keine zentralisierte Log-Aggregation
- [ ] **PDF-Vorschau Frontend**: Ausgangsrechnungs-PDF nur als Download, keine In-Browser-Vorschau

---

## 10. Bekannte Bugs / Pitfalls

| Bereich | Problem | Status |
|---|---|---|
| Decimal-Serialisierung | `1E+1` statt `10` bei `Decimal.normalize()` | Behoben (`format(..., "f")`) |
| `crypto.randomUUID()` | Nicht auf HTTP verfügbar | Behoben (Fallback mit `Date.now`) |
| Docker Healthcheck | `${POSTGRES_USER}` nicht aus `env_file` | Behoben (Wert hardcodiert) |
| Rechnungsnummer-Format | War numerisch; jetzt `YYYY-NNNN` | Behoben seit letztem Release |
| Dialog-Scrolling | Speichern-Button außerhalb sichtbarer Fläche | Behoben (`flex flex-col` + overflow) |
| shadcn Checkbox | Nicht installiert | Workaround: native `<input type="checkbox">` |
| Passwort Mitarbeiter-Anlegen | War kein Pflichtfeld | Behoben |

---

## 11. Projektstruktur (vereinfacht)

```
DEMRE/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # 10 Router-Module
│   │   ├── models/          # 9 SQLAlchemy-Modelle
│   │   ├── schemas/         # Pydantic v2 Schemas
│   │   ├── services/        # invoice, sepa, zugferd, datev, extractor, csv_import
│   │   └── scheduler/       # APScheduler + 3 Jobs
│   ├── alembic/versions/    # Migrationen 0001–0006
│   └── create_admin.py
├── frontend/
│   ├── src/
│   │   ├── pages/           # 17 Seitenkomponenten
│   │   ├── components/ui/   # shadcn/ui
│   │   ├── types/index.ts   # Alle TypeScript-Typen
│   │   └── lib/             # api.ts (Axios), utils.ts
│   ├── Dockerfile           # Dev (Vite)
│   └── Dockerfile.prod      # Prod (nginx)
├── docker-compose.yml       # Dev
├── docker-compose.prod.yml  # Prod
├── Eingangsrechnungen/      # Watch-Ordner → Watcher
├── Belege/                  # Watch-Ordner → Watcher
└── storage/                 # Generierte Dateien (in .gitignore)
```

---

## 12. Empfohlene nächste Schritte

1. **E-Mail-Integration** — SMTP-Konfiguration + Button „Rechnung per E-Mail senden" (höchste Priorität laut Nutzungsmuster)
2. **Dashboard-Kennzahlen** — Offene Forderungen, überfällige Rechnungen, Monatsübersicht
3. **HTTPS einrichten** — Let's Encrypt / Reverse Proxy (Caddy/nginx) vor Port 8081, beseitigt auch den `crypto.randomUUID()`-Workaround
4. **Automatisches Backup** — PostgreSQL `pg_dump` als Cron-Job + Upload auf externen Speicher
5. **Automatisierte Tests** — Zumindest Integrationstests für Rechnungslauf + SEPA-Export
6. **Mahnwesen** — Automatischer Job: überfällige Rechnungen markieren, Mahnliste im Frontend
7. **Quartalliche Abrechnung** — Rechnungslauf-Logik für `billing_period = quarterly` korrekt implementieren

---

*Dieses Dokument ist eine Momentaufnahme und sollte bei größeren Feature-Releases aktualisiert werden.*
