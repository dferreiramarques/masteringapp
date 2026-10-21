# MasteringApp

Webapp local que analisa uma mistura stereo e aplica uma cadeia de masterização
estilo **rock vintage**, com ajuste fino (fine-tuning) em quasi-tempo-real:

1. análise: LUFS-I, true peak (4× oversampled), LRA, correlação estéreo, espectro 1/3 oitava
2. comparação com **curva-alvo do género** e sugestões de balanço
3. cadeia: HPF → EQ corretivo → saturação de fita → compressor lento → shelves → **ambiência** (reverb de mix de rescate, default 0%, teto 20%) → low-end mono (M/S) → **Maximizer estilo Waves L2** (push + ceiling + Maxximizer/IDR de uma passada), limiter de ganho com margem de TP por true peak
4. **fine-tuning**: 19 parâmetros editáveis (incl. Out Ceiling / Push / Maxximizer IDR / Largura de imagem / Reverb de mix) + re-masterização sem novo upload
   - **pré-escuta rápida (20 s)** na parte mais energética da música (render em ~2 s)
   - modo **live**: re-aplica automaticamente ao soltar um slider
5. **A/B com volume equalizado** + espectro antes/depois
6. export 24-bit WAV

## Géneros

indie · post-punk · krautrock/vintage · pop · electrónica · acústico · experimental/ambiental · noise/drone

## Fase 2 — decisão automática (1 + 2 + 3)

- **Biologia do ouvido:** índices de excesso por zona (boomy <125 Hz, boxy 200–500 Hz,
  harsh 2–5 kHz, sibilância 5–10 kHz) e cortes ergonómicos escalados pelo slider
  `Mitigação biológica` (0–100%)
- **Interpretação técnica:** rótulos automáticos no diagnóstico (boomy/boxy/harsh/sibilância)
- **Dinâmica:** decisão LRA → *soltar compressão* (LRA < 3.5) vs *densidade* (LRA > 8.5)
- Botão **Ajustar à minha mistura (auto)** no passo 2: mede a mistura (excessos
  biológicos + LRA) e ajusta os sliders **sobre o perfil em uso** (respeita
  afinções manuais e nunca reduz a mitigação biológica; mostra o diff das
  mudanças). **Repor perfil** volta ao perfil puro do género — recalcula a
  decisão sem re-upload (endpoint `/auto`; `/profile/{g}` para repor)

## Harmónicos e LED de clipping

- **Exciter harmónico** (default desligado): gera réplicas de 2.ª/3.ª harmónica
  (banda 2.8–8.5 kHz, só os produtos, nunca o sinal saturado) — brilho por
  "harmonização de frequências", não estilístico
- **LED verde/amarelo/vermelho** no passo 3: percentagem de amostras que tocam
  o topo do limiter (<0.05% verde · <1% amarelo · ≥1% vermelho)
- Limitador com ataque suavizado (sem saltos de ganho por-amostra = sem "zipper")

## Export por plataforma (metas de streaming)

Passo 5: render completo com a cadeia criativa atual, normalizado ao spec de cada
serviço. Specs idênticas agrupam-se num ficheiro único:

- **−14 LUFS** → Spotify · YouTube · Amazon · Tidal (1 só master; hover mostra o grupo)
- **−15 LUFS** → Deezer
- **−16 LUFS** → Apple Music

TP ≤ −1 dBTP para todos; push desativado no export. Devolve WAV 24-bit +
verificação de conformidade (`spec_ok`). Descargas com o nome do ficheiro de entrada +
sufixo: `Song_master.wav`, `Song_master_-14LUFS.wav`, `Song_original.wav`, etc.
Repetir um export já renderizado
(mesmo uid + perfil + alvo) sai **em cache** — instantâneo, e re-cliques não duplicam a linha.

## Como correr

```
mastering-app\run.bat
```

Abre `http://localhost:7860` automaticamente.

## Product page

`/product` — página do produto (estilo kerf.monco.io, primary amarelo torrado
`#d9a92c` = cor do chip MANUAL): herói, features, modos manual/auto, cadeia de
9 estágios e downloads. Sirve `static/product.html`. Os CTAs de download usam
`/get-setup` e `/get-portable`, que servem os binários de `dist/`
(`MasteringApp-Setup-1.0.0.exe`, `MasteringApp-portable.zip`) quando existem —
procura primeiro ao lado do exe (empacotado), depois `<projeto>/dist/` (dev);
sem binário, o botão passa a «Indisponível nesta instalação». Chip «PRODUTO» no
cabeçalho da app liga à página.

## Executável local (PyInstaller)

`dist/MasteringApp/` é o app completo como **.exe standalone** (pasta com
`MasteringApp.exe` + `_internal/`, ~141 MB; zip portátil de ~72 MB em
`dist/MasteringApp-portable.zip`). Duplo clique (ou o atalho `MasteringApp`
no Desktop) e o app corre numa **janela nativa própria** — sem browser, sem
tabs, sem consola: a UI abre dentro da janela do app (pywebview +
WebView2/Edge, que o Windows 10/11 já traz). O backend FastAPI corre no
porto 7860 (sobe para 7861/7862/… se ocupado), invisível ao utilizador.
Fechar a janela = fechar o app (o servidor encerra com ele).

