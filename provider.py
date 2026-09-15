from pathlib import Path

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from raster_caster_plugin.algorithms.cast_raster_algorithm import CastRasterAlgorithm
from raster_caster_plugin.algorithms.generate_geopackage_algorithm import (
    GenerateGeopackageAlgorithm,
)

ICON_PATH = Path(__file__).parent / "icon.svg"


class RasterCasterProvider(QgsProcessingProvider):

    def id(self) -> str:
        return "raster_caster"

    def name(self) -> str:
        return "Raster Caster"

    def longName(self) -> str:
        return "Raster Caster"

    def icon(self) -> QIcon:
        return QIcon(str(ICON_PATH))

    def loadAlgorithms(self) -> None:
        self.addAlgorithm(GenerateGeopackageAlgorithm())
        self.addAlgorithm(CastRasterAlgorithm())
