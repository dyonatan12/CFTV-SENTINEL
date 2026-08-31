# 🗺️ Roadmap de Evolução — CFTV Sentinel

Este documento define a visão e o planejamento de novas funcionalidades e marcos do projeto **CFTV Sentinel**.

---

## 📍 Versão 2.0 (Atual — Concluída ✅)
* [x] **Segurança Completa**: Autenticação JWT, PBKDF2-SHA256, roles RBAC (`admin`, `operator`, `viewer`) e rate limiting.
* [x] **Criptografia em Repouso**: AES-256 (Fernet) para proteção de credenciais de câmeras e DVRs.
* [x] **Arquitetura Modular**: Camadas `core/`, `models/`, `state/`, `routes/`, `tests/` e eliminação de God-Classes.
* [x] **Barramento de Eventos (EventBus)**: Desacoplamento de alertas e transmissão SSE.
* [x] **Banco de Dados SQLite**: Histórico de incidentes persistente com exportação de relatórios em CSV.
* [x] **Docker & Compose**: Imagens otimizadas com Chromium/Puppeteer e healthchecks.
* [x] **Observabilidade & Métricas**: Endpoints `/api/health`, `/api/ready` e exportador de métricas Prometheus `/metrics`.
* [x] **Suíte de Testes Automatizados**: Cobertura com Pytest e workflows de CI no GitHub Actions.

---

## 🚀 Versão 2.1 (Próximo Ciclo)
* [ ] **Suporte a PostgreSQL**: Driver plugável para ambientes empresariais de grande porte.
* [ ] **Webhooks Genéricos**: Disparo de alertas para Discord, Microsoft Teams, Slack e sistemas NOC (Zabbix/PagerDuty).
* [ ] **Compressão WebP e Rotação Automática**: Redução de consumo de disco para snapshots antigos (> 7 dias).
* [ ] **Detecção de NVR por Agrupamento Dinâmico**: Algoritmo adaptativo baseado em topologia de rede.

---

## 🔮 Versão 3.0 (Visão Futura)
* [ ] **IA de Visão Computacional na Borda**:
  * Detecção de adulteração de câmera (lente tampada, spray ou mudança brusca de ângulo).
  * Detecção de perda de iluminação/infravermelho no período noturno.
* [ ] **Painel NOC Modernizado**: Interface web em React/Next.js com dashboard em tempo real, mapas interativos e suporte a Mobile PWA.
* [ ] **Multi-Gateway WhatsApp com Load Balancer**: Rotação entre múltiplos números para grandes centrais de monitoramento (+1.000 câmeras).
