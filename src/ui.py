from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from .analytics import build_focus_list, build_mission, compute_metrics
from .config import get_settings
from .dataframes import prepare_task_frame
from .storage import Database
from .todoist_client import TodoistClient


PRIORITY_ORDER = ["P4", "P3", "P2", "P1"]
PRIORITY_CLASS = {4: "priority-p1", 3: "priority-p2", 2: "priority-p3", 1: "priority-p4"}


def _load_data(db: Database):
    return db.fetch_tasks(), db.fetch_projects(), db.fetch_metrics_history(), db.fetch_sync_state()


def _inject_styles():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp {
            background: #0B1020;
            color: #F8FAFC;
            font-family: Inter, system-ui, sans-serif;
        }
        .block-container {padding-top: 1.25rem; max-width: 1520px;}
        section[data-testid="stSidebar"] {
            background: #111827;
            border-right: 1px solid #25304A;
        }
        section[data-testid="stSidebar"] * {color: #CBD5E1;}
        h1, h2, h3, h4, h5, h6, p, label, span, div {letter-spacing: 0;}
        h1 {font-size: 42px !important; font-weight: 700 !important; color: #F8FAFC !important;}
        h3 {font-size: 24px !important; font-weight: 600 !important; color: #F8FAFC !important;}
        .stMarkdown, .stCaption, .stText {color: #CBD5E1;}
        div[data-testid="stMetric"] {
            background: #161D2E;
            border: 1px solid #25304A;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.16);
        }
        div[data-testid="stMetric"] label {color: #94A3B8 !important;}
        div[data-testid="stMetricValue"] {color: #F8FAFC !important;}
        div[data-testid="stMetricDelta"] {color: #22C55E !important;}
        div[data-testid="stTabs"] button {color: #CBD5E1;}
        .mission-header {
            min-height: 120px;
            border: 1px solid #25304A;
            border-radius: 16px;
            background: linear-gradient(135deg, #0B1020 0%, #111827 58%, #161D2E 100%);
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
            box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
        }
        .mission-header-grid {
            display: grid;
            grid-template-columns: 1.5fr repeat(3, minmax(130px, 0.5fr));
            gap: 1rem;
            align-items: center;
        }
        .mission-title {
            color: #F8FAFC;
            font-size: 2.35rem;
            line-height: 1;
            font-weight: 700;
        }
        .mission-subtitle {color: #94A3B8; margin-top: 0.35rem; font-size: 0.95rem;}
        .mission-header-stat {
            border-left: 1px solid #25304A;
            padding-left: 1rem;
        }
        .mission-header-stat-label {
            color: #64748B;
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
        }
        .mission-header-stat-value {
            color: #F8FAFC;
            font-size: 1.05rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }
        .deck-card {
            border: 1px solid #25304A;
            border-radius: 16px;
            padding: 1rem;
            background: #161D2E;
            min-height: 128px;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.18);
            transition: transform 200ms ease, border-color 200ms ease, background 200ms ease;
        }
        .deck-card:hover, .task-card:hover {
            transform: translateY(-2px);
            border-color: #3B82F6;
            background: #1B2438;
        }
        .deck-kicker {
            color: #64748B;
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .deck-value {
            color: #F8FAFC;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.25;
        }
        .deck-note {color: #CBD5E1; font-size: 0.88rem; margin-top: 0.5rem;}
        .mission-panel {
            min-height: 220px;
            border-left: 6px solid #3B82F6;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), #161D2E 52%);
        }
        .briefing-panel {
            min-height: 220px;
            border-left: 6px solid #8B5CF6;
        }
        .task-card {
            border: 1px solid #25304A;
            border-radius: 16px;
            padding: 0.85rem;
            background: #161D2E;
            margin-bottom: 0.65rem;
            min-height: 150px;
            transition: transform 200ms ease, border-color 200ms ease, background 200ms ease;
        }
        .badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.12rem 0.45rem;
            margin-right: 0.25rem;
            font-size: 0.72rem;
            border: 1px solid #25304A;
            color: #CBD5E1;
            background: #111827;
        }
        .badge-hot, .priority-p1 {background: rgba(239, 68, 68, 0.16); border-color: #EF4444; color: #FCA5A5;}
        .priority-p2 {background: rgba(245, 158, 11, 0.16); border-color: #F59E0B; color: #FCD34D;}
        .priority-p3 {background: rgba(59, 130, 246, 0.16); border-color: #3B82F6; color: #93C5FD;}
        .priority-p4 {background: rgba(100, 116, 139, 0.16); border-color: #64748B; color: #CBD5E1;}
        .insight-list li {margin-bottom: 0.35rem;}
        .mission-section-title {
            color: #F8FAFC;
            font-size: 1.35rem;
            font-weight: 700;
            margin: 1.4rem 0 0.8rem;
        }
        .stProgress > div > div {background-color: #25304A;}
        .stProgress > div > div > div {background: linear-gradient(90deg, #3B82F6, #22C55E);}
        @media (max-width: 900px) {
            .mission-header-grid {grid-template-columns: 1fr;}
            .mission-header-stat {border-left: none; padding-left: 0; border-top: 1px solid #25304A; padding-top: 0.75rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _metric_delta(metric_name: str, current_value, history):
    if len(history) < 2:
        return None
    previous = history[1].get(metric_name)
    if previous is None:
        return None
    try:
        delta = float(current_value) - float(previous)
    except (TypeError, ValueError):
        return None
    if delta == 0:
        return "0"
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:g} vs snapshot"


def _format_last_sync(sync_state):
    if not sync_state or not sync_state.get("last_sync"):
        return "Not synced"
    try:
        synced_at = pd.Timestamp(sync_state["last_sync"])
        now = pd.Timestamp.utcnow().tz_localize(None)
        synced_at = synced_at.tz_localize(None) if synced_at.tzinfo else synced_at
        minutes = max(0, int((now - synced_at).total_seconds() // 60))
    except Exception:
        return sync_state["last_sync"]
    if minutes < 1:
        return "Just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    return f"{hours} h ago"


def _apply_filters(task_df, selected_root, selected_priority, show_completed):
    filtered = task_df.copy()
    if filtered.empty:
        return filtered
    if selected_root != "Todos":
        filtered = filtered[filtered["root_name"] == selected_root]
    if selected_priority != "Todas":
        filtered = filtered[filtered["priority"] == int(selected_priority[1])]
    if not show_completed:
        filtered = filtered[filtered["status"] == "open"]
    return filtered


def _due_label(row):
    if pd.isna(row.get("due_date")):
        return "Sem prazo"
    today = pd.Timestamp(date.today())
    delta = (row["due_date"].normalize() - today).days
    if delta < 0:
        return f"Atrasada {abs(delta)} dia(s)"
    if delta == 0:
        return "Vence hoje"
    if delta == 1:
        return "Vence amanha"
    return f"Vence em {delta} dia(s)"


def _due_bucket(due_date):
    if pd.isna(due_date):
        return "Sem data"
    today = pd.Timestamp(date.today())
    due = pd.Timestamp(due_date).normalize()
    if due < today:
        return "Atrasado"
    if due == today:
        return "Hoje"
    if due <= today + pd.Timedelta(days=7):
        return "Semana"
    return "Futuro"


def _focus_now_card(focused):
    if not focused:
        st.info("Sincronize o Todoist para calcular o foco atual.")
        return
    item = focused[0]
    priority_class = PRIORITY_CLASS.get(item.priority, "priority-p4")
    st.markdown(
        f"""
        <div class="deck-card">
          <div class="deck-kicker">Focus Now</div>
          <div class="deck-value">{item.content}</div>
          <div style="margin-top: 0.65rem;">
            <span class="badge {priority_class}">P{item.priority}</span>
            <span class="badge">{item.project_name}</span>
            <span class="badge">score {item.score}</span>
          </div>
          <div class="deck-note">{item.reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _risk_panel(metrics):
    risk_items = [
        ("Vencem hoje", metrics["due_today"]),
        ("Atrasadas", metrics["overdue_tasks"]),
        ("Sem data", metrics["no_date_tasks"]),
        ("Prox. 7 dias", metrics["due_next_7"]),
    ]
    body = "".join(
        f"<div><strong>{value}</strong> <span>{label}</span></div>"
        for label, value in risk_items
    )
    st.markdown(
        f"""
        <div class="deck-card">
          <div class="deck-kicker">Riscos</div>
          <div class="deck-value">Janela critica</div>
          <div class="deck-note">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _mission_panel(mission_text):
    st.markdown("<div class='mission-section-title'>Mission Center</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="deck-card mission-panel">
          <div class="deck-kicker">Mission of the Day</div>
          <pre style="white-space: pre-wrap; margin: 0; font-family: inherit;">{mission_text}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _flight_deck(metrics, filtered_df):
    focus_score = metrics["focus_score"]
    stress = "LOW"
    if metrics["due_today"] >= 5 or metrics["overdue_tasks"] >= 3 or focus_score < 55:
        stress = "HIGH"
    elif metrics["due_today"] >= 2 or focus_score < 75:
        stress = "MEDIUM"
    status = "OPERATIONAL" if focus_score >= 50 else "CRITICAL"
    mission_project = "NO PROJECT"
    next_window = "NO WINDOW"
    if not filtered_df.empty:
        root_counts = filtered_df[filtered_df["status"] == "open"].groupby("root_name").size().sort_values(ascending=False)
        if not root_counts.empty:
            mission_project = str(root_counts.index[0]).upper()
        dated = filtered_df[filtered_df["status"] == "open"].dropna(subset=["due_date"]).sort_values("due_date")
        if not dated.empty:
            next_window = dated.iloc[0]["due_date"].date().isoformat()

    cols = st.columns(4)
    cards = [
        ("System Status", status, f"{focus_score}% health"),
        ("Stress Level", stress, f"{metrics['due_today']} due today"),
        ("Active Mission", mission_project, f"{metrics['open_tasks']} open tasks"),
        ("Next Window", next_window, f"{metrics['due_next_7']} next 7 days"),
    ]
    for col, (kicker, value, note) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="deck-card">
                  <div class="deck-kicker">{kicker}</div>
                  <div class="deck-value">{value}</div>
                  <div class="deck-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_kpis(metrics, history):
    cols = st.columns(6)
    items = [
        ("Abertas", metrics["open_tasks"], "open_tasks"),
        ("Atrasadas", metrics["overdue_tasks"], "overdue_tasks"),
        ("Completed today", metrics["completed_today"], "completed_today"),
        ("Weekly rate", f"{metrics['completion_rate']}%", "completion_rate"),
        ("Focus score", metrics["focus_score"], "focus_score"),
        ("Prox. 7 dias", metrics["due_next_7"], "due_next_7"),
    ]
    for col, (label, value, key) in zip(cols, items):
        col.metric(label, value, delta=_metric_delta(key, value, history))


def _render_header(metrics, filtered_df, sync_state):
    current_mission = "NO ACTIVE MISSION"
    if not filtered_df.empty:
        root_counts = filtered_df[filtered_df["status"] == "open"].groupby("root_name").size().sort_values(ascending=False)
        if not root_counts.empty:
            current_mission = str(root_counts.index[0]).upper()
    st.markdown(
        f"""
        <div class="mission-header">
          <div class="mission-header-grid">
            <div>
              <div class="mission-title">TODOIST MISSION CONTROL</div>
              <div class="mission-subtitle">Personal Operations Center</div>
            </div>
            <div class="mission-header-stat">
              <div class="mission-header-stat-label">Current Mission</div>
              <div class="mission-header-stat-value">{current_mission}</div>
            </div>
            <div class="mission-header-stat">
              <div class="mission-header-stat-label">Backlog Health</div>
              <div class="mission-header-stat-value">{metrics["focus_score"]}%</div>
            </div>
            <div class="mission-header-stat">
              <div class="mission-header-stat-label">Last Sync</div>
              <div class="mission-header-stat-value">{_format_last_sync(sync_state)}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_critical_tasks(focused):
    st.markdown("<div class='mission-section-title'>Critical Tasks Area</div>", unsafe_allow_html=True)
    if not focused:
        st.info("Nenhuma tarefa aberta para priorizar ainda.")
        return
    cols = st.columns(5)
    for col, item in zip(cols, focused[:5]):
        with col:
            priority_class = PRIORITY_CLASS.get(item.priority, "priority-p4")
            st.markdown(
                f"""
                <div class="task-card">
                  <span class="badge {priority_class}">P{item.priority}</span>
                  <span class="badge">{item.project_name}</span>
                  <div style="font-weight: 700; margin-top: 0.5rem;">{item.content}</div>
                  <div class="deck-note">Impact: High</div>
                  <div class="deck-note">Risk: {item.reason}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_priority_matrix(task_df):
    st.markdown("#### Risk Matrix")
    if task_df.empty:
        st.info("Sem tarefas para montar a matriz.")
        return
    matrix_df = task_df[task_df["status"] == "open"].copy()
    matrix_df["prazo"] = matrix_df["due_date"].apply(_due_bucket)
    matrix = (
        matrix_df.pivot_table(
            index="priority_label",
            columns="prazo",
            values="task_id",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(index=PRIORITY_ORDER, fill_value=0)
        .reindex(columns=["Atrasado", "Hoje", "Semana", "Futuro", "Sem data"], fill_value=0)
    )
    fig = px.imshow(
        matrix,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Reds",
        labels={"x": "Prazo", "y": "Prioridade", "color": "Tarefas"},
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_workload_allocation(task_df):
    st.markdown("<div class='mission-section-title'>Workload Command View</div>", unsafe_allow_html=True)
    if task_df.empty:
        st.info("Sem tarefas para calcular carga.")
        return
    workload = task_df.groupby("root_name").size().reset_index(name="tasks").sort_values("tasks", ascending=False)
    total = max(1, workload["tasks"].sum())
    display = workload.head(6).copy()
    for _, row in display.iterrows():
        percent = row["tasks"] / total
        st.progress(percent, text=f"{row['root_name']} - {percent:.0%} ({int(row['tasks'])})")
    with st.expander("Treemap detalhado", expanded=False):
        tree = task_df.groupby(["root_name", "priority_label"]).size().reset_index(name="tasks")
        fig = px.treemap(tree, path=["root_name", "priority_label"], values="tasks", hover_data=["tasks"])
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)


def _render_insights(task_df, metrics):
    st.markdown("<div class='mission-section-title'>Tactical Insights</div>", unsafe_allow_html=True)
    if task_df.empty:
        st.info("Sem dados suficientes para gerar insights.")
        return
    open_df = task_df[task_df["status"] == "open"]
    p1_today = open_df[(open_df["priority"] >= 4) & (open_df["due_date"].apply(_due_bucket).isin(["Atrasado", "Hoje"]))]
    top_projects = open_df.groupby("root_name").size().sort_values(ascending=False).head(2)
    total_open = max(1, len(open_df))
    project_sentence = "Sem projeto dominante"
    if not top_projects.empty:
        share = top_projects.sum() / total_open
        project_sentence = f"{' e '.join(top_projects.index.tolist())} representam {share:.0%} da carga aberta."
    aging_avg = open_df["aging_days"].dropna().mean()
    aging_sentence = "Aging medio indisponivel."
    if pd.notna(aging_avg):
        aging_sentence = f"Aging medio atual: {aging_avg:.1f} dia(s)."
    insights = [
        f"{metrics['due_today']} tarefa(s) vencem hoje e {metrics['overdue_tasks']} estao atrasadas.",
        project_sentence,
        f"{len(p1_today)} tarefa(s) P1 estao atrasadas ou vencem hoje.",
        aging_sentence,
    ]
    st.markdown(
        "<div class='deck-card briefing-panel'><div class='deck-kicker'>Intelligence Report</div><ul class='insight-list'>"
        + "".join(f"<li>{item}</li>" for item in insights)
        + "</ul></div>",
        unsafe_allow_html=True,
    )


def _render_timeline(task_df):
    st.markdown("#### Mission Timeline")
    if task_df.empty:
        st.info("Sem tarefas para timeline.")
        return
    today = pd.Timestamp(date.today())
    horizon = today + pd.Timedelta(days=14)
    timeline = task_df[
        (task_df["status"] == "open")
        & task_df["due_date"].notna()
        & (task_df["due_date"] >= today)
        & (task_df["due_date"] <= horizon)
    ].sort_values(["due_date", "priority"], ascending=[True, False])
    if timeline.empty:
        st.info("Nenhuma tarefa com prazo nos proximos 14 dias.")
        return
    for due_day, group in timeline.groupby(timeline["due_date"].dt.date):
        st.markdown(f"**{due_day.isoformat()}**")
        for _, row in group.head(5).iterrows():
            st.markdown(f"- `[P{int(row['priority'])}]` {row['content']} - {row['project_name']}")


def _render_task_cards(task_df, limit=6):
    st.markdown("<div class='mission-section-title'>Active Operations</div>", unsafe_allow_html=True)
    if task_df.empty:
        st.info("Sem tarefas para exibir em cards.")
        return
    for _, row in task_df.head(limit).iterrows():
        due = _due_label(row)
        aging = int(row["aging_days"]) if pd.notna(row.get("aging_days")) else 0
        priority_class = PRIORITY_CLASS.get(int(row["priority"]), "priority-p4")
        st.markdown(
            f"""
            <div class="task-card">
              <div class="deck-kicker">Operation</div>
              <span class="badge {priority_class}">P{int(row['priority'])}</span>
              <span class="badge">{row['root_name']}</span>
              <div style="font-weight: 700; margin-top: 0.5rem;">{row['content']}</div>
              <div class="deck-note">Status: Active</div>
              <div class="deck-note">Due: {due} | Aging: {aging} dia(s)</div>
              <div class="deck-note">Blocking: {row['project_name']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_analytics(task_df):
    tab_matrix, tab_deadlines, tab_velocity, tab_backlog = st.tabs(["Mission Risk", "Deadlines", "Velocity", "Backlog Health"])
    with tab_matrix:
        _render_priority_matrix(task_df)
    with tab_deadlines:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Deadline Heatmap")
            heatmap_df = task_df[task_df["status"] == "open"].dropna(subset=["due_date"]).copy()
            if not heatmap_df.empty:
                pivot = (
                    heatmap_df.pivot_table(
                        index="priority_label",
                        columns=heatmap_df["due_date"].dt.date,
                        values="task_id",
                        aggfunc="count",
                        fill_value=0,
                    )
                    .reindex(index=PRIORITY_ORDER, fill_value=0)
                )
                fig = px.imshow(
                    pivot,
                    aspect="auto",
                    color_continuous_scale=["#22C55E", "#F59E0B", "#EF4444"],
                    labels={"x": "Dia", "y": "Prioridade", "color": "Tarefas"},
                )
                fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem prazos suficientes para o heatmap.")
        with right:
            _render_timeline(task_df)
    with tab_velocity:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Velocity Telemetry")
            trend_df = task_df.copy()
            trend_df["created_week"] = trend_df["created_day"].apply(
                lambda d: pd.Timestamp(d).to_period("W").start_time.date() if pd.notna(d) else None
            )
            trend_df["completed_week"] = trend_df["completed_day"].apply(
                lambda d: pd.Timestamp(d).to_period("W").start_time.date() if pd.notna(d) else None
            )
            created = trend_df.dropna(subset=["created_week"]).groupby("created_week").size().reset_index(name="created")
            completed = trend_df.dropna(subset=["completed_week"]).groupby("completed_week").size().reset_index(name="completed")
            merged = pd.merge(created, completed, left_on="created_week", right_on="completed_week", how="outer").fillna(0)
            merged["week"] = merged["created_week"].fillna(merged["completed_week"])
            fig = go.Figure()
            fig.add_trace(go.Bar(x=merged["week"], y=merged["created"], name="Criadas"))
            fig.add_trace(go.Bar(x=merged["week"], y=merged["completed"], name="Concluidas"))
            fig.add_trace(go.Scatter(x=merged["week"], y=merged["created"] - merged["completed"], name="Net backlog", mode="lines+markers"))
            fig.update_layout(barmode="group", xaxis_title="Semana", yaxis_title="Tarefas", height=320)
            st.plotly_chart(fig, use_container_width=True)
        with right:
            _render_workload_allocation(task_df)
    with tab_backlog:
        st.markdown("#### Backlog Health")
        aging_df = task_df[task_df["status"] == "open"].dropna(subset=["aging_days"]).copy()
        if not aging_df.empty:
            aging_df["aging_bucket"] = pd.cut(
                aging_df["aging_days"],
                bins=[-1, 2, 7, 14, 30, 9999],
                labels=["0-2", "3-7", "8-14", "15-30", "30+"],
            )
            aging_summary = aging_df.groupby("aging_bucket", observed=False).size().reset_index(name="tasks")
            fig = px.bar(aging_summary, x="aging_bucket", y="tasks", labels={"aging_bucket": "Faixa", "tasks": "Tarefas"})
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem backlog aberto para aging.")


def main():
    st.set_page_config(page_title="Todoist Command Center", layout="wide")
    pio.templates.default = "plotly_dark"
    _inject_styles()
    settings = get_settings()
    db = Database(settings.database_path)
    client = TodoistClient(settings.todoist_api_token)

    with st.sidebar:
        st.subheader("Sincronizacao")
        st.write(f"Banco local: `{settings.database_path.name}`")
        if client.is_configured():
            if st.button("Sincronizar agora", use_container_width=True):
                with st.spinner("Buscando dados do Todoist..."):
                    result = client.sync()
                    db.upsert_projects(result.projects)
                    db.replace_tasks(result.tasks)
                    db.replace_sync_state("todoist", result.sync_token)
                st.success("Dados sincronizados.")
        else:
            st.info("Defina `TODOIST_API_TOKEN` para carregar dados reais.")

    tasks, projects, metric_history, sync_state = _load_data(db)
    metrics = compute_metrics(tasks, projects)
    db.save_metrics(date.today(), metrics)
    project_index = metrics["project_index"]
    task_df = prepare_task_frame(tasks, project_index)

    project_options = ["Todos"] + sorted({node.root_name for node in project_index.values()})
    with st.sidebar:
        selected_root = st.selectbox("Projeto raiz", project_options)
        selected_priority = st.selectbox("Prioridade", ["Todas", "P1", "P2", "P3", "P4"])
        show_completed = st.checkbox("Incluir concluidas nos graficos", value=False)

    filtered_df = _apply_filters(task_df, selected_root, selected_priority, show_completed)
    focused = build_focus_list(tasks, projects)

    _render_header(metrics, filtered_df, sync_state)
    _flight_deck(metrics, filtered_df)
    st.write("")
    _render_kpis(metrics, metric_history)
    st.write("")

    top_left, top_right = st.columns([1.1, 0.9], gap="large")
    with top_left:
        _focus_now_card(focused)
    with top_right:
        _risk_panel(metrics)

    mission_col, insights_col = st.columns([1.15, 0.85], gap="large")
    with mission_col:
        _mission_panel(build_mission(tasks, projects))
    with insights_col:
        _render_insights(filtered_df, metrics)

    _render_critical_tasks(focused)

    left, right = st.columns([0.95, 1.05], gap="large")
    with left:
        _render_workload_allocation(filtered_df)
    with right:
        _render_task_cards(
            filtered_df[filtered_df["status"] == "open"].sort_values(["priority", "aging_days"], ascending=[False, False]),
            limit=5,
        )

    st.markdown("### Analytics")
    if filtered_df.empty:
        st.info("Sem dados para analytics com os filtros atuais.")
    else:
        _render_analytics(filtered_df)

    st.markdown("### Resumo operacional")
    cols = st.columns(3)
    cols[0].write(f"Projetos ativos: **{len(projects)}**")
    cols[1].write(f"Semana: **{metrics['completed_week']} concluidas / {metrics['created_week']} criadas**")
    cols[2].write(f"Data: **{date.today().isoformat()}**")
