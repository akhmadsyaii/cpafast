"""
timing.py — Natural Timing Distributions for Human-Like Behavior

Mengapa distribusi timing itu penting:
- random.randint(a, b) → uniform distribution → mudah dideteksi karena
  semua nilai punya probabilitas yang sama. Real user gak gitu.
- truncated_normal(mean, 2, 5, 30) → nilai cluster di sekitar mean,
  jarang ekstrem. Mirip real user: kebanyakan visit 10-20 detik.
- lognormal_delay(5, 30) → distribusi miring ke kanan. Kadang delay
  panjang (30 detik), sering delay pendek (2-8 detik).
- bimodal_delay(peaks, stds, weights, min_val, max_val) → dua puncak.
  Cocok untuk simulasi "cepat" vs "lambat" (misal: user yang baca cepat
  vs user yang baca sambil nge-scroll).

Semua fungsi menjamin nilai dalam range [min_val, max_val].
"""

import math
import random
from typing import List, Optional, Tuple


def _validate_range(lo: float, hi: float) -> Tuple[float, float]:
    """Ensure lo < hi, swap if needed (user-friendly). Returns (lo, hi)."""
    if lo > hi:
        return hi, lo
    return lo, hi


def truncated_normal(mean: float = 5.0, std: float = 2.0,
                     lo: float = 0.5, hi: float = 30.0) -> float:
    """
    Truncated Normal Distribution — distribusi paling natural.

    Nilai cluster di sekitar `mean`, dengan variasi `std`.
    Gak pernah keluar dari [lo, hi] — dijamin.

    🔬 Kenapa truncated normal?
    - Real human behavior: kebanyakan nilai mendekati rata-rata
    - Sedikit nilai ekstrem (tapi gak keluar batas)
    - Cocok untuk: visit duration, scroll delay, typing speed

    Args:
        mean: Rata-rata waktu (default: 5 detik)
        std: Standar deviasi (default: 2)
        lo: Batas bawah (default: 0.5)
        hi: Batas atas (default: 30)

    Returns:
        Float dalam range [lo, hi]
    """
    lo, hi = _validate_range(lo, hi)
    # Clamp std: gak boleh lebih besar dari range/3 biar meaningful
    std = min(std, (hi - lo) / 3.0)
    # Iterative sampling with truncation
    for _ in range(20):
        val = random.gauss(mean, std)
        if lo <= val <= hi:
            return val
    # Fallback: Box-Muller with rejection inside range
    val = random.gauss(mean, std)
    return max(lo, min(hi, val))


def truncated_normal_int(mean: float = 5.0, std: float = 2.0,
                         lo: int = 1, hi: int = 30) -> int:
    """
    Truncated Normal → Integer.

    Args:
        mean: Rata-rata
        std: Standar deviasi
        lo: Batas bawah integer
        hi: Batas atas integer

    Returns:
        Integer dalam range [lo, hi]
    """
    return max(lo, min(hi, int(round(truncated_normal(float(mean), std, float(lo), float(hi))))))


def lognormal_delay(mean_sec: float = 5.0, max_sec: float = 30.0) -> float:
    """
    Log-Normal Distribution — distribusi miring ke kanan.

    Banyak nilai kecil (di bawah mean), sedikit nilai besar (di atas mean).
    Ini mencerminkan realitas: kebanyakan orang bergerak cepat,
    tapi kadang ada yang lambat.

    🔬 Contoh: waktu baca artikel
    - 60% user baca 3-10 detik
    - 30% user baca 10-25 detik
    - 10% user baca 25-60+ detik (deep reading)

    Args:
        mean_sec: Perkiraan mean (default: 5)
        max_sec: Batas maksimum (default: 30)

    Returns:
        Float dalam range [0.3, max_sec]
    """
    mu = math.log(max(0.5, mean_sec))
    sigma = 0.6  # Spread factor
    delay = random.lognormvariate(mu, sigma)
    return min(max(0.3, delay), max_sec)


