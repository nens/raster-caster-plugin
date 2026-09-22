import math
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np
from osgeo import gdal, ogr
from osgeo.gdal import ApplyGeoTransform, InvGeoTransform
from scipy.interpolate import LinearNDInterpolator
from shapely import constrained_delaunay_triangles, from_wkb
from shapely.geometry import Point

from .utils import nearest_segment_projection, periodic_linear_interp


def insert_ring_points(ring_geom: Any, insertions: list) -> None:
    """Insert (segment index, x, y, z) points in the ring, keeping vertex order."""
    per_segment = defaultdict(list)
    for segment_index, x, y, z in insertions:
        per_segment[segment_index].append((x, y, z))

    new_points = []
    for index in range(ring_geom.GetPointCount() - 1):
        start = ring_geom.GetPoint(index)
        new_points.append(start)
        # Multiple points on one segment have to follow each other in the
        # direction of that segment, so order in distance to start vertex
        segment_points = sorted(
            per_segment.get(index, ()),
            # Drop Z, the elevations would otherwise dominate the ordering
            key=lambda point: math.dist(point[:2], start[:2]),
        )
        for point in segment_points:
            new_points.append(point)
    new_points.append(new_points[0])

    # SetPoint appends whenever the index is past the last point of the ring
    for index, (x, y, z) in enumerate(new_points):
        ring_geom.SetPoint(index, x, y, z)


def apply_constant(surface_path: str, surface_layer_name: str, out_ds: Any) -> None:
    gdal.Rasterize(
        out_ds,
        surface_path,
        layers=[surface_layer_name],
        attribute="param_1",
        where="definition_type = 'constant'",
    )


