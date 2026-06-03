from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .analytics import build_focus_list, build_mission, compute_metrics
from .config import get_settings
from .dataframes import prepare_task_frame
from .storage import Database
from .todoist_client import TodoistClient


PRIORITY_ORDER = ["P4", "P3", "P2", "P1"]


def _load_data(db: Database):
    return db.fetch_tasks(), db.fetch_projects(), db.fetch_metrics_history()


def _inject_styles():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem; max-width: 1480px;}
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }
        .deck-card {
            border: 1px solid #dbe3ef;
            border-radius: 8px;
            padding: 1rem;
            background: #ffffff;
            min-height: 128px;
        }
        .deck-kicker {
            color: #64748b;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0;
            margin-bottom: 0.25rem;
        }
        .deck-value {
            color: #0f172a;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.25;
        }
        .deck-note {color: #475569; font-size: 0.88rem; margin-top: 0.5rem;}
        .task-card {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            padding: 0.85rem;
            background: #ffffff;
            margin-bottom: 0.65rem;
        }
        .badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.12rem 0.45rem;
            margin-right: 0.25rem;
            font-size: 0.72rem;
            border: 1px solid #cbd5e1;
            color: #334155;
            background: #f8fafc;
        }
        .badge-hot {background: #fee2e2; border-color: #fecaca; color: #991b1b;}
        .insight-list li {margin-bottom: 0.35rem;}
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
    return f"{sign}{delta:g} vs ultimo snapshot"


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
    hot = "badge badge-hot" if item.priority >= 4 else "badge"
    st.markdown(
        f"""
        <div class="deck-card">
          <div class="deck-kicker">Focus Now</div>
          <div class="deck-value">{item.content}</div>
          <div style="margin-top: 0.65rem;">
            <span class="{hot}">P{item.priority}</span>
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
    st.markdown("#### Missao do Dia")
    st.markdown(
        f"""
        <div class="deck-card">
          <pre style="white-space: pre-wrap; margin: 0; font-family: inherit;">{mission_text}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _flight_deck(metrics, filtered_df):
    focus_score = metrics["focus_score"]
    stress = "Baixo"
    if metrics["due_today"] >= 5 or metrics["overdue_tasks"] >= 3 or focus_score < 55:
        stress = "Alto"
    elif metrics["due_today"] >= 2 or focus_score < 75:
        stress = "Medio"
    status = "Operacional" if focus_score >= 50 else "Critico"
    mission_project = "Sem projeto"
    next_window = "Sem prazo definido"
    if not filtered_df.empty:
        root_counts = filtered_df[filtered_df["status"] == "open"].groupby("root_name").size().sort_values(ascending=False)
        if not root_counts.empty:
            mission_project = root_counts.index[0]
        dated = filtered_df[filtered_df["status"] == "open"].dropna(subset=["due_date"]).sort_values("due_date")
        if not dated.empty:
            next_window = dated.iloc[0]["due_date"].date().isoformat()

    cols = st.columns(4)
    cards = [
        ("Sistema", status, f"Backlog health: {focus_score}%"),
        ("Stress Level", stress, f"{metrics['due_today']} hoje / {metrics['overdue_tasks']} atrasadas"),
        ("Missao Atual", mission_project, f"{metrics['open_tasks']} tarefas abertas"),
        ("Proxima Janela", next_window, f"{metrics['due_next_7']} nos proximos 7 dias"),
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
        ("Concluidas hoje", metrics["completed_today"], "completed_today"),
        ("Taxa semanal", f"{metrics['completion_rate']}%", "completion_rate"),
        ("Focus score", metrics["focus_score"], "focus_score"),
        ("Prox. 7 dias", metrics["due_next_7"], "due_next_7"),
    ]
    for col, (label, value, key) in zip(cols, items):
        col.metric(label, value, delta=_metric_delta(key, value, history))


def _render_critical_tasks(focused):
    st.markdown("#### Tarefas Criticas")
    if not focused:
        st.info("Nenhuma tarefa aberta para priorizar ainda.")
        return
    cols = st.columns(5)
    for col, item in zip(cols, focused[:5]):
        with col:
            hot = "badge badge-hot" if item.priority >= 4 else "badge"
            st.markdown(
                f"""
                <div class="task-card">
                  <span class="{hot}">P{item.priority}</span>
                  <span class="badge">{item.score}</span>
                  <div style="font-weight: 700; margin-top: 0.5rem;">{item.content}</div>
                  <div class="deck-note">{item.project_name}</div>
                  <div class="deck-note">{item.reason}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_priority_matrix(task_df):
    st.markdown("#### Prioridade x Prazo")
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
    st.markdown("#### Workload Allocation")
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
    st.markdown("#### Insights")
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
        "<ul class='insight-list'>" + "".join(f"<li>{item}</li>" for item in insights) + "</ul>",
        unsafe_allow_html=True,
    )


def _render_timeline(task_df):
    st.markdown("#### Roadmap dos Proximos 14 Dias")
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
    st.markdown("#### Cards de Contexto")
    if task_df.empty:
        st.info("Sem tarefas para exibir em cards.")
        return
    for _, row in task_df.head(limit).iterrows():
        due = _due_label(row)
        aging = int(row["aging_days"]) if pd.notna(row.get("aging_days")) else 0
        hot = "badge badge-hot" if int(row["priority"]) >= 4 else "badge"
        st.markdown(
            f"""
            <div class="task-card">
              <span class="{hot}">P{int(row['priority'])}</span>
              <span class="badge">{row['root_name']}</span>
              <div style="font-weight: 700; margin-top: 0.5rem;">{row['content']}</div>
              <div class="deck-note">{row['project_name']}</div>
              <div class="deck-note">{due} | Aging: {aging} dia(s)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_analytics(task_df):
    tab_matrix, tab_time, tab_backlog = st.tabs(["Prioridade e prazo", "Tempo", "Backlog"])
    with tab_matrix:
        _render_priority_matrix(task_df)
    with tab_time:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Heatmap de prazos")
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
                    color_continuous_scale="Blues",
                    labels={"x": "Dia", "y": "Prioridade", "color": "Tarefas"},
                )
                fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem prazos suficientes para o heatmap.")
        with right:
            _render_timeline(task_df)
    with tab_backlog:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Tendencia semanal")
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
            fig.update_layout(barmode="group", xaxis_title="Semana", yaxis_title="Tarefas", height=320)
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.markdown("#### Aging do backlog")
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
    _inject_styles()
    settings = get_settings()
    db = Database(settings.database_path)
    client = TodoistClient(settings.todoist_api_token)

    st.title("Todoist Flight Deck")
    st.caption("Centro de comando pessoal para produtividade, foco e backlog.")

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

    tasks, projects, metric_history = _load_data(db)
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
