<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis styleCategories="Symbology|Labeling|Fields|Forms" version="3.40.6-Bratislava">
  <pipe-data-defined-properties>
    <Option type="Map">
      <Option value="" name="name" type="QString"/>
      <Option name="properties"/>
      <Option value="collection" name="type" type="QString"/>
    </Option>
  </pipe-data-defined-properties>
  <pipe>
    <provider>
      <resampling maxOversampling="2" zoomedOutResamplingMethod="nearestNeighbour" enabled="false" zoomedInResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer nodataColor="" band="1" alphaBand="-1" classificationMin="46.5800018" type="singlebandpseudocolor" classificationMax="141.6900024" opacity="1">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>MinMax</limits>
        <extent>UpdatedCanvas</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader labelPrecision="4" clip="0" colorRampType="INTERPOLATED" minimumValue="46.580001799999998" maximumValue="141.6900024" classificationMode="2">
          <colorramp name="[source]" type="gradient">
            <Option type="Map">
              <Option value="1,133,113,255,rgb:0.00392156862745098,0.52156862745098043,0.44313725490196076,1" name="color1" type="QString"/>
              <Option value="166,97,26,255,rgb:0.65098039215686276,0.38039215686274508,0.10196078431372549,1" name="color2" type="QString"/>
              <Option value="ccw" name="direction" type="QString"/>
              <Option value="0" name="discrete" type="QString"/>
              <Option value="gradient" name="rampType" type="QString"/>
              <Option value="rgb" name="spec" type="QString"/>
              <Option value="0.25;128,205,193,255,rgb:0.50196078431372548,0.80392156862745101,0.75686274509803919,1;rgb;ccw:0.5;245,245,245,255,rgb:0.96078431372549022,0.96078431372549022,0.96078431372549022,1;rgb;ccw:0.75;223,194,125,255,rgb:0.87450980392156863,0.76078431372549016,0.49019607843137253,1;rgb;ccw" name="stops" type="QString"/>
            </Option>
          </colorramp>
          <item value="46.580001831055" label="46.6" alpha="255" color="#018571"/>
          <item value="57.14777967665" label="57.1" alpha="255" color="#39a595"/>
          <item value="67.715557522245" label="67.7" alpha="255" color="#72c5b8"/>
          <item value="78.28333536784" label="78.3" alpha="255" color="#a7dad2"/>
          <item value="88.851113213435" label="88.9" alpha="255" color="#dbece9"/>
          <item value="99.41889105903" label="99.4" alpha="255" color="#f0eada"/>
          <item value="109.98666890462499" label="110" alpha="255" color="#e6d3a5"/>
          <item value="120.55444675022" label="121" alpha="255" color="#d9b772"/>
          <item value="131.122224595815" label="131" alpha="255" color="#bf8c46"/>
          <item value="141.69000244141" label="142" alpha="255" color="#a6611a"/>
          <rampLegendSettings maximumLabel="" suffix="" useContinuousLegend="1" prefix="" minimumLabel="" orientation="2" direction="0">
            <numericFormat id="basic">
              <Option type="Map">
                <Option name="decimal_separator" type="invalid"/>
                <Option value="6" name="decimals" type="int"/>
                <Option value="0" name="rounding_type" type="int"/>
                <Option value="false" name="show_plus" type="bool"/>
                <Option value="true" name="show_thousand_separator" type="bool"/>
                <Option value="false" name="show_trailing_zeros" type="bool"/>
                <Option name="thousand_separator" type="invalid"/>
              </Option>
            </numericFormat>
          </rampLegendSettings>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" colorizeGreen="128" grayscaleMode="0" colorizeOn="0" colorizeRed="255" colorizeStrength="100" invertColors="0" colorizeBlue="128"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
