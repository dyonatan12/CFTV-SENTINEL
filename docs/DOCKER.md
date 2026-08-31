# 🐳 Guia de Execução com Docker — CFTV Sentinel

Este documento explica como executar toda a infraestrutura do **CFTV Sentinel** em produção ou desenvolvimento utilizando **Docker** e **Docker Compose**.

---

## 📋 Pré-requisitos
* **Docker Engine 24.0+**
* **Docker Compose v2.20+**

---

## 🚀 Passo a Passo de Execução

### 1. Configurar Variáveis de Ambiente
Copie o arquivo de exemplo e ajuste suas credenciais:
```bash
cp .env.example .env
```

Edite o `.env` e configure sua chave secreta JWT e parâmetros de notificação:
```bash
JWT_SECRET_KEY=sua_chave_secreta_de_32_caracteres_minimo
SERVER_PORT=8001
```

### 2. Criar Diretórios de Persistência
```bash
mkdir -p data/snapshots data/config data/logs data/whatsapp-session
```

Copie os arquivos de configuração iniciais para a pasta persistente se desejar:
```bash
cp cftv-monitor-v2/settings.json data/config/
cp cftv-monitor-v2/cameras.json data/config/
cp cftv-monitor-v2/clients.json data/config/
```

### 3. Iniciar os Serviços com Docker Compose
```bash
docker compose up -d --build
```

### 4. Acessar os Painéis
* 🌐 **Painel Central NOC (v2.0):** [http://localhost:8001](http://localhost:8001)
* 📱 **Gateway WhatsApp & Leitor de QR Code:** [http://localhost:8080](http://localhost:8080)
* 🩺 **Health Check API:** [http://localhost:8001/api/health](http://localhost:8001/api/health)
* 📊 **Métricas Prometheus:** [http://localhost:8001/metrics](http://localhost:8001/metrics)

---

## 🛠️ Comandos Úteis

#### Ver logs em tempo real:
```bash
docker compose logs -f
```

#### Ver logs apenas do monitor:
```bash
docker compose logs -f cftv-monitor
```

#### Reiniciar os serviços:
```bash
docker compose restart
```

#### Parar os serviços:
```bash
docker compose down
```
