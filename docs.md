# Build “The Last Clue” — A Spooky Multiplayer Imposter Game for Arduino UNO Q

## Your role

Act as a senior full-stack engineer, multiplayer game developer, UI/UX designer, and Arduino UNO Q developer. Build a complete, polished, working game called **The Last Clue**.

Do not merely create a plan, mockup, or tutorial. Inspect the current project and implement the actual application, including its frontend, multiplayer server, game engine, local AI integration, Arduino UNO Q LED matrix integration, tests, and documentation.

Make sensible implementation decisions without asking me unnecessary questions. Prioritize a reliable, playable MVP with excellent presentation over unnecessary features.

## 1. Project overview

The Last Clue is a horror-themed multiplayer social-deduction word game inspired by the Imposter and Undercover party games.

Players join a game hosted by an Arduino UNO Q through a browser on their phones or laptops. All players except one receive the same secret horror-themed word. One player, the Imposter, does not know the secret word and must pretend to know it.

Players take turns submitting short clues, discuss who they suspect, and vote to identify the Imposter. If the group catches the Imposter, the Imposter gets one final opportunity to guess the secret word.

The Arduino UNO Q acts as the physical game master: it hosts the game server, runs a small compatible open-weight AI model locally, and uses its built-in 8×13 LED matrix to display a spooky ghost character whose expressions change during gameplay.

**Core project statement:**

“An offline-capable, LAN multiplayer horror word game where your Arduino UNO Q becomes a haunted game master, uses local AI to create spooky rounds, and physically reacts to every game.”

## 2. Non-negotiable requirements

- The application must be a real, playable multiplayer game—not a static demo.
- The Arduino UNO Q must have a meaningful role in hosting and controlling the game.
- Players must be able to join using their own phones or computers on the same local network.
- No additional sensors, electronics, or displays may be required.
- Use the built-in LED matrix for physical game feedback.
- Integrate an actual open-weight AI model running locally on the UNO Q for optional horror-themed content generation.
- Do not send player data, secret words, or game content to an external AI API.
- The core game must still work if local AI inference is unavailable, using bundled word packs.
- Do not expose the secret word or player roles to unauthorized clients.
- The application must run without a cloud account, paid service, or external backend.
- The UI must work well on small mobile screens.
- All critical game rules, scoring, timing, and role assignments must be deterministic and controlled by the server.
- The code must be maintainable, documented, tested, and ready to demonstrate at a hackathon.

## 3. Target hardware and constraints

Primary device: Arduino UNO Q.

Available hardware:
- The UNO Q's Linux-based computing environment.
- Built-in Wi-Fi connectivity.
- Built-in 8×13 LED matrix.
- The board's supported microcontroller and hardware integration APIs.
- Players' existing phones or laptops.

Development computer: macOS.

Network requirements:
- The UNO Q hosts the game server on the local network.
- Players connect to the same Wi-Fi network.
- The server binds to `0.0.0.0`, not only `127.0.0.1`.
- Display the local game URL, network connection status, and a join QR code.
- Do not require an internet connection during normal gameplay once dependencies and the local AI model have been installed.
- Support development on macOS using a simulated LED matrix, while using the real hardware adapter on the UNO Q.

Before implementing hardware-specific code, inspect the UNO Q's actual software environment, official documentation, available libraries, processor architecture, and supported AI runtimes. Never invent hardware APIs or assume that a library designed for a different Arduino board will work.

## 4. Game rules

### Players and roles

Support 4–10 players.

For the first version:
- Assign exactly one Imposter per round.
- All remaining players are Survivors.
- Randomly choose the Imposter using server-side randomness.
- Select one secret word and its horror category for every round.
- All Survivors privately receive the same word.
- The Imposter privately receives the category but not the secret word.
- Do not let players choose their own roles.
- A player must never be able to inspect another player's private role or secret word by manipulating browser requests.

Example round:

Category: Horror Creature

Secret word: Vampire

Survivors receive:
“Your secret word is VAMPIRE.”

