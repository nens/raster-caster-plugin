# Raster Caster

A QGIS plugin that casts elevation values onto a raster using surface polygons and
elevation points stored in a GeoPackage.

## Usage

The plugin adds a **Raster Caster** provider to the Processing Toolbox with two
algorithms.

### 1. Begin new

Creates an empty GeoPackage in the CRS of your choice (EPSG:28992 by default) and
loads its two layers into the project:

- **surface** (Polygon): the areas to cast.
  - `definition_type = 'constant'`: `param_1` holds the elevation value.
  - `definition_type = 'tin'`: the elevation is interpolated from the elevation
    points inside the surface.
- **elevation point** (PointZ): supporting points for TIN surfaces. The `elevation`
  attribute is used, not the geometry Z value.

### 2. Cast

Burns the surfaces into a new raster. Constant surfaces are rasterized with their
`param_1` value; TIN surfaces are interpolated from the elevation points they
contain.

- **Input GeoPackage**: a GeoPackage created by *Begin new*.
- **Input Raster**: optional; its extent and pixel size are used for the output. Surfaces are cast onto this raster.
- **Pixel Size**: output resolution, required when no input raster is given.
- **Snapping distance**: search buffer around a TIN surface for elevation points
  that lie just outside it.

Without an input raster, the output extent follows the extent of the surface layer.

## Development

Run the tests in the provided container:

```bash
docker compose build
docker compose run --rm qgis pytest
```

Build an installable plugin zip:

```bash
python zip_plugin.py
```
