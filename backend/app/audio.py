"""Lectura de audio WAV (el navegador graba PCM 16 bits a 16 kHz)."""
from __future__ import annotations

import io
import wave

import numpy as np

TARGET_SR = 16000


def wav_to_float(data: bytes) -> tuple[np.ndarray, int]:
    """WAV en bytes → (muestras float32 mono a 16 kHz, sample rate original)."""
    with wave.open(io.BytesIO(data), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        x = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif width == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        raise ValueError("Formato WAV no soportado")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != TARGET_SR and len(x):
        n = int(round(len(x) * TARGET_SR / sr))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x, sr


def trim_silence(x: np.ndarray, sr: int = TARGET_SR, thresh: float = 0.02) -> np.ndarray:
    """Recorta silencio al inicio y al final (deja 150 ms de margen)."""
    if not len(x):
        return x
    frame = int(sr * 0.02)
    energy = np.array([np.abs(x[i : i + frame]).max() for i in range(0, len(x), frame)])
    peak = energy.max() if len(energy) else 0
    if peak <= 0:
        return x
    idx = np.where(energy > max(thresh, peak * 0.08))[0]
    if not len(idx):
        return x
    pad = int(0.15 * sr)
    start = max(0, idx[0] * frame - pad)
    end = min(len(x), (idx[-1] + 1) * frame + pad)
    return x[start:end]


def duration(x: np.ndarray, sr: int = TARGET_SR) -> float:
    return len(x) / sr
