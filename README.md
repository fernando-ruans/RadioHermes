<div align="center">

<img src="assets/logo.png" alt="Rádio Hermes" width="120"/>

# Rádio Hermes

**Player de música desktop com locutor de IA** para Windows e Linux.

Adicione músicas do YouTube (vídeo, playlist ou busca com thumbnail) ou arquivos
locais, e o **locutor de IA** abre, comenta e encerra cada faixa com voz natural
em português — sempre coerente com a hora do dia.

`Python` `PySide6 (Qt6)` `FFmpeg` `yt-dlp` `LLM (BYOK)`

</div>

---

## Sumário

- [Primeira execução](#primeira-execução)
- [Recursos](#recursos)
- [Como funciona por dentro](#como-funciona-por-dentro)
- [Onde os arquivos ficam](#onde-os-arquivos-ficam)
- [O locutor de IA](#o-locutor-de-ia)
- [Provedores suportados](#provedores-suportados)
- [Configuração](#configuração)
- [Build](#build)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Correções](#correções)
- [Roadmap](#roadmap)
- [Licença](#licença)

---

## Primeira execução

O app roda **imediatamente após clonar** — o `config.example.toml` é usado por
padrão com `mode = "template"` (locução offline, sem chave de API, sem rede).
Para ativar a locução por IA:

```bash
# 1. copie o exemplo para o config real (uma vez só)
#    Windows:  copy config.example.toml config.toml
#    Linux:    cp config.example.toml config.toml

# 2. edite config.toml:
#    - mode = "api"
#    - preencha base_url, model e as chaves (ou aponte p/ Ollama/LM Studio)
```

Alternativa: abra o app e configure tudo pela janela **Configurações**
(seletor de provedores + botão "Buscar modelos" que lista os disponíveis).

> 🔒 **Segurança**: `config.toml` (com suas chaves) está no `.gitignore` e
> **nunca é commitado**. O versionado é só o `config.example.toml`, sem segredos.

---

## Recursos

### Player e fila
- **Fila com drag & drop** para reordenar, duplo-clique para tocar, clique
  direito para remover, e botões que **respeitam** o que você aperta.
- **Playlist do YouTube inteira** de uma vez (cola a URL e tudo entra na fila),
  com detecção inteligente: URLs com `&list=RD...&index=...` (recomendações do
  navegador) são tratadas como vídeo avulso, não como playlist.
- **Busca com cards**: resultados mostram **thumbnail real do YouTube**, título,
  duração e botão de adicionar — sem texto puro.
- **Arquivos locais**: arraste MP3/WAV/OGG/M4A/FLAC/Opus/AAC direto para a fila.
- **Status coloridos** na fila: `▶` pronto (verde), `⏳` preparando (âmbar),
  `✕` erro (vermelho), com duração exibida.

### Player moderno
- **Tema escuro** profissional (roxo/ciano), aplicado globalmente via stylesheet.
- **Visualizador de ondas sonoras animadas** que reage ao playback (congela ao
  pausar).
- **Logo própria** no player e como **ícone da janela/taskbar** (use a sua em
  `assets/logo.png`; sem ela, uma nota musical estilizada).
- Controles grandes (play circular), slider de progresso estilizado, volume e
  **troca de voz pt-BR** em um clique (`Voz: ♀/♂`).

### Locução de IA
- **Abertura**: sempre, antes da música começar.
- **Encerramento**: sempre, depois da música.
- **No meio** (às vezes, configurável): o volume da música **baixa** e o locutor
  fala por cima, sem interromper (ducking pré-processado).
- **Contexto temporal real**: a IA sabe a hora e o período do dia e **nunca
  contradiz o horário** (nada de "boa madrugada" às 14h).
- **Imprevisível e natural**: a cada fala ela sorteia o comportamento — às vezes
  foca na música, às vezes marca a hora, às vezes fala com o ouvinte ou comenta
  o clima.
- **Duração máxima** configurável por tipo de locução (abertura/encerramento/meio).

### Experiência
- **Nativo e leve**: interface Qt6 de verdade — sem Electron, sem WebView.
- **Preparação em background**: várias faixas da fila são preparadas em paralelo
  enquanto a atual toca — a interface nunca congela.
- **Cache inteligente**: a mesma música não é preparada de novo — pular/voltar
  é instantâneo.
- **Subprocessos invisíveis**: ffmpeg/yt-dlp rodam com `CREATE_NO_WINDOW` no
  Windows — nenhum terminal pipoca na tela.

---

## Como funciona por dentro

```
┌────────────────────────────────────────────────────────────┐
│              Rádio Hermes (PySide6/Qt6)                    │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────┐  │
│  │  SearchPanel │   │  Playlist    │   │   PlayerBar   │  │
│  │ (busca+cards)│   │  (fila d&d)  │   │ (ondas+logo)  │  │
│  └──────┬───────┘   └──────┬───────┘   └──────┬────────┘  │
│         │                  │                  │           │
│  ┌──────▼──────────────────▼──────────────────▼─────────┐ │
│  │                       Engine                          │ │
│  │  fila + QMediaPlayer + preparo em background + cache  │ │
│  └──────┬──────────────────┬──────────────────┬──────────┘ │
│         │                  │                  │           │
│  ┌──────▼──────┐   ┌───────▼────────┐  ┌──────▼────────┐  │
│  │  fetcher    │   │   prepare      │  │  workers      │  │
│  │ (yt-dlp)    │   │ (locução+ffmpeg)│ │  (QThread)    │  │
│  └──────┬──────┘   └───────┬────────┘  └──────┬────────┘  │
│         │                  │                  │           │
│  ┌──────▼──────┐   ┌───────▼────────┐         │           │
│  │   brain     │   │  mixer (ffmpeg)│         │           │
│  │  (LLM BYOK) │   │ normalize/duck │         │           │
│  │   + tts     │   │ concat_segments│         │           │
│  └─────────────┘   └────────────────┘         │           │
└────────────────────────────────────────────────────────────┘
```

| Camada | Tecnologia |
|--------|-----------|
| Interface | PySide6 (Qt6) com tema escuro próprio (QSS) |
| Áudio | FFmpeg via subprocess (normalizar, ducking, concat) |
| YouTube | yt-dlp (busca, vídeos, playlists, thumbnails) |
| Locutor | LLM em qualquer endpoint OpenAI-compatível + edge-tts |
| Concorrência | QThread para download/preparação/locução |

Fluxo de uma faixa: o usuário adiciona → `fetcher` baixa (se YouTube) → `brain`
gera a locução (LLM) → `tts` transforma em voz → `mixer` monta o MP3 final
(intro + música [+ ducking no meio] + outro) → `engine` toca via QMediaPlayer.
Tudo isso roda em background enquanto a música atual toca.

---

## Onde os arquivos ficam

| Tipo | Local padrão |
|------|--------------|
| Config (real, com chaves) | `config.toml` (na pasta do app — **não versionado**) |
| Config de exemplo | `config.example.toml` (versionado, sem segredos) |
| Downloads | `cache/` (áudios baixados do YouTube) |
| Faixas montadas | `cache/prep/` (MP3 final com locução) |
| Logo | `assets/logo.png` (exibida no player e no ícone) |

> 💡 Config e cache ficam **sempre na pasta do app**, mesmo se o executável for
> aberto de outro diretório.

---

## O locutor de IA

O locutor usa **qualquer LLM** (sua chave ou um servidor local) para gerar o
texto das locuções e o **edge-tts** (gratuito, sem chave) para converter em voz
natural pt-BR. Dois modos:

- `mode = "api"` — gera as locuções via LLM (nuvem ou local).
- `mode = "template"` — offline, usa frases locais prontas (roda sem rede).

O contexto enviado ao LLM a cada locução inclui: tipo (abertura/meio/encerramento),
música atual, próxima música, **horário real**, período do dia, dia da semana e a
**duração máxima** da fala. A resposta é limpa automaticamente (sem markdown,
limitada a 1-2 frases) antes de virar áudio.

### Provedores suportados

O `brain` aceita **qualquer endpoint OpenAI-compatível** (BYOK). Basta apontar
`base_url` + `model` nas configurações:

| Provedor | base_url | modelo exemplo |
|---|---|---|
| Gemini API | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.1-flash-lite` |
| Ollama (local) | `http://localhost:11434/v1` | `gemma3:1b`, `llama3.2:1b` |
| LM Studio (local) | `http://localhost:1234/v1` | `google/gemma-3-1b-it` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant` |
| vLLM / llama.cpp (local) | `http://localhost:8000/v1` | qualquer |

A janela de **Configurações** tem um seletor de provedores com presets e um
botão **"Buscar modelos"** que consulta `GET {base_url}/models` do servidor e
lista os modelos disponíveis (funciona com Ollama, LM Studio, vLLM, etc.).

---

## Configuração

O arquivo `config.toml` (na pasta do app) centraliza tudo:

- `[brain]` / `[brain.api]` — modo, persona, temperatura, `base_url`, `model`,
  `fallback_model`, **chaves (1 ou várias, com rotação e cooldown)**, timeouts.
- `[voice]` — voz do edge-tts (`pt-BR-FranciscaNeural` / `pt-BR-AntonioNeural`),
  taxa, volume.
- `[locucao]` — liga/desliga abertura/encerramento/meio, chance de locução no
  meio, duração mínima da música, **duração máxima por tipo**, duck gain.
- `[player]` — auto-advance, loop, quantas faixas preparar com antecedência,
  volume inicial.
- `[cache]` — onde baixar e limites de duração/timeout do yt-dlp.

> 💡 Tudo isso também é ajustável pela janela **Configurações** do app, que salva
> direto no `config.toml`.

---

## Build

### Pré-requisitos

| Requisito | Windows | Linux (Ubuntu/Debian) |
|-----------|---------|------------------------|
| Python    | 3.11+ com "Add to PATH" | `sudo apt install python3 python3-venv python3-pip` |
| FFmpeg    | baixar do [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) e adicionar o `bin` ao PATH | `sudo apt install ffmpeg` |

Verifique antes de prosseguir:

```bash
python --version
ffmpeg -version
yt-dlp --version
```

### Rodar em desenvolvimento

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Release — Windows (PyInstaller)

```bat
pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name RadioHermes ^
  --paths "." ^
  --hidden-import "src.gui" --hidden-import "src.engine" ^
  --collect-submodules "edge_tts" ^
  --add-data "config.toml;." ^
  --add-data "assets;assets" ^
  --icon "assets\logo.png" ^
  main.py
```

Resultado: `dist\RadioHermes\RadioHermes.exe`.

### Instalação na máquina de destino

O executável empacota Python e Qt6, mas **depende do FFmpeg e do yt-dlp no PATH**:

- **Windows**: instale o FFmpeg (gyan.dev) e o yt-dlp, adicione ao PATH.
- **Linux**: `sudo apt install ffmpeg` e `pip install yt-dlp`.

> 💡 O app verifica FFmpeg/yt-dlp ao rodar; sem eles, downloads e mixagem não
> funcionam (a interface abre normalmente).

### Ícone e logo

Coloque sua logo em `assets/logo.png` — ela aparece no player e como ícone da
janela/taskbar (e é usada no ícone do `.exe` no build).

---

## Estrutura do projeto

```
.
├── main.py                  # entry point (aplica tema + ícone, abre a janela)
├── config.toml              # configuração real (chaves) — NÃO versionado
├── config.example.toml      # template sem segredos (versionado)
├── requirements.txt         # dependências Python
├── src/
│   ├── engine.py            # fila + QMediaPlayer + preparo em background + cache
│   ├── brain.py             # LLM (BYOK): qualquer endpoint OpenAI-compatível
│   ├── tts.py               # edge-tts (voz natural pt-BR)
│   ├── fetcher.py           # yt-dlp: busca, vídeos, playlists, thumbnails
│   ├── prepare.py           # monta cada faixa (locução + ducking + concat)
│   ├── mixer.py             # FFmpeg: normalizar, cortar, ducking, concatenar
│   ├── probe.py             # ffprobe (duração)
│   ├── proc.py              # subprocessos sem janela de console (Windows)
│   ├── config.py            # carregador TOML
│   ├── workers.py           # QThreads: preparação, busca, playlist, info
│   └── gui/
│       ├── main_window.py   # janela principal (junta tudo)
│       ├── player_bar.py    # logo, agora tocando, ondas, controles, volume
│       ├── visualizer.py    # visualizador de ondas sonoras animadas
│       ├── playlist.py      # fila com status coloridos e drag & drop
│       ├── search.py        # busca com cards de thumbnail
│       ├── settings.py      # configurações (provedores + descoberta de modelos)
│       └── styles.py        # tema escuro (QSS + palette)
├── assets/
│   └── logo.png             # logo do app (player + ícone)
├── cache/                   # downloads e faixas montadas (criado ao rodar)
└── dist/RadioHermes/        # build PyInstaller (gerado)
```

---

## Testes

O projeto não tem suíte automatizada ainda (funcionalidades validadas por testes
manuais de integração). O plano é cobrir com `pytest`:

- Mixagem FFmpeg (normalizar, corte, ducking, concatenação)
- Detecção de URL (vídeo vs. playlist, limpeza de `&list=RD`)
- Brain: prompt por comportamento, coerência temporal, limpeza de resposta
- Engine: fila, cache, prefetch, play/pause/next/prev
- GUI offscreen: janela, cards, visualizador, settings

---

## Correções

### [2026-08-11] Música errada ao adicionar por busca ou URL
- **Sintoma:** o locutor anunciava o nome certo, mas o áudio que tocava era de
  outra música (geralmente a primeira adicionada na sessão).
- **Causa:** faixas adicionadas por busca ficavam sem o `vid` (o ID só era
  extraído da URL quando o título ainda não existia). Sem `vid`, todas baixavam
  para o mesmo arquivo `cache/None.mp3` — a 1ª música era baixada ali e as
  seguintes **reaproveitavam esse arquivo** no lugar do áudio real.
- **Correção:** o `vid` agora é sempre extraído da URL na adição; e o preparador
  usa uma chave estável como fallback no nome do download, nunca mais o literal
  `None.mp3`.

---

## Roadmap

- **Fase 6** — Suíte de testes `pytest`, verificação de FFmpeg/yt-dlp na abertura
- **Fase 7** — Lista de reprodução persistente (salvar/carregar fila), arrastar
  URL do YouTube direto da web para a janela
- **Fase 8** — CI/CD multi-plataforma, assinatura do executável Windows, build
  Linux em 1 clique, versão portable

---

## Licença

Distribuído sob a licença **MIT** — use, modifique e distribua à vontade.

---

<div align="center">

Feito com 🐍, 🎙️ e FFmpeg.

</div>
