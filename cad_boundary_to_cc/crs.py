from __future__ import annotations

from typing import Optional

from pyproj import CRS, Transformer


def parse_crs(crs_str: Optional[str]) -> Optional[CRS]:
    if not crs_str:
        return None
    return CRS.from_user_input(crs_str)


def make_transformer(src: Optional[CRS], dst: Optional[CRS]) -> Optional[Transformer]:
    if src is None or dst is None:
        return None
    if src == dst:
        return None
    return Transformer.from_crs(src, dst, always_xy=True)
