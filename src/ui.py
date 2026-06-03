from __future__ import annotations

from datetime import date
from dataclasses import asdict
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .analytics import build_focus_list, build_mission, compute_metrics
from .config import get_settings
from .storage import Database
from .todoist_client import TodoistClient


def _load_data(db: Database):
    with db.connect() as conn:
        projects = conn.execute("SELECT * FROM projects ORDER BY project_name").fetchall()
        tasks = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
    return tasks, projects


def _prepare_task_frame(tasks, project_index):
    task_df = pd.DataFrame(tasks)
    if task_df.empty:
        return task_df
    project_path_map = {project_id: node.path for project_id, node in project_index.items()}
    root_name_map = {project_id: node.root_name for project_id, node in project_index.items()}
    task_df["project_name"] = task_df["project_id"].map(project_path_map).fillna("Sem projeto")
    task_df["root_name"] = task_df["project_id"].map(root_name_map).fillna("Sem projeto")
    task_df["due_date"] = pd.to_datetime(task_df["due_date"], errors="coerce")
    task_df["created_at_dt"] = pd.to_datetime(task_df["created_at"], errors="coerce")
    task_df["completed_at_dt"] = pd.to_datetime(task_df["completed_at"], errors="coerce")
    task_df["due_day"] = task_df["due_date"].dt.date
    task_df["created_day"] = task_df["created_at_dt"].dt.date
    task_df["completed_day"] = task_df["completed_at_dt"].dt.date
    task_df["priority_label"] = "P" + task_df["priority"].astype(str)
    task_df["labels_text"] = task_df["labels_json"].fillna("[]")
    today = pd.Timestamp(date.today())
    task_df["aging_days"] = (today - task_df["created_at_dt"]).dt.days
    return task_df


def _render_task_cards(task_df, limit=6):
    if task_df.empty:
        st.info("Sem tarefas para exibir em cards.")
        return
    for _, row in task_df.head(limit).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['content']}**")
            st.caption(f"{row['project_name']} | P{int(row['priority'])} | {row['status']}")
            details = []
            if pd.notna(row.get("due_date")):
                details.append(f"vencimento: {row['due_date'].date().isoformat()}")
            if pd.notna(row.get("created_at_dt")):
                details.append(f"criada: {row['created_at_dt'].date().isoformat()}")
            if pd.notna(row.get("aging_days")):
                details.append(f"aging: {int(row['aging_days'])} dia(s)")
            if row.get("labels_text") and row["labels_text"] != "[]":
                details.append(f"labels: {row['labels_text']}")
            st.write(" | ".join(details) if details else "Sem contexto adicional.")


