import numpy as np
import pytest
from numpy.testing import assert_allclose
from osgeo import ogr

from algorithms.casting import insert_ring_points
from algorithms.utils import nearest_segment_projection, periodic_linear_interp

NODATA = -9999.0


def make_ring(vertices: list[tuple[float, float, float]]) -> ogr.Geometry:
    """Build a closed LinearRing from vertices, the closing point is added."""
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y, z in vertices:
        ring.AddPoint(x, y, z)
    ring.AddPoint(*vertices[0])
    return ring


def ring_points(ring: ogr.Geometry) -> list[tuple[float, float, float]]:
    return [ring.GetPoint(index) for index in range(ring.GetPointCount())]


class TestInsertRingPoints:
    """Tests for insert_ring_points."""

    def setup_method(self) -> None:
        self.square = [
            (0.0, 0.0, NODATA),
            (10.0, 0.0, NODATA),
            (10.0, 10.0, NODATA),
            (0.0, 10.0, NODATA),
        ]

    def test_single_insertion(self) -> None:
        ring = make_ring(self.square)
        insert_ring_points(ring, [(0, 5.0, 0.0, 1.5)])
        assert ring_points(ring) == [
            (0.0, 0.0, NODATA),
            (5.0, 0.0, 1.5),
            (10.0, 0.0, NODATA),
            (10.0, 10.0, NODATA),
            (0.0, 10.0, NODATA),
            (0.0, 0.0, NODATA),
        ]

    def test_ring_stays_closed(self) -> None:
        ring = make_ring(self.square)
        insert_ring_points(ring, [(1, 10.0, 4.0, 2.0)])
        points = ring_points(ring)
        assert points[0] == points[-1]

    def test_multiple_insertions_follow_segment_direction(self) -> None:
        # Supplied out of order, they have to end up ordered along the segment
        ring = make_ring(self.square)
        insert_ring_points(
            ring, [(0, 7.0, 0.0, 3.0), (0, 2.0, 0.0, 1.0), (0, 5.0, 0.0, 2.0)]
        )
        assert ring_points(ring)[:5] == [
            (0.0, 0.0, NODATA),
            (2.0, 0.0, 1.0),
            (5.0, 0.0, 2.0),
            (7.0, 0.0, 3.0),
            (10.0, 0.0, NODATA),
        ]

    def test_ordering_ignores_elevation(self) -> None:
        # Sorting on 3D distance would put the far point first, the start
        # vertex carries the NODATA Z
        ring = make_ring(self.square)
        insert_ring_points(ring, [(0, 2.0, 0.0, 1000.0), (0, 7.0, 0.0, -1000.0)])
        assert ring_points(ring)[1:3] == [(2.0, 0.0, 1000.0), (7.0, 0.0, -1000.0)]

    def test_insertion_on_closing_segment(self) -> None:
        ring = make_ring(self.square)
        insert_ring_points(ring, [(3, 0.0, 5.0, 4.0)])
        assert ring_points(ring) == [
            (0.0, 0.0, NODATA),
            (10.0, 0.0, NODATA),
            (10.0, 10.0, NODATA),
            (0.0, 10.0, NODATA),
            (0.0, 5.0, 4.0),
            (0.0, 0.0, NODATA),
        ]

    def test_insertions_on_several_segments(self) -> None:
        ring = make_ring(self.square)
        insert_ring_points(ring, [(2, 4.0, 10.0, 2.0), (0, 5.0, 0.0, 1.0)])
        assert ring_points(ring) == [
            (0.0, 0.0, NODATA),
            (5.0, 0.0, 1.0),
            (10.0, 0.0, NODATA),
            (10.0, 10.0, NODATA),
            (4.0, 10.0, 2.0),
            (0.0, 10.0, NODATA),
            (0.0, 0.0, NODATA),
        ]

    def test_existing_vertices_keep_their_elevation(self) -> None:
        vertices = [
            (0.0, 0.0, 1.0),
            (10.0, 0.0, 2.0),
            (10.0, 10.0, 3.0),
            (0.0, 10.0, 4.0),
        ]
        ring = make_ring(vertices)
        insert_ring_points(ring, [(1, 10.0, 6.0, 9.0)])
        assert ring_points(ring) == [
            (0.0, 0.0, 1.0),
            (10.0, 0.0, 2.0),
            (10.0, 6.0, 9.0),
            (10.0, 10.0, 3.0),
            (0.0, 10.0, 4.0),
            (0.0, 0.0, 1.0),
        ]


