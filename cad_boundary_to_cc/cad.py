from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set, Tuple

import ezdxf


def extract_dxf_polylines(
    dxf_path: str,
    layer: Optional[str],
) -> List[List[Tuple[float, float, Optional[float]]]]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    polylines: List[List[Tuple[float, float, Optional[float]]]] = []

    def layer_ok(e) -> bool:
        if not layer:
            return True
        return (e.dxf.layer or "") == layer

    for e in msp:
        if not layer_ok(e):
            continue

        t = e.dxftype()
        if t == "LWPOLYLINE":
            pts = []
            for v in e.get_points("xyseb"):
                x = float(v[0])
                y = float(v[1])
                z = None
                try:
                    z = float(e.dxf.elevation)
                except Exception:
                    z = None
                pts.append((x, y, z))
            if len(pts) >= 2:
                polylines.append(pts)
        elif t == "POLYLINE":
            if e.is_2d_polyline or e.is_3d_polyline:
                pts = [
                    (float(v.dxf.location.x), float(v.dxf.location.y), float(v.dxf.location.z))
                    for v in e.vertices
                ]
                if len(pts) >= 2:
                    polylines.append(pts)
        elif t == "LINE":
            pts = [
                (float(e.dxf.start.x), float(e.dxf.start.y), float(e.dxf.start.z)),
                (float(e.dxf.end.x), float(e.dxf.end.y), float(e.dxf.end.z)),
            ]
            polylines.append(pts)

    if not polylines:
        raise ValueError("No supported linework found in DXF (LWPOLYLINE/POLYLINE/LINE)")
    return polylines


def list_dxf_layers(dxf_path: str) -> List[str]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    layers: Set[str] = set()
    for e in msp:
        t = e.dxftype()
        if t not in ("LWPOLYLINE", "POLYLINE", "LINE"):
            continue
        name = str(getattr(e.dxf, "layer", "") or "")
        if name:
            layers.add(name)
    return sorted(layers)


def extract_dxf_polylines_with_layer(
    dxf_path: str,
    layers: Optional[Iterable[str]],
) -> List[Tuple[str, List[Tuple[float, float, Optional[float]]]]]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    allow: Optional[Set[str]]
    if layers is None:
        allow = None
    else:
        allow = {str(x) for x in layers if str(x)}
        if not allow:
            allow = None

    out: List[Tuple[str, List[Tuple[float, float, Optional[float]]]]] = []

    for e in msp:
        layer_name = str(getattr(e.dxf, "layer", "") or "")
        if allow is not None and layer_name not in allow:
            continue

        t = e.dxftype()
        if t == "LWPOLYLINE":
            pts = []
            for v in e.get_points("xyseb"):
                x = float(v[0])
                y = float(v[1])
                z = None
                try:
                    z = float(e.dxf.elevation)
                except Exception:
                    z = None
                pts.append((x, y, z))
            if len(pts) >= 2:
                out.append((layer_name, pts))
        elif t == "POLYLINE":
            if e.is_2d_polyline or e.is_3d_polyline:
                pts = [
                    (float(v.dxf.location.x), float(v.dxf.location.y), float(v.dxf.location.z))
                    for v in e.vertices
                ]
                if len(pts) >= 2:
                    out.append((layer_name, pts))
        elif t == "LINE":
            pts = [
                (float(e.dxf.start.x), float(e.dxf.start.y), float(e.dxf.start.z)),
                (float(e.dxf.end.x), float(e.dxf.end.y), float(e.dxf.end.z)),
            ]
            out.append((layer_name, pts))

    if not out:
        raise ValueError("No supported linework found in DXF (LWPOLYLINE/POLYLINE/LINE)")
    return out


def compute_bbox(xy_points: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in xy_points]
    ys = [p[1] for p in xy_points]
    return min(xs), min(ys), max(xs), max(ys)
