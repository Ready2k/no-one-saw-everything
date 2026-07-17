import { Howl, Howler } from 'howler';

// Sensible defaults
const DEFAULT_MASTER = 0.7;
const AMBIENT_MULT = 0.35;
const STINGER_MULT = 0.8;
const UI_MULT = 0.45;

export type AudioState = {
  unlocked: boolean;
  muted: boolean;
  volume: number;
};

// Cooldowns
const COOLDOWNS: Record<string, number> = {
  clue_discovered: 800,
  contradiction_locked: 1200,
  pressure_defensive: 2000,
  pressure_cracking: 2500,
  accusation_submitted: 1000,
  case_solved: 3000,
  case_failed: 3000,
};

class AudioManager {
  private state: AudioState = {
    unlocked: true,
    muted: localStorage.getItem('audio_muted') === 'true',
    volume: parseFloat(localStorage.getItem('audio_volume') || String(DEFAULT_MASTER)),
  };

  private listeners: Set<(state: AudioState) => void> = new Set();
  
  private manifest: any = null;
  private howls: Record<string, Howl> = {};
  private currentAmbient: string | null = null;
  private currentAmbientHowl: Howl | null = null;
  private currentPlaylistTracks: string[] = [];
  private currentPlaylistIndex = -1;
  
  private lastPlayed: Record<string, number> = {};
  
  constructor() {
    Howler.volume(this.state.volume);
    Howler.mute(this.state.muted);
    this.init();

    // Auto-unlock/resume audio context on first user interaction
    const unlockAudio = () => {
      const ctx = Howler.ctx;
      if (ctx && ctx.state === 'suspended') {
        ctx.resume();
      }
      window.removeEventListener('click', unlockAudio);
      window.removeEventListener('keydown', unlockAudio);
      window.removeEventListener('touchstart', unlockAudio);
    };
    if (typeof window !== 'undefined') {
      window.addEventListener('click', unlockAudio);
      window.addEventListener('keydown', unlockAudio);
      window.addEventListener('touchstart', unlockAudio);
    }
  }

  private async init() {
    try {
      const res = await fetch('/audio/manifest.json');
      if (!res.ok) throw new Error('Manifest not found');
      this.manifest = await res.json();
      if (this.currentAmbient) {
        const name = this.currentAmbient;
        this.currentAmbient = null;
        this.playAmbient(name);
      }
    } catch (e) {
      if ((import.meta as any).env.DEV) {
        console.warn('Audio manifest failed to load, audio is disabled.', e);
      }
    }
  }

  public subscribe(listener: (state: AudioState) => void) {
    this.listeners.add(listener);
    listener({ ...this.state });
    return () => { this.listeners.delete(listener); };
  }

  private notify() {
    const stateCopy = { ...this.state };
    this.listeners.forEach((l) => l(stateCopy));
  }

  public unlock() {
    const ctx = Howler.ctx;
    if (ctx && ctx.state === 'suspended') {
      ctx.resume();
    }
  }

  public setVolume(value: number) {
    this.state.volume = Math.max(0, Math.min(1, value));
    localStorage.setItem('audio_volume', String(this.state.volume));
    Howler.volume(this.state.volume);
    this.notify();
  }

  public setMuted(value: boolean) {
    this.state.muted = value;
    localStorage.setItem('audio_muted', String(this.state.muted));
    Howler.mute(this.state.muted);
    this.notify();
  }

  public toggleMute() {
    this.setMuted(!this.state.muted);
  }

  public getAudioState() {
    return { ...this.state };
  }

  private getHowl(category: string, name: string, volumeMult: number, loop = false): Howl | null {
    if (!this.manifest || !this.manifest[category] || !this.manifest[category][name]) {
      return null;
    }
    const key = `${category}_${name}`;
    if (!this.howls[key]) {
      const src = this.manifest[category][name];
      this.howls[key] = new Howl({
        src: [src],
        loop,
        volume: volumeMult,
        onloaderror: (_id, e) => {
          if ((import.meta as any).env.DEV) {
            console.warn(`Failed to load audio: ${src}`, e);
          }
        },
        onplayerror: (_id, e) => {
          if ((import.meta as any).env.DEV) {
            console.warn(`Failed to play audio: ${src}`, e);
          }
          this.howls[key].once('unlock', () => {
            this.howls[key].play();
          });
        }
      });
    }
    return this.howls[key];
  }

  public playAmbient(name: string) {
    if (!this.state.unlocked) return;
    if (this.currentAmbient === name) return;
    
    this.stopAmbient();
    this.currentAmbient = name;

    if (this.manifest?.playlists?.[name]) {
      const tracks = this.manifest.playlists[name];
      this.currentPlaylistTracks = [...tracks].sort(() => Math.random() - 0.5);
      this.currentPlaylistIndex = 0;
      this.playNextPlaylistTrack();
    } else {
      const howl = this.getHowl('ambient', name, AMBIENT_MULT, true);
      if (!howl) return;
      this.currentAmbientHowl = howl;
      howl.play();
      howl.fade(0, AMBIENT_MULT, 1000);
    }
  }

  private playNextPlaylistTrack() {
    if (this.currentPlaylistTracks.length === 0) return;
    
    const trackName = this.currentPlaylistTracks[this.currentPlaylistIndex];
    const howl = this.getHowl('ambient', trackName, AMBIENT_MULT, false);
    if (!howl) return;
    
    this.currentAmbientHowl = howl;
    howl.off('end');
    
    howl.once('end', () => {
      if (this.currentPlaylistTracks.length > 0) {
        this.currentPlaylistIndex = (this.currentPlaylistIndex + 1) % this.currentPlaylistTracks.length;
        this.playNextPlaylistTrack();
      }
    });
    
    howl.play();
    howl.fade(0, AMBIENT_MULT, 1000);
  }

  public stopAmbient() {
    if (!this.currentAmbient) return;
    
    this.currentAmbient = null;
    this.currentPlaylistTracks = [];
    
    const oldHowl = this.currentAmbientHowl;
    this.currentAmbientHowl = null;
    
    if (oldHowl) {
      oldHowl.off('end');
      oldHowl.fade(AMBIENT_MULT, 0, 1000);
      oldHowl.once('fade', () => oldHowl.stop());
    }
  }

  public fadeToAmbient(name: string) {
    if (this.currentAmbient === name) return;
    this.playAmbient(name);
  }

  public playStinger(name: string) {
    if (!this.state.unlocked) return;
    
    // Cooldown check
    const now = Date.now();
    const cooldown = COOLDOWNS[name] || 500;
    if (this.lastPlayed[name] && now - this.lastPlayed[name] < cooldown) {
      return;
    }
    this.lastPlayed[name] = now;

    const howl = this.getHowl('stingers', name, STINGER_MULT);
    if (!howl) return;

    howl.play();

    // Ducking logic
    if (this.currentAmbientHowl) {
      const ambient = this.currentAmbientHowl;
      ambient.fade(AMBIENT_MULT, AMBIENT_MULT * 0.2, 200);
      setTimeout(() => {
        if (this.currentAmbientHowl === ambient) {
          ambient.fade(AMBIENT_MULT * 0.2, AMBIENT_MULT, 1000);
        }
      }, howl.duration() * 1000 || 2000);
    }
  }

  public playUi(name: string): boolean {
    if (!this.state.unlocked) return false;
    const howl = this.getHowl('ui', name, UI_MULT);
    if (!howl) return false;
    howl.play();
    return true;
  }
}

export const audioManager = new AudioManager();
