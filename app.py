import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from db import engine, SessionLocal, Base
from models import User, Bucket, Giant, Movement, Bill
from logic import compute_bucket_splits, payoff_efficiency, normalize_percents

from babel.numbers import format_currency
from babel.dates import format_date

# ---- Helpers BR ----
def money_br(v: float) -> str:
    try:
        return format_currency(v, 'BRL', locale='pt_BR')
    except Exception:
        # fallback
        s = f"{v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {s}"

def date_br(d) -> str:
    try:
        return format_date(d, format='short', locale='pt_BR')  # dd/mm/aa
    except Exception:
        return d.strftime('%d/%m/%y')

def parse_money_br(s: str) -> float:
    if s is None:
        return 0.0
    s = s.strip().replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

# ---- App config ----
st.set_page_config(page_title="APP DAVI", layout="wide")
Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    return SessionLocal()

def get_or_create_user(db: Session, name: str) -> User:
    u = db.execute(select(User).where(User.name == name)).scalar_one_or_none()
    if u:
        return u
    u = User(name=name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

# ---- Sidebar ----
with st.sidebar:
    st.header("Usuário")
    name = st.text_input("Seu nome", value=st.session_state.get("user_name", "Gustavo"))
    if st.button("Entrar / Criar"):
        with get_db() as db:
            user = get_or_create_user(db, name.strip() or "Usuário")
            st.session_state["user_id"] = user.id
            st.session_state["user_name"] = user.name
    st.markdown("---")
    page = st.radio("Navegação", ["Dashboard", "Plano de Ataque", "Baldes", "Entrada Diária", "Livro Caixa", "Calendário", "Atrasos & Riscos", "Configurações"])

user_id = st.session_state.get("user_id", None)
if not user_id:
    st.info("👈 Informe o seu **nome** e clique em **Entrar / Criar** para começar.")
    st.stop()

# ---- Load helpers ----
def load_buckets(db: Session, user_id: int):
    return db.execute(select(Bucket).where(Bucket.user_id == user_id)).scalars().all()

def load_giants(db: Session, user_id: int):
    return db.execute(select(Giant).where(Giant.user_id == user_id)).scalars().all()

def load_movements(db: Session, user_id: int):
    return db.execute(select(Movement).where(Movement.user_id == user_id).order_by(Movement.date.desc())).scalars().all()

def load_bills(db: Session, user_id: int):
    return db.execute(select(Bill).where(Bill.user_id == user_id).order_by(Bill.due_date.asc())).scalars().all()

# ---- Pages ----
if page == "Dashboard":
    st.title("📊 Dashboard")
    with get_db() as db:
        buckets = load_buckets(db, user_id)
        giants = load_giants(db, user_id)
        movs = load_movements(db, user_id)

        total_balance = sum(b.balance for b in buckets)

        # Métricas mensais e totais
        today = date.today()
        month_movs = [m for m in movs if m.date.month == today.month and m.date.year == today.year]
        total_income_val = sum(m.amount for m in movs if m.kind == 'income')
        total_expense_val = sum(m.amount for m in movs if m.kind in ('expense', 'transfer'))
        month_income = sum(m.amount for m in month_movs if m.kind == 'income')
        month_expense = sum(m.amount for m in month_movs if m.kind in ('expense', 'transfer'))

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("Saldo total nos Baldes", money_br(total_balance))
        with col2:
            st.metric("Receitas (mês)", money_br(month_income))
        with col3:
            st.metric("Despesas/Transf. (mês)", money_br(month_expense))
        with col4:
            st.metric("Receitas (total)", money_br(total_income_val))
        with col5:
            st.metric("Despesas/Transf. (total)", money_br(total_expense_val))
        with col6:
            active = [g for g in giants if g.status == "active"]
            st.metric("Gigantes ativos", len(active))

        if buckets:
            df_b = pd.DataFrame([{"Balde": b.name, "%": b.percent, "Saldo": money_br(b.balance)} for b in buckets])
            st.subheader("Distribuição por Balde")
            st.dataframe(df_b, use_container_width=True)

        if giants:
            giants_sorted = sorted(giants, key=lambda g: (g.priority, -g.total_to_pay))
            df_g = pd.DataFrame([{"Gigante": g.name, "Total a Quitar": money_br(g.total_to_pay), "Prioridade": g.priority, "Status": g.status} for g in giants_sorted])
            st.subheader("Gigantes")
            st.dataframe(df_g, use_container_width=True)

        defeated = [g for g in giants if g.status == "defeated"]
        st.caption(f"Vitórias: {len(defeated)}")

elif page == "Plano de Ataque":
    st.title("🛡️ Plano de Ataque — Gigantes")
    with get_db() as db:
        with st.form("novo_gigante"):
            st.subheader("Novo Gigante")
            name_g = st.text_input("Nome", placeholder="Ex.: Cartão X")
            total_str = st.text_input("Total a Quitar (R$)", value="")
            total = parse_money_br(total_str) if total_str else 0.0
            parcels = st.number_input("Parcelas", min_value=0, step=1, value=0)
            months_left = st.number_input("Meses restantes", min_value=0, step=1, value=0)
            priority = st.number_input("Prioridade (1=maior)", min_value=1, step=1, value=1)
            submitted = st.form_submit_button("Adicionar")
            if submitted and name_g.strip():
                g = Giant(user_id=user_id, name=name_g.strip(), total_to_pay=total,
                          parcels=parcels, months_left=months_left, priority=priority, status="active")
                db.add(g)
                db.commit()
                st.success("Gigante criado!")

        giants = load_giants(db, user_id)
        if giants:
            giants_sorted = sorted(giants, key=lambda g: (g.priority, -g.total_to_pay))
            st.subheader("Seus Gigantes")
            for g in giants_sorted:
                with st.expander(f"{g.name} — {money_br(g.total_to_pay)} | prioridade {g.priority} | status {g.status}"):
                    monthly_str = st.text_input(f"Aporte mensal para {g.name} (R$)", value="", key=f"mi_{g.id}")
                    monthly_input = parse_money_br(monthly_str) if monthly_str else 0.0
                    if monthly_input > 0:
                        eff = payoff_efficiency(g, monthly_input)
                        st.write(f"Eficiência (R$/1k): {eff['r_per_1k']}")
                        st.write(f"Meses até a vitória: {eff['months_to_victory']}")
                    if st.button("Marcar Vitória", key=f"def_{g.id}"):
                        g.status = "defeated"
                        db.commit()
                        st.success("🎉 Vitória! Gigante derrotado.")

elif page == "Baldes":
    st.title("🪣 Baldes")
    with get_db() as db:
        with st.form("novo_balde"):
            st.subheader("Adicionar Balde")
            name_b = st.text_input("Nome do Balde", placeholder="Ex.: Operacional")
            desc_b = st.text_input("Descrição", placeholder="Opcional")
            percent_b = st.number_input("Percentual (%)", min_value=0.0, max_value=100.0, step=1.0)
            type_b = st.text_input("Tipo", value="generic")
            submitted = st.form_submit_button("Salvar")
            if submitted and name_b.strip():
                b = Bucket(user_id=user_id, name=name_b.strip(), description=desc_b.strip(),
                           percent=percent_b, type=type_b, balance=0.0)
                db.add(b)
                db.commit()
                st.success("Balde salvo!")

        buckets = load_buckets(db, user_id)
        if buckets:
            total_percent = sum(b.percent for b in buckets)
            if total_percent < 0 or any(b.percent < 0 for b in buckets):
                st.error("Há percentuais negativos. Ajuste para continuar usando a divisão.")
            st.info(f"Percentuais atuais somam **{total_percent:.2f}%**. Se não for 100%, a divisão é normalizada na Entrada Diária.")
            if st.button("Normalizar percentuais para 100%"):
                if total_percent <= 0:
                    st.warning("Não é possível normalizar: soma é 0%.")
                else:
                    factor = 100.0 / total_percent
                    for b in buckets:
                        b.percent = round(b.percent * factor, 2)
                    db.commit()
                    st.success("Percentuais normalizados para 100%. Recarregue a página.")

            df_b = pd.DataFrame([{"ID": b.id, "Nome": b.name, "Descrição": b.description, "%": b.percent, "Tipo": b.type, "Saldo": money_br(b.balance)} for b in buckets])
            st.dataframe(df_b, use_container_width=True)

            st.subheader("Editar balde existente")
            ids = [b.id for b in buckets]
            sel = st.selectbox("Escolha o ID", ids) if ids else None
            if sel:
                b = next(x for x in buckets if x.id == sel)
                with st.form(f"edit_balde_{sel}"):
                    name_b2 = st.text_input("Nome", value=b.name)
                    desc_b2 = st.text_input("Descrição", value=b.description)
                    percent_b2 = st.number_input("Percentual (%)", min_value=0.0, max_value=100.0, step=1.0, value=float(b.percent))
                    type_b2 = st.text_input("Tipo", value=b.type)
                    confirm = st.checkbox("Confirmar alterações")
                    saveb = st.form_submit_button("Salvar alterações")
                    if saveb and confirm:
                        b.name, b.description, b.percent, b.type = name_b2, desc_b2, percent_b2, type_b2
                        db.commit()
                        st.success("Balde atualizado!")
                    elif saveb and not confirm:
                        st.warning("Confirme as alterações para salvar.")

elif page == "Entrada Diária":
    st.title("📥 Entrada Diária")
    with get_db() as db:
        buckets = load_buckets(db, user_id)
        if not buckets:
            st.warning("Crie baldes primeiro.")
        else:
            d = st.date_input("Data", value=date.today())
            val_str = st.text_input("Valor total recebido (ex.: 10.249,00)", value="")
            val = parse_money_br(val_str) if val_str else 0.0
            if st.button("Dividir e Lançar"):
                splits = compute_bucket_splits(buckets, val)
                for s in splits:
                    m = Movement(user_id=user_id, bucket_id=s["bucket_id"], kind="income",
                                 amount=s["value"], description="Entrada diária", date=d)
                    db.add(m)
                    b = db.get(Bucket, s["bucket_id"])
                    if b and b.user_id == user_id:
                        b.balance += s["value"]
                db.commit()
                st.success("Entrada lançada e dividida entre os baldes.")
                df = pd.DataFrame([{"Balde": s["name"], "% efetivo": s["percent_effective"], "Valor": money_br(s["value"])} for s in splits])
                st.table(df)

elif page == "Livro Caixa":
    st.title("📗 Livro Caixa")
    with get_db() as db:
        st.subheader("Nova movimentação")
        kind = st.selectbox("Tipo", ["income", "expense", "transfer"], index=0)
        buckets_all = load_buckets(db, user_id)
        ids = [b.id for b in buckets_all]
        allow_negative = st.checkbox("Permitir saldo negativo no(s) balde(s)", value=False)

        if kind == "transfer":
            orig = st.selectbox("Balde de origem", ids, index=0 if ids else None)
            dest = st.selectbox("Balde de destino", ids, index=1 if ids and len(ids) > 1 else 0)
            val_str = st.text_input("Valor (R$)", value="")
            val = parse_money_br(val_str) if val_str else 0.0
            d = st.date_input("Data", value=date.today())
            desc = st.text_input("Descrição", value="Transferência entre baldes")
            if st.button("Transferir"):
                if val > 0 and orig != dest:
                    b_orig = db.get(Bucket, orig)
                    b_dest = db.get(Bucket, dest)
                    if b_orig and b_dest:
                        if not allow_negative and b_orig.balance - val < 0:
                            st.error("Saldo insuficiente no balde de origem (desmarque o bloqueio para permitir negativo).")
                        else:
                            m_out = Movement(user_id=user_id, bucket_id=orig, kind="transfer", amount=val, description=desc + " (saída)", date=d)
                            m_in = Movement(user_id=user_id, bucket_id=dest, kind="income", amount=val, description=desc + " (entrada)", date=d)
                            db.add(m_out)
                            db.add(m_in)
                            b_orig.balance -= val
                            b_dest.balance += val
                            db.commit()
                            st.success("Transferência realizada.")
                else:
                    st.warning("Informe um valor > 0 e selecione baldes diferentes.")
        else:
            bucket_id = st.selectbox("Balde", ids, index=0 if ids else None)
            val_str = st.text_input("Valor (R$)", value="")
            val = parse_money_br(val_str) if val_str else 0.0
            d = st.date_input("Data", value=date.today())
            desc = st.text_input("Descrição", value="")
            if st.button("Lançar"):
                if val > 0 and bucket_id:
                    m = Movement(user_id=user_id, bucket_id=bucket_id, kind=kind, amount=val, description=desc, date=d)
                    db.add(m)
                    b = db.get(Bucket, bucket_id)
                    if b and b.user_id == user_id:
                        if kind == "income":
                            b.balance += val
                        elif kind in ("expense", "transfer"):
                            if not allow_negative and b.balance - val < 0:
                                st.error("Saldo insuficiente no balde selecionado (desmarque o bloqueio para permitir negativo).")
                                db.rollback()
                                st.stop()
                            else:
                                b.balance -= val
                    db.commit()
                    st.success("Movimentação lançada")
                else:
                    st.warning("Informe um valor > 0 e selecione um balde.")

        movs = load_movements(db, user_id)
        if movs:
            df = pd.DataFrame([{"Data": date_br(m.date), "Tipo": m.kind, "BaldeID": m.bucket_id, "Valor": money_br(m.amount), "Descrição": m.description} for m in movs])
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Exportar CSV", data=csv, file_name="livro_caixa.csv")
        else:
            st.info("Sem movimentações ainda.")

elif page == "Calendário":
    st.title("🗓️ Calendário de Despesas")
    with get_db() as db:
        with st.form("nova_conta"):
            title = st.text_input("Título", placeholder="Ex.: Cartão C6 - Fatura")
            amount_str = st.text_input("Valor (R$)", value="")
            amount = parse_money_br(amount_str) if amount_str else 0.0
            due = st.date_input("Vencimento", value=date.today())
            critical = st.checkbox("Crítica (cartão/ empréstimo/ consórcio)")
            submitted = st.form_submit_button("Adicionar")
            if submitted and title.strip():
                b = Bill(user_id=user_id, title=title.strip(), amount=amount, due_date=due, is_critical=critical, paid=False)
                db.add(b)
                db.commit()
                st.success("Conta adicionada.")

        bills = load_bills(db, user_id)
        if bills:
            df = pd.DataFrame([{"ID": b.id, "Título": b.title, "Valor": money_br(b.amount), "Vencimento": date_br(b.due_date), "Crítica": b.is_critical, "Paga": b.paid} for b in bills])
            st.dataframe(df, use_container_width=True)

            st.subheader("Editar conta")
            ids = [b.id for b in bills]
            sel = st.selectbox("Escolha o ID", ids) if ids else None
            if sel:
                b = next(x for x in bills if x.id == sel)
                with st.form(f"edit_bill_{sel}"):
                    title2 = st.text_input("Título", value=b.title)
                    amount2_str = st.text_input("Valor (R$)", value=str(b.amount).replace('.', ','))
                    amount2 = parse_money_br(amount2_str) if amount2_str else b.amount
                    due2 = st.date_input("Vencimento", value=b.due_date)
                    critical2 = st.checkbox("Crítica", value=b.is_critical)
                    paid2 = st.checkbox("Paga", value=b.paid)
                    confirm = st.checkbox("Confirmar alterações")
                    sb = st.form_submit_button("Salvar alterações")
                    if sb and confirm:
                        b.title, b.amount, b.due_date, b.is_critical, b.paid = title2, amount2, due2, critical2, paid2
                        db.commit()
                        st.success("Conta atualizada!")
                    elif sb and not confirm:
                        st.warning("Confirme as alterações marcando a caixa.")

elif page == "Atrasos & Riscos":
    st.title("⏰ Atrasos & Riscos")
    today = date.today()
    with get_db() as db:
        bills = load_bills(db, user_id)
        overdue = [b for b in bills if (not b.paid and b.due_date < today)]
        due_soon = [b for b in bills if (not b.paid and today <= b.due_date <= today + timedelta(days=3))]

        st.subheader("Vencidas")
        if overdue:
            df1 = pd.DataFrame([{"ID": b.id, "Título": b.title, "Valor": money_br(b.amount), "Venceu em": date_br(b.due_date), "Crítica": b.is_critical, "Paga": b.paid} for b in overdue])
            st.dataframe(df1, use_container_width=True)
            ids1 = [b.id for b in overdue]
            sel1 = st.selectbox("ID vencida", ids1) if ids1 else None
            if sel1:
                b = next(x for x in bills if x.id == sel1)
                with st.form(f"edit_overdue_{sel1}"):
                    title2 = st.text_input("Título", value=b.title)
                    amount2_str = st.text_input("Valor (R$)", value=str(b.amount).replace('.', ','))
                    amount2 = parse_money_br(amount2_str) if amount2_str else b.amount
                    due2 = st.date_input("Vencimento", value=b.due_date)
                    critical2 = st.checkbox("Crítica", value=b.is_critical)
                    paid2 = st.checkbox("Paga", value=b.paid)
                    confirm = st.checkbox("Confirmar alterações")
                    sb = st.form_submit_button("Salvar")
                    if sb and confirm:
                        b.title, b.amount, b.due_date, b.is_critical, b.paid = title2, amount2, due2, critical2, paid2
                        db.commit()
                        st.success("Atualizada!")
                    elif sb and not confirm:
                        st.warning("Confirme as alterações marcando a caixa.")

        else:
            st.write("Sem contas vencidas.")

        st.subheader("Vencendo em até 3 dias")
        if due_soon:
            df2 = pd.DataFrame([{"ID": b.id, "Título": b.title, "Valor": money_br(b.amount), "Vencimento": date_br(b.due_date), "Crítica": b.is_critical, "Paga": b.paid} for b in due_soon])
            st.dataframe(df2, use_container_width=True)
            ids2 = [b.id for b in due_soon]
            sel2 = st.selectbox("ID a vencer", ids2) if ids2 else None
            if sel2:
                b = next(x for x in bills if x.id == sel2)
                with st.form(f"edit_duesoon_{sel2}"):
                    title2 = st.text_input("Título", value=b.title)
                    amount2_str = st.text_input("Valor (R$)", value=str(b.amount).replace('.', ','))
                    amount2 = parse_money_br(amount2_str) if amount2_str else b.amount
                    due2 = st.date_input("Vencimento", value=b.due_date)
                    critical2 = st.checkbox("Crítica", value=b.is_critical)
                    paid2 = st.checkbox("Paga", value=b.paid)
                    confirm = st.checkbox("Confirmar alterações")
                    sb = st.form_submit_button("Salvar")
                    if sb and confirm:
                        b.title, b.amount, b.due_date, b.is_critical, b.paid = title2, amount2, due2, critical2, paid2
                        db.commit()
                        st.success("Atualizada!")
                    elif sb and not confirm:
                        st.warning("Confirme as alterações marcando a caixa.")
        else:
            st.write("Sem contas críticas nos próximos 3 dias.")

elif page == "Configurações":
    st.title("⚙️ Configurações")
    st.write("Altere o usuário ativo pela barra lateral.")
    with get_db() as db:
        if st.button("Reset (apagar tudo)"):
            db.query(Bill).delete()
            db.query(Movement).delete()
            db.query(Giant).delete()
            db.query(Bucket).delete()
            db.query(User).delete()
            db.commit()
            st.session_state.pop("user_id", None)
            st.session_state.pop("user_name", None)
            st.success("Banco limpo. Recarregue e crie um novo usuário.")
