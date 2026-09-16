# Changelog

## V1.4 - 2026-09-16

### Changed
- Reworked the merge tool to use two inputs: original DLTB and extracted sliver polygons.
- Removed the requirement for the original DLTB to contain `SLV_FLAG`.
- Added spatial overlap matching between extracted sliver polygons and original polygons.
- Outputs a complete modified DLTB after merging.

### Merge rules
- Optional target SQL filter.
- Optional attribute consistency fields.
- Target area minimum / maximum.
- Minimum shared boundary length.
- Target selection by longest shared boundary, largest area, or smallest area.
- Minimum overlap percentage between extracted sliver polygon and original polygon.
- Optional merging into other sliver polygons.

## V1.1–V1.3

- Introduced the two-stage “scale conditions + shape conditions” identification method.
- Added equivalent average width `2A/P`.
- Added recommended default parameters for identification and merging.
- Improved ArcGIS Desktop 10.x / Python 2.7 compatibility.
