from pathlib import Path
from typing import Any

from osgeo import ogr, osr
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QIcon

ICON_PATH = Path(__file__).parent.parent / "icon_algorithm.svg"
STYLING_DIR = Path(__file__).parent.parent / "styling"


class GenerateGeopackageAlgorithm(QgsProcessingAlgorithm):
    """Creates an empty Raster Caster GeoPackage (SRID 28992).

    Tables created:
        surface          – Polygon
        elevation_point  – PointZ
    """

    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "generate_geopackage"

    def displayName(self) -> str:
        return "Begin new"

    def icon(self) -> QIcon:
        return QIcon(str(ICON_PATH))

    def shortHelpString(self) -> str:
        return (
            "Creates an empty Raster Caster GeoPackage (EPSG:28992) and loads its "
            "layers into the project.\n\n"
            "Layers:\n"
            "- surface (Polygon): the areas to cast. Set 'definition_type' to "
            "'constant' or 'tin'. For 'constant', 'param_1' holds the elevation "
            "value; for 'tin' the elevation is interpolated from the elevation "
            "points inside the surface.\n"
            "- elevation_point (PointZ): supporting points for TIN surfaces. The "
            "'elevation' attribute is used, not the geometry Z value.\n\n"
            "Fill these layers, then run 'Cast Raster' to produce the raster."
        )

    def createInstance(self) -> "GenerateGeopackageAlgorithm":
        return GenerateGeopackageAlgorithm()

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                "Output GeoPackage",
                fileFilter="GeoPackage files (*.gpkg)",
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        output_path = self.parameterAsString(parameters, self.OUTPUT, context)

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(28992)

        driver = ogr.GetDriverByName("GPKG")
        ds = driver.CreateDataSource(output_path)

        self.create_surface(ds, srs)
        self.create_el_point(ds, srs)

        ds = None  # flush and close

        style_files = {
            "surface": STYLING_DIR / "surface.qml",
            "elevation_point": STYLING_DIR / "elevation_point.qml",
        }
        for name, style_path in style_files.items():
            uri = f"{output_path}|layername={name}"
            layer = QgsVectorLayer(uri, name, "ogr")
            layer.loadNamedStyle(str(style_path))
            # persist the style in the GeoPackage's layer_styles table
            error_message = layer.saveStyleToDatabase(name, "", True, "")
            if error_message:
                feedback.reportError(
                    f"Failed to save style for layer '{name}': {error_message}"
                )
            context.temporaryLayerStore().addMapLayer(layer)
            context.addLayerToLoadOnCompletion(
                layer.id(),
                QgsProcessingContext.LayerDetails(name, context.project(), name),
            )

        return {self.OUTPUT: output_path}

    @staticmethod
    def create_surface(ds: ogr.DataSource, srs: osr.SpatialReference) -> None:
        lyr = ds.CreateLayer("surface", srs, ogr.wkbPolygon)

        fld = ogr.FieldDefn("definition", ogr.OFTString)
        fld.SetDefault("'NULL'")
        lyr.CreateField(fld)
        lyr.CreateField(ogr.FieldDefn("definition_type", ogr.OFTString))
        lyr.CreateField(ogr.FieldDefn("comment", ogr.OFTString))
        for i in range(1, 7):
            lyr.CreateField(ogr.FieldDefn(f"param_{i}", ogr.OFTReal))

    @staticmethod
    def create_el_point(ds: ogr.DataSource, srs: osr.SpatialReference) -> None:
        lyr = ds.CreateLayer("elevation_point", srs, ogr.wkbPoint25D)
        lyr.CreateField(ogr.FieldDefn("comment", ogr.OFTString))
        lyr.CreateField(ogr.FieldDefn("elevation", ogr.OFTReal))
