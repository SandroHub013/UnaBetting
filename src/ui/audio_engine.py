"""
Audio Engine v2.0 — Programmatic Audio Generation.
No external audio files needed. Uses numpy sine waves + pygame.sndarray.
TTS with proper text cleaning (no markup read aloud).
"""
import re
import threading
import yaml
import numpy as np
import pygame
import pyttsx3


class AudioEngine:
    """
    Generates all sounds programmatically.
    SFX: ascending/descending tones.
    Ambient: low-frequency drone loop.
    TTS: pyttsx3 with markup stripping.
    """

    _SAMPLE_RATE = 44100

    def __init__(self, config_path="config/config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        self.settings = config.get("audio", {})
        self.tts_enabled = self.settings.get("voice_enabled", True)
        self.tts_auto = self.settings.get("tts_auto", False)
        self.sfx_enabled = self.settings.get("sfx_enabled", True)
        self.music_enabled = self.settings.get("music_enabled", True)
        self.vol_sfx = self.settings.get("volume_sfx", 0.7)
        self.vol_music = self.settings.get("volume_music", 0.15)

        # Last agent response (for /speak command)
        self.last_response = ""

        # Initialize Pygame Mixer (stereo — sndarray needs 2D)
        try:
            pygame.mixer.init(frequency=self._SAMPLE_RATE, size=-16, channels=2, buffer=1024)
            self._mixer_ok = True
        except Exception:
            self._mixer_ok = False

        # Pre-generate SFX sounds
        self._sounds = {}
        if self._mixer_ok:
            self._sounds["scan_complete"] = self._make_ascending_tone()
            self._sounds["error"] = self._make_descending_tone()
            self._sounds["startup"] = self._make_arpeggio()
            self._sounds["click"] = self._make_click()

        # Initialize TTS engine
        self._tts_engine = None
        self._tts_lock = threading.Lock()
        try:
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty('rate', 175)
            self._tts_engine.setProperty('volume', 0.8)
            # Try Italian voice
            voices = self._tts_engine.getProperty('voices')
            for voice in voices:
                if "italian" in voice.name.lower() or "ita" in voice.id.lower():
                    self._tts_engine.setProperty('voice', voice.id)
                    break
        except Exception:
            self._tts_engine = None

    # ------------------------------------------------------------------
    # Tone generation
    # ------------------------------------------------------------------

    def _generate_tone(self, freq: float, duration_ms: int, volume: float = 0.5) -> np.ndarray:
        """Generate a sine wave tone with fade in/out. Returns 1D int16 array."""
        n_samples = int(self._SAMPLE_RATE * duration_ms / 1000)
        t = np.linspace(0, duration_ms / 1000, n_samples, endpoint=False)
        wave = np.sin(2 * np.pi * freq * t) * volume

        # Fade in/out (10ms each) to prevent click artifacts
        fade_samples = min(int(self._SAMPLE_RATE * 0.01), n_samples // 4)
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            wave[:fade_samples] *= fade_in
            wave[-fade_samples:] *= fade_out

        return (wave * 32767).astype(np.int16)

    @staticmethod
    def _to_stereo(mono: np.ndarray) -> np.ndarray:
        """Convert 1D mono array to 2D stereo (required by pygame.sndarray)."""
        return np.column_stack((mono, mono))

    def _make_ascending_tone(self) -> pygame.mixer.Sound:
        """Scan complete: C5 -> E5 ascending (happy sound)."""
        tone1 = self._generate_tone(523.25, 120, self.vol_sfx)  # C5
        tone2 = self._generate_tone(659.25, 180, self.vol_sfx)  # E5
        silence = np.zeros(int(self._SAMPLE_RATE * 0.03), dtype=np.int16)
        combined = np.concatenate([tone1, silence, tone2])
        return pygame.sndarray.make_sound(self._to_stereo(combined))

    def _make_descending_tone(self) -> pygame.mixer.Sound:
        """Error: E4 -> C4 descending (alert sound)."""
        tone1 = self._generate_tone(329.63, 150, self.vol_sfx)  # E4
        tone2 = self._generate_tone(261.63, 200, self.vol_sfx)  # C4
        silence = np.zeros(int(self._SAMPLE_RATE * 0.03), dtype=np.int16)
        combined = np.concatenate([tone1, silence, tone2])
        return pygame.sndarray.make_sound(self._to_stereo(combined))

    def _make_arpeggio(self) -> pygame.mixer.Sound:
        """Startup: C5-E5-G5 arpeggio."""
        tone1 = self._generate_tone(523.25, 100, self.vol_sfx * 0.6)  # C5
        tone2 = self._generate_tone(659.25, 100, self.vol_sfx * 0.6)  # E5
        tone3 = self._generate_tone(783.99, 160, self.vol_sfx * 0.6)  # G5
        silence = np.zeros(int(self._SAMPLE_RATE * 0.02), dtype=np.int16)
        combined = np.concatenate([tone1, silence, tone2, silence, tone3])
        return pygame.sndarray.make_sound(self._to_stereo(combined))

    def _make_click(self) -> pygame.mixer.Sound:
        """Subtle UI click."""
        tone = self._generate_tone(1000, 30, self.vol_sfx * 0.3)
        return pygame.sndarray.make_sound(self._to_stereo(tone))

    def _generate_ambient_drone(self) -> pygame.mixer.Sound:
        """Generate 10s ambient drone: A1(55Hz) + E2(82Hz) + A2(110Hz) with tremolo."""
        duration = 10.0
        n_samples = int(self._SAMPLE_RATE * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # Three harmonics
        wave = (
            np.sin(2 * np.pi * 55 * t) * 0.4 +    # A1
            np.sin(2 * np.pi * 82.41 * t) * 0.3 +  # E2
            np.sin(2 * np.pi * 110 * t) * 0.2       # A2
        )

        # Tremolo (slow amplitude modulation at ~3Hz)
        tremolo = 0.7 + 0.3 * np.sin(2 * np.pi * 3 * t)
        wave *= tremolo

        # Overall volume (very low)
        wave *= self.vol_music

        # Smooth loop: fade first/last 500ms
        fade_n = int(self._SAMPLE_RATE * 0.5)
        wave[:fade_n] *= np.linspace(0, 1, fade_n)
        wave[-fade_n:] *= np.linspace(1, 0, fade_n)

        mono = (wave * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(self._to_stereo(mono))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_music(self):
        """Start ambient drone loop."""
        if not self.music_enabled or not self._mixer_ok:
            return
        try:
            drone = self._generate_ambient_drone()
            # Play on a channel in a loop
            channel = pygame.mixer.Channel(7)  # Reserve channel 7 for ambient
            channel.play(drone, loops=-1)
            channel.set_volume(self.vol_music)
        except Exception:
            pass

    def play_sfx(self, sfx_type: str = "scan_complete"):
        """Play a programmatic sound effect."""
        if not self.sfx_enabled or not self._mixer_ok:
            return
        sound = self._sounds.get(sfx_type)
        if sound:
            try:
                sound.play()
            except Exception:
                pass

    def speak(self, text: str):
        """TTS synthesis in background thread with markup cleaning."""
        if not self.tts_enabled or not self._tts_engine:
            return
        self.last_response = text

        def _talk():
            with self._tts_lock:
                try:
                    clean = self._clean_for_speech(text)
                    if clean and len(clean) > 3:
                        self._tts_engine.say(clean)
                        self._tts_engine.runAndWait()
                except Exception:
                    pass

        threading.Thread(target=_talk, daemon=True).start()

    def speak_last(self):
        """Speak the last agent response (for /speak command)."""
        if self.last_response:
            self.speak(self.last_response)

    def stop_all(self):
        """Cleanup on terminal exit."""
        try:
            pygame.mixer.stop()
            pygame.mixer.quit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Text cleaning for TTS
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Strip Rich markup, emoji, markdown, box chars for clean TTS."""
        # Rich tags: [bold green], [/bold], [#FF0000], etc.
        text = re.sub(r'\[/?[a-zA-Z0-9 #_\-\.]+\]', '', text)
        # Star ratings
        text = re.sub(r'[★⭐]+', lambda m: f"{len(m.group())} stelle", text)
        text = re.sub(r'[☆]', '', text)
        # Emoji (broad Unicode ranges)
        text = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F]', '', text)
        # Markdown formatting
        text = re.sub(r'[*_~`#]', '', text)
        # Box-drawing characters
        text = re.sub(r'[─═│┌┐└┘├┤┬┴┼█░▓▒]', '', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
