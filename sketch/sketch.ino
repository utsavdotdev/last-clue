// The Last Clue — Arduino UNO Q 8x13 LED Matrix Ghost Controller
// Pixel masks match python/last_clue/hardware/frames.py 1-to-1.
// Bridge.provide_safe handlers store state without blocking RPC; loop() renders with millis().

#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>

static const int STATE_BOOT = 1;
static const int STATE_LOBBY = 2;
static const int STATE_ROLES_ASSIGNED = 3;
static const int STATE_CLUE_PHASE = 4;
static const int STATE_VOTING_PHASE = 5;
static const int STATE_RUNOFF = 6;
static const int STATE_IMPOSTER_DISCOVERED = 7;
static const int STATE_SURVIVORS_WIN = 8;
static const int STATE_IMPOSTER_WINS = 9;
static const int STATE_IDLE = 10;

static const int ROWS = 8;
static const int COLS = 13;

// Primary 8x13 sprites indexed by state_code - 1
static const uint16_t PRIMARY_SPRITES[10][8] = {
    {0, 224, 336, 496, 224, 64, 0, 0},                    // 1: BOOT
    {496, 1016, 1708, 2044, 2044, 2044, 1772, 1092},      // 2: LOBBY
    {4593, 1016, 1188, 2044, 1884, 2044, 1364, 4097},     // 3: ROLES_ASSIGNED
    {6640, 5112, 1628, 2044, 6140, 2044, 1772, 584},      // 4: CLUE_PHASE
    {0, 1980, 2470, 2470, 1980, 0, 496, 0},               // 5: VOTING_PHASE
    {4593, 5113, 1300, 2044, 1820, 2044, 5349, 4617},     // 6: RUNOFF
    {1252, 1016, 1708, 1820, 2044, 1708, 2044, 1364},     // 7: IMPOSTER_DISCOVERED
    {0, 0, 0, 496, 680, 2044, 4094, 6891},                // 8: SURVIVORS_WIN
    {2546, 2044, 3758, 4094, 3414, 3758, 2044, 2322},     // 9: IMPOSTER_WINS
    {0, 496, 1016, 1708, 2044, 2044, 1772, 1092},         // 10: IDLE
};

// Secondary 8x13 animation beat sprites indexed by state_code - 1
static const uint16_t SECONDARY_SPRITES[10][8] = {
    {496, 1016, 1708, 2044, 2044, 2044, 1772, 1092},      // 1: BOOT
    {0, 496, 1016, 1708, 2044, 2044, 1884, 520},          // 2: LOBBY
    {496, 1016, 1708, 2044, 2044, 2044, 1772, 1092},      // 3: ROLES_ASSIGNED
    {496, 1016, 1708, 2044, 2044, 2044, 1772, 1092},      // 4: CLUE_PHASE
    {0, 1980, 3250, 3250, 1980, 0, 496, 0},               // 5: VOTING_PHASE
    {0, 0, 0, 0, 0, 0, 0, 0},                             // 6: RUNOFF (rapid blink)
    {4593, 1016, 1188, 2044, 1884, 2044, 1364, 4097},     // 7: IMPOSTER_DISCOVERED
    {0, 224, 336, 496, 224, 64, 0, 0},                    // 8: SURVIVORS_WIN
    {1252, 1016, 1708, 1820, 2044, 1708, 2044, 1364},     // 9: IMPOSTER_WINS
    {0, 496, 1016, 1708, 2044, 2044, 1884, 520},          // 10: IDLE
};

static Arduino_LED_Matrix matrix;
static int currentState = STATE_BOOT;
static int lastGeneration = -1;
static int currentBeat = 0;
static bool dirty = true;
static unsigned long stateStartedAt = 0;
static uint8_t frame[ROWS * COLS];

unsigned long beat_interval_ms(int state_code) {
  if (state_code == STATE_RUNOFF) {
    return 160;
  }
  if (state_code == STATE_IMPOSTER_DISCOVERED || state_code == STATE_ROLES_ASSIGNED) {
    return 240;
  }
  if (state_code == STATE_VOTING_PHASE) {
    return 380;
  }
  return 650;
}

void set_ghost_state(int state_code, int generation) {
  if (state_code < STATE_BOOT || state_code > STATE_IDLE) {
    return;
  }
  if (generation == lastGeneration) {
    return;
  }
  lastGeneration = generation;
  currentState = state_code;
  currentBeat = 0;
  stateStartedAt = millis();
  dirty = true;
}

void render_current_frame() {
  int idx = currentState - 1;
  if (idx < 0 || idx >= 10) {
    idx = STATE_IDLE - 1;
  }
  const uint16_t* rows = (currentBeat % 2 == 0) ? PRIMARY_SPRITES[idx] : SECONDARY_SPRITES[idx];
  for (int row = 0; row < ROWS; ++row) {
    uint16_t mask = rows[row];
    for (int col = 0; col < COLS; ++col) {
      frame[row * COLS + col] = ((mask & (1 << col)) != 0) ? 1 : 0;
    }
  }
  matrix.draw(frame);
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(1);
  Bridge.begin();
  Bridge.provide_safe("set_ghost_state", set_ghost_state);
  stateStartedAt = millis();
  render_current_frame();
  dirty = false;
}

void loop() {
  unsigned long now = millis();

  // Automatically settle from BOOT into IDLE after 2.4 seconds if no lobby state arrived yet
  if (currentState == STATE_BOOT && (now - stateStartedAt) > 2400) {
    currentState = STATE_IDLE;
    stateStartedAt = now;
    currentBeat = 0;
    dirty = true;
  }

  unsigned long interval = beat_interval_ms(currentState);
  int nextBeat = static_cast<int>((now - stateStartedAt) / interval) % 2;
  if (nextBeat != currentBeat) {
    currentBeat = nextBeat;
    dirty = true;
  }

  if (!dirty) {
    return;
  }
  render_current_frame();
  dirty = false;
}