class TestNearestSegmentProjection:
    """Tests for nearest_segment_projection."""

    def setup_method(self) -> None:
        # Unit square, counter clockwise, without the closing vertex
        self.square = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])

    def test_point_outside_projects_on_nearest_segment(self) -> None:
        points = np.array([[0.5, -2.0]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist() == [0]
        assert_allclose(projections, [[0.5, 0.0]])
        assert_allclose(distances, [2.0])

    def test_point_inside_projects_on_nearest_segment(self) -> None:
        points = np.array([[0.75, 0.5]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist() == [1]
        assert_allclose(projections, [[1.0, 0.5]])
        assert_allclose(distances, [0.25])

    def test_point_on_ring_has_zero_distance(self) -> None:
        points = np.array([[1.0, 0.25]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist() == [1]
        assert_allclose(projections, [[1.0, 0.25]])
        assert_allclose(distances, [0.0], atol=1e-12)

    def test_projection_on_vertex_uses_an_adjoining_segment(self) -> None:
        # Beyond the corner, so both adjoining segments are equally near and
        # shapely may report either of them
        points = np.array([[2.0, -1.0]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist()[0] in (0, 1)
        assert_allclose(projections, [[1.0, 0.0]])
        assert_allclose(distances, [np.hypot(1.0, 1.0)])

    def test_projection_on_first_vertex(self) -> None:
        points = np.array([[-1.0, -1.0]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist()[0] in (0, 3)
        assert_allclose(projections, [[0.0, 0.0]])
        assert_allclose(distances, [np.hypot(1.0, 1.0)])

    def test_closing_segment(self) -> None:
        points = np.array([[-2.0, 0.5]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist() == [3]
        assert_allclose(projections, [[0.0, 0.5]])
        assert_allclose(distances, [2.0])

    def test_multiple_points(self) -> None:
        points = np.array([[0.5, -2.0], [0.75, 0.5], [-2.0, 0.5]])
        nearest, projections, distances = nearest_segment_projection(
            points, self.square
        )
        assert nearest.tolist() == [0, 1, 3]
        assert_allclose(projections, [[0.5, 0.0], [1.0, 0.5], [0.0, 0.5]])
        assert_allclose(distances, [2.0, 0.25, 2.0])

    def test_duplicate_vertex_is_skipped(self) -> None:
        # A zero length segment must not swallow the projection
        vertices = np.array(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        )
        points = np.array([[2.0, 0.5]])
        nearest, projections, distances = nearest_segment_projection(points, vertices)
        assert nearest.tolist() == [2]
        assert_allclose(projections, [[1.0, 0.5]])
        assert_allclose(distances, [1.0])


class TestPeriodicLinearInterp:
    """Tests for periodic_linear_interp."""

    def setup_method(self) -> None:
        self.xp = [90, 180, 270]
        self.fp = [1.0, 3.0, 2.0]
        self.period = 360

    def test_at_knot_points(self) -> None:
        result = periodic_linear_interp(
            np.array([90, 180, 270]), self.xp, self.fp, self.period
        )
        assert_allclose(result, [1.0, 3.0, 2.0])

    def test_between_knots(self) -> None:
        result = periodic_linear_interp(np.array([135]), self.xp, self.fp, self.period)
        assert_allclose(result, [2.0])

    def test_wrap_around_after_last_knot(self) -> None:
        result = periodic_linear_interp(np.array([360]), self.xp, self.fp, self.period)
        assert_allclose(result, [1.5])

    def test_wrap_around_before_first_knot(self) -> None:
        # x=45 is before xp[0]=90, shifted to 405
        # interp between (270, 2.0) and (450, 1.0): at 405 -> 2.0 - 135/180 = 1.25
        result = periodic_linear_interp(np.array([45]), self.xp, self.fp, self.period)
        assert_allclose(result, [1.25])

    def test_x_beyond_period(self) -> None:
        # x=450 should behave same as x=90
        result = periodic_linear_interp(np.array([450]), self.xp, self.fp, self.period)
        assert_allclose(result, [1.0])

    def test_negative_x(self) -> None:
        # x=-270 % 360 = 90
        result = periodic_linear_interp(np.array([-270]), self.xp, self.fp, self.period)
        assert_allclose(result, [1.0])

    def test_scalar_input(self) -> None:
        result = periodic_linear_interp(135, self.xp, self.fp, self.period)
        assert_allclose(result, 2.0)

    def test_array_input(self) -> None:
        x = np.array([90, 135, 180, 270, 360])
        result = periodic_linear_interp(x, self.xp, self.fp, self.period)
        assert_allclose(result, [1.0, 2.0, 3.0, 2.0, 1.5])

    def test_two_knot_points(self) -> None:
        xp = [0, 180]
        fp = [0.0, 10.0]
        result = periodic_linear_interp(np.array([90, 270]), xp, fp, 360)
        assert_allclose(result, [5.0, 5.0])

    def test_single_knot_point(self) -> None:
        # With one knot, the value is constant everywhere
        result = periodic_linear_interp(np.array([0, 90, 180]), [0], [5.0], 360)
        assert_allclose(result, [5.0, 5.0, 5.0])

    def test_unsorted_knots_rejected(self) -> None:
        with pytest.raises(ValueError):
            periodic_linear_interp(np.array([45]), [180, 0, 270], [2.0, 0.0, 3.0], 360)

    def test_duplicate_knots_rejected(self) -> None:
        # A zero length ring segment yields two knots at the same position
        with pytest.raises(ValueError):
            periodic_linear_interp(np.array([45]), [0, 90, 90], [0.0, 1.0, 5.0], 360)
