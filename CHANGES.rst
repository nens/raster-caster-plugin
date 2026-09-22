Raster Caster changelog
===============================

0.3 (unreleased)
----------------

- Added an optional progress callback to ``apply_tin`` that reports the
  percentage of processed TIN surfaces.
- Connected the cast algorithm to the Processing progress bar.
- Dropped coincident elevation points before snapping, and only insert the
  first of several elevation points that project onto the same spot of a ring
  segment.
- Interpolate triangles on coordinates local to the triangle, so sliver
  triangles are no longer rejected as degenerate by Qhull.
- Removed the debug code that wrote the triangulation to a GeoPackage.
- Added validation on input layers.
- Elevation point layer is now a Point layer, not PointZ.
- input files are now properly unlocked in case of validation errors.
- Several fields are now no longer nullable (elevation, definition-type).
- Inputs are now layers instead of geopackage.
- Generate geopackage: no longer able to save to temporary file.
- Set styling to output raster.

0.2 (2026-09-21)
----------------

- Update of documentation and clean up.


0.1 (2026-09-15)
----------------

- Initial commit