def lognormal_int(mean: float = 5.0, max_val: float = 30.0) -> int:
    """Log-normal → Integer."""
    return max(1, int(round(lognormal_delay(mean, max_val))))


def bimodal_delay(peak1: float = 3.0, peak2: float = 15.0,
                  std1: float = 1.0, std2: float = 4.0,
                  weight1: float = 0.6, lo: float = 0.5,
                  hi: float = 30.0) -> float:
    """
    Bimodal Normal Distribution — dua puncak perilaku.

    Cocok untuk simulasi user dengan dua kecepatan:
    - Puncak 1: "Cepat" — user yang scan doang (60%)
    - Puncak 2: "Lambat" — user yang baca beneran (40%)

    🔬 Contoh: waktu scrolling
    - 60% user: scroll cepat, 2-5 detik antar scroll
    - 40% user: scroll lambat, 10-20 detik (lagi baca)

    Args:
        peak1: Mean puncak pertama (default: 3)
        peak2: Mean puncak kedua (default: 15)
        std1: Std puncak pertama (default: 1)
        std2: Std puncak kedua (default: 4)
        weight1: Probabilitas puncak pertama (0-1, default: 0.6)
        lo: Batas bawah (default: 0.5)
        hi: Batas atas (default: 30)

    Returns:
        Float dalam range [lo, hi]
    """
    lo, hi = _validate_range(lo, hi)
    # Pilih puncak berdasarkan weight
    if random.random() < weight1:
        val = random.gauss(peak1, std1)
    else:
        val = random.gauss(peak2, std2)
    return max(lo, min(hi, val))


def bimodal_int(peak1: float = 3.0, peak2: float = 15.0,
                std1: float = 1.0, std2: float = 4.0,
                weight1: float = 0.6, lo: int = 1, hi: int = 30) -> int:
    """Bimodal → Integer."""
    return max(lo, min(hi, int(round(bimodal_delay(peak1, peak2, std1, std2, weight1, float(lo), float(hi))))))


def pareto_delay(scale: float = 3.0, alpha: float = 2.5,
                 lo: float = 0.5, hi: float = 60.0) -> float:
    """
    Pareto (Power-Law) Distribution — heavy tail.

    Sebagian besar nilai kecil, tapi ada beberapa nilai SANGAT besar.
    Ini mencerminkan fenomena "some users are really slow".

    🔬 Contoh: waktu antar visit
    - 80% visit dalam 2-10 detik
    - 15% visit dalam 10-30 detik
    - 5% visit dalam 30-60+ detik (distraction)

    Args:
        scale: Nilai minimum tipikal (default: 3)
        alpha: Shape parameter — makin kecil, makin heavy tail (default: 2.5)
        lo: Batas bawah (default: 0.5)
        hi: Batas atas (default: 60)

    Returns:
        Float dalam range [lo, hi]
    """
    lo, hi = _validate_range(lo, hi)
    # Pareto: val = scale / (random.random() ** (1/alpha))
    # Tapi ini gak ada batas atas, jadi kita truncate
    try:
        val = scale / (random.random() ** (1.0 / alpha))
    except (ZeroDivisionError, ValueError):
        val = scale
    return max(lo, min(hi, val))


def pareto_int(scale: float = 3.0, alpha: float = 2.5,
               lo: int = 1, hi: int = 60) -> int:
    """Pareto → Integer."""
    return max(lo, min(hi, int(round(pareto_delay(scale, alpha, float(lo), float(hi))))))


