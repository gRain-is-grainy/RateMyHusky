# RateMyHusky

A full-stack web application for searching, browsing, and comparing Northeastern University professors. Aggregates ratings from **RateMyProfessors (RMP)** and **TRACE** (NEU's official course evaluations).

## Features

- **Professor Catalog** — Browse and filter professors by college, department, rating range, and review count
- **Professor Profiles** — View RMP ratings, TRACE scores, course history, and student comments
- **Compare** — Side-by-side comparison of two professors across key metrics
- **Shuffle** — Slot-machine randomizer to discover professors
- **Search** — Autocomplete search for professors and courses
- **Google OAuth** — Sign in with your `husky.neu.edu` account (required for TRACE comments)
- **Dark Mode** — Full theme toggle support
- **Mobile Friendly** — Responsive layout across all pages

## Tech Stack

| Layer    | Technology                                    |
| -------- | --------------------------------------------- |
| Frontend | React 19, TypeScript, Vite, React Router DOM  |
| Backend  | Python 3, Flask, Pandas, NumPy                |
| Auth     | Google OAuth 2.0, PyJWT                       |
| Data     | CSV files (RMP scrapes, TRACE exports, photos)|

## Setup

### Prerequisites

- Python 3.8+
- Node.js 18+
- Unzip `trace_comments.zip` into `backend/Better_Scraper/output_data/`

### Backend

```bash
pip install flask flask-cors flask-limiter pandas numpy pyjwt requests python-dotenv
```

Create `backend/.env`:

```
GOOGLE_CLIENT_ID=<your-google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<your-google-oauth-client-secret>
JWT_SECRET=<generate-with-openssl-rand-hex-32>
```

```bash
python backend/server.py
```

If `python` doesn't work, use `python3` and `pip3` instead.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at [http://localhost:5173](http://localhost:5173) with the backend on port 5000.

## Project Structure

```
├── backend/
│   ├── server.py                  # Flask API server
│   ├── .env                       # OAuth & JWT secrets (not committed)
│   └── Better_Scraper/
│       └── output_data/           # CSV data files
│           ├── rmp_professors.csv
│           ├── rmp_reviews.csv
│           ├── trace_courses.csv
│           ├── trace_scores.csv
│           ├── trace_comments.csv
│           └── professor_photos.csv
├── frontend/
│   └── src/
│       ├── App.tsx                # Routes
│       ├── api/api.ts             # API client
│       ├── context/AuthContext.tsx # Auth provider
│       ├── components/            # Navbar, SignInModal, Feedback
│       └── pages/                 # Homepage, ProfessorCatalog, Professor, Compare
└── README.md
```