The Imposter receives:
“You are the IMPOSTER. The category is HORROR CREATURE. Blend in, discover the secret word, and avoid detection.”

The browser must receive only the private information authorized for that specific player.

### Phase 1 — Lobby

Create a polished lobby where players can:
- Enter a nickname.
- Join the current room.
- See other players' nicknames and connection status.
- See the number of connected players.
- View the room code.
- See whether the host is ready to start.
- Leave the room.
- Reconnect after an accidental network disconnection.

The game starts only when at least four players have joined.

Provide a host control for starting the game. The host is the person operating the board's host interface or local admin screen. Ordinary players must not be able to force-start a game or modify server settings.

Prevent duplicate nicknames within the same room, normalize user input, and enforce sensible nickname length limits.

### Phase 2 — Secret role reveal

When a round starts:
1. Lock the current roster.
2. Randomly assign the secret roles.
3. Choose a secret word and category.
4. Show each player a private role card.
5. Allow players to reveal their role on their own device without showing it to other players.
6. Keep the secret word private after the reveal phase.

Use suspenseful animations, but allow the player to skip them.

The Imposter must not receive the secret word through hidden frontend state, a shared game-state response, a WebSocket broadcast, or any other client-accessible payload.

### Phase 3 — Clue round

Every player contributes one short clue intended to demonstrate that they know the secret word.

Requirements:
- Randomize the speaking order each round.
- Display the current player's turn clearly.
- Allow players to submit a short clue using their phone.
- Set a reasonable maximum clue length, such as 40 characters.
- Once submitted, reveal that clue to all players.
- Prevent edits after submission.
- Mark which players have submitted.
- Do not reveal roles.
- Allow the game to continue if a player disconnects, using a sensible host-controlled skip or timeout rule.

Use suspenseful language such as “The spirits are listening” and “One of you does not know the word.”

The default gameplay should be simple enough for people who have never played before.

### Phase 4 — Discussion

After everyone has submitted a clue, begin a configurable discussion timer, defaulting to 60 seconds.

Show:
- All submitted clues.
- Their corresponding player nicknames.
- The remaining discussion time.
- A clear transition to voting.

Do not automatically decide who the Imposter is based on AI analysis. Human players must make the deduction and vote.

### Phase 5 — Secret voting

Each connected player may cast exactly one vote for another player.

Requirements:
- Players cannot vote for themselves.
- Players cannot vote multiple times.
- Votes must remain secret until voting ends.
- Do not expose individual votes to other clients or to the public game feed.
- Show voting progress without revealing vote choices.
- Use a configurable voting timer.
- Do not count disconnected players as having voted unless the server has already received their valid vote.

When voting closes, tally the votes on the server.

If one player receives the most votes, that player is accused.

If multiple players tie for the highest number of votes:
- Start one runoff vote between the tied candidates.
- Keep the runoff private.
- If the runoff is still tied, no one is caught and the Imposter escapes.

Clearly explain these rules in the game instructions.

### Phase 6 — Final guess and reveal

If the accused player is the Imposter:
1. Show a suspenseful accusation animation.
2. Tell the accused player that they have been discovered.
3. Give them one final guess at the secret word.
4. Accept one guess only.
5. Compare the normalized guess against the secret word.
6. If correct, the Imposter wins.
7. If incorrect, the Survivors win.

If the accused player is not the Imposter, the Imposter escapes and wins the round.

At the end of the round, reveal:
- The secret word.
- Its category.
- The Imposter's identity.
- Every player's clue.
- The voting outcome.
- Whether the Imposter guessed correctly.
- The winner.

Trigger a distinct LED matrix animation for the outcome.

### Phase 7 — Replay and scoring

Allow players to:
- Start another round with the same group.
- Return to the lobby.
- See cumulative player scores.
- Reset scores from the host controls.
- Leave without breaking the remaining players' game session.

