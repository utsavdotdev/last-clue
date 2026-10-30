<p align="center">
  <img src="assets/logo.svg" alt="The Last Clue logo" width="128" height="128">
</p>

<h1 align="center">The Last Clue</h1>

<p align="center">
  <em>A spooky multiplayer word-imposter game where everyone knows the word except the Imposter.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e11d38" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-00142f" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/board-Arduino%20UNO%20Q-0070f3" alt="Arduino UNO Q">
</p>

Host a room on an Arduino UNO Q (or a laptop), then play from phones and browsers on the same Wi-Fi network. Survivors share short clues about a secret horror word. One Imposter does not know the word and has to blend in.

## Features

- **LAN multiplayer** for 4–10 players in any modern browser. No accounts, cloud APIs, or internet connection during play.
- **Secret roles.** Survivors see the word privately. The Imposter sees only the category.
- **Horror word packs.** Fifty bundled words across Horror Creatures, Haunted Locations, Cursed Objects, Horror Films and Classic Tropes, and Supernatural Events.
- **Player-paced rounds.** After each clue pass, the table can start voting or play another clue round. There is no discussion or voting timer.
- **Secret voting** with a runoff if the top suspects tie. Catch the Imposter, or they escape.
- **Final guess.** A caught Imposter gets one chance to name the secret word.
- **UNO Q LED matrix.** Ten ghost expressions on the board's 8×13 matrix, driven over `Arduino_RouterBridge`. Off-board development uses a simulated matrix.
- **Optional local AI.** Arduino App Lab can serve `Qwen3.5-0.8B-Q4_0` for extra words and flavor text. If the model is slow, disabled, or missing, the game uses the bundled packs.

## How to play

1. **Join a room.** One player hosts. Everyone else scans the QR code or opens the join URL and picks a nickname.
2. **Draw cards.** Hold to peek: Survivors see the secret word; the Imposter sees only the category.
3. **Give clues.** Players take turns submitting one short clue. Hint at the word without handing it to the Imposter.
4. **Vote or continue.** After a full pass, start voting or run another clue round.
5. **Find the Imposter.** Vote secretly. A tie goes to a runoff. A second tie, or accusing a Survivor, lets the Imposter win.
6. **The last clue.** If the Imposter is caught, they guess the word. A correct guess (including a listed synonym) wins for the Imposter (+2). Otherwise Survivors who voted correctly score +1.

## Hardware and requirements

| Role | Requirement |
| --- | --- |
| Target board | Arduino UNO Q on the same Wi-Fi network as the players |
| Development machine | macOS or Linux, Python 3.11+, Node.js 18+ (needed to build the frontend) |
| Players | 4–10 phones or laptops with a current mobile or desktop browser |
| Optional AI | Arduino App Lab `arduino:llm` brick, model `llamacpp:Qwen3.5-0.8B-Q4_0` |

Guest Wi-Fi and some campus networks enable client isolation, which blocks phones from reaching the host. Use a normal home network or a hotspot that allows device-to-device traffic.

## Getting started

### Quick start

```bash
./scripts/dev.sh
```

This creates `.venv` if needed, installs Python dependencies, builds the frontend when `python/last_clue/static/` is missing, and starts the server on `http://0.0.0.0:8765`.

### Manual setup

```bash
python3 -m venv --copies .venv
source .venv/bin/activate
pip install -r python/requirements-dev.txt
./scripts/build.sh
python python/main.py
```

Open `http://localhost:8765` on the host machine. On another device, use the printed **LAN Join URL** (also shown as a QR code in the lobby), for example `http://192.168.1.50:8765/?room=XXXXXX`.

### Frontend hot reload

```bash
.venv/bin/python python/main.py
```

```bash
cd frontend && npm run dev
```

Vite runs at `http://localhost:5173` and proxies `/api` and `/ws` to port 8765.

### Environment variables

The process reads these environment variables ([`.env.example`](.env.example) is a template to export or source):

