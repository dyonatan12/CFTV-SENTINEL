# 📹 CFTV Monitor - Sistema de Monitoramento de Câmeras IP

Sistema assíncrono para monitoramento contínuo de status de câmeras IP e Gravadores (NVD / iNVD Intelbras).

---

## 🌐 Como Rodar o Painel Web (Dashboard no Navegador)

Inicie o servidor web integrado com um único comando:

### 1. Teste do Painel com Câmeras Simuladas:
```bash
python app.py --mock
```
Em seguida, abra no seu navegador: **`http://localhost:8000`**

### 2. Teste do Painel com as 128 Câmeras Virtuais:
```bash
python app.py --file cameras_128.json --mock
```

### 3. Rodar na Rede Real / Produção:
```bash
python app.py
```

---

## 💻 Recursos do Painel Web:
- **Grade Visual em Tempo Real:** Cards com status verde (Online), vermelho (Offline) e amarelo (Instável).
- **Filtros Dinâmicos:** Filtre por texto, apenas offline ou selecione um gravador específico (NVD/iNVD).
- **Sem Recarregar a Página:** Atualizações automáticas instantâneas via *Server-Sent Events (SSE)*.
- **Botão "Varredura Agora":** Força a checagem imediata de todas as câmeras a qualquer momento.
- **Histórico de Eventos:** Log ao vivo de quedas e restabelecimentos no rodapé da página.

---

## ⚙️ Arquivos do Projeto

* `cameras.json`: Lista de dispositivos com IP, porta RTSP (554) ou Intelbras (37777), NVR e canal.
* `config.py`: Ajuste de intervalo de checagem, timeout e tolerância a falhas.
* `checker.py`: Motor de verificação de portas TCP via sockets assíncronos.
* `tracker.py`: Mecanismo de estados e anti-flapping (evita falso-positivo).
* `notifier.py`: Despachante de notificações (imprime alertas e gera log `cftv_monitor.log`).
* `main.py`: Loop principal assíncrono de varredura.