Use a simple scoring system:
- Each Survivor who votes correctly for the Imposter earns one point when the Survivors win.
- The Imposter earns two points when the Imposter wins.
- Show cumulative scores on the results screen.

Keep the scoring rules visible in the instructions.

## 5. Horror-themed word packs

Bundle enough word content that the game remains playable without AI. Provide at least five categories and at least 10 secret words per category.

Include categories such as:

**Horror creatures**
- Vampire
- Werewolf
- Zombie
- Ghost
- Witch
- Demon
- Mummy
- Phantom
- Banshee
- Skeleton

**Haunted locations**
- Graveyard
- Abandoned hospital
- Haunted mansion
- Creepy basement
- Abandoned school
- Dark forest
- Haunted hotel
- Underground tunnel
- Abandoned asylum
- Old church

**Cursed objects**
- Ouija board
- Cursed doll
- Haunted mirror
- Bloody knife
- Ancient spellbook
- Crystal ball
- Haunted portrait
- Cursed necklace
- Mysterious key
- Vintage videotape

**Horror films and classic tropes**
- Jump scare
- Final survivor
- Haunted recording
- Cursed videotape
- Masked killer
- Forbidden room
- Creepy nursery
- Secret passage
- Strange knocking
- Flickering lights

**Supernatural events**
- Possession
- Poltergeist
- Exorcism
- Premonition
- Apparition
- Curse
- Séance
- Telekinesis
- Paranormal investigation
- Unexplained disappearance

Avoid ambiguous, duplicated, excessively obscure, or overly similar words that create unfair rounds.

Store the word packs in structured local data. Each entry should include its word, category, difficulty, and optional synonyms accepted during the final guess.

Allow the host to choose a theme or let the system choose a random category.

## 6. Local AI — The Haunted Game Master

The AI must be genuinely local and use an open-weight model running on the UNO Q. Do not pretend that fixed random strings are AI-generated content.

Before implementing the AI:
1. Inspect the device architecture, memory, installed packages, and supported local inference runtimes.
2. Select a genuinely compatible, appropriately licensed open-weight model that fits the available hardware.
3. Prefer a small quantized model when necessary.
4. Use the most practical supported runtime, such as a compatible local inference runner or `llama.cpp` if the board and model support it.
5. Document the chosen model, source, license, runtime, installation procedure, and hardware requirements.
6. Do not claim hardware acceleration unless it has been verified.
7. Never use a cloud model as a fallback.

Use the model for tasks that add personality without controlling the critical game logic.

### AI capability A — Horror round introduction

Generate a short atmospheric introduction for a new round.

Example:
“The hospital has been silent for 30 years. Tonight, someone heard a heartbeat behind the locked operating-room door.”

The introduction must not reveal the secret word.

### AI capability B — Additional word packs

Optionally generate a set of candidate words and categories using structured JSON output.

Validate every generated result before making it available:
- All required fields must exist.
- Categories must be appropriate.
- Words must be unambiguous and playable.
- Entries must not contain duplicates.
- The introduction must not reveal the secret word.
- The content must not contain instructions that modify game rules or server state.

Do not let a model-generated word enter an active round unless validation succeeds. Keep the bundled word packs as the reliable fallback.

### AI capability C — Haunted narration

Generate short, spooky announcements at appropriate points in the game:
- Starting a ritual.
- Finishing the clue round.
- Starting the vote.
- Revealing the Imposter.
- Announcing the result.

Limit response length to avoid long waits.

### AI architecture requirements

- Keep AI calls on the UNO Q.
- Never expose the model to unnecessary player data.
- Never send secret roles or active secret words to player clients.
- Never let generated content alter votes, roles, scores, timers, or other critical game state.
- Cache generated content where useful.
- Generate round flavor text before the relevant phase whenever possible.
- Apply inference timeouts and graceful fallback behavior.
- Expose a status indicator showing whether local AI is ready, generating, or using fallback content.
- Include an explicit “AI unavailable — using built-in content” state rather than silently pretending that inference succeeded.

The AI should improve the atmosphere without making the game slower or less fair.

