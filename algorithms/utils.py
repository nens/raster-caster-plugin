import numpy as np
import shapely
from numpy.typing import ArrayLike, NDArray


def nearest_segment_projection(
    points: NDArray, vertices: NDArray
) -> tuple[NDArray, NDArray, NDArray]:
    """Project points on the closed ring formed by vertices.

    For each point, returns the index of the nearest segment (the segment
    starting at the vertex with that index), the projection of the point onto
    that segment, and the distance between the point and that projection.

    A projection landing exactly on a vertex is equally near to both adjoining
    segments, and either of the two may be reported.
    """
    # Two point line per segment, the last one closing the ring
    # Note that stack() creates a new axis/dimension
    segments = shapely.linestrings(
        np.stack([vertices, np.roll(vertices, -1, axis=0)], axis=1)
    )
    targets = shapely.points(points)

    nearest = shapely.STRtree(segments).nearest(targets)

    # shortest_line yields two coordinates per point,
    # the first point (projection on segment) and the second point is target itself.
    projections = shapely.get_coordinates(
        shapely.shortest_line(segments[nearest], targets)
    )[
        0::2
    ]  # remove target points from list
    distances = np.linalg.norm(points - projections, axis=1)

    return nearest, projections, distances


def periodic_linear_interp(
    x: ArrayLike, xp: ArrayLike, fp: ArrayLike, period: float
) -> NDArray:
    x = x % period

    xp = np.asarray(xp)
    fp = np.asarray(fp)

    # np.interp silently returns nonsense when the knots are not increasing,
    # a tie means the ring has a zero length segment
    if np.any(np.diff(xp) <= 0):
        raise ValueError("knot positions have to be increasing")

    # Duplicates the first knot point at position xp[0] + period (with its
    # corresponding value fp[0]), so np.interp can linearly interpolate across
    # the periodic boundary between the last and first knot points.
    xp2 = np.concatenate([xp, [xp[0] + period]])
    fp2 = np.concatenate([fp, [fp[0]]])

    # if x smaller than first control point, move to next period,
    # so it is surrounded by knots
    x2 = np.where(x < xp[0], x + period, x)

    return np.interp(x2, xp2, fp2)
