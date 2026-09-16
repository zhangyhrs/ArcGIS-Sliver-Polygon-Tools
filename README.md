# ArcGIS Sliver Polygon Tools

[中文说明](README_ZH.md)

ArcGIS Desktop 10.x toolbox for identifying and merging sliver polygons.

**Current version: V1.4**

## Features

### 1. Find Sliver Polygons
The tool uses a two-stage rule: **scale conditions + shape conditions**.

Scale indicators:
- Area
- Minimum bounding rectangle width
- Equivalent average width: `2 × Area / Perimeter`

Shape indicators:
- Length-width ratio: `L / W`
- Compactness: `4πA / P²`
- Shape index: `P / (2√(πA))`
- Perimeter-area ratio: `P² / A`

Only polygons satisfying both configured scale and shape rules are flagged, which helps reduce false positives for naturally elongated rivers and roads.

### 2. Merge Extracted Sliver Polygons
The merge tool uses two polygon inputs:
1. Original DLTB
2. Extracted and reviewed sliver polygons

It spatially matches the extracted polygons back to the original layer, evaluates neighboring polygons, selects a target by configured rules, and outputs a complete modified DLTB.

Supported rules include longest shared boundary, target area, attribute consistency, target SQL filters, minimum shared boundary length, and minimum overlap percentage.

## Recommended Workflow

`Original DLTB → Find → Manual review → Merge → Modified DLTB`

## Requirements

- ArcGIS Desktop 10.x / ArcMap
- Python 2.7
- ArcPy
- Polygon data
- Projected coordinate system recommended for meter/m² thresholds

## Default Identification Parameters

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

These values are initial working defaults, not universal standards.

## Merge Defaults

| Parameter | Default |
|---|---:|
| Target minimum area | 1000 m² |
| Minimum shared boundary | 1 m |
| Target priority | Longest shared boundary |
| Minimum overlap with original polygon | 80% |
| Merge into another sliver polygon | No |

## Notes

- Input data are not modified directly; a new output dataset is written.
- Review representative samples before batch processing.
- Sliver thresholds should be adjusted for project scale and data characteristics.
- Features without a valid merge target are retained unchanged.

## License

GPL-3.0. See [LICENSE](LICENSE).

Copyright © 2026 Zhang Y.H.
