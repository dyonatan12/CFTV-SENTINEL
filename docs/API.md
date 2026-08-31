# 📖 Referência da API REST — CFTV Sentinel v2.0

A API do **CFTV Sentinel** é construída com **FastAPI**, oferecendo documentação interativa Swagger em `/docs` e OpenAPI em `/openapi.json`.

---

## 🔐 Autenticação (`/api/auth`)

Todas as rotas de modificação ou leitura sensível exigem autenticação via Bearer Token JWT no header:
```http
Authorization: Bearer <seu_token_jwt>
```

### 1. Autenticação de Usuário (Login)
* **Endpoint:** `POST /api/auth/login`
* **Rate Limit:** 5 tentativas por minuto por IP

#### Exemplo de Requisição:
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin_cftv_change_me!"}'
```

#### Exemplo de Resposta (`200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "usr-a1b2c3",
    "username": "admin",
    "name": "Administrador Central",
    "role": "admin"
  }
}
```

---

## 📸 Câmeras & Dispositivos (`/api/cameras`)

### 1. Listar Câmeras
* **Endpoint:** `GET /api/cameras`
* **Query Params:** `?client_id=cli-xyz` (opcional)

```bash
curl -X GET http://localhost:8001/api/cameras \
  -H "Authorization: Bearer <token>"
```

### 2. Cadastrar Câmera
* **Endpoint:** `POST /api/cameras`
* **Permissão Mínima:** `operator` ou `admin`

```bash
curl -X POST http://localhost:8001/api/cameras \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Portaria Entrada",
    "ip": "192.168.1.100",
    "port": 554,
    "http_port": 80,
    "username": "admin",
    "password": "senha_segura_aqui",
    "client_id": "cli-01",
    "custom_failure_threshold": 3
  }'
```

### 3. Cadastro em Lote (DVR / Faixa de IPs)
* **Endpoint:** `POST /api/cameras/bulk-generate`

```bash
curl -X POST http://localhost:8001/api/cameras/bulk-generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "dvr_channels",
    "client_id": "cli-01",
    "dvr_name": "NVD-Empresa",
    "dvr_ip": "192.168.1.200",
    "channel_start": 1,
    "channel_end": 16,
    "username": "admin",
    "password": "senha_do_nvr"
  }'
```

---

## 🏢 Gestão de Clientes (`/api/clients`)

* `GET /api/clients` — Lista todos os clientes
* `POST /api/clients` — Cria novo cliente (Requer `operator`/`admin`)
* `PUT /api/clients/{id}` — Atualiza dados do cliente
* `DELETE /api/clients/{id}` — Remove cliente

---

## 📊 Histórico de Alertas (`/api/alerts`)

### 1. Consultar Histórico Paginado
* **Endpoint:** `GET /api/alerts`
* **Query Params:** `client_id`, `device_id`, `status` (`ONLINE`/`OFFLINE`), `limit`, `offset`

```bash
curl -X GET "http://localhost:8001/api/alerts?status=OFFLINE&limit=20"
```

### 2. Exportar Histórico para CSV
* **Endpoint:** `GET /api/alerts/export/csv`

```bash
curl -X GET "http://localhost:8001/api/alerts/export/csv?client_id=cli-01" \
  -o relatorio_alertas.csv
```

---

## 🩺 Saúde & Métricas

* `GET /api/health` — Status detalhado da central e conexões
* `GET /api/ready` — Readiness check do container
* `GET /metrics` — Métricas no formato do Prometheus
