# 🤝 Guia de Contribuição — CFTV Sentinel

Obrigado pelo interesse em contribuir com o **CFTV Sentinel**! Este documento orienta sobre o fluxo de desenvolvimento, padrões de código e submissão de pull requests.

---

## 🛠️ Configuração do Ambiente Local

### 1. Clonar o Repositório
```bash
git clone https://github.com/dyonatan12/CFTV-CENTINEL.git
cd CFTV-CENTINEL
```

### 2. Configurar o Backend Python
```bash
cd cftv-monitor-v2
python -m venv .venv
# Linux/Mac: source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install pytest pytest-asyncio
```

### 3. Configurar o Gateway WhatsApp (Node.js)
```bash
cd ../whatsapp-gateway
npm install
```

---

## 🧪 Executando os Testes

Antes de submeter qualquer alteração, certifique-se de que todos os testes automatizados estão passando:

```bash
cd cftv-monitor-v2
python -m pytest tests/ -v
```

---

## 📐 Padrões de Código

* **Python:** PEP 8 com tipagem estática do Pydantic (`type hints`).
* **Segurança:** Nunca comitar senhas, tokens ou arquivos `.env` e `.wwebjs_auth`.
* **Commits Semânticos:**
  * `feat: adiciona suporte a webhooks`
  * `fix: corrige timeout no diagnóstico RTSP`
  * `docs: atualiza guia de instalação do Docker`
  * `test: adiciona teste para histórico de alertas`

---

## 🚀 Fluxo de Pull Request

1. Crie uma branch para sua funcionalidade: `git checkout -b feat/minha-melhoria`
2. Faça as alterações e rode os testes: `pytest tests/`
3. Faça commit: `git commit -m 'feat: minha melhoria'`
4. Envie para o GitHub: `git push origin feat/minha-melhoria`
5. Abra um **Pull Request** detalhando as mudanças realizadas.
