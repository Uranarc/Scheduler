# Serviço de notificações WhatsApp — via GitHub Actions (grátis, sem VM)

Corre 1x/dia nos servidores do GitHub, não precisa do teu PC nem de nenhuma VM.
Trade-off aceite: confirmações só são lidas na próxima execução agendada, não em
tempo real.

## ⚠️ Importante: o repositório TEM de ficar privado
Vai guardar números de telefone e a sessão do WhatsApp. GitHub → Settings →
General → em baixo, "Change visibility" → **Private**.

## 1. Login inicial no WhatsApp (uma vez, no teu PC)

```bash
cd notify_service
npm install
cp config.example.json config.json
node index.js --groups
```

Aparece um QR code no terminal → WhatsApp no telemóvel → Dispositivos ligados →
Ligar dispositivo → aponta a câmara. Depois de ligar, o comando lista os grupos:

```
1203630...@g.us    Nome do teu grupo
```

Copia o `id` certo para `config.json`, campo `"groupId"`.

## 2. Guardar o config.json como secret do GitHub

No repositório → Settings → Secrets and variables → Actions → **New repository secret**:
- Nome: `NOTIFY_CONFIG_JSON`
- Valor: o conteúdo completo do teu `config.json` (com o `groupId` já preenchido)

## 3. Subir a sessão do WhatsApp para o repositório (uma vez)

```bash
cd ..   # raiz do repo
git add -f notify_service/auth_state notify_service/notify.db
git commit -m "Sessão inicial do serviço de notificações"
git push
```

## 4. Ativar o workflow

Já está em `.github/workflows/notify.yml`, corre todos os dias às 9h (UTC) — ajusta
a linha `cron:` se quiseres outra hora. Também podes correr manualmente:
GitHub → Actions → "Notificações WhatsApp" → **Run workflow**.

## Como funciona

- Antes de cada envio, a app desktop tem de clicar em **🔄 Sincronizar** — isso
  escreve `schedule_data.json` na raiz do repo e faz `git push`.
- O workflow lê esse ficheiro, liga-se ao WhatsApp (sessão já guardada, sem QR),
  envia lembretes (grupo + DM) para eventos a `reminderDaysBefore` dias de distância,
  fica ~25s a ouvir respostas ("CONFIRMO"/"NÃO CONSIGO"), regista tudo em
  `notify.db`, e faz commit de volta do estado atualizado.
- Editar quantos dias de antecedência: `reminderDaysBefore` no `config.json`
  (e atualizar o secret `NOTIFY_CONFIG_JSON` também).