- **sem consola e sem browser** — entrada pelo `desktop.py`
  (`--windowed` + `--collect-all webview/pythonnet/clr_loader`)
- fallback honesto: sem WebView2 na máquina, abre a **janela de status +
  browser** (modo antigo) em vez de falhar
- ícone próprio (knob dourado + LED de clipping, `static/app_icon.ico`,
  gerado por `make_icon.py`) e metadados de versão (`version.txt` →
  Propriedades do .exe: ProductName/FileVersion/CompanyName)
- `uploads/` fica **ao lado do .exe**: misturas e cache de exports persistem entre runs
- o 1.º arranque pode demorar ~15 s (antivírus a escanear os ficheiros novos);
  os seguintes são ~2–5 s
- o Windows SmartScreen pode avisar («Mais informações → Executar assim mesmo»)
- rebuild: `.venv\Scripts\pyinstaller.exe --noconfirm --name MasteringApp
  --onedir --windowed --icon "static\app_icon.ico" --version-file "version.txt"
  --collect-all pedalboard --collect-all webview --collect-all pythonnet
  --collect-all clr_loader --hidden-import multipart
  --hidden-import webview.platforms.winforms --add-data "static;static"
  desktop.py` (spec gerada: `MasteringApp.spec`)
- validado E2E contra o .exe com janela nativa (`test_exe.py`): process →
  remaster → export −14 LUFS → download com nome correto e WAV RIFF válido

### Instalador Windows

`dist/MasteringApp-Setup-1.0.0.exe` (45 MB) — instalador **por-utilizador**
(sem UAC, instala em `{localappdata}\Programs\MasteringApp`):

- wizard em português («Inno Setup» + `Languages\Portuguese.isl`)
- cria atalho no Desktop (opção no wizard,_checked por defeito) e no menu Iniciar
- **desinstalador** em Definições → Aplicações; os `uploads/` do utilizador
  **não são apagados** na desinstalação (são dados do utilizador)
- script: `installer.iss` — rebuild: `ISCC.exe installer.iss` (Inno Setup 6,
  instalado em `%LOCALAPPDATA%\Programs\Inno Setup 6\`)
- verificação E2E do instalador feita: instalar silencioso → correr o app
  instalado (server 200 + fix do toast no HTML servido) → desinstalar
  silencioso → pasta limpa

## Deploy no Railway

O projeto inclui `Dockerfile`, `requirements.txt` (pinadas às versões testadas) e
`railway.json` (build Dockerfile + healthcheck `/genres`). Passos:

1. Põe o diretório `mastering-app/` num repositório GitHub
   (o `.dockerignore` exclui venv, uploads, wavs e testes do build).
2. [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
   → escolhe o repo. O Railway deteta o `Dockerfile` e injeta a variável `PORT`.
3. No serviço: **Settings → Networking → Generate Domain** (TCP proxy → `$PORT`).
4. Lê o log do build; o healthcheck `/genres` deve passar a verde.
5. Recomendado: **Settings → Resources ≈ 2 GB de RAM** (renders de músicas
   completas fazem pico de memória; o limiter + FFT de ambiência trabalham
   sobre o sinal float64 completo).

Validação em ambiente limpo feita localmente: venv de raiz com
`requirements.txt` + `HOST/PORT` via `python app.py` → servidor a servir
`0.0.0.0` (o que o container faz).

**Limitações honestas de cloud:**

- `uploads/` e `JOBS` são efémeros — um redeploy/restart limpa misturas e
  cache de exports (re-upload volta a renderizar; nada se perde além de tempo)
- 1 instância (o estado é em RAM): não escalar réplicas
- o URL é público e **sem autenticação** — quem o tiver usa; para partilhar,
  convém adicionar um token simples
- ficheiros de input muito grandes fazem uploads lentos/esbarram no limite do proxy (limite prático ~100 MB)

## Requisito

Python 3.12 (instalado em `%LOCALAPPDATA%\Programs\Python\Python312`) —
dependências em `requirements.txt` já instaladas no `.venv` do projeto.

## Ficheiros

- `app.py` — backend FastAPI (análise + render DSP com pedalboard/scipy/pyloudnorm)
- `desktop.py` — lançador desktop do .exe (janela nativa pywebview; fallback para janela de status + browser)
- `make_icon.py` / `version.txt` — ícone e metadados do executável
- `static/index.html` — UI (botão «?» no topo abre a documentação)
- `static/help.html` — documentação F1: fluxo, cadeia com diagrama, 19 controlos, métricas, arquitetura, API e glossário
- `uploads/` — ficheiros processados (podes apagar)
- `test_thd.py` — teste de distorção (senoide pela cadeia)
- `test_tape.py` — teste A/B do efeito do tape drive no master (waveform + crest, não FFT)
- `test_api.py` / `test_export.py` / `test_f2_api.py` — testes E2E (correm contra o servidor em localhost:7860)
- `test_exe.py` — E2E mínimo contra qualquer instância (`MASTERING_BASE`, usado p/ validar o .exe)
- `test_l2.py` / `test_tpfix.py` — regressões do maximizer/limiter
  (o `peak_limit` opera no envelope 4× oversampled — picos intersample reais)