def natural_delay(mean: float = 5.0, min_val: float = 0.5,
                  max_val: float = 30.0,
                  distribution: str = "auto") -> float:
    """
    PINTAR: Auto-pilih distribusi paling cocok.

    Ini fungsi utama yang harus dipakai di mana-mana.
    Dia otomatis pilih distribusi terbaik berdasarkan mean & range.

    - mean ≤ 3: truncated_normal (cluster rapat, user gerak cepat)
    - mean 3-10: lognormal (miring ke kanan, natural)
    - mean > 10: bimodal (dua mode: cepet & lambat)

    Args:
        mean: Rata-rata yang diinginkan
        min_val: Nilai minimum
        max_val: Nilai maksimum
        distribution: Paksa distribusi tertentu (normal, lognormal, bimodal, pareto, auto)

    Returns:
        Float dalam range [min_val, max_val]
    """
    min_val, max_val = _validate_range(min_val, max_val)

    if distribution == "normal":
        std = min(mean / 2.0, (max_val - min_val) / 3.0)
        return truncated_normal(mean, std, min_val, max_val)
    elif distribution == "lognormal":
        return lognormal_delay(mean, max_val)
    elif distribution == "bimodal":
        peak1 = mean * 0.4
        peak2 = mean * 1.6
        std1 = peak1 / 3.0
        std2 = peak2 / 4.0
        return bimodal_delay(peak1, peak2, std1, std2, lo=min_val, hi=max_val)
    elif distribution == "pareto":
        return pareto_delay(mean * 0.5, 2.5, min_val, max_val)

    # Auto: pilih distribusi berdasarkan mean
    if mean <= 3.0:
        # Short delays: truncated normal
        std = max(0.5, mean / 2.0)
        return truncated_normal(mean, std, min_val, max_val)
    elif mean <= 10.0:
        # Medium delays: log-normal (natural right skew)
        return lognormal_delay(mean, max_val)
    else:
        # Long delays: bimodal (some fast, some slow)
        peak1 = mean * 0.3
        peak2 = mean * 1.4
        std1 = peak1 / 3.0
        std2 = peak2 / 3.0
        return bimodal_delay(peak1, peak2, std1, std2, lo=min_val, hi=max_val)


def natural_int(mean: float = 5.0, min_val: int = 1,
                max_val: int = 30, distribution: str = "auto") -> int:
    """natural_delay → Integer."""
    return max(min_val, min(max_val, int(round(natural_delay(mean, float(min_val), float(max_val), distribution)))))


# ── Convenience: context manager for manual timing ────────────────────
# Berguna kalau butuh timing yang presisi

def sleep_ms(ms: int):
    """Sleep in milliseconds (import time for you)."""
    import time
    time.sleep(ms / 1000.0)


# ── Demonstrasi ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import collections
    import time

    print("=" * 60)
    print("  Timing Distribution Demo")
    print("=" * 60)

    entries = [
        ("uniform(5,30)",    lambda: random.uniform(5, 30),            17.5, 5, 30),
        ("trunc_normal(10,3)", lambda: truncated_normal(10, 3, 1, 30), 10,  1, 30),
        ("lognormal(8,30)",  lambda: lognormal_delay(8, 30),           8,   1, 30),
        ("bimodal(3,15)",    lambda: bimodal_delay(3, 15, 1, 4, 0.6),  3,   1, 30),
        ("pareto(3,2.5)",    lambda: pareto_delay(3, 2.5, 1, 60),      3,   1, 60),
        ("natural(5)",       lambda: natural_delay(5, 1, 30),          5,   1, 30),
        ("natural(15)",      lambda: natural_delay(15, 1, 60),         15,  1, 60),
    ]

    for dist_name, func, _mean, lo, hi in entries:
        samples = [func() for _ in range(1000)]
        avg = sum(samples) / len(samples)
        mn = min(samples)
        mx = max(samples)
        # Histogram (10 buckets)
        buckets = [0] * 10
        for s in samples:
            idx = min(9, int((s - lo) / max(0.001, (hi - lo)) * 10))
            buckets[min(9, idx)] += 1
        bar = " ".join(f"{'█' * (b // 10):4s}" for b in buckets)
        print(f"\n  {dist_name:30s} avg={avg:5.2f}  [{mn:5.2f} - {mx:5.2f}]")
        print(f"  {'':30s} {bar}")
