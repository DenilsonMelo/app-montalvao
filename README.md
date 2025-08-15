# Sistema Financeiro — PRO (PT-BR) (CLEAN)
Pasta completa com **finance.db já criado**, mas **sem baldes** e **sem entrada inicial**.
- Objetivos/cartões e calendário já vêm preenchidos como exemplo.
- Você pode editar tudo pela interface.

## Como rodar (Mac)
```bash
cd /caminho/para/finance_app_mac_plus_READY_CLEAN
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Se quiser redefinir, apague `finance.db` e rode novamente o app (as tabelas serão recriadas).

## Dica de uso inicial
1. Vá na aba **Baldes** e crie seus baldes (ex.: Dízimo, Stone OPEX, BNB Empréstimos, NuPJ Cartões, Nu PF Ataque) com percentuais.
2. Use **Distribuição diária** para lançar sua primeira entrada (R$).
3. Abra **Plano de Ataque** para ver o ranking dos cartões.