## 7. Arduino UNO Q LED matrix

The built-in LED matrix is a key part of the experience.

Create a hardware abstraction with a real UNO Q implementation and a simulation implementation for development on macOS.

First inspect official UNO Q examples and the installed environment to identify the correct API. Do not invent method names or assume a different board's LED matrix library works.

Implement recognizable patterns for:

- **Boot:** a ghost appearing.
- **Lobby:** a calm, floating ghost.
- **Roles assigned:** a short suspense animation.
- **Clue phase:** a curious ghost.
- **Voting phase:** flashing suspicious eyes.
- **Runoff:** a rapidly blinking ghost.
- **Imposter discovered:** an angry ghost.
- **Survivors win:** a defeated ghost.
- **Imposter wins:** an evil, victorious ghost.
- **Idle:** a subtle looping animation.

Use appropriate pixel-art sprites and animations designed for the matrix's actual dimensions and orientation. Confirm orientation against the hardware documentation.

The matrix must update in response to actual server events, not run an unrelated decorative animation.

Keep hardware communication reliable. Avoid blocking the game server while a frame is being drawn. Add sensible error handling and reconnect behavior if supported.

On macOS, include a simulator that displays the matrix's pixels in a small grid on the host interface or development console. Make it obvious that this is simulation rather than physical hardware.

## 8. Technical architecture

Use a modular architecture that is easy to build, test, and maintain.

### Backend
- Python 3.
- FastAPI.
- Native WebSockets for real-time multiplayer events.
- Pydantic for request and event validation.
- Server-authoritative game engine.
- In-memory game session state for the initial version.
- A dedicated local AI service abstraction.
- A dedicated UNO Q LED matrix adapter.

### Frontend
- Vite.
- React.
- TypeScript.
- Responsive custom CSS or a small, suitable styling library.
- Native browser WebSocket communication.
- A mobile-first, install-free web interface.
- Locally bundled production assets so the game UI does not depend on a public CDN.

Do not introduce a database, account system, Docker requirement, or cloud infrastructure unless strictly necessary.

Keep the server and frontend separate during development, then serve the production frontend build through the backend.

Suggested project structure:

