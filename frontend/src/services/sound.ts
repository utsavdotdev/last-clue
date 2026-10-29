/**
 * Subtle synthesized Web Audio cues for The Last Clue.
 * Disabled by default; only plays when explicitly enabled by the player.
 */

class SoundCueService {
  private ctx: AudioContext | null = null;
  public enabled = false;

  private ensureContext(): AudioContext | null {
    if (!this.enabled || typeof window === "undefined") {
      return null;
    }
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
    return this.ctx;
  }

  public playTone(freq: number, durationMs: number, type: OscillatorType = "sine", gainLevel = 0.05): void {
    const ctx = this.ensureContext();
    if (!ctx) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);

    gain.gain.setValueAtTime(gainLevel, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + durationMs / 1000);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + durationMs / 1000);
  }

  public playPhaseTransition(): void {
    this.playTone(196, 260, "triangle", 0.06);
    setTimeout(() => this.playTone(233.08, 320, "sine", 0.05), 110);
  }

  public playAccusation(): void {
    this.playTone(146.83, 420, "sawtooth", 0.05);
    setTimeout(() => this.playTone(110.0, 520, "triangle", 0.06), 140);
  }

  public playTap(): void {
    this.playTone(330, 65, "sine", 0.03);
  }
}

export const soundCues = new SoundCueService();
