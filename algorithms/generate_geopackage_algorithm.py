from pathlib import Path
from typing import Any

from osgeo import gdal, ogr, osr
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingOutputLayerDefinition,
    QgsProcessingParameterCrs,
    QgsProcessingParameterVectorDestination,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QIcon

ICON_PATH = Path(__file__).parent.parent / "icon.svg"
STYLING_DIR = Path(__file__).parent.parent / "styling"


class GenerateGeopackageAlgorithm(QgsProcessingAlgorithm):
    """Creates an empty Raster Caster GeoPackage.

    Tables created:
        surface          – Polygon
        elevation_point  – Point
    """

    CRS = "CRS"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "generate_geopackage"

    def displayName(self) -> str:
        return "Begin new"

    def icon(self) -> QIcon:
        return QIcon(str(ICON_PATH))

    def shortHelpString(self) -> str:
        return (
            "Creates an empty Raster Caster GeoPackage in the selected CRS "
            "(EPSG:28992 by default) and loads its layers into the project.\n\n"
            "Layers:\n\n"
            "- surface (Polygon): the areas to cast. 'definition_type' is required "
            "and must be 'constant' or 'tin'. For 'constant', 'param_1' holds the "
            "elevation value; for 'tin' the elevation is interpolated from the "
            "elevation points inside the surface.\n"
            "- elevation point (Point): supporting points for TIN surfaces. The "
            "'elevation' attribute is required and holds the height.\n\n"
            "Fill these layers, then run 'Cast' to produce the raster."
        )

    def createInstance(self) -> "GenerateGeopackageAlgorithm":
        return GenerateGeopackageAlgorithm()

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                "Coordinate reference system",
                defaultValue="EPSG:28992",
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT,
                "Output GeoPackage",
                type=QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )

    def checkParameterValues(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
    ) -> Any:
        value = parameters.get(self.OUTPUT)
        if isinstance(value, QgsProcessingOutputLayerDefinition):
            value = value.sink.staticValue()
        if not value or value == QgsProcessing.TEMPORARY_OUTPUT:
            return False, (
                "Choose a file to save the GeoPackage to; a temporary file is not "
                "supported because the layers are meant to be edited and reused."
            )
        return super().checkParameterValues(parameters, context)

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        crs: QgsCoordinateReferenceSystem = self.parameterAsCrs(
            parameters, self.CRS, context
        )

        # set only when 'Open output file after running algorithm' is checked
        destination_value = parameters.get(self.OUTPUT)
        destination_project = (
            destination_value.destinationProject
            if isinstance(destination_value, QgsProcessingOutputLayerDefinition)
            else None
        )

        srs = osr.SpatialReference()
        if srs.SetFromUserInput(crs.authid() or crs.toWkt()) != 0:
            raise QgsProcessingException(
                f"Could not interpret the selected CRS: {crs.authid() or crs.toWkt()}"
            )

        driver = gdal.GetDriverByName("GPKG")
        ds = driver.Create(output_path, 0, 0, 0, gdal.GDT_Unknown)

        self.create_surface(ds, srs)
        self.create_el_point(ds, srs)

        ds.Close()  # flush and close

        style_files = {
            "surface": STYLING_DIR / "surface.qml",
            "elevation_point": STYLING_DIR / "elevation_point.qml",
        }
        if destination_project is not None:
            # drop the single layer the framework registered for the GeoPackage path
            layers_to_load = context.layersToLoadOnCompletion()
            layers_to_load.pop(output_path, None)
            context.setLayersToLoadOnCompletion(layers_to_load)

        for name, style_path in style_files.items():
            display_name = name.replace("_", " ")
            uri = f"{output_path}|layername={name}"
            layer = QgsVectorLayer(uri, display_name, "ogr")
            layer.loadNamedStyle(str(style_path))
            # persist the style in the GeoPackage's layer_styles table
            error_message = layer.saveStyleToDatabase(name, "", True, "")
            if error_message:
                feedback.reportError(
                    f"Failed to save style for layer '{name}': {error_message}"
                )
            if destination_project is None:
                continue
            context.temporaryLayerStore().addMapLayer(layer)
            context.addLayerToLoadOnCompletion(
                layer.id(),
                QgsProcessingContext.LayerDetails(
                    display_name, destination_project, name
                ),
            )

        return {self.OUTPUT: output_path}

    @staticmethod
    def create_surface(ds: gdal.Dataset, srs: osr.SpatialReference) -> None:
        lyr = ds.CreateLayer("surface", srs, ogr.wkbPolygon)

        fld = ogr.FieldDefn("definition", ogr.OFTString)
        fld.SetDefault("'NULL'")
        lyr.CreateField(fld)

        ds.AddFieldDomain(
            ogr.CreateCodedFieldDomain(
                "definition_type",
                "How the surface elevation is defined",
                ogr.OFTString,
                ogr.OFSTNone,
                {"constant": "Constant elevation", "tin": "TIN interpolation"},
            )
        )
        fld = ogr.FieldDefn("definition_type", ogr.OFTString)
        fld.SetNullable(False)
        fld.SetDomainName("definition_type")
        lyr.CreateField(fld)

        lyr.CreateField(ogr.FieldDefn("comment", ogr.OFTString))
        for i in range(1, 7):
            lyr.CreateField(ogr.FieldDefn(f"param_{i}", ogr.OFTReal))

    @staticmethod
    def create_el_point(ds: gdal.Dataset, srs: osr.SpatialReference) -> None:
        lyr = ds.CreateLayer("elevation_point", srs, ogr.wkbPoint)
        lyr.CreateField(ogr.FieldDefn("comment", ogr.OFTString))

        fld = ogr.FieldDefn("elevation", ogr.OFTReal)
        fld.SetNullable(False)
        lyr.CreateField(fld)
