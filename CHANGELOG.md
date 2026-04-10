# DEMRE – Änderungsprotokoll

## Projektübersicht

**DEMRE** ist ein Abrechnungssystem für die Demme Immobilien Verwaltung GmbH.  
Automatische monatliche Rechnungsgenerierung auf Basis von Serviceverträgen.

**Stack:** FastAPI (Python) + React/TypeScript + PostgreSQL 16 + Docker Compose

---

## Aktueller Stand (2026-04-03)

### Fertig implementiert

#### Backend (`/backend`)
- Kunden-, Artikel-, Vertrags- und Rechnungsverwaltung (vollständige CRUD-APIs)
- Automatischer Scheduler: 1. des Monats 02:00 Uhr – generiert Rechnungen aus aktiven Verträgen
- Rechnungs-Lifecycle: `draft → issued → sent → paid / overdue / cancelled`
- PDF-Generierung (ReportLab)
- ZUGFeRD XML (EN16931) – mit Fallback auf manuelle XML-Generierung
- SEPA pain.001 XML Export
- DATEV CSV Export
- JWT-Authentifizierung mit Refresh Tokens
- Benutzerrollen: `admin`, `user`, `readonly`
- CSV-Import für Artikel (`/articles/import/preview`, `/articles/import/confirm`)
- CSV-Import für Kunden (`/customers/import/preview`, `/customers/import/confirm`) ← neu

#### Frontend (`/frontend`)
- Login-Seite mit JWT-Authentifizierung
- Dashboard mit Statistiken und Charts
- Kundenliste mit Suche, Pagination, Erstellen/Bearbeiten/Löschen
- Kundendetailseite
- Artikelliste mit CSV-Import-Dialog
- Kundenliste mit CSV-Import-Dialog ← neu
- Vertragsliste und Vertragsdetailseite
- Rechnungsliste und Rechnungsdetailseite
- Exportseite (SEPA, DATEV, PDF)
- Einstellungsseite

---

## Änderungen in dieser Session

### 1. CSV-Import für Kunden (neu)

**Backend:**
- `backend/app/schemas/customer.py` – `CustomerImportRow` Schema hinzugefügt
- `backend/app/services/csv_import_service.py` – `parse_customers_csv()` Funktion ergänzt
- `backend/app/api/v1/customers.py` – Endpoints `/customers/import/preview` und `/customers/import/confirm`

**Frontend:**
- `frontend/src/types/index.ts` – `CustomerImportRow` Type ergänzt
- `frontend/src/pages/CustomerListPage.tsx` – Import-Button und Dialog mit Vorschau-Tabelle

**CSV-Format Kunden:**
```
customer_number;company_name;first_name;last_name;address_line1;postal_code;city;email;phone;iban;bic;vat_id;datev_account_number;notes
```
Pflichtfeld: `customer_number`. Trennzeichen `;` oder `,`, Encoding UTF-8/CP1252/Latin-1.

---

### 2. Dependency-Fixes (requirements.txt)

| Paket | Alt | Neu | Grund |
|-------|-----|-----|-------|
| `drafthorse` | `0.14.0` | `2025.2.0` | Version existierte nicht |
| `sepaxml` | `2.3.1` | `2.7.0` | Version existierte nicht |
| `bcrypt` | (nicht gepinnt) | `4.0.1` | Inkompatibilität mit `passlib 1.7.4` |
| `@radix-ui/react-badge` | `^1.0.0` | entfernt | Package existiert nicht |

---

### 3. Alembic Migration Fix

**Problem:** `CREATE TYPE userrole AS ENUM (...)` schlug fehl wenn Typen bereits existierten.  
**Lösung:**
- Alle ENUM-Erstellungen auf `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$` umgestellt
- Alle `sa.Enum(...)` in `op.create_table()` auf `postgresql.ENUM(..., create_type=False)` geändert

Datei: `backend/alembic/versions/0001_initial_schema.py`

---

### 4. Docker-Fixes

- `docker-compose.yml`: `VITE_API_URL: http://backend:8000` für Frontend ergänzt  
  (damit der Vite-Proxy im Container den Backend-Service findet)
- `backend/start.sh`: Prüfung ob Tabellen bereits existieren → `alembic stamp head` statt erneute Migration

---

### 5. Automatische Kundennummern

- Kundennummern werden automatisch vergeben: fortlaufend, 6-stellig, beginnend bei `100001`
- Beim manuellen Anlegen wird kein Kundennummer-Feld angezeigt — wird serverseitig generiert
- Beim Bearbeiten wird die Kundennummer schreibgeschützt angezeigt
- CSV-Import: `customer_number` ist optional — fehlt sie, wird automatisch eine vergeben
- Technisch: PostgreSQL-Sequence `customer_number_seq` in `backend/app/core/number_generator.py`

---

### 6. Kundentypen: WEG / Firma / Person

**DB:** Neues Feld `customer_type` (String, default `weg`) — Migration `0002_customer_type.py`

**Formular** zeigt je nach Typ unterschiedliche Felder:
- **WEG**: WEG-Name (`company_name`), c/o-Zeile (`address_line2`), Adresse — Zielgruppe: "WEG Musterstraße 17 c/o Demme Immobilien..."
- **Firma**: Firmenname, Ansprechpartner (Anrede/Vor-/Nachname), Adresse, USt-IdNr.
- **Person**: Anrede, Vor-/Nachname, Adresse

Bankverbindung (IBAN, BIC, Bank, Kontoinhaber) erscheint bei allen Typen.  
Tabelle zeigt Typ als Badge und c/o-Zeile unter dem WEG-Namen.

---

## Login-Zugangsdaten (Entwicklung)

| Feld | Wert |
|------|------|
| E-Mail | `admin@demre.de` |
| Passwort | `admin123` |

> **Hinweis:** Passwort nach dem ersten Login ändern!

---

## Starten der Anwendung

```powershell
cd C:\Projekte\DEMRE
docker compose up -d
```

Erreichbar unter:
- Frontend: http://localhost:5173
- Backend API / Swagger: http://localhost:8000/docs

Vollständiger Neustart (Datenbank löschen):
```powershell
docker compose down
docker volume rm demre_pgdata
docker compose up -d
```