def apply_tin(
    surface_layer: Any,
    elev_point_layer: Any,
    out_ds: Any,
    distance: float,
    progress_callback: Callable[[float], None] | None = None,
) -> bool:
    # Retrieve tin surfaces
    surface_layer.SetAttributeFilter("definition_type = 'tin'")
    tin_surface_features = [f for f in surface_layer]
    surface_layer.SetAttributeFilter(None)

    out_geotransform = out_ds.GetGeoTransform()
    pixel_size = max(abs(out_geotransform[1]), abs(out_geotransform[5]))

    surface_count = len(tin_surface_features)
    if progress_callback is not None:
        progress_callback(0.0 if surface_count else 100.0)

    for surface_index, tin_surface in enumerate(tin_surface_features):
        # Convert surface polygons to PolygonZ
        tin_geom = tin_surface.GetGeometryRef()
        polygon_z = ogr.Geometry(ogr.wkbPolygon25D)
        for ring_index in range(tin_geom.GetGeometryCount()):
            source_ring = tin_geom.GetGeometryRef(ring_index)
            ring_z = ogr.Geometry(ogr.wkbLinearRing)
            for point_index in range(source_ring.GetPointCount()):
                x, y, _ = source_ring.GetPoint(point_index)
                ring_z.AddPoint(x, y, -9999.0)
            polygon_z.AddGeometry(ring_z)
        tin_geom = polygon_z

        # Get the elevation points in the polygon. The convex hull is used so that
        # points in holes or concave parts of the polygon are also considered.
        elev_point_layer.SetSpatialFilter(tin_geom.ConvexHull().Buffer(distance))
        elev_coords = np.array(
            [
                (
                    f.GetGeometryRef().GetX(),
                    f.GetGeometryRef().GetY(),
                    f[
                        "elevation"
                    ],  # Note that this is not the Z, but attribute "elevation"
                )
                for f in elev_point_layer
            ]
        )
        elev_point_layer.SetSpatialFilter(None)

        if len(elev_coords) < 1:
            if progress_callback is not None:
                progress_callback((surface_index + 1) / surface_count * 100.0)
            continue

        # Coincident elevation points would snap onto the same ring vertex or
        # insert a zero length ring segment, keep the first of each location
        _, first_occurrences = np.unique(elev_coords[:, :2], axis=0, return_index=True)
        elev_coords = elev_coords[np.sort(first_occurrences)]

        # Use 2D for determining nearest elevation point
        elev_xy = elev_coords[:, :2]  # drop Z

        # Loop over the rings (index 0 is exterior). Iterate over the holes
        # in reverse so removing one keeps the remaining ring indices valid.
        # Rings with no assigned elevation points will be used as pure masks
        mask_rings = []
        for ring_index in reversed(range(0, tin_geom.GetGeometryCount())):
            ring_geom = tin_geom.GetGeometryRef(ring_index)
            ring_vertices = np.array(
                [
                    ring_geom.GetPoint(index)[:2]  # drop Z
                    for index in range(ring_geom.GetPointCount() - 1)
                ]
            )

            # newaxis allows for broadcasting:
            # (distances[i, j] = elev_xy[i] - tin_vertices[j])
            distances = elev_xy[:, np.newaxis] - ring_vertices[np.newaxis, :]
            # Sum the squared x-distance and y-distance, and take the minimum
            nearest_vertex_indices = np.argmin(
                np.sum(distances * distances, axis=2), axis=1
            )

            (
                nearest_segment_indices,
                segment_projections,
                segment_distances,
            ) = nearest_segment_projection(elev_xy, ring_vertices)

            # Replace each nearest ring vertex Z-value with the elevation point
            # value (Note that this is not the Z-value, but the attribute value)
            # Only when it is not too far away, otherwise a vertex is inserted
            closing_point_index = ring_geom.GetPointCount() - 1
            assigned_an_elevation = False
            insertions = []
            inserted_per_segment: dict[int, list[tuple[float, float]]] = defaultdict(
                list
            )
            for elevation_point_index, (elevation_point, vertex_index) in enumerate(
                zip(elev_coords, nearest_vertex_indices)
            ):
                segment_index = int(nearest_segment_indices[elevation_point_index])
                projection = segment_projections[elevation_point_index]
                segment_start = ring_vertices[segment_index]
                segment_end = ring_vertices[(segment_index + 1) % len(ring_vertices)]
                # The elevation point sits beside a segment rather than on top of
                # one of its vertices, so the segment gets an extra vertex at the
                # projection of the elevation point. Projections that fall onto an
                # existing vertex are left to the snapping below, inserting them
                # would create a (close to) zero length segment.
                if (
                    segment_distances[elevation_point_index] <= distance
                    and np.hypot(*(projection - segment_start)) > 2 * pixel_size
                    and np.hypot(*(projection - segment_end)) > 2 * pixel_size
                ):
                    # Elevation points lined up perpendicular to a segment share
                    # their projection, only the first one is inserted
                    if any(
                        np.hypot(projection[0] - x, projection[1] - y) <= 2 * pixel_size
                        for x, y in inserted_per_segment[segment_index]
                    ):
                        continue
                    assigned_an_elevation = True
                    inserted_per_segment[segment_index].append(
                        (float(projection[0]), float(projection[1]))
                    )
                    # We'll add this point later to the ring
                    insertions.append(
                        (
                            segment_index,
                            float(projection[0]),
                            float(projection[1]),
                            elevation_point[2],
                        )
                    )
                    continue

                # If we continue here, the elevation point is close to a vertex
                x, y, z = ring_geom.GetPoint(int(vertex_index))
                # Only snap elevation points that are close enough to the ring
                # Hypot calculates Euclidean distance
                if np.hypot(elevation_point[0] - x, elevation_point[1] - y) > distance:
                    continue
                assigned_an_elevation = True
                ring_geom.SetPoint(int(vertex_index), x, y, elevation_point[2])
                if vertex_index == 0:
                    # The ring is closed, update both start and end
                    ring_geom.SetPoint(closing_point_index, x, y, elevation_point[2])

            if insertions:
                insert_ring_points(ring_geom, insertions)
                closing_point_index = ring_geom.GetPointCount() - 1
                # Refresh ring_vertices list, vertices can have been added above
                ring_vertices = np.array(
                    [
                        ring_geom.GetPoint(index)[:2]  # drop Z
                        for index in range(closing_point_index)
                    ]
                )

            # This ring does not have assigned elevation points, should only be used to
            # mask raster
            if not assigned_an_elevation:
                if ring_index == 0:
                    return False
                # Clone first, RemoveGeometry destroys the ring
                mask_rings.append(ring_geom.Clone())
                tin_geom.RemoveGeometry(ring_index)
            else:
                # Determine the individ. segment lengths and perimeter of geometry by
                # determining the norm between a vertex and the previous.
                # Validated in QGIS with Measurement tool (extract vertices)
                edge_lengths = np.linalg.norm(
                    np.roll(ring_vertices, -1, axis=0) - ring_vertices,
                    axis=1,
                )
                # Validated in QGIS with $perimeter
                perimeter = float(np.sum(edge_lengths))

                ring_vertices_z = np.array(
                    [
                        ring_geom.GetPoint(index)[2]
                        for index in range(len(ring_vertices))
                    ]
                )
                known_vertices_mask = ring_vertices_z != -9999.0
                # Calc the distance along the perimeter to the start of each vertex.
                # Take cumulutive sum up to second last edge, prepend with 0.0 for
                # first vertex. Note that the final arc (returning to first vertex)
                # is excluded.
                arc_lengths = np.concatenate(([0.0], np.cumsum(edge_lengths[:-1])))
                if perimeter > 0 and np.any(known_vertices_mask):
                    ring_vertices_z[~known_vertices_mask] = periodic_linear_interp(
                        arc_lengths[~known_vertices_mask],
                        arc_lengths[known_vertices_mask],
                        ring_vertices_z[known_vertices_mask],
                        period=perimeter,
                    )
                    # Set the newly calculated elevations to the geometry
                    for vertex_index, z in enumerate(ring_vertices_z):
                        x, y, _ = ring_geom.GetPoint(vertex_index)
                        ring_geom.SetPoint(vertex_index, x, y, z)
                    x, y, _ = ring_geom.GetPoint(0)
                    ring_geom.SetPoint(closing_point_index, x, y, ring_vertices_z[0])

        # Wrap the mask rings in polygons so pixels can be tested against them
        mask_polygons = []
        for mask_ring in mask_rings:
            mask_polygon = ogr.Geometry(ogr.wkbPolygon)
            mask_polygon.AddGeometry(mask_ring)
            mask_polygons.append(from_wkb(bytes(mask_polygon.ExportToWkb())))

        # Determine constrained delaunay triangulation
        shapely_polygon = from_wkb(bytes(tin_geom.ExportToWkb()))
        triangles = constrained_delaunay_triangles(shapely_polygon)

        # Apply interpolation to raster
        band = out_ds.GetRasterBand(1)
        band.SetNoDataValue(-9999.0)
        geotransform = out_ds.GetGeoTransform()
        minx, px_width, _, maxy, _, px_height = geotransform
        raster_array = band.ReadAsArray()

        for triangle in triangles.geoms:
            coords = list(triangle.exterior.coords)[:-1]
            if len(coords) != 3:
                return False

            # Sort so a triangle always yields the same interpolator, regardless of
            # the vertex order the triangulation happened to emit, LinearNDInterpolator
            # can have a numerical noise depending on the order.
            coords.sort()
            tri_points = np.array([(coord[0], coord[1]) for coord in coords])
            tri_z = np.array([coord[2] for coord in coords])
            # Qhull judges degeneracy against the magnitude of the coordinates, so
            # sliver triangles are rejected on map coordinates but not on local ones
            origin = tri_points[0]
            interp = LinearNDInterpolator(
                tri_points - origin, tri_z, fill_value=-9999.0
            )

            # Convert triangle bounds to raster pixel coordinates
            min_tri_x, min_tri_y, max_tri_x, max_tri_y = triangle.bounds
            inv_geotransform = InvGeoTransform(geotransform)

            col_start_float, row_start_float = ApplyGeoTransform(
                inv_geotransform, min_tri_x, max_tri_y
            )
            col_end_float, row_end_float = ApplyGeoTransform(
                inv_geotransform, max_tri_x, min_tri_y
            )

            # Clamping to prevent setting of pixels outside the raster
            col_start = max(0, int(np.floor(col_start_float)) - 1)
            col_end = min(raster_array.shape[1], int(np.ceil(col_end_float)) + 1)
            row_start = max(0, int(np.floor(row_start_float)) - 1)
            row_end = min(raster_array.shape[0], int(np.ceil(row_end_float)) + 1)

            for row in range(row_start, row_end):
                for col in range(col_start, col_end):
                    # Test pixel centers
                    px_x = minx + (col + 0.5) * px_width
                    px_y = maxy + (row + 0.5) * px_height
                    pixel = Point(px_x, px_y)
                    if not triangle.covers(pixel):
                        continue
                    # Masked rings are not set
                    if any(
                        mask_polygon.covers(pixel) for mask_polygon in mask_polygons
                    ):
                        continue
                    raster_array[row, col] = interp(px_x - origin[0], px_y - origin[1])

        band.WriteArray(raster_array)

        if progress_callback is not None:
            progress_callback((surface_index + 1) / surface_count * 100.0)
    return True
