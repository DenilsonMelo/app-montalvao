# Finance App (UI corrigida)
Passos:
1) Ative o venv e instale deps (você já tem `requirements.txt`):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2) Substitua o seu `app.py` por este aqui (backup se quiser) e copie a pasta `assets/` para a raiz do projeto.
3) Rode:
   ```bash
   streamlit run app.py
   ```
Notas:
- Botões **🧽 Limpar** zeram campos sem perder o estado do formulário.
- Botões **🗑️ Apagar** removem o lançamento via `logic.delete_transaction` se existir; caso contrário, usa um fallback em memória.
- Todos os inputs possuem **labels** (sem warnings de acessibilidade) e os valores monetários mostram **(R$)**.
- Incluída seção de **Lançamento extra (Entrada/ Saída)**.
