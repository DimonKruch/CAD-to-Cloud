from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def read_las_bbox_z_stats(las_path: str, bbox: Tuple[float, float, float, float]) -> np.ndarray:
    import laspy

    minx, miny, maxx, maxy = bbox

    with laspy.open(las_path) as lf:
        hdr = lf.header
        las_bbox = (float(hdr.mins[0]), float(hdr.mins[1]), float(hdr.maxs[0]), float(hdr.maxs[1]))
        z_vals: List[np.ndarray] = []
        for points in lf.chunk_iterator(2_000_000):
            x = points.x
            y = points.y
            mask = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
            if np.any(mask):
                z_vals.append(np.asarray(points.z[mask], dtype=np.float64))

    if not z_vals:
        raise ValueError(
            "Ошибка: Облако точек не привязано\n"
            f"boundary_bbox={bbox} las_bbox={las_bbox}"
        )
    return np.concatenate(z_vals)


def read_las_points_in_bbox(
    las_path: str,
    bbox: Tuple[float, float, float, float],
    *,
    max_points: Optional[int] = None,
) -> np.ndarray:
    import laspy

    minx, miny, maxx, maxy = bbox

    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    zs: List[np.ndarray] = []

    with laspy.open(las_path) as lf:
        hdr = lf.header
        las_bbox = (float(hdr.mins[0]), float(hdr.mins[1]), float(hdr.maxs[0]), float(hdr.maxs[1]))
        for points in lf.chunk_iterator(2_000_000):
            x = points.x
            y = points.y
            mask = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
            if not np.any(mask):
                continue
            xs.append(np.asarray(points.x[mask], dtype=np.float64))
            ys.append(np.asarray(points.y[mask], dtype=np.float64))
            zs.append(np.asarray(points.z[mask], dtype=np.float64))

            if max_points is not None:
                cur = sum(a.size for a in xs)
                if cur >= max_points:
                    break

    if not xs:
        raise ValueError(
            "Ошибка: Облако точек не привязано\n"
            f"boundary_bbox={bbox} las_bbox={las_bbox}"
        )

    x = np.concatenate(xs)
    y = np.concatenate(ys)
    z = np.concatenate(zs)
    pts = np.column_stack([x, y, z])

    if max_points is not None and pts.shape[0] > max_points:
        idx = np.random.default_rng(0).choice(pts.shape[0], size=max_points, replace=False)
        pts = pts[idx]
    return pts
