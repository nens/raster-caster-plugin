# RasterCaster
**Make DEMs and other rasters from polygons with a specific gradient definition for each polygon.**

## Introduction
The RasterCaster allows the user to create digital elevation models (GeoTIFF) from vector data (points, lines and polygons). Elevation is a continous variable and therefore better represented by a raster than polygons or other vector formats. However, raster data is much harder to edit than vector data. RasterCaster bridges this gap. The user makes a set of polygons that cover the area of interest and do not overlap. The polygons may be hand-drawn directly into GIS, but can also be derived from landscape desings (usually CAD drawings). 

The polygons can be seen as ‘molds’, that are used to ‘cast’ the elevation map into. Each polygon contains a definition of the altitude variations within it. Simple elevation profiles (e.g. flat building footprints) can be cast using a simple definition, while at the same time the RasterCaster offers the user flexibility to add more complex shapes (e.g. the exact shape of a retention basin). Currently, molds can be defined in four different way - see under Definition Types.

The RasterCaster can be used as a QGIS plugin. All vector data and settings are stored in a GeoPackage. 

## Requirements
QGIS >= 4.2.2

## Installation
- Go to https://github.com/nens/raster-caster-plugin/releases.
- Under _Assets_ in the most recent release, download the .zip.
- Open QGIS 4.2.2 or higher.
- Go to Plugins > Manage and Install Plugins > Install From ZIP > Browse to the downloaded zip > Install Plugin.

## User manual

The plugin adds a **Raster Caster** provider to the Processing Toolbox with two
algorithms.

### 1. Begin new

Creates an empty GeoPackage in the CRS of your choice (EPSG:28992 by default) and
loads its layers into the project:

- **surface** (Polygon): the areas to cast.
  - `definition_type = 'constant'`: `param_1` holds the elevation value.
  - `definition_type = 'tin'`: the elevation is interpolated from the elevation
    points inside the surface.
- **elevation point** (Point): supporting points for TIN surfaces. The `elevation`
  attribute is used to define height. Set `in_polygon_only` to true to restrict a
  point to the surfaces it actually lies inside.
- **settings** (non-spatial table): `variable` / `value` pairs used by *Cast*. It is
  filled with `pixel_size` = 0.5 and `elevation_point_search_radius` = 0.1; edit
  these values to change the casting behaviour.

### 2. Cast

Burns the surfaces into a new raster. Constant surfaces are rasterized with their
`param_1` value; TIN surfaces are interpolated from the elevation points they
contain.

- **Surface layer**: polygons with the `definition_type` and `param_1` fields, as
  created by *Begin new*.
- **Elevation point layer**: points with an `elevation` and `in_polygon_only` field.
- **Settings layer**: the non-spatial `settings` table with `variable` and `value`
  fields, holding:
  - `pixel_size`: output resolution, required when no input raster is given.
  - `elevation_point_search_radius`: search buffer around a TIN surface for
    elevation points that lie just outside it. Points with `in_polygon_only` set
    are not picked up by this buffer.
- **Input Raster**: optional; its extent and pixel size are used for the output. Surfaces are cast onto this raster.

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

Use `fullrelease` to update the release notes etc, tag the commits and generate a new Github release. Note that you'll need the qgis plugin for `zest.releaser` (https://github.com/nens/qgispluginreleaser).

```bash
fullrelease
```