| Variable | Default | Purpose |
| --- | --- | --- |
| `LAST_CLUE_HOST` | `0.0.0.0` | Bind address |
| `LAST_CLUE_PORT` | `8765` | HTTP and WebSocket port |
| `LAST_CLUE_PUBLIC_HOST` | detected LAN IPv4 | Host shown in join URLs and QR codes |
| `LAST_CLUE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `LAST_CLUE_AI_ENABLED` | `true` | Allow local model calls |
| `LAST_CLUE_LLM_URL` | `http://llamacpp-models-runner:9999/v1/chat/completions` | App Lab llama-server endpoint |
| `LAST_CLUE_LLM_MODEL` | `Qwen3.5-0.8B-Q4_0` | Model name sent to that endpoint |
| `LAST_CLUE_LLM_TIMEOUT` | `90` | Seconds to wait for a local model response |

`HOST_IP` is accepted as an alias for `LAST_CLUE_PUBLIC_HOST`. If port 8765 is taken, set `LAST_CLUE_PORT` to another value.

## Arduino UNO Q setup

1. Put the UNO Q on the same Wi-Fi network as the player devices.
2. Open this repository in **Arduino App Lab**.
3. Confirm App Lab sees [`app.yaml`](app.yaml) (port `8765` and the `arduino:llm` brick), [`python/main.py`](python/main.py), and [`sketch/sketch.ino`](sketch/sketch.ino).
4. Click **Run**. App Lab flashes the STM32 sketch (`arduino:zephyr` with `Arduino_RouterBridge` 0.3.0), installs [`python/requirements.txt`](python/requirements.txt), and starts the FastAPI server on `0.0.0.0:8765`.
5. In the App Lab console, copy the **LAN Join URL**. The 8×13 matrix should show the boot ghost, then the lobby expression. The log line `8x13 LED Matrix: UNO Q Router Bridge Connected` means the MCU bridge is up; otherwise the game still runs with a simulated matrix.

The sketch in [`sketch/sketch.ino`](sketch/sketch.ino) renders ten non-blocking ghost states: Boot, Lobby, Roles Assigned, Clue Phase, Voting, Runoff, Imposter Discovered, Survivors Win, Imposter Wins, and Idle.

On-board AI is optional. The first request after boot can take a while while weights load. If generation times out or fails validation, the room keeps the bundled word packs and continues.

## Development

```text
last-clue/
├── app.yaml                 # App Lab manifest
├── assets/                  # Project logo and icon
├── sketch/                  # STM32 8×13 LED matrix firmware
├── python/                  # FastAPI server, game engine, static build output
├── frontend/                # Vite + React + TypeScript UI
├── tests/                   # Engine, WebSocket, AI, matrix, and QR tests
└── scripts/                 # dev.sh, build.sh
```

```bash
# Tests (from the repo root, with python/ on PYTHONPATH via pyproject.toml)
pytest

# Lint
ruff check python tests

# Production frontend bundle → python/last_clue/static/
./scripts/build.sh
```

Word packs live in [`python/last_clue/word_packs.py`](python/last_clue/word_packs.py). Final guesses match the secret word or its synonyms after normalizing case, punctuation, accents, and leading articles.

## Contributing

Issues and pull requests are welcome.

1. Fork the repository and create a branch from `main`.
2. Run `pytest` and `ruff check python tests` before you push.
3. Open a pull request that explains the change and how you tested it.

## License

[MIT](LICENSE) © 2026 Utsav Bhattarai.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), and [Pydantic](https://docs.pydantic.dev/) for the LAN server
- [React](https://react.dev/), [Vite](https://vite.dev/), [TypeScript](https://www.typescriptlang.org/), and [Phosphor Icons](https://phosphoricons.com/) for the client
- Arduino_LED_Matrix and Arduino_RouterBridge for the UNO Q 8×13 matrix
- Qwen3.5-0.8B via Arduino App Lab's `arduino:llm` brick, used only when local AI is enabled
