# RateMyHusky

RateMyHusky is a full-stack web app for discovering, searching, and comparing Northeastern University professors.

It combines:
- RateMyProfessors (RMP) data
- TRACE course evaluation data
- Internal profile metadata such as course history and professor photos

## Features

- Professor catalog with filters for college, department, ratings, and review volume
- Professor profile pages with RMP ratings, TRACE scores, comments, and related courses
- Side-by-side professor comparison view
- Search with autocomplete for professors and courses
- Shuffle/random discovery experience
- Google OAuth sign-in flow for gated functionality
- Responsive UI with theme support

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router |
| Backend | Python, Flask, Flask-CORS, Flask-Limiter |
| Auth | Google OAuth 2.0, JWT (PyJWT) |
| Database | CockroachDB (via psycopg2) |
| Data ingestion | CSV-based scraper outputs + migration scripts |

## Prerequisites

- Python 3.8+
- Node.js 18+
- npm
- A reachable CockroachDB instance

## Quick Start

1. Unzip `trace_comments.zip` into `backend/Better_Scraper/output_data/`.
2. Install backend dependencies.
3. Configure backend environment variables.
4. Start backend API server.
5. Install frontend dependencies.
6. Start frontend dev server.

Detailed commands are below.

## Backend Setup

From the repository root:

```bash
pip install -r backend/requirements.txt
```

Create backend/.env with at least:

```env
CRDB_DATABASE_URL=<your-cockroachdb-connection-string>
JWT_SECRET=<generate-with-openssl-rand-hex-32>
```

Optional (required for Google OAuth login flow):

```env
GOOGLE_CLIENT_ID=<your-google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<your-google-oauth-client-secret>
FRONTEND_URL=http://localhost:5173
```

Run the backend:

```bash
python backend/server.py
```

Backend default: http://localhost:5001

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend default: http://localhost:5173

The frontend calls the backend API on port 5001 in local development.

## Data Setup

**Required:** Unzip `trace_comments.zip` before running any scraper or migration workflows:

```bash
unzip trace_comments.zip -d backend/Better_Scraper/output_data/
```

Additional notes:
- Scraper files are in backend/Better_Scraper.
- CSV outputs are stored in backend/Better_Scraper/output_data.
- The backend runtime serves data from CockroachDB, so CSV files are for ingestion/migration workflows.

## Project Structure

```text
.
├── backend/
│   ├── server.py
│   ├── requirements.txt
│   ├── migrate_to_crdb.py
│   ├── precompute.py
│   └── Better_Scraper/
│       └── output_data/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api/
│       ├── components/
│       ├── context/
│       └── pages/
└── README.md
```

## Useful Commands

Backend:

```bash
python backend/server.py
```

Frontend:

```bash
cd frontend
npm run dev
npm run build
npm run preview
```