```text
the-last-clue/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── networking.py
│   │   ├── room_manager.py
│   │   ├── game_engine.py
│   │   ├── word_packs.py
│   │   ├── scoring.py
│   │   ├── ai/
│   │   │   ├── service.py
│   │   │   ├── local_provider.py
│   │   │   └── fallback_provider.py
│   │   └── hardware/
│   │       ├── matrix_adapter.py
│   │       ├── uno_q_matrix.py
│   │       └── simulator.py
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── styles/
│   └── package.json
├── assets/
├── scripts/
├── docs/
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

Adjust the structure when necessary, but keep game rules, networking, AI, and hardware code separated.

## 9. Multiplayer networking and integrity

The server is authoritative. Clients may display the game, submit valid actions, and receive updates; they may not decide the winner or modify roles.

Implement:
- Real-time WebSocket events.
- Player identities and reconnect tokens.
- Server-side nickname and room validation.
- Unique player IDs independent of nicknames.
- Reconnection to an existing session when possible.
- Correct handling of disconnects and reconnects during each game phase.
- A single source of truth for active timers.
- Server-side enforcement of game transitions.
- Validation of every client action against the current game phase.
- Prevention of duplicate clues, votes, and final guesses.
- Basic rate limiting for repeated invalid actions.
- Safe handling of malformed messages.
- Safe rendering of player-provided text.
- Graceful shutdown and reset behavior.

Use cryptographically secure randomness for secret role assignment and other security-sensitive random choices.

Do not broadcast the entire internal game-state object. Build separate public and per-player private payloads.

For example:
- Public state: player list, phase, submitted clues, timer, voting status.
- Private role event: the specific player's role and authorized secret information.
- Private actions: validated submissions from an authenticated player.

Never transmit the Imposter's identity or the secret word as hidden fields in shared public-state objects.

The game must remain playable when one client refreshes or disconnects unexpectedly. Explain what happens if the host disconnects.

## 10. High-quality design and UX

Design the UI as a polished indie horror game, not a generic admin dashboard.

### Visual direction

Use a dark, cinematic paranormal aesthetic inspired by haunted CRT screens and vintage supernatural investigations.

Suggested palette:
- Near-black background.
- Deep charcoal panels.
- Muted violet and midnight blue.
- Bone-white primary text.
- Restrained blood-red warning accents.
- Subtle ghostly cyan for interactive highlights.

Use:
- Bold typography for key messages.
- A clear hierarchy of headings, status labels, and actions.
- Subtle film grain, fog, particles, and glowing edges where they improve the experience.
- Smooth transitions between game phases.
- Custom ghost illustrations or pixel-art assets.
- Clearly differentiated secret-role cards.
- Animated vote reveal and final guessing screens.
- Small sound effects only when explicitly enabled by the player.

Do not overuse neon, blur, glass effects, gradients, or excessive animation. Make the application spooky but legible.

### Essential screens

1. Landing page with a strong game title, short instructions, and a “Host a Game” or “Join Game” action.
2. Join-room screen with nickname and room code.
3. Lobby showing players, connection status, room URL, and QR code.
4. Private role-reveal screen.
5. Clue submission and clue-board screen.
6. Discussion timer.
7. Secret voting screen.
8. Runoff voting screen.
9. Imposter final-guess screen.
10. Dramatic results screen.
11. Leaderboard and next-round screen.
12. Host settings and local AI status.

### UX requirements

- Every screen must explain what the player should do next.
- Clearly distinguish enabled, disabled, waiting, submitted, and completed states.
- Include loading states and actionable error messages.
- Avoid relying on color alone to convey game information.
- Support reduced-motion preferences.
- Use semantic HTML and accessible contrast.
- Make primary actions easy to tap with one hand.
- Ensure layout works at mobile widths around 360 pixels and on desktop browsers.
- Keep private information readable while preventing accidental screen-sharing leaks where practical.
- Include a short rules panel available at any time before the game begins.

Do not let animations block gameplay controls.

## 11. Host, room, and network configuration

On startup:
- Detect available local network addresses where possible.
- Print the local access URL in the terminal.
- Start the server on the appropriate interface.
- Expose the listening port as a configurable setting.
- Generate a join QR code.
- Show useful errors when the port is occupied or no usable network interface is available.

Provide a straightforward way to run the game on the same Wi-Fi network from phones and laptops.

If a platform prevents local connections due to Wi-Fi client isolation, firewall settings, or network configuration, document how to diagnose the issue. Do not claim that the application can automatically bypass these restrictions.

The game should not require a particular router or external internet service.

Use a configurable port such as 8765, and document how to change it.

## 12. Testing and quality assurance

Create automated tests for the critical game rules.

At minimum, test:

- The minimum player count.
- Role assignment.
- Only one Imposter per round.
- Private role and word delivery.
- Clue submission and duplicate-submission prevention.
- Clue ordering.
- Voting and duplicate-vote prevention.
- Disallowing self-votes.
- Vote counting.
- Runoff ties.
- Correct and incorrect final guesses.
- Both win conditions.
- Scoring.
- Invalid game-state transitions.
- Reconnection behavior.
- AI output validation and fallback.
- Matrix adapter behavior.
- Handling disconnected players and expired timers.

Test the most important network flows using multiple simulated clients.

Perform a manual acceptance test with at least four distinct player sessions, where practical:
1. Create a room.
2. Join four players.
3. Verify their individual role cards.
4. Submit clues.
5. Discuss.
6. Vote.
7. Catch the Imposter.
8. Enter a correct or incorrect final guess.
9. Reveal the result.
10. Start another round.

Also test the alternative path where the Imposter escapes and wins.

Do not mark a test as passed unless it has actually run successfully.

## 13. Deployment and developer experience

Provide commands and scripts for:
- Creating the Python environment.
- Installing backend dependencies.
- Installing frontend dependencies.
- Running the frontend in development mode.
- Running the backend in development mode.
- Building the production frontend.
- Running automated tests.
- Starting the production server.
- Deploying to the UNO Q.
- Running on macOS with the simulated LED matrix.

Provide a simple one-command startup script for a prepared environment. Avoid requiring a developer to manually start multiple commands every time if a combined development script can reasonably do so.

The production application should serve its built frontend and API from the same host and port.

Do not require Docker. Keep all required installation steps documented.

## 14. Documentation

Write a detailed README with:

- Project name, tagline, and feature summary.
- A clear explanation of how the game is played.
- Screenshot placeholders only when real screenshots have not yet been captured.
- Architecture diagram using Mermaid.
- Hardware and software requirements.
- UNO Q setup instructions.
- Local network setup.
- macOS development instructions.
- Installation and startup commands.
- Local AI setup and model licensing.
- LED matrix setup and verification.
- Word pack format and customization.
- Testing instructions.
- Troubleshooting.
- Privacy and local-network behavior.
- Limitations and known issues.
- A short hackathon demo script.
- License information.

Do not invent screenshots, test results, hardware results, AI benchmark results, or deployment success. Clearly label features that have not yet been tested on the physical board.

Document the actual limitations of the selected local AI model, including memory requirements and expected latency when known.

## 15. Implementation order

Implement in the following order, keeping the project playable at each stage.

**Stage 1 — Working multiplayer core**
- Create the application structure.
- Implement the backend and responsive frontend.
- Implement lobby, private roles, clues, discussion, voting, final guesses, and scoring.
- Run tests and fix errors.

**Stage 2 — Spooky visual experience**
- Build the full UI.
- Add animations, horror word packs, round transitions, and final reveals.
- Add the QR code and connection status.
- Verify the game works on mobile and desktop.

**Stage 3 — Physical hardware**
- Implement the correct UNO Q LED matrix adapter.
- Build the simulator for macOS.
- Connect game events to matrix expressions and animations.
- Test the actual matrix interface when running on the physical board.

**Stage 4 — Local AI**
- Verify the board's supported inference options.
- Configure an appropriately small open-weight model.
- Implement the local AI provider.
- Add structured outputs, validation, caching, timeouts, and fallback behavior.
- Demonstrate that AI generation runs locally, without cloud requests.

**Stage 5 — Final verification**
- Run the automated test suite.
- Fix all critical and high-priority defects.
- Test a complete multiplayer game.
- Validate startup and production build commands.
- Finish the README and deployment instructions.

Do not stop after describing these stages. Execute them in the available development environment and implement the project.

## 16. Definition of done

The project is ready only when:

- Players can join over the same local Wi-Fi network.
- A complete multiplayer round works end to end.
- Private roles and the secret word are correctly protected.
- Voting, tie resolution, final guessing, and win conditions work.
- The application is responsive and visually polished.
- The UNO Q's matrix responds to real game events using its supported hardware API.
- The local open-weight model performs a genuine, documented task on the board when configured.
- The game still works with bundled word packs if AI is unavailable.
- Automated tests pass.
- Installation, execution, deployment, and troubleshooting steps are documented.
- No critical feature is represented only by a mockup or placeholder.
- The final report states what was implemented, what was tested, and what still needs verification on physical hardware.

## Final instruction

Start by inspecting the repository and available environment. Then implement the game in working stages, run it, test it, and fix problems as you discover them.

Make The Last Clue feel like a real, memorable horror party game: fast rounds, tense secret clues, dramatic accusations, creepy visuals, a physical ghost on the Arduino UNO Q, and locally generated spooky content.

Prioritize a reliable and impressive complete game over unnecessary complexity. Never fabricate AI capabilities, hardware support, or test results. If a particular hardware or model capability cannot be verified, explain the limitation and implement the best working alternative without breaking the core game.