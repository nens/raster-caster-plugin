import math
from pathlib import Path
from typing import Any

from osgeo import gdal, ogr
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
)
from qgis.PyQt.QtGui import QIcon

from .casting import apply_constant, apply_tin

ICON_PATH = Path(__file__).parent.parent / "icon.svg"


class CastRasterAlgorithm(QgsProcessingAlgorithm):
    """Skeleton algorithm — implementation pending."""

    INPUT_SURFACE = "INPUT_SURFACE"
    INPUT_ELEVATION_POINTS = "INPUT_ELEVATION_POINTS"
    INPUT_RASTER = "INPUT_RASTER"
    PIXEL_SIZE = "PIXEL_SIZE"
    SNAPPING_DISTANCE = "SNAPPING_DISTANCE"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "cast_raster"

    def displayName(self) -> str:
        return "Cast"

    def icon(self) -> QIcon:
        return QIcon(str(ICON_PATH))

    def shortHelpString(self) -> str:
        return (
            "Casts elevation values onto a new raster using a surface polygon layer "
            "and an elevation point layer. Surfaces with definition_type 'constant' "
            "are burned in with their 'param_1' value; surfaces with 'tin' are "
            "interpolated from the elevation points they contain. The output extent "
            "follows the extent of the surface layer.\n\n"
            "Parameters:\n"
            "- Surface layer: polygons with the 'definition_type' and 'param_1' "
            "fields, as created by 'Begin new'.\n"
            "- Elevation point layer: points with an 'elevation' field.\n"
            "- Input Raster: optional; optional; its extent and pixel size are used"
            " for the output. Surfaces are cast onto this raster.\n"
            "- Pixel Size: output resolution, required when no input raster is given.\n"
            "- Snapping distance: search buffer around a TIN surface for elevation "
            "points that lie just outside it."
        )

    def createInstance(self) -> "CastRasterAlgorithm":
        return CastRasterAlgorithm()

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_SURFACE,
                "Surface layer",
                types=[QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_ELEVATION_POINTS,
                "Elevation point layer",
                types=[QgsProcessing.SourceType.TypeVectorPoint],
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_RASTER,
                "Input Raster",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PIXEL_SIZE,
                "Pixel Size",
                type=QgsProcessingParameterNumber.Type.Double,
                optional=True,
                minValue=0.0,
                defaultValue=0.5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SNAPPING_DISTANCE,
                "Snapping distance",
                type=QgsProcessingParameterNumber.Type.Double,
                minValue=0.0,
                defaultValue=3.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Output Raster",
            )
        )

    def checkParameterValues(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
    ) -> Any:
        raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        pixel_size = self.parameterAsDouble(parameters, self.PIXEL_SIZE, context)
        if raster is None and (self.PIXEL_SIZE not in parameters or pixel_size <= 0):
            return False, "Pixel Size is required when no Input Raster is provided."
        return super().checkParameterValues(parameters, context)

    @staticmethod
    def validateLayers(surface_layer: Any, point_layer: Any) -> None:
        if surface_layer.GetFeatureCount() == 0:
            raise QgsProcessingException("The surface layer has no features.")

        surface_defn = surface_layer.GetLayerDefn()
        for field_name in ("definition_type", "param_1"):
            if surface_defn.GetFieldIndex(field_name) < 0:
                raise QgsProcessingException(
                    f"The surface layer has no '{field_name}' field."
                )

        for feature in surface_layer:
            definition_type = feature.GetField("definition_type")
            if definition_type not in ("constant", "tin"):
                raise QgsProcessingException(
                    f"Surface {feature.GetFID()}: 'definition_type' must be "
                    f"'constant' or 'tin', got {definition_type!r}."
                )
            if definition_type == "constant" and not feature.IsFieldSetAndNotNull(
                "param_1"
            ):
                raise QgsProcessingException(
                    f"Surface {feature.GetFID()}: 'param_1' is required when "
                    "'definition_type' is 'constant'."
                )

        if point_layer.GetLayerDefn().GetFieldIndex("elevation") < 0:
            raise QgsProcessingException(
                "The elevation point layer has no 'elevation' field."
            )

        for feature in point_layer:
            if not feature.IsFieldSetAndNotNull("elevation"):
                raise QgsProcessingException(
                    f"Elevation point {feature.GetFID()}: 'elevation' is required."
                )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        snapping_distance = self.parameterAsDouble(
            parameters, self.SNAPPING_DISTANCE, context
        )

        # Writes a temporary GeoPackage (if needed) for sources GDAL cannot
        # read directly
        surface_path, surface_name = (
            self.parameterAsCompatibleSourceLayerPathAndLayerName(
                parameters, self.INPUT_SURFACE, context, ["gpkg"], "gpkg", feedback
            )
        )
        points_path, points_name = (
            self.parameterAsCompatibleSourceLayerPathAndLayerName(
                parameters,
                self.INPUT_ELEVATION_POINTS,
                context,
                ["gpkg"],
                "gpkg",
                feedback,
            )
        )

        surface_ds = ogr.Open(surface_path)
        if surface_ds is None:
            raise QgsProcessingException(
                f"Could not open the surface layer source: {surface_path}"
            )
        points_ds = ogr.Open(points_path)
        if points_ds is None:
            surface_ds.Close()
            raise QgsProcessingException(
                f"Could not open the elevation point layer source: {points_path}"
            )

        # Closes the sources even when an exception leaves references alive
        with surface_ds, points_ds:
            surface_layer = (
                surface_ds.GetLayerByName(surface_name)
                if surface_name
                else surface_ds.GetLayer(0)
            )
            point_layer = (
                points_ds.GetLayerByName(points_name)
                if points_name
                else points_ds.GetLayer(0)
            )
            self.validateLayers(surface_layer, point_layer)

            if raster is not None:
                pixel_size = raster.rasterUnitsPerPixelX()
            else:
                pixel_size = self.parameterAsDouble(
                    parameters, self.PIXEL_SIZE, context
                )

            extent = surface_layer.GetExtent()  # (minX, maxX, minY, maxY)
            srs = surface_layer.GetSpatialRef()

            # Create the new raster
            if raster is not None:
                src_ds = gdal.Open(raster.source())
                driver = gdal.GetDriverByName("GTiff")
                out_ds = driver.CreateCopy(output_path, src_ds)
                src_ds = None
            else:
                min_x, max_x, min_y, max_y = extent
                cols = math.ceil((max_x - min_x) / pixel_size)
                rows = math.ceil((max_y - min_y) / pixel_size)
                if cols < 1 or rows < 1:
                    raise QgsProcessingException(
                        f"The extent of the surface layer ({min_x}, {min_y}) - "
                        f"({max_x}, {max_y}) is too small for the requested pixel "
                        f"size of {pixel_size}."
                    )

                driver = gdal.GetDriverByName("GTiff")
                out_ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32)
                out_ds.SetGeoTransform((min_x, pixel_size, 0, max_y, 0, -pixel_size))
                out_ds.SetProjection(srs.ExportToWkt())

                band = out_ds.GetRasterBand(1)
                band.SetNoDataValue(-9999.0)

            try:
                apply_constant(surface_path, surface_layer.GetName(), out_ds)
                apply_tin(
                    surface_layer,
                    point_layer,
                    out_ds,
                    snapping_distance,
                    feedback.setProgress,
                )
            finally:
                out_ds.Close()

        return {self.OUTPUT: output_path}
