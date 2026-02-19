from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple


def densify_polyline(
    vertices: Sequence[Tuple[float, float, Optional[float]]],
    step_m: float,
) -> List[Tuple[float, float, Optional[float]]]:
    if len(vertices) < 2:
        return list(vertices)

    if step_m <= 0:
        raise ValueError("step_m must be > 0")

    out: List[Tuple[float, float, Optional[float]]] = []
    for i in range(len(vertices) - 1):
        x0, y0, z0 = vertices[i]
        x1, y1, z1 = vertices[i + 1]
        dx = x1 - x0
        dy = y1 - y0
        seg_len = math.hypot(dx, dy)
        if seg_len == 0:
            continue

        n = max(1, int(math.ceil(seg_len / step_m)))
        for j in range(n):
            t = j / n
            zt = None if z0 is None or z1 is None else float(z0 + (z1 - z0) * t)
            out.append((x0 + dx * t, y0 + dy * t, zt))

    out.append(vertices[-1])

    dedup: List[Tuple[float, float, Optional[float]]] = []
    for xy in out:
        if not dedup or (abs(dedup[-1][0] - xy[0]) > 1e-9 or abs(dedup[-1][1] - xy[1]) > 1e-9):
            dedup.append(xy)
    return dedup
