# ArcGIS Sliver Polygon Tools

![Version](https://img.shields.io/badge/version-1.4-blue)
![Platform](https://img.shields.io/badge/platform-ArcGIS%20Desktop%2010.x-2C7FB8)
![Language](https://img.shields.io/badge/language-Python%202.7-3776AB?logo=python&logoColor=white)
![Toolbox](https://img.shields.io/badge/toolbox-Python%20Toolbox-289C8E)
![License](https://img.shields.io/badge/license-GPL--3.0-green)

**English | [简体中文](README_ZH.md)**

A Python Toolbox for **ArcGIS Desktop 10.x / ArcMap / Python 2.7** that identifies sliver polygons and merges reviewed sliver polygons into suitable adjacent polygons.

Current version: **V1.4**.

> **Source:** [`SliverPolygonTools_ArcGIS10x_V1.4.pyt`](SliverPolygonTools_ArcGIS10x_V1.4.pyt)  
> **Environment:** ArcGIS Desktop 10.x / ArcMap / Python 2.7 / ArcPy

## Screenshots

<table>
  <tr>
    <td width="50%" align="center">
      <a href="assets/01_find_parameters.png"><img src="assets/01_find_parameters.png" alt="Find Sliver Polygons Parameters" width="100%"></a><br>
      <b>Find Sliver Polygons - Parameters</b>
    </td>
    <td width="50%" align="center">
      <a href="assets/02_find_result.png"><img src="assets/02_find_result.png" alt="Sliver Polygon Identification Result" width="100%"></a><br>
      <b>Sliver Polygon Identification Result</b>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <a href="assets/03_merge_parameters.png"><img src="assets/03_merge_parameters.png" alt="Merge Extracted Sliver Polygons Parameters" width="100%"></a><br>
      <b>Merge Extracted Sliver Polygons - Parameters</b>
    </td>
    <td width="50%" align="center">
      <a href="assets/04_merge_result.png"><img src="assets/04_merge_result.png" alt="Sliver Polygon Merge Result" width="100%"></a><br>
      <b>Sliver Polygon Merge Result</b>
    </td>
  </tr>
</table>

## Toolbox

- **1 - Find Sliver Polygons**
- **2 - Merge Extracted Sliver Polygons**

## Features

### 1. Find Sliver Polygons

The identification tool uses a two-stage rule: **scale conditions + shape conditions**.

**Scale indicators**
- Polygon area
- Minimum bounding rectangle width
- Equivalent average width: `2 × Area / Perimeter`

**Shape indicators**
- Length-width ratio: `L / W`
- Compactness: `4πA / P²`
- Shape index: `P / (2√(πA))`
- Perimeter-area ratio: `P² / A`

A polygon is flagged only when both the configured scale and shape rules are satisfied. This helps reduce false positives for naturally elongated features such as rivers and roads.

### 2. Merge Extracted Sliver Polygons

The merge tool takes two polygon inputs:

1. **Original polygon layer (DLTB)**
2. **Extracted and manually reviewed sliver polygons**

The tool spatially matches the extracted polygons back to the original DLTB, analyzes polygon neighbors, selects a target based on configured rules, and writes a complete modified DLTB.

Supported constraints include:
- Longest shared boundary
- Largest target area
- Smallest target area
- Attribute consistency
- Target area range
- Minimum shared boundary length
- Minimum overlap percentage

## Recommended Workflow

`Original DLTB → Identify → Manual review → Merge → Modified DLTB`

Manual review is recommended before batch geometry modification.

## Default Parameters

### Identification

| Parameter | Default |
|---|---:|
| Area upper limit | 1000 m² |
| Minimum bounding rectangle width upper limit | 5 m |
| Equivalent average width upper limit | 5 m |
| Scale rule | At least 1 condition |
| Length-width ratio lower limit | 5 |
| Compactness upper limit | 0.25 |
| Shape index lower limit | 2 |
| Perimeter-area ratio lower limit | 40 |
| Shape rule | At least 2 conditions |

### Merge

| Parameter | Default |
|---|---:|
| Target minimum area | 1000 m² |
| Minimum shared boundary | 1 m |
| Target priority | Longest shared boundary |
| Minimum overlap with original polygon | 80% |
| Merge into another sliver polygon | No |

These values are initial working defaults rather than universal standards. Adjust them for project scale, data characteristics, and business requirements.

## Installation

1. Download `SliverPolygonTools_ArcGIS10x_V1.4.pyt`.
2. Open ArcMap.
3. In ArcToolbox or Catalog, choose **Add Toolbox**.
4. Select the `.pyt` file.
5. Open **Sliver Polygon Processing Toolbox V1.4**.

## Requirements

- ArcGIS Desktop 10.x / ArcMap
- Python 2.7
- ArcPy
- Polygon data
- A projected coordinate system is recommended when meter/m² thresholds are used.

## Notes

- The input dataset is not modified directly; the tool writes a new output dataset.
- Test thresholds on representative samples before batch processing.
- Select attribute consistency fields when target polygons must remain in the same land-use, ownership, or business class.
- Features without a valid merge target are retained unchanged.
- There is no universal sliver threshold for every project; parameters should be calibrated to the actual data.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Copyright (c) 2026 Zhang Y.H.

This project is released under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE).

ArcGIS, ArcMap and ArcPy are Esri product or technology names. This project is not affiliated with or endorsed by Esri.

## Follow & Community

Follow the WeChat official account **测绘地信**, use the WeChat Mini Program **测绘地信**, or join the Knowledge Planet community **测绘地理信息共享中心**.

<table>
  <tr>
    <th width="33%">WeChat Official Account<br>微信公众号：测绘地信</th>
    <th width="33%">WeChat Mini Program<br>微信小程序：测绘地信</th>
    <th width="33%">Knowledge Planet<br>知识星球：测绘地理信息共享中心</th>
  </tr>
  <tr>
    <td align="center" valign="middle"><img src="https://raw.githubusercontent.com/zhangyhrs/GeoStar-Selector-QGIS/main/assets/wechat-official-account.png" alt="微信公众号：测绘地信" height="150"></td>
    <td align="center" valign="middle"><img src="https://raw.githubusercontent.com/zhangyhrs/GeoStar-Selector-QGIS/main/assets/wechat-mini-program.jpg" alt="微信小程序：测绘地信" height="150"></td>
    <td align="center" valign="middle"><img src="https://raw.githubusercontent.com/zhangyhrs/GeoStar-Selector-QGIS/main/assets/knowledge-planet.jpg" alt="知识星球：测绘地理信息共享中心" height="150"></td>
  </tr>
</table>

## Author

**Zhang Y.H.** · GitHub [@zhangyhrs](https://github.com/zhangyhrs)

Related projects: [SHP2KMZ Tool](https://github.com/zhangyhrs/SHP2KMZ_Tool) · [GeoStar Selector for QGIS](https://github.com/zhangyhrs/GeoStar-Selector-QGIS)
