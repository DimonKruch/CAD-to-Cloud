from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from cad_boundary_to_cc.cad import compute_bbox, extract_dxf_polylines, extract_dxf_polylines_with_layer
from cad_boundary_to_cc.cloud_las import read_las_bbox_z_stats, read_las_points_in_bbox
from cad_boundary_to_cc.crs import make_transformer, parse_crs
from cad_boundary_to_cc.densify import densify_polyline
from cad_boundary_to_cc.export_xyz import (
    ColorRGB,
    Point3D,
    write_xyz,
    write_xyz_with_id,
    write_xyz_with_sf,
    write_xyzrgb,
    write_xyzrgb_per_point,
)
from cad_boundary_to_cc.z_assign import pick_constant_z, surface_z_from_neighbors


def _write_combined_las_with_cad_points(
    *,
    cloud_path: str,
    out_las: str,
    cad_pts_xyz: np.ndarray,
    cad_rgbs_u8: np.ndarray,
    progress: Optional[Callable[[int, str], None]] = None,
) -> None:
    import os

    import laspy

    os.makedirs(os.path.dirname(os.path.abspath(out_las)), exist_ok=True)

    if cad_pts_xyz.ndim != 2 or cad_pts_xyz.shape[1] != 3:
        raise ValueError("cad_pts_xyz must be Nx3")
    if cad_rgbs_u8.ndim != 2 or cad_rgbs_u8.shape[1] != 3:
        raise ValueError("cad_rgbs_u8 must be Nx3")
    if cad_rgbs_u8.shape[0] != cad_pts_xyz.shape[0]:
        raise ValueError("cad_rgbs_u8 length must match cad_pts_xyz")

    try:
        if progress is not None:
            progress(55, "Чтение LAS")
        with laspy.open(cloud_path) as lf:
            hdr = lf.header
            total = int(getattr(hdr, "point_count", 0) or 0)

            chunks_xyz: List[np.ndarray] = []
            chunks_rgb: List[np.ndarray] = []
            read_count = 0
            chunk_size = 2_000_000
            for points in lf.chunk_iterator(chunk_size):
                x = np.asarray(points.x, dtype=np.float64)
                y = np.asarray(points.y, dtype=np.float64)
                z = np.asarray(points.z, dtype=np.float64)
                chunks_xyz.append(np.column_stack([x, y, z]))

                pf = hdr.point_format
                has_rgb = ("red" in pf.dimension_names) and ("green" in pf.dimension_names) and ("blue" in pf.dimension_names)
                if has_rgb:
                    r = np.asarray(points.red, dtype=np.uint16)
                    g = np.asarray(points.green, dtype=np.uint16)
                    b = np.asarray(points.blue, dtype=np.uint16)
                    chunks_rgb.append(np.column_stack([r, g, b]))

                read_count += int(x.size)
                if progress is not None and total > 0:
                    p = 55 + int(20 * min(1.0, read_count / float(total)))
                    progress(p, "Чтение LAS")

            base_xyz = np.vstack(chunks_xyz) if chunks_xyz else np.zeros((0, 3), dtype=np.float64)
            base_rgb16 = np.vstack(chunks_rgb) if chunks_rgb else None

    except Exception as e:
        low = str(cloud_path).lower()
        if low.endswith(".laz"):
            raise ValueError(
                "Не удалось прочитать LAZ. Для LAZ нужна поддержка сжатия (laszip/lazrs). "
                "Поставьте lazrs или используйте входной LAS.\n"
                f"details={e}"
            )
        raise

    # Ensure output can store RGB. If the input point format already supports it,
    # keep it. Otherwise upgrade to the closest RGB-capable format.
    pf = hdr.point_format
    has_rgb = ("red" in pf.dimension_names) and ("green" in pf.dimension_names) and ("blue" in pf.dimension_names)

    out_pf_id = pf.id
    if not has_rgb:
        out_pf_id = 2 if pf.id <= 5 else 7

    out_hdr = laspy.LasHeader(point_format=out_pf_id, version=hdr.version)
    out_hdr.scales = hdr.scales
    out_hdr.offsets = hdr.offsets

    out = laspy.LasData(out_hdr)

    # Copy XYZ from base and append CAD XYZ
    all_xyz = np.vstack([base_xyz, cad_pts_xyz.astype(np.float64, copy=False)])
    out.x = all_xyz[:, 0]
    out.y = all_xyz[:, 1]
    out.z = all_xyz[:, 2]

    # Fill RGB: base points get black if they did not have RGB
    n_base = base_xyz.shape[0]
    n_cad = cad_pts_xyz.shape[0]
    rgb16 = np.zeros((n_base + n_cad, 3), dtype=np.uint16)

    if has_rgb and base_rgb16 is not None and base_rgb16.shape[0] == n_base:
        rgb16[:n_base, :] = base_rgb16

    rgb16[n_base:, :] = cad_rgbs_u8.astype(np.uint16) * 257
    out.red = rgb16[:, 0]
    out.green = rgb16[:, 1]
    out.blue = rgb16[:, 2]

    if progress is not None:
        progress(95, "Запись LAS")
    out.write(out_las)
    if progress is not None:
        progress(100, "Готово")


def export_combined_las_with_cad_points(
    *,
    cloud_path: str,
    out_las: str,
    cad_pts_xyz: np.ndarray,
    cad_rgbs_u8: np.ndarray,
    progress: Optional[Callable[[int, str], None]] = None,
) -> None:
    _write_combined_las_with_cad_points(
        cloud_path=cloud_path,
        out_las=out_las,
        cad_pts_xyz=cad_pts_xyz,
        cad_rgbs_u8=cad_rgbs_u8,
        progress=progress,
    )


