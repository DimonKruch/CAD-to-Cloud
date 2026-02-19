import argparse
from typing import Optional

from cad_boundary_to_cc.pipeline import run


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert DXF boundary to XYZ points for CloudCompare overlay")
    p.add_argument("--dxf", required=True, help="Input DXF with boundary polylines")
    p.add_argument("--cloud", required=True, help="Input cloud LAS/LAZ")
    p.add_argument("--out", required=True, help="Output XYZ path")
    p.add_argument("--step-m", type=float, default=1.0, help="Densification step in meters")
    p.add_argument(
        "--density",
        default=None,
        choices=["low", "medium", "high", "ultra"],
        help="Preset for point density (overrides --step-m): low=2.0, medium=1.0, high=0.5, ultra=0.2",
    )
    p.add_argument("--layer", default=None, help="DXF layer name to filter (optional)")

    crs = p.add_argument_group("CRS")
    crs.add_argument(
        "--assume-same-crs",
        action="store_true",
        help="Assume CAD and cloud are in same CRS (no transform). Recommended default.",
    )
    crs.add_argument("--cad-crs", default=None, help="CAD CRS (EPSG code like 3857 or PROJ string)")
    crs.add_argument("--cloud-crs", default=None, help="Cloud CRS (EPSG code like 3857 or PROJ string)")

    z = p.add_argument_group("Z")
    z.add_argument(
        "--z-mode",
        default="p95",
        choices=["p95", "median", "surface_p10"],
        help="Z assignment: constant (p95/median) or relief-following (surface_p10)",
    )
    z.add_argument("--z-offset", type=float, default=1.0, help="Offset added to Z (meters)")
    z.add_argument("--z-radius-m", type=float, default=2.0, help="For surface_p10: neighbor search radius (meters)")
    z.add_argument("--z-k", type=int, default=64, help="For surface_p10: max neighbors to consider")
    z.add_argument("--z-quantile", type=float, default=0.10, help="For surface_p10: quantile of neighbor Z")
    z.add_argument(
        "--las-max-points",
        type=int,
        default=2_000_000,
        help="Max LAS points to load for surface mode (subsamples if more). Set 0 to disable cap.",
    )

    out = p.add_argument_group("Output")
    out.add_argument("--write-poly-id", action="store_true", help="Write 4th column with polyline id")
    out.add_argument(
        "--rgb",
        default="255,0,0",
        help="Write XYZRGB with fixed color (default red). Format: R,G,B. Use --no-rgb to disable.",
    )
    out.add_argument(
        "--no-rgb",
        action="store_true",
        help="Disable XYZRGB output and write plain XYZ (or XYZ+id if --write-poly-id).",
    )

    dxfz = p.add_argument_group("DXF Z")
    dxfz.add_argument(
        "--prefer-dxf-z",
        action="store_true",
        help="If DXF provides Z for vertices, use it (no sampling from cloud).",
    )

    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    las_max_points = None if args.las_max_points == 0 else int(args.las_max_points)

    step_m = float(args.step_m)
    if args.density is not None:
        preset = args.density.lower()
        step_m = {
            "low": 2.0,
            "medium": 1.0,
            "high": 0.5,
            "ultra": 0.2,
        }[preset]

    rgb_s = str(args.rgb)
    try:
        parts = [int(x.strip()) for x in rgb_s.split(",")]
        if len(parts) != 3:
            raise ValueError
        rgb = (max(0, min(255, parts[0])), max(0, min(255, parts[1])), max(0, min(255, parts[2])))
    except Exception:
        raise ValueError("--rgb must be in format R,G,B with values 0..255")

    run(
        dxf_path=args.dxf,
        cloud_path=args.cloud,
        out_xyz=args.out,
        step_m=step_m,
        layer=args.layer,
        assume_same_crs=True if not (args.cad_crs or args.cloud_crs) else args.assume_same_crs,
        cad_crs_str=args.cad_crs,
        cloud_crs_str=args.cloud_crs,
        z_mode=args.z_mode,
        z_offset=args.z_offset,
        z_radius_m=args.z_radius_m,
        z_k=args.z_k,
        z_quantile=args.z_quantile,
        las_max_points=las_max_points,
        write_poly_id=args.write_poly_id,
        prefer_dxf_z=args.prefer_dxf_z,
        out_rgb=not args.no_rgb and (not args.write_poly_id),
        rgb=rgb,
    )


if __name__ == "__main__":
    main()
