# 🛡️ CFTV Sentinel NOC v2.0 — Central de Monitoramento & Alertas Inteligentes

Sistema completo e corporativo de monitoramento em tempo real para infraestrutura de **CFTV (Câmeras IP, NVRs e DVRs Intelbras, Dahua, Hikvision)** com diagnóstico híbrido ultrarrápido, suporte Multi-Clientes (*Multi-Tenant*), snapshots ao vivo, histórico de incidentes em SQLite e despacho de alertas automatizados via **WhatsApp (com Anti-Ban e Grupos)** e **Telegram**.

---

## 🚀 O que há de Novo na Versão 2.0

* 🔒 **Segurança & RBAC:** Autenticação JWT com PBKDF2-SHA256, papéis de acesso (`admin`, `operator`, `viewer`), rate limiting anti-força bruta e criptografia AES-256 para senhas de DVR/Câmeras.
* 🏛️ **Arquitetura Modular Limpa:** Camadas desacopladas (`core/`, `models/`, `state/`, `routes/`, `tests/`) com barramento assíncrono de eventos (*EventBus/Pub-Sub*).
* 🐳 **Docker & Docker Compose:** Imagens otimizadas com Chromium/Puppeteer e healthchecks automáticos.
* 💾 **Histórico de Incidentes em SQLite:** Gravação automática de eventos de queda/recuperação com exportação de relatórios em CSV.
* 📊 **Métricas Prometheus & Observabilidade:** Endpoints `/api/health`, `/api/ready` e `/metrics` prontos para integração com Grafana.
* 🧪 **Suíte de Testes Automatizados:** 19 testes automatizados com Pytest e CI/CD no GitHub Actions.

---

## 📂 Estrutura do Repositório

```
📁 CFTV-CENTINEL/
├── 📂 cftv-monitor-v2/         -> Central Multi-Clientes / FastAPI (Porta 8001)
│   ├── 📂 core/                -> Diagnóstico, Tracker, Notifier, EventBus, Auth, DB
│   ├── 📂 models/              -> Modelos Pydantic (schemas.py)
│   ├── 📂 routes/              -> Rotas modulares (auth, cameras, clients, alerts, health)
│   ├── 📂 state/               -> Gerenciamento centralizado de estado (app_state.py)
│   ├── 📂 tests/               -> Suíte completa de testes (pytest)
│   └── 📄 Dockerfile           -> Container Python 3.11 com OpenCV
├── 📂 whatsapp-gateway/        -> Microserviço Gateway de WhatsApp Web (Porta 8080)
│   ├── 📄 server.js            -> Motor WhatsApp-Web.js com 5 camadas Anti-Ban
│   └── 📄 Dockerfile           -> Container Node.js com Chromium
├── 📂 docs/                    -> Documentação técnica completa
│   ├── 📄 ARCHITECTURE.md      -> Diagramas de arquitetura e fluxo de dados
│   ├── 📄 API.md               -> Referência de endpoints e exemplos curl
│   └── 📄 DOCKER.md            -> Guia detalhado de deploy com Docker
├── 📄 docker-compose.yml       -> Orquestração de todos os microserviços
├── 📄 .env.example             -> Modelo de variáveis de ambiente e segurança
├── 📄 ROADMAP.md               -> Visão e planejamento de novas versões
├── 📄 CONTRIBUTING.md          -> Guia de contribuição
└── 📄 README.md                -> Apresentação principal
```

---

## ⚡ Como Executar

### Opção 1: Via Docker Compose (Recomendado para Produção)

1. Clone o repositório e crie o arquivo de ambiente:
```bash
git clone https://github.com/dyonatan12/CFTV-CENTINEL.git
cd CFTV-CENTINEL
cp .env.example .env
```

2. Inicie todos os serviços:
```bash
docker compose up -d --build
```

3. Acesse os serviços no navegador:
* 🌐 **Painel Central NOC (v2.0):** [http://localhost:8001](http://localhost:8001)
* 📱 **Gateway WhatsApp & Leitor de QR Code:** [http://localhost:8080](http://localhost:8080)
* 🩺 **Health Check:** [http://localhost:8001/api/health](http://localhost:8001/api/health)
* 📊 **Métricas Prometheus:** [http://localhost:8001/metrics](http://localhost:8001/metrics)

---

### Opção 2: Execução Local Direta (Desenvolvimento)

#### 1. Iniciar o Gateway do WhatsApp (Node.js):
```bash
cd whatsapp-gateway
npm install
npm start
```

#### 2. Iniciar o Monitor CFTV (Python / FastAPI):
```bash
cd cftv-monitor-v2
pip install -r requirements.txt
python app.py
```

---

## 🧪 Rodando os Testes Automatizados

```bash
cd cftv-monitor-v2
python -m pytest tests/ -v
```

---

## 📚 Documentação Adicional

* 🏛️ [Arquitetura e Fluxo de Dados (docs/ARCHITECTURE.md)](docs/ARCHITECTURE.md)
* 📖 [Manual da API REST (docs/API.md)](docs/API.md)
* 🐳 [Guia do Docker Compose (docs/DOCKER.md)](docs/DOCKER.md)
* 🗺️ [Roadmap do Projeto (ROADMAP.md)](ROADMAP.md)
* 🤝 [Como Contribuir (CONTRIBUTING.md)](CONTRIBUTING.md)

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para obter mais informações.