@dataclass(frozen=True)
class SamplePoint:
    x: float
    y: float
    poly_id: int
    z: Optional[float] = None


def run(
    dxf_path: str,
    cloud_path: str,
    out_xyz: Optional[str],
    step_m: float,
    layer: Optional[str],
    assume_same_crs: bool,
    cad_crs_str: Optional[str],
    cloud_crs_str: Optional[str],
    z_mode: str,
    z_offset: float,
    z_radius_m: float,
    z_k: int,
    z_quantile: float,
    las_max_points: Optional[int],
    write_poly_id: bool,
    out_rgb: bool,
    rgb: Tuple[int, int, int],
    layers_selected: Optional[Iterable[str]] = None,
    layer_colors: Optional[Dict[str, Tuple[int, int, int]]] = None,
    all_layers_one_color: bool = False,
    write_combined_las: bool = False,
    out_las: Optional[str] = None,
    write_sf: bool = False,
    sf_mode: str = "const",
    sf_value: float = 1.0,
    progress: Optional[Callable[[int, str], None]] = None,
) -> None:
    if progress is not None:
        progress(0, "Старт")

    if progress is not None:
        progress(2, "Чтение DXF")
    if layer_colors is not None or layers_selected is not None:
        polys_with_layer = extract_dxf_polylines_with_layer(dxf_path, layers=layers_selected)
        polylines = [pl for _, pl in polys_with_layer]
        poly_layers = [ln for ln, _ in polys_with_layer]
    else:
        polylines = extract_dxf_polylines(dxf_path, layer=layer)
        poly_layers = ["" for _ in polylines]

    if progress is not None:
        progress(8, "Дискретизация линий")
    samples: List[SamplePoint] = []
    sample_layers: List[str] = []
    for poly_id, pl in enumerate(polylines):
        for x, y, z in densify_polyline(pl, step_m=step_m):
            samples.append(SamplePoint(x=x, y=y, z=z, poly_id=poly_id))
            sample_layers.append(poly_layers[poly_id] if poly_id < len(poly_layers) else "")

    xy_all: List[Tuple[float, float]] = [(s.x, s.y) for s in samples]

    if not assume_same_crs:
        cad_crs = parse_crs(cad_crs_str)
        cloud_crs = parse_crs(cloud_crs_str)
        tr = make_transformer(cad_crs, cloud_crs)
        if tr is not None:
            xs, ys = zip(*xy_all)
            tx, ty = tr.transform(xs, ys)
            xy_all = list(zip(map(float, tx), map(float, ty)))

    bbox = compute_bbox(xy_all)

    if not cloud_path.lower().endswith((".las", ".laz")):
        raise ValueError("Only LAS/LAZ is supported")

    mode = z_mode.lower()

    if mode.startswith("surface") or mode in ("p95",):
        if progress is not None:
            progress(15, "Чтение LAS (для Z)")
        cloud_xyz = read_las_points_in_bbox(cloud_path, bbox=bbox, max_points=las_max_points)
        zs = cloud_xyz[:, 2]
        fallback_z = pick_constant_z(zs, mode="median", offset=0.0)
        samples_xy = np.array(xy_all, dtype=np.float64)

        offset_val = 0.0
        if mode in ("surface_offset", "p95"):
            offset_val = float(z_offset)
        if progress is not None:
            progress(40, "Расчет Z")
        def _z_prog(p: int) -> None:
            if progress is None:
                return
            pp = max(0, min(100, int(p)))
            progress(40 + int(7 * pp / 100), "Расчет Z")

        z_vals = surface_z_from_neighbors(
            cloud_xyz,
            samples_xy,
            radius_m=z_radius_m,
            k=z_k,
            quantile=z_quantile,
            fallback_z=fallback_z,
            offset=offset_val,
            progress=_z_prog if progress is not None else None,
            batch_size=512,
            method="fast",
        )
        pts = [Point3D(x=float(x), y=float(y), z=float(z)) for (x, y), z in zip(xy_all, z_vals)]
    else:
        raise ValueError("Unsupported z_mode")

    if write_sf:
        mode_sf = (sf_mode or "const").lower()
        if mode_sf == "poly_id":
            sf = [float(s.poly_id) for s in samples]
        else:
            sf = [float(sf_value)] * len(samples)
        if out_xyz:
            write_xyz_with_sf(out_xyz, pts, sf)

    if out_xyz:
        if progress is not None:
            progress(48, "Запись XYZ")

        if out_rgb:
            if all_layers_one_color or not layer_colors:
                r, g, b = rgb
                write_xyzrgb(out_xyz, pts, ColorRGB(r=r, g=g, b=b))
            else:
                rgbs = [layer_colors.get(ln, rgb) for ln in sample_layers]
                write_xyzrgb_per_point(out_xyz, pts, rgbs)
        elif write_poly_id:
            write_xyz_with_id(out_xyz, pts, [s.poly_id for s in samples])
        else:
            write_xyz(out_xyz, pts)

        if progress is not None:
            progress(52, "XYZ записан")

    if write_combined_las:
        if not out_las:
            raise ValueError("out_las must be provided when write_combined_las=True")

        cad_xyz = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64)
        if all_layers_one_color or not layer_colors:
            cad_rgbs = np.tile(np.array(rgb, dtype=np.uint8), (cad_xyz.shape[0], 1))
        else:
            cad_rgbs = np.array([layer_colors.get(ln, rgb) for ln in sample_layers], dtype=np.uint8)

        _write_combined_las_with_cad_points(
            cloud_path=cloud_path,
            out_las=out_las,
            cad_pts_xyz=cad_xyz,
            cad_rgbs_u8=cad_rgbs,
            progress=progress,
        )
