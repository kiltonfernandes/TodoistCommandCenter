# Todoist Command Center

Todoist Command Center is a personal productivity dashboard built with Streamlit, SQLite, and the Todoist REST API v2.

## V1 features

- Import Todoist projects, labels, and active tasks
- Store data locally in SQLite
- Compute focus and workload metrics
- Show executive KPIs and a daily mission
- Render a local Streamlit dashboard

## Run locally

1. Create a `.env` file or set environment variables:

```bash
TODOIST_API_TOKEN=your_token_here
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
streamlit run app.py
```

## Deploy online

The recommended hosting path for this V1 is Streamlit Community Cloud.

1. Push this repo to GitHub.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/).
3. Connect your GitHub account.
4. Choose this repository and set `app.py` as the entry point.
5. Add the secret `TODOIST_API_TOKEN` in the app settings.

### Why Streamlit Cloud

- It runs Streamlit natively.
- It is simpler than reshaping the app for Vercel.
- It fits the personal, dashboard-style use case of this project.

## Notes

- The app uses the Todoist REST API v2 for data sync.
- If no token is set, the dashboard still opens with empty demo-safe state.