def main():
    st.set_page_config(page_title="Todoist Command Center", layout="wide")
    settings = get_settings()
    db = Database(settings.database_path)
    client = TodoistClient(settings.todoist_api_token)

    st.title("Todoist Command Center")
    st.caption("Centro de comando pessoal para produtividade, foco e backlog.")

    with st.sidebar:
        st.subheader("Sincronização")
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

    tasks, projects = _load_data(db)
    metrics = compute_metrics(tasks, projects)
    db.save_metrics(date.today(), metrics)
    project_index = metrics["project_index"]

    kpi_cols = st.columns(7)
    kpi_cols[0].metric("Abertas", metrics["open_tasks"])
    kpi_cols[1].metric("Atrasadas", metrics["overdue_tasks"])
    kpi_cols[2].metric("Concluídas hoje", metrics["completed_today"])
    kpi_cols[3].metric("Taxa semanal", f"{metrics['completion_rate']}%")
    kpi_cols[4].metric("Focus score", metrics["focus_score"])
    kpi_cols[5].metric("Vencem hoje", metrics["due_today"])
    kpi_cols[6].metric("Próx. 7 dias", metrics["due_next_7"])

    project_options = ["Todos"] + sorted({node.root_name for node in project_index.values()})
    selected_root = st.sidebar.selectbox("Projeto raiz", project_options)
    selected_priority = st.sidebar.selectbox("Prioridade", ["Todas", "P1", "P2", "P3", "P4"])
    show_completed = st.sidebar.checkbox("Incluir concluídas nos gráficos", value=False)

    task_df = _prepare_task_frame(tasks, project_index)
    left, right = st.columns([1.15, 0.85], gap="large")

    with left:
        st.subheader("Tarefas prioritárias")
        focused = build_focus_list(tasks, projects)
        if focused:
            focus_df = pd.DataFrame([asdict(item) for item in focused])
            st.dataframe(focus_df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma tarefa aberta para priorizar ainda.")

        st.subheader("Tarefas por prioridade e data")
        if not task_df.empty:
            if selected_root != "Todos":
                task_df = task_df[task_df["root_name"] == selected_root]
            if selected_priority != "Todas":
                task_df = task_df[task_df["priority"] == int(selected_priority[1])]
            if not show_completed:
                task_df = task_df[task_df["status"] == "open"]
            priority_counts = (
                task_df.groupby(["priority"])
                .size()
                .reset_index(name="tasks")
                .sort_values("priority", ascending=False)
            )
            fig = px.bar(
                priority_counts,
                x="priority",
                y="tasks",
                color="priority",
                labels={"priority": "Prioridade", "tasks": "Tarefas"},
                hover_data={"tasks": True},
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            due_focus = task_df.dropna(subset=["due_date"]).copy()
            due_focus["due_day"] = due_focus["due_date"].dt.date
            if not due_focus.empty:
                fig2 = px.scatter(
                    due_focus,
                    x="due_day",
                    y="content",
                    color="priority",
                    hover_data=["project_name", "labels_text", "created_at", "status"],
                    labels={"due_day": "Data", "content": "Tarefa", "priority": "Prioridade"},
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sem tarefas com data para detalhar.")
        else:
            st.info("Sem dados para os gráficos de prioridade.")

    with right:
        st.subheader("Missão do dia")
        st.code(build_mission(tasks, projects), language="text")

        st.subheader("Carga por projeto")
        if not task_df.empty:
            workload = (
                task_df.groupby("project_name")
                .agg(tasks=("task_id", "size"), open_tasks=("status", lambda s: (s == "open").sum()))
                .reset_index()
                .sort_values("tasks", ascending=False)
            )
            fig = px.bar(
                workload.head(12),
                x="tasks",
                y="project_name",
                orientation="h",
                hover_data={"open_tasks": True},
                labels={"project_name": "Projeto", "tasks": "Tarefas"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem projetos ou tarefas para o workload.")

        st.subheader("Distribuição granular")
        if not task_df.empty:
            if selected_root != "Todos":
                task_df = task_df[task_df["root_name"] == selected_root]
            breakdown = task_df.groupby(["root_name", "priority_label"]).size().reset_index(name="tasks")
            fig3 = px.treemap(
                breakdown,
                path=["root_name", "priority_label"],
                values="tasks",
                hover_data=["tasks"],
            )
            st.plotly_chart(fig3, use_container_width=True)

        st.subheader("Heatmap de prazos")
        heatmap_df = task_df.copy()
        if not heatmap_df.empty:
            if selected_root != "Todos":
                heatmap_df = heatmap_df[heatmap_df["root_name"] == selected_root]
            if selected_priority != "Todas":
                heatmap_df = heatmap_df[heatmap_df["priority"] == int(selected_priority[1])]
            heatmap_df = heatmap_df[heatmap_df["status"] == "open"].dropna(subset=["due_date"])
            if not heatmap_df.empty:
                heatmap_df["due_day"] = heatmap_df["due_date"].dt.date
                pivot = (
                    heatmap_df.pivot_table(index="priority_label", columns="due_day", values="task_id", aggfunc="count", fill_value=0)
                    .sort_index(ascending=False)
                )
                fig_heat = px.imshow(
                    pivot,
                    aspect="auto",
                    color_continuous_scale="Blues",
                    labels={"x": "Dia", "y": "Prioridade", "color": "Tarefas"},
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("Sem prazos suficientes para o heatmap.")

        st.subheader("Tendência semanal")
        if not task_df.empty:
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
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(x=merged["week"], y=merged["created"], name="Criadas", hovertemplate="Semana=%{x}<br>Criadas=%{y}<extra></extra>"))
            fig4.add_trace(go.Bar(x=merged["week"], y=merged["completed"], name="Concluídas", hovertemplate="Semana=%{x}<br>Concluídas=%{y}<extra></extra>"))
            fig4.update_layout(barmode="group", xaxis_title="Semana", yaxis_title="Tarefas")
            st.plotly_chart(fig4, use_container_width=True)

        st.subheader("Aging do backlog")
        if not task_df.empty:
            aging_df = task_df[task_df["status"] == "open"].dropna(subset=["aging_days"]).copy()
            if not aging_df.empty:
                aging_df["aging_bucket"] = pd.cut(
                    aging_df["aging_days"],
                    bins=[-1, 2, 7, 14, 30, 9999],
                    labels=["0-2", "3-7", "8-14", "15-30", "30+"],
                )
                aging_summary = aging_df.groupby("aging_bucket").size().reset_index(name="tasks")
                fig5 = px.bar(
                    aging_summary,
                    x="aging_bucket",
                    y="tasks",
                    labels={"aging_bucket": "Faixa de idade", "tasks": "Tarefas"},
                )
                st.plotly_chart(fig5, use_container_width=True)
            else:
                st.info("Sem backlog aberto para aging.")

        st.subheader("Cards de contexto")
        if not task_df.empty:
            task_subset = task_df[task_df["status"] == "open"].sort_values(["priority", "aging_days"], ascending=[False, False])
            _render_task_cards(task_subset, limit=5)
        else:
            st.info("Sem cards de tarefa no momento.")

    st.subheader("Resumo operacional")
    summary_cols = st.columns(3)
    summary_cols[0].write(f"Projetos ativos: **{len(projects)}**")
    summary_cols[1].write(f"Semana: **{metrics['completed_week']} concluídas / {metrics['created_week']} criadas**")
    summary_cols[2].write(f"Data: **{date.today().isoformat()}**")

    st.subheader("Cards de projeto")
    if not task_df.empty:
        project_cards = (
            task_df.groupby("project_name")
            .agg(
                open_tasks=("status", lambda s: (s == "open").sum()),
                completed_tasks=("status", lambda s: (s == "completed").sum()),
                max_aging=("aging_days", "max"),
            )
            .reset_index()
            .sort_values("open_tasks", ascending=False)
        )
        for _, row in project_cards.head(6).iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['project_name']}**")
                st.write(
                    f"Abertas: {int(row['open_tasks'])} | Concluídas: {int(row['completed_tasks'])} | Aging máximo: {int(row['max_aging']) if pd.notna(row['max_aging']) else 0} dia(s)"
                )
    else:
        st.info("Sem projetos para exibir em cards.")
