from shutil import copy2
from datetime import date, datetime, timedelta
import streamlit as st
import pandas as pd
import sqlite3
import os
import altair as alt
import db
import logic

st.set_page_config(page_title="Sistema Financeiro — PRO (PT-BR)", layout="wide")

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 0.8rem; padding-bottom: 2rem; }
    .stMetric { background: #0f172a11; border-radius: 12px; padding: 8px 12px; }
    .stButton>button { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True
)

def br_format(v: float) -> str:
    try: v = float(v)
    except: v = 0.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_brl(txt) -> float:
    if txt is None: return 0.0
    s = str(txt).strip()
    if not s: return 0.0
    s = s.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def conn() -> sqlite3.Connection:
    return db.get_conn()

def ensure_defaults():
    ss = st.session_state
    ss.setdefault("last_batch_id", None)
    ss.setdefault("dist_date", date.today())
    ss.setdefault("dist_desc", "")
    ss.setdefault("dist_store", "")
    ss.setdefault("dist_value_txt", "")
    ss.setdefault("out_date", date.today())
    ss.setdefault("out_bucket", None)
    ss.setdefault("out_desc", "")
    ss.setdefault("out_store", "")
    ss.setdefault("out_value_txt", "")
    ss.setdefault("trans_date", date.today())
    ss.setdefault("trans_from", None)
    ss.setdefault("trans_to", None)
    ss.setdefault("trans_desc", "")
    ss.setdefault("trans_value_txt", "")

db.init_db()
ensure_defaults()

# Sidebar: backup/restore
st.sidebar.header("Utilitários")
if st.sidebar.button("📦 Criar backup do banco"):
    os.makedirs("backups", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join("backups", f"finance_{ts}.db")
    try:
        copy2("finance.db", dst)
        st.sidebar.success(f"Backup criado em: {dst}")
    except Exception as e:
        st.sidebar.error(f"Erro ao criar backup: {e}")

rest = st.sidebar.file_uploader("🔁 Restaurar backup (.db)", type=["db"])
if st.sidebar.button("Aplicar restauração") and rest is not None:
    try:
        with open("finance.db", "wb") as f:
            f.write(rest.read())
        st.sidebar.success("Banco restaurado. Recarregue (⌘+R).")
    except Exception as e:
        st.sidebar.error(f"Erro ao restaurar: {e}")

if os.path.exists("assets/header.jpg"):
    st.image("assets/header.jpg", use_column_width=True)
else:
    st.title("Sistema Financeiro — PRO (PT-BR)")

tabs = st.tabs([
    "Dashboard",
    "Distribuição diária",
    "Baldes",
    "Objetivos",
    "Plano de Ataque (Cartões)",
    "Calendário de Vencimentos",
    "Movimentações"
])

# =================== Dashboard ===================
with tabs[0]:
    st.subheader("Saldos por Balde")
    with conn() as c:
        saldos = logic.balances_by_bucket(c)
    df_saldos = pd.DataFrame(saldos)
    if not df_saldos.empty:
        df_saldos["Saldo (R$)"] = df_saldos["saldo"].apply(br_format)
        st.dataframe(
            df_saldos[["id", "name", "Saldo (R$)"]].rename(columns={"id":"ID","name":"Balde"}),
            hide_index=True, use_container_width=True
        )
        pos = df_saldos[df_saldos["saldo"] > 0]
        if not pos.empty:
            pie = alt.Chart(pos).mark_arc().encode(
                theta="saldo:Q",
                color=alt.Color("name:N", title="Balde"),
                tooltip=["name:N", alt.Tooltip("saldo:Q", format=",.2f")]
            ).properties(height=300)
            st.altair_chart(pie, use_container_width=True)
    else:
        st.info("Sem baldes. Cadastre em **Baldes**.")

    st.divider()
    st.subheader("Acompanhamento Diário — Entradas x Saídas (30 dias)")
    with conn() as c:
        series = logic.totals_by_day(c, days=30)
    df = pd.DataFrame(series)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        melted = df.melt(id_vars=["date"], value_vars=["entradas","saidas","liquido"], var_name="Tipo", value_name="Valor")
        line = alt.Chart(melted).mark_line().encode(
            x="date:T", y="Valor:Q", color="Tipo:N",
            tooltip=[alt.Tooltip("date:T", title="Data"), "Tipo:N", alt.Tooltip("Valor:Q", format=",.2f")]
        ).properties(height=320)
        st.altair_chart(line, use_container_width=True)
    else:
        st.caption("Sem movimentações para exibir.")

    st.divider()
    st.subheader("Acompanhamento Mensal — Entradas x Saídas")
    with conn() as c:
        mseries = logic.totals_by_month(c)
    mdf = pd.DataFrame(mseries)
    if not mdf.empty:
        mdf["ym"] = pd.to_datetime(mdf["ym"] + "-01")
        mmelt = mdf.melt(id_vars=["ym"], value_vars=["entradas","saidas","liquido"], var_name="Tipo", value_name="Valor")
        bar = alt.Chart(mmelt).mark_bar().encode(
            x=alt.X("ym:T", title="Mês"), y=alt.Y("Valor:Q", title="R$"),
            color="Tipo:N", tooltip=[alt.Tooltip("ym:T", title="Mês"), "Tipo:N", alt.Tooltip("Valor:Q", format=",.2f")]
        ).properties(height=320)
        st.altair_chart(bar, use_container_width=True)
    else:
        st.caption("Sem meses consolidados.")

    st.divider()
    st.subheader("Ataque aos Cartões — Pronto para quitar?")
    with conn() as c:
        gname, saldo_ataque, custo = logic.attack_ready(c)
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Saldo em 'Nu PF Ataque'", br_format(saldo_ataque))
    with col2: st.metric("Próximo alvo", gname or "—")
    with col3: st.metric("Custo alvo", br_format(custo or 0))
    if gname and custo is not None and saldo_ataque >= custo > 0:
        st.success("✅ PRONTO PARA QUITAR")

# =================== Distribuição diária ===================
with tabs[1]:
    if os.path.exists("assets/baldes.jpg"):
        st.image("assets/baldes.jpg", use_column_width=True)
    st.subheader("Distribuição de Entrada do Dia")

    with st.form("form_dist", clear_on_submit=False):
        colA, colB, colC, colD = st.columns([1,2,2,2])
        with colA: st.date_input("Data", key="dist_date", format="DD/MM/YYYY")
        with colB: st.text_input("Descrição", key="dist_desc", placeholder="Ex.: Recebimento do dia")
        with colC: st.text_input("Origem/Loja", key="dist_store", placeholder="Ex.: Caixa, Pix, iFood")
        with colD: st.text_input("Entrada do dia (R$)", key="dist_value_txt", placeholder="Ex.: R$ 1.000,00")

        c1, c2, c3 = st.columns([1,1,1])
        do_dist = c1.form_submit_button("Distribuir")
        do_clear = c2.form_submit_button("Limpar formulário")
        do_undo  = c3.form_submit_button("Desfazer última distribuição")

    if do_clear:
        st.session_state["dist_date"] = date.today()
        st.session_state["dist_desc"] = ""
        st.session_state["dist_store"] = ""
        st.session_state["dist_value_txt"] = ""
        st.experimental_rerun()

    if do_dist:
        with conn() as c:
            buckets = logic.get_buckets(c)
        if not buckets:
            st.warning("Cadastre baldes na aba **Baldes**.")
        else:
            valor = parse_brl(st.session_state.dist_value_txt)
            if valor <= 0:
                st.error("Informe um valor de entrada válido (R$).")
            else:
                with conn() as c:
                    alloc, batch_id = logic.distribute_daily(
                        c, valor, st.session_state.dist_date.isoformat(),
                        st.session_state.dist_desc.strip(), st.session_state.dist_store.strip()
                    )
                st.session_state["last_batch_id"] = batch_id
                if alloc:
                    df_alloc = pd.DataFrame(alloc)
                    df_alloc["Valor (R$)"] = df_alloc["value"].apply(br_format)
                    st.success("Distribuição realizada.")
                    st.dataframe(df_alloc[["bucket","Valor (R$)"]], hide_index=True, use_container_width=True)

    if do_undo:
        bid = st.session_state.get("last_batch_id")
        if bid:
            with conn() as c:
                logic.undo_batch(c, bid)
            st.success("Última distribuição desfeita.")
            st.session_state["last_batch_id"] = None
        else:
            st.info("Nenhuma distribuição recente para desfazer.")

    st.divider()
    st.subheader("Saída diária (pagamento manual)")
    with conn() as c:
        bucket_opts = logic.list_buckets(c)
    with st.form("form_out", clear_on_submit=False):
        col1, col2, col3, col4, col5 = st.columns([1,2,2,2,2])
        with col1: st.date_input("Data", key="out_date", format="DD/MM/YYYY")
        with col2: sel = st.selectbox("Balde de origem", options=[(None,"— Selecione —")] + bucket_opts,
                                      format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="out_bucket")
        with col3: st.text_input("Descrição", key="out_desc", placeholder="Ex.: Pagamento fornecedor")
        with col4: st.text_input("Origem/Loja", key="out_store", placeholder="Ex.: Boleto, Cartão")
        with col5: st.text_input("Valor (R$)", key="out_value_txt", placeholder="Ex.: R$ 250,00")
        b1, b2 = st.columns([1,1])
        do_save_out = b1.form_submit_button("Lançar saída")
        do_clear_out = b2.form_submit_button("Limpar formulário")

    if do_clear_out:
        for k in ["out_date","out_bucket","out_desc","out_store","out_value_txt"]:
            st.session_state[k] = date.today() if k=="out_date" else (None if k=="out_bucket" else "")
        st.experimental_rerun()

    if do_save_out:
        if not isinstance(st.session_state.out_bucket, tuple) or st.session_state.out_bucket[0] is None:
            st.error("Selecione um balde de origem.")
        else:
            val = parse_brl(st.session_state.out_value_txt)
            if val <= 0:
                st.error("Informe um valor válido (R$).")
            else:
                with conn() as c:
                    logic.add_transaction(c, {
                        "date": st.session_state.out_date.isoformat(),
                        "description": st.session_state.out_desc.strip(),
                        "t_type": "out",
                        "value": val,
                        "bucket_id": st.session_state.out_bucket[0],
                        "store": st.session_state.out_store.strip(),
                    })
                st.success("Saída lançada.")

    st.divider()
    st.subheader("Transferência entre Baldes")
    with conn() as c:
        bucket_opts = logic.list_buckets(c)
    with st.form("form_trans", clear_on_submit=False):
        col1, col2, col3, col4, col5 = st.columns([1,2,2,2,2])
        with col1: st.date_input("Data", key="trans_date", format="DD/MM/YYYY")
        with col2: from_opt = st.selectbox("Balde de origem", options=[(None,"— Selecione —")] + bucket_opts,
                                           format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="trans_from")
        with col3: to_opt = st.selectbox("Balde de destino", options=[(None,"— Selecione —")] + bucket_opts,
                                         format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="trans_to")
        with col4: st.text_input("Descrição", key="trans_desc", placeholder="Ex.: Transferência para ajuste")
        with col5: st.text_input("Valor (R$)", key="trans_value_txt", placeholder="Ex.: R$ 100,00")
        c1, c2 = st.columns([1,1])
        do_trans = c1.form_submit_button("Transferir")
        do_clear_trans = c2.form_submit_button("Limpar formulário")

    if do_clear_trans:
        for k in ["trans_date","trans_from","trans_to","trans_desc","trans_value_txt"]:
            st.session_state[k] = date.today() if k=="trans_date" else (None if k in ("trans_from","trans_to") else "")
        st.experimental_rerun()

    if do_trans:
        ok = True; msg = None
        if not (isinstance(from_opt, tuple) and isinstance(to_opt, tuple) and from_opt[0] and to_opt[0]):
            ok = False; msg = "Selecione o balde de origem e de destino."
        elif from_opt[0] == to_opt[0]:
            ok = False; msg = "Origem e destino não podem ser o mesmo balde."
        val = parse_brl(st.session_state.trans_value_txt)
        if val <= 0:
            ok = False; msg = (msg + " " if msg else "") + "Informe um valor válido (R$)."
        if not ok:
            st.error(msg)
        else:
            with conn() as c:
                logic.add_transaction(c, {
                    "date": st.session_state.trans_date.isoformat(),
                    "description": f"Transferência para {to_opt[1]} — {st.session_state.trans_desc.strip()}",
                    "t_type": "out", "value": val, "bucket_id": from_opt[0], "store": "transfer"
                })
                logic.add_transaction(c, {
                    "date": st.session_state.trans_date.isoformat(),
                    "description": f"Transferência de {from_opt[1]} — {st.session_state.trans_desc.strip()}",
                    "t_type": "transfer", "value": val, "bucket_id": to_opt[0], "store": "transfer"
                })
            st.success("Transferência realizada.")

# =================== Baldes ===================
with tabs[2]:
    st.subheader("Cadastro de Baldes (Percentual em %)")
    with conn() as c:
        buckets = logic.get_buckets(c)
    df = pd.DataFrame(buckets) if buckets else pd.DataFrame(columns=["id","name","kind","priority_pre","percentage","active"])
    if "percentage" in df.columns:
        df["Percentual (%)"] = (df["percentage"].astype(float) * 100).round(2)
    else:
        df["Percentual (%)"] = 0.0
    edited = st.data_editor(
        df[["id","name","priority_pre","Percentual (%)","active"]].rename(columns={
            "id":"ID","name":"Nome do Balde","priority_pre":"Prioridade (antes do rateio)","active":"Ativo (1/0)"
        }),
        num_rows="dynamic", use_container_width=True,
        column_config={
            "Prioridade (antes do rateio)": st.column_config.SelectboxColumn("Prioridade (antes do rateio)", options=[0,1]),
            "Percentual (%)": st.column_config.NumberColumn("Percentual (%)", min_value=0.0, max_value=100.0, step=0.5),
            "Ativo (1/0)": st.column_config.SelectboxColumn("Ativo (1/0)", options=[1,0])
        }
    )
    if st.button("Salvar alterações de baldes"):
        rows = edited.copy()
        rows["Prioridade (antes do rateio)"] = rows["Prioridade (antes do rateio)"].fillna(0).astype(int)
        rows["Percentual (%)"] = rows["Percentual (%)"].fillna(0).astype(float)
        rows["Ativo (1/0)"] = rows["Ativo (1/0)"].fillna(1).astype(int)

        soma_prioritarios = float(rows.loc[rows["Prioridade (antes do rateio)"] == 1, "Percentual (%)"].sum() or 0)/100.0
        if soma_prioritarios > 1.0 + 1e-9:
            st.error("A soma dos percentuais dos baldes prioritários não pode ultrapassar 100%.")
            st.stop()

        payload, keep_ids = [], []
        for _, r in rows.iterrows():
            name = str(r.get("Nome do Balde","")).strip()
            if not name: continue
            pid = r.get("ID")
            item = {
                "id": int(pid) if pd.notna(pid) else None,
                "name": name,
                "priority_pre": int(r["Prioridade (antes do rateio)"]),
                "percentage": float(r["Percentual (%)"])/100.0,
                "active": int(r["Ativo (1/0)"]),
            }
            payload.append(item)
            if item["id"]: keep_ids.append(item["id"])
        with conn() as c:
            logic.save_buckets(c, payload)
            cur = c.execute("SELECT id FROM accounts WHERE kind='bucket';")
            all_ids = [rid for (rid,) in cur.fetchall()]
            to_keep = keep_ids if keep_ids else [p.get('id') for p in payload if p.get('id')]
            if to_keep:
                logic.delete_buckets_not_in(c, keep_ids=to_keep)
        st.success("Baldes salvos.")

# =================== Objetivos ===================
with tabs[3]:
    st.subheader("Objetivos (Cartões) — Preencha manualmente")
    with conn() as c:
        df_goals = pd.read_sql_query(
            "SELECT id, name, goal_type, cost, monthly_relief, interest_pa, priority_weight, color FROM goals;", c
        )
    df_show = df_goals.rename(columns={
        "name":"Nome","goal_type":"Tipo (debt/poupanca)","cost":"Custo/Meta (R$)",
        "monthly_relief":"Alívio Mensal (R$)","priority_weight":"Peso","color":"Cor"
    })
    edited = st.data_editor(
        df_show, num_rows="dynamic", use_container_width=True,
        column_config={
            "Tipo (debt/poupanca)": st.column_config.SelectboxColumn("Tipo (debt/poupanca)", options=["debt","poupanca"],
                help="debt = dívida/cartão | poupanca = meta de poupar"),
            "Custo/Meta (R$)": st.column_config.TextColumn(help="Ex.: R$ 2.500,00"),
            "Alívio Mensal (R$)": st.column_config.TextColumn(help="Ex.: R$ 250,00"),
            "Peso": st.column_config.NumberColumn(help="Usado na estratégia Personalizada"),
            "Cor": st.column_config.TextColumn(help="Hex opcional, ex.: #1976D2"),
        }
    )
    strat = st.radio("Estratégia", ["Avalanche","Snowball","Personalizada"], horizontal=True)
    if st.button("Salvar objetivos"):
        with conn() as c:
            c.execute("DELETE FROM goals;")
            for _, r in edited.fillna({"Tipo (debt/poupanca)":"debt","Custo/Meta (R$)":0,"Alívio Mensal (R$)":0,"Peso":0}).iterrows():
                name = str(r.get("Nome","")).strip()
                if not name: continue
                goal_type = str(r.get("Tipo (debt/poupanca)","debt")).strip().lower()
                if goal_type.startswith("pou"): goal_type = "savings"
                elif goal_type in {"debt","divida","dívida"}: goal_type = "debt"
                else:
                    st.error(f"Tipo inválido para '{name}'. Selecione 'debt' ou 'poupanca'.")
                    st.stop()
                cost = parse_brl(r.get("Custo/Meta (R$)",0))
                relief = parse_brl(r.get("Alívio Mensal (R$)",0))
                color = str(r.get("Cor","#1976D2")).strip() or "#1976D2"
                weight = float(r.get("Peso",0) or 0)
                logic.upsert_goal(c, name, goal_type, cost, relief, color, priority_weight=weight)
        st.success("Objetivos salvos.")

    strategy_map = {"Avalanche":"avalanche","Snowball":"snowball","Personalizada":"custom"}
    with conn() as c:
        ranked = logic.goals_with_scores(c, strategy=strategy_map[strat])
    if ranked:
        df_rank = pd.DataFrame(ranked)
        df_rank["Custo (R$)"] = df_rank["cost"].apply(br_format)
        df_rank["Alívio (R$)"] = df_rank["monthly_relief"].apply(br_format)
        st.dataframe(df_rank[["name","goal_type","Custo (R$)","Alívio (R$)","score"]].rename(columns={
            "name":"Nome","goal_type":"Tipo","score":"Score"
        }), hide_index=True, use_container_width=True)

# =================== Plano de Ataque ===================
with tabs[4]:
    st.subheader("Plano de Ataque — Eficiência")
    with conn() as c:
        ranked = logic.goals_with_scores(c, strategy="avalanche")
    if ranked:
        dfp = pd.DataFrame(ranked)
        dfp["Payoff Efficiency (R$/1k)"] = (dfp["monthly_relief"] / dfp["cost"].replace(0, pd.NA).fillna(1)) * 1000
        dfp["Custo (R$)"] = dfp["cost"].apply(br_format)
        dfp["Alívio (R$)"] = dfp["monthly_relief"].apply(br_format)
        st.dataframe(dfp[["name","Custo (R$)","Alívio (R$)","Payoff Efficiency (R$/1k)"]].rename(columns={"name":"Nome"}),
                     hide_index=True, use_container_width=True)
        chart = alt.Chart(dfp).mark_bar().encode(
            x=alt.X("name:N", title="Objetivo"),
            y=alt.Y("cost:Q", title="Saldo a Quitar (R$)"),
            tooltip=["name:N", alt.Tooltip("cost:Q", format=",.2f")]
        ).properties(height=350)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Cadastre objetivos na aba **Objetivos**.")

# =================== Calendário ===================
with tabs[5]:
    st.subheader("Calendário de Vencimentos")
    with conn() as c:
        df_dues = pd.read_sql_query("SELECT id, name, due_date, amount, kind, note FROM dues ORDER BY due_date ASC;", c)
    
    # Converter amount para string formatada para exibição/edição
    df_dues_display = df_dues.copy()
    if not df_dues_display.empty and 'amount' in df_dues_display.columns:
        df_dues_display['amount'] = df_dues_display['amount'].apply(lambda x: br_format(x) if pd.notna(x) else "R$ 0,00")
    
    df_edit = st.data_editor(
        df_dues_display.rename(columns={
            "name":"Nome","due_date":"Vencimento (AAAA-MM-DD)","amount":"Valor (R$)","kind":"Tipo","note":"Observação"
        }), num_rows="dynamic", use_container_width=True,
        column_config={
            "Vencimento (AAAA-MM-DD)": st.column_config.TextColumn(help="Formato AAAA-MM-DD"),
            "Valor (R$)": st.column_config.TextColumn(help="Aceita R$ 1.234,56")
        }
    )
    if st.button("Salvar calendário"):
        with conn() as c:
            c.execute("DELETE FROM dues;")
            for _, r in df_edit.fillna({"Vencimento (AAAA-MM-DD)":"", "Valor (R$)":"R$ 0,00"}).iterrows():
                nome = str(r.get("Nome","")).strip()
                venc = str(r.get("Vencimento (AAAA-MM-DD)","")).strip()
                if not nome or not venc: continue
                val = parse_brl(r.get("Valor (R$)","R$ 0,00"))
                tipo = str(r.get("Tipo","")).strip()
                obs  = str(r.get("Observação","")).strip()
                c.execute("INSERT INTO dues (name, due_date, amount, kind, note) VALUES (?, ?, ?, ?, ?);",
                          (nome, venc, val, tipo, obs))
            c.commit()
        st.success("Calendário salvo.")

# =================== Movimentações ===================
with tabs[6]:
    st.subheader("Movimentações")
    with conn() as c:
        df_tx = pd.read_sql_query("""
            SELECT t.id, t.date, t.description, t.t_type, t.value, t.store, a.name AS bucket
            FROM transactions t
            LEFT JOIN accounts a ON a.id = t.bucket_id
            ORDER BY t.date DESC, t.id DESC;
        """, c)
    if df_tx.empty:
        st.info("Sem movimentações.")
    else:
        df_tx["Valor (R$)"] = df_tx["value"].apply(br_format)
        df_show = df_tx[["id","date","bucket","description","t_type","Valor (R$)","store"]].rename(columns={
            "id":"ID","date":"Data","bucket":"Balde","description":"Descrição","t_type":"Tipo","store":"Origem/Loja"
        })
        df_show["Deletar?"] = False
        edited = st.data_editor(df_show, use_container_width=True)
        col1, col2, col3 = st.columns([1,1,1])
        if col1.button("Apagar selecionados"):
            ids = [int(r["ID"]) for _, r in edited.iterrows() if r.get("Deletar?")]
            if ids:
                with conn() as c:
                    logic.delete_transactions_by_ids(c, ids)
                st.success("Movimentações apagadas.")
                st.experimental_rerun()
            else:
                st.info("Nenhuma linha marcada.")
        csv = df_tx.to_csv(index=False).encode("utf-8")
        col2.download_button("Exportar CSV", data=csv, file_name="movimentacoes.csv", mime="text/csv")
        try:
            import io
            bio = io.BytesIO()
            with pd.ExcelWriter(bio, engine="openpyxl") as xw:
                df_tx.to_excel(xw, "Movimentacoes", index=False)
            col3.download_button("Exportar Excel", data=bio.getvalue(), file_name="movimentacoes.xlsx",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.caption(f"Exportação Excel indisponível: {e}")
