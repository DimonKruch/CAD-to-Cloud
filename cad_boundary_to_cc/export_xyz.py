from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class ColorRGB:
    r: int
    g: int
    b: int


def write_xyz(path: str, pts: Sequence[Point3D]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p in pts:
            f.write(f"{p.x:.3f} {p.y:.3f} {p.z:.3f}\n")


def write_xyz_with_id(path: str, pts: Sequence[Point3D], poly_ids: Sequence[int]) -> None:
    if len(pts) != len(poly_ids):
        raise ValueError("poly_ids length must match pts length")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p, pid in zip(pts, poly_ids):
            f.write(f"{p.x:.3f} {p.y:.3f} {p.z:.3f} {int(pid)}\n")


def write_xyz_with_sf(path: str, pts: Sequence[Point3D], sf: Sequence[float]) -> None:
    if len(pts) != len(sf):
        raise ValueError("sf length must match pts length")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p, s in zip(pts, sf):
            f.write(f"{p.x:.3f} {p.y:.3f} {p.z:.3f} {float(s):.6f}\n")


def write_xyzrgb(path: str, pts: Sequence[Point3D], color: ColorRGB) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    r = int(color.r)
    g = int(color.g)
    b = int(color.b)
    with open(path, "w", encoding="utf-8") as f:
        for p in pts:
            f.write(f"{p.x:.3f} {p.y:.3f} {p.z:.3f} {r} {g} {b}\n")


def write_xyzrgb_per_point(path: str, pts: Sequence[Point3D], rgbs: Sequence[Tuple[int, int, int]]) -> None:
    if len(pts) != len(rgbs):
        raise ValueError("rgbs length must match pts length")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p, (r, g, b) in zip(pts, rgbs):
            f.write(f"{p.x:.3f} {p.y:.3f} {p.z:.3f} {int(r)} {int(g)} {int(b)}\n")
