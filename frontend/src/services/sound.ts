/**
 * Synthesized Web Audio sound effects for The Last Clue.
 * Enabled by default so players hear tactile feedback on every action;
 * can be muted/unmuted anytime from the top header bar.
 */

class SoundCueService {
  private ctx: AudioContext | null = null;
  public enabled = true;

  private ensureContext(): AudioContext | null {
    if (!this.enabled || typeof window === "undefined") {
      return null;
    }
    if (!this.ctx) {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
    return this.ctx;
  }

  public playTone(
    freq: number,
    durationMs: number,
    type: OscillatorType = "sine",
    gainLevel = 0.06,
    delayMs = 0,
    endFreq?: number
  ): void {
    const ctx = this.ensureContext();
    if (!ctx) return;

    const startTime = ctx.currentTime + delayMs / 1000;
    const stopTime = startTime + durationMs / 1000;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, startTime);
    if (endFreq !== undefined) {
      osc.frequency.exponentialRampToValueAtTime(
        Math.max(20, endFreq),
        stopTime
      );
    }

    gain.gain.setValueAtTime(0.0001, startTime);
    gain.gain.linearRampToValueAtTime(gainLevel, startTime + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, stopTime);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(startTime);
    osc.stop(stopTime);
  }

  /** Crisp UI tap for buttons and switches */
  public playTap(): void {
    this.playTone(420, 55, "sine", 0.04, 0, 520);
  }

  /** Confirmation chime when copying room code or link */
  public playCopy(): void {
    this.playTone(587.33, 90, "triangle", 0.055, 0);
    this.playTone(880, 140, "sine", 0.055, 70);
  }

  /** Rising chime when a player joins the lobby */
  public playPlayerJoin(): void {
    this.playTone(392.0, 110, "triangle", 0.05, 0);
    this.playTone(523.25, 160, "sine", 0.055, 90);
  }

  /** Sliding shutter sound when revealing or hiding the secret role card */
  public playCardFlip(revealing: boolean): void {
    if (revealing) {
      this.playTone(220, 160, "triangle", 0.06, 0, 440);
      this.playTone(659.25, 180, "sine", 0.045, 95);
    } else {
      this.playTone(400, 130, "triangle", 0.05, 0, 196);
    }
  }

  /** Atmospheric chord when transitioning between game phases */
  public playPhaseTransition(): void {
    this.playTone(220.0, 260, "triangle", 0.055, 0);
    this.playTone(261.63, 280, "sine", 0.05, 90);
    this.playTone(329.63, 340, "sine", 0.05, 180);
  }

  /** Distinct double-chime when it becomes this player's turn to give a clue */
  public playYourTurn(): void {
    this.playTone(523.25, 140, "triangle", 0.065, 0);
    this.playTone(659.25, 140, "triangle", 0.065, 120);
    this.playTone(783.99, 240, "sine", 0.065, 240);
  }

  /** Pop chime when a clue is submitted to the board */
  public playClueSubmitted(): void {
    this.playTone(349.23, 95, "triangle", 0.055, 0);
    this.playTone(523.25, 150, "sine", 0.06, 75);
  }

  /** Low lock-in pulse when casting a secret vote */
  public playVoteLocked(): void {
    this.playTone(293.66, 110, "triangle", 0.06, 0);
    this.playTone(220.0, 210, "sine", 0.065, 95);
  }

  /** Dramatic sting when the Imposter is discovered and faces Final Guess */
  public playAccusation(): void {
    this.playTone(196.0, 320, "sawtooth", 0.055, 0, 146.83);
    this.playTone(138.59, 480, "triangle", 0.07, 160, 110.0);
  }

  /** Bright victorious arpeggio when Survivors win */
  public playVictorySurvivors(): void {
    this.playTone(392.0, 150, "triangle", 0.06, 0);
    this.playTone(493.88, 150, "triangle", 0.06, 120);
    this.playTone(587.33, 160, "triangle", 0.06, 240);
    this.playTone(783.99, 420, "sine", 0.075, 360);
  }

  /** Eerie minor chord when the Imposter wins */
  public playVictoryImposter(): void {
    this.playTone(293.66, 200, "sawtooth", 0.045, 0);
    this.playTone(277.18, 220, "triangle", 0.055, 150);
    this.playTone(220.0, 500, "triangle", 0.07, 310, 164.81);
  }
}

export const soundCues = new SoundCueService();
