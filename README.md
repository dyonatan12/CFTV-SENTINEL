# 🛡️ CFTV Sentinel - Central de Monitoramento NOC & Alertas Inteligentes

Sistema completo de monitoramento em tempo real para infraestrutura de **CFTV (Câmeras IP, NVRs e DVRs Intelbras/Dahua/Hikvision)** com diagnóstico híbrido, suporte Multi-Clientes (v2.0), snapshots ao vivo e despacho de alertas automatizados via **WhatsApp (com Anti-Ban e Grupos)** e **Telegram**.

---

## 🚀 Arquitetura do Sistema

```
📁 scratch/
├── 📂 cftv-monitor/          -> v1.0: Monitoramento Monolítico (Porta 8000)
├── 📂 cftv-monitor-v2/       -> v2.0: Central Multi-Clientes / Multi-Tenant (Porta 8001)
├── 📂 whatsapp-gateway/      -> Microserviço Gateway de WhatsApp Web (Porta 8080)
├── 📄 .gitignore             -> Proteção de credenciais, sessões e arquivos de mídia
└── 📄 README.md              -> Documentação Completa
```

---

## ✨ Principais Funcionalidades

### 1. 🔍 Diagnóstico Híbrido Ultrarrápido & Snapshots Reais
* **HTTP CGI + RTSP OpenCV (Porta 554):** Captura imagens reais dos canais do gravador em menos de 500ms.
* **Detecção Cirúrgica de Canais:** Identifica canais vazios ou sem sinal (ex: `HTTP 400 Host não encontrado`) marcando-os como **🔴 OFFLINE** sem falsos positivos.
* **Prevenção de Sobrecarga:** Semáforo de concorrência que impede o travamento da CPU dos gravadores.
* **Visualização Sem Flickering:** DOM diffing cirúrgico com atualização suave de status e fotos.

### 2. 🏢 Central Multi-Clientes (v2.0 - Porta 8001)
* **Gestão de Empresas/Clientes:** Cadastre clientes com contatos e números dedicados.
* **Cadastro em Lote de Gravadores:** Gere todos os canais de um DVR (ex: 1 ao 16) e vincule à empresa com 1 clique.
* **Filtros por Empresa:** Visualize o mosaico de câmeras de um cliente específico ou a visão geral do NOC.
* **Alertas Personalizados:** Envie notificações da queda de uma loja diretamente para o gerente daquela unidade e para a equipe de segurança.

### 3. 💬 Gateway WhatsApp Local com Proteção Anti-Ban & Grupos (Porta 8080)
* **Sem Necessidade de API Paga:** Utiliza motor `whatsapp-web.js` com sessão persistente via `LocalAuth`.
* **5 Camadas Anti-Ban:**
  1. Fila de despacho sequencial com intervalo humano aleatório (3s a 5s).
  2. Simulação real de digitação (*composing*).
  3. Cooldown de 10 minutos por câmera (anti-flapping).
  4. Limite de intervalo por destinatário.
  5. Agrupador inteligente de alertas de NVR.
* **Suporte Completo a Grupos (`@g.us`):** Descobre e envia alertas diretamente para grupos de plantão e segurança.

### 4. 🤖 Notificações no Telegram
* Bot integrado com suporte a mensagens formatadas em Markdown e snapshots anexados.

---

## 🛠️ Como Instalar e Executar

### Pré-requisitos
* **Python 3.10+** (com OpenCV, FastAPI, Uvicorn, Pillow, HTTPX, Pydantic)
* **Node.js 18+** (para o Gateway do WhatsApp)
* **Google Chrome** instalado (usado pelo Puppeteer)

### 1. Instalar Dependências do Python
```bash
cd cftv-monitor-v2
pip install fastapi uvicorn httpx pillow opencv-python pydantic requests
```

### 2. Instalar Dependências do WhatsApp Gateway
```bash
cd whatsapp-gateway
npm install
```

---

## 🚦 Como Iniciar

### Iniciar o Gateway do WhatsApp:
```bash
cd whatsapp-gateway
node server.js
```
> Acesse **http://localhost:8080** para escanear o QR Code no primeiro uso.

### Iniciar o Monitor v2.0 (Multi-Clientes):
```bash
cd cftv-monitor-v2
python app.py
```
> Acesse o painel web em: **http://localhost:8001**

### Iniciar o Monitor v1.0 (Cliente Único):
```bash
cd cftv-monitor
python app.py
```
> Acesse o painel web em: **http://localhost:8000**

---

## 📋 Variáveis & Configurações (`settings.json`)

Você pode configurar todos os parâmetros diretamente pela interface web (ícone de engrenagem ⚙️ **Ajustes**) ou no arquivo `settings.json`:

```json
{
  "check_interval": 45,
  "connection_timeout": 3.5,
  "failure_threshold": 2,
  "recovery_threshold": 1,
  "whatsapp": {
    "enabled": true,
    "provider": "evolution",
    "api_url": "http://localhost:8080",
    "instance_name": "cftv-gateway",
    "api_key": "cftv-secret-key",
    "target_number": "5511999998888"
  },
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  }
}
```

---

## 🛡️ Segurança & Privacidade
* As pastas `.wwebjs_auth/` e os arquivos de cache de mídia e snapshots são ignorados via `.gitignore` para garantir que nenhuma credencial ou imagem sensível seja enviada ao repositório.

---

## 📄 Licença
Distribuído sob a licença **MIT**.
