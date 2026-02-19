from __future__ import annotations

import math
from typing import Callable, Literal, Optional

import numpy as np


ZConstMode = Literal["p95", "median"]


def pick_constant_z(zs: np.ndarray, mode: ZConstMode, offset: float) -> float:
    mode_l = mode.lower()
    if mode_l == "p95":
        base = float(np.percentile(zs, 95))
    elif mode_l == "median":
        base = float(np.median(zs))
    else:
        raise ValueError("Unsupported z_mode. Use: p95, median")
    return base + float(offset)


def surface_z_from_neighbors(
    cloud_xyz: np.ndarray,
    samples_xy: np.ndarray,
    *,
    radius_m: float,
    k: int,
    quantile: float,
    fallback_z: float,
    offset: float,
    progress: Optional[Callable[[int], None]] = None,
    batch_size: int = 1024,
    method: Literal["fast", "grid"] = "fast",
) -> np.ndarray:
    if radius_m <= 0:
        raise ValueError("radius_m must be > 0")
    if k <= 0:
        raise ValueError("k must be > 0")
    if not (0.0 <= quantile <= 1.0):
        raise ValueError("quantile must be within [0, 1]")

    # The original fully-vectorized (B,N) distance matrix approach can allocate
    # huge temporary arrays and effectively "hang" (heavy swapping) on large clouds.
    # To keep performance predictable we use the grid-based neighbor search for both
    # 'grid' and default 'fast' methods.
    return _surface_z_from_neighbors_grid(
        cloud_xyz,
        samples_xy,
        radius_m=radius_m,
        k=k,
        quantile=quantile,
        fallback_z=fallback_z,
        offset=offset,
        progress=progress,
    )


def _surface_z_from_neighbors_grid(
    cloud_xyz: np.ndarray,
    samples_xy: np.ndarray,
    *,
    radius_m: float,
    k: int,
    quantile: float,
    fallback_z: float,
    offset: float,
    progress: Optional[Callable[[int], None]] = None,
) -> np.ndarray:
    cloud_xy = np.asarray(cloud_xyz[:, :2], dtype=np.float64)
    cloud_z = np.asarray(cloud_xyz[:, 2], dtype=np.float64)
    samples_xy = np.asarray(samples_xy, dtype=np.float64)
    out = np.empty(samples_xy.shape[0], dtype=np.float64)

    if cloud_xy.shape[0] <= 0:
        raise ValueError("cloud_xyz is empty")

    r = float(radius_m)
    r2 = r * r
    cell = r

    ix = np.floor(cloud_xy[:, 0] / cell).astype(np.int32)
    iy = np.floor(cloud_xy[:, 1] / cell).astype(np.int32)
    keys = (ix.astype(np.int64) << 32) ^ (iy.astype(np.int64) & 0xFFFFFFFF)

    order = np.argsort(keys)
    keys_sorted = keys[order]
    uniq, start_idx, counts = np.unique(keys_sorted, return_index=True, return_counts=True)

    def _cell_indices(kkey: np.int64) -> np.ndarray:
        pos = np.searchsorted(uniq, kkey)
        if pos >= uniq.size or uniq[pos] != kkey:
            return np.empty((0,), dtype=np.int64)
        s = int(start_idx[pos])
        c = int(counts[pos])
        return order[s : s + c]

    k_eff_max = int(max(1, k))
    n = int(samples_xy.shape[0])
    last_p = -1
    for i in range(n):
        sx = float(samples_xy[i, 0])
        sy = float(samples_xy[i, 1])
        cx = int(math.floor(sx / cell))
        cy = int(math.floor(sy / cell))

        cand: list[np.ndarray] = []
        for dx_cell in (-1, 0, 1):
            for dy_cell in (-1, 0, 1):
                kkey = (np.int64(cx + dx_cell) << 32) ^ (np.int64(cy + dy_cell) & 0xFFFFFFFF)
                ids = _cell_indices(kkey)
                if ids.size:
                    cand.append(ids)

        if not cand:
            out[i] = float(fallback_z) + float(offset)
        else:
            ids_all = np.concatenate(cand)
            pts = cloud_xy[ids_all]
            ddx = pts[:, 0] - sx
            ddy = pts[:, 1] - sy
            d2 = ddx * ddx + ddy * ddy

            m = d2 <= r2
            if not np.any(m):
                out[i] = float(fallback_z) + float(offset)
            else:
                ids_in = ids_all[m]
                d2_in = d2[m]
                if ids_in.size > k_eff_max:
                    sel = np.argpartition(d2_in, kth=k_eff_max - 1)[:k_eff_max]
                    ids_in = ids_in[sel]
                z = cloud_z[ids_in]
                out[i] = float(np.quantile(z, quantile)) + float(offset)

        if progress is not None:
            p = int(100 * (i + 1) / max(1, n))
            if p != last_p:
                last_p = p
                progress(p)

    return out
