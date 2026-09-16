# -*- coding: utf-8 -*-
"""
Source Name:   SliverPolygonTools_ArcGIS10x_V1.4.pyt
Version:       V1.4
Platform:      ArcGIS Desktop 10.x / ArcMap / Python 2.7
Description:   狭长细碎图斑查找与相邻合并工具箱

V1.1:
1. 查找工具采用“尺度条件 + 形状条件”两级判定；
2. 新增等效平均宽度指标：2*A/P；
3. 避免将面积很大、天然狭长的河流/道路等误判为细碎图斑；
4. 保留相邻合并工具；
5. 为相邻合并工具增加推荐默认参数。

Copyright (c) 2026 Zhang Y.H.
"""

import arcpy
import os
import math
import uuid


class Toolbox(object):
    def __init__(self):
        self.label = u"狭长细碎图斑处理工具箱 V1.4"
        self.alias = "SliverPolygonTools"
        self.tools = [FindSliverPolygons, MergeSliverPolygons]


# ============================================================
# 通用函数
# ============================================================

def addMessage(messages, text):
    try:
        messages.addMessage(text)
    except Exception:
        arcpy.AddMessage(text)


def addWarning(messages, text):
    try:
        messages.addWarningMessage(text)
    except Exception:
        arcpy.AddWarning(text)


def safeDelete(path):
    try:
        if path and arcpy.Exists(path):
            arcpy.Delete_management(path)
    except Exception:
        pass


def fieldExists(fc, field_name):
    for f in arcpy.ListFields(fc):
        if f.name.upper() == field_name.upper():
            return True
    return False


def ensureField(fc, field_name, field_type, length=None):
    if fieldExists(fc, field_name):
        return
    if length:
        arcpy.AddField_management(
            fc, field_name, field_type,
            field_length=length
        )
    else:
        arcpy.AddField_management(
            fc, field_name, field_type
        )


def toFloat(value):
    if value in (None, "", "#"):
        return None
    return float(value)


def parseMultiValue(value):
    if not value:
        return []

    result = []
    for item in value.split(";"):
        item = item.strip().strip("'").strip('"')
        if item:
            result.append(item)
    return result


def checkProjectedMeter(fc):
    try:
        sr = arcpy.Describe(fc).spatialReference

        if sr is None:
            return False, u"未读取到空间参考。"

        if sr.type != "Projected":
            return False, u"输入数据不是投影坐标系，建议先投影到米制坐标系。"

        unit_name = sr.linearUnitName or ""
        unit_lower = unit_name.lower()

        if ("meter" not in unit_lower and
                "metre" not in unit_lower and
                u"米" not in unit_name):
            return False, u"当前坐标系线性单位可能不是米，请核实面积、宽度和边界长度阈值。"

    except Exception:
        pass

    return True, ""


def getMbgFields(fc):
    orig_field = None
    width_field = None
    length_field = None

    for f in arcpy.ListFields(fc):
        name = f.name.upper()

        if name in ("ORIG_FID", "ORIGFID"):
            orig_field = f.name

        elif name in ("MBG_WIDTH", "WIDTH"):
            width_field = f.name

        elif name in ("MBG_LENGTH", "LENGTH"):
            length_field = f.name

    return orig_field, width_field, length_field


def getNeighborFields(table):
    src_field = None
    nbr_field = None
    length_field = None

    for f in arcpy.ListFields(table):
        name = f.name.lower()

        if name == "src_tmp_mrgid":
            src_field = f.name
        elif name == "nbr_tmp_mrgid":
            nbr_field = f.name
        elif name == "length":
            length_field = f.name

    if src_field is None or nbr_field is None:

        for f in arcpy.ListFields(table):
            name = f.name.lower()

            if src_field is None and name.startswith("src_"):
                src_field = f.name

            if nbr_field is None and name.startswith("nbr_"):
                nbr_field = f.name

    return src_field, nbr_field, length_field


# ============================================================
# 工具1：查找狭长细碎图斑
# ============================================================

class FindSliverPolygons(object):

    def __init__(self):
        self.label = u"1-查找狭长细碎图斑"
        self.description = (
            u"采用“尺度条件 + 形状条件”两级判定，"
            u"避免将面积很大但天然狭长的河流、道路等误判为细碎图斑。"
        )
        self.canRunInBackground = False

    def getParameterInfo(self):

        p0 = arcpy.Parameter(
            displayName=u"输入面图层",
            name="in_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        p0.filter.list = ["Polygon"]

        p1 = arcpy.Parameter(
            displayName=u"输出结果",
            name="out_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")

        # ---------------- 尺度条件 ----------------
        p2 = arcpy.Parameter(
            displayName=u"尺度条件 - 面积上限（平方米）",
            name="max_area",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p2.value = 1000.0

        p3 = arcpy.Parameter(
            displayName=u"尺度条件 - 最小外接矩形宽度上限（米）",
            name="max_mbg_width",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p3.value = 5.0

        p4 = arcpy.Parameter(
            displayName=u"尺度条件 - 等效平均宽度上限（米，2*A/P）",
            name="max_equiv_width",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p4.value = 5.0

        p5 = arcpy.Parameter(
            displayName=u"尺度条件组合方式",
            name="scale_mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        p5.filter.type = "ValueList"
        p5.filter.list = [
            u"至少满足1项",
            u"全部满足",
            u"至少满足N项"
        ]
        p5.value = u"至少满足1项"

        p6 = arcpy.Parameter(
            displayName=u"尺度条件至少满足数量 N",
            name="scale_min_hits",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        p6.value = 1

        # ---------------- 形状条件 ----------------
        p7 = arcpy.Parameter(
            displayName=u"形状条件 - 长宽比下限（长度/宽度）",
            name="min_ratio",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p7.value = 5.0

        p8 = arcpy.Parameter(
            displayName=u"形状条件 - 紧凑度上限（4*pi*A/P^2）",
            name="max_compactness",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p8.value = 0.25

        p9 = arcpy.Parameter(
            displayName=u"形状条件 - 形状指数下限（P/(2*sqrt(pi*A))）",
            name="min_shape_index",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p9.value = 2.0

        p10 = arcpy.Parameter(
            displayName=u"形状条件 - 周长面积比下限（P^2/A）",
            name="min_pa_ratio",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p10.value = 40.0

        p11 = arcpy.Parameter(
            displayName=u"形状条件组合方式",
            name="shape_mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        p11.filter.type = "ValueList"
        p11.filter.list = [
            u"至少满足2项",
            u"全部满足",
            u"任意满足",
            u"至少满足N项"
        ]
        p11.value = u"至少满足2项"

        p12 = arcpy.Parameter(
            displayName=u"形状条件至少满足数量 N",
            name="shape_min_hits",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        p12.value = 2

        p13 = arcpy.Parameter(
            displayName=u"仅输出疑似狭长细碎图斑",
            name="only_flagged",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        p13.value = True

        return [
            p0, p1,
            p2, p3, p4, p5, p6,
            p7, p8, p9, p10, p11, p12,
            p13
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):

        parameters[6].enabled = (
            parameters[5].valueAsText == u"至少满足N项"
        )

        parameters[12].enabled = (
            parameters[11].valueAsText == u"至少满足N项"
        )

    def updateMessages(self, parameters):

        if parameters[0].valueAsText:

            ok, text = checkProjectedMeter(
                parameters[0].valueAsText
            )

            if not ok:
                parameters[0].setWarningMessage(text)

    def execute(self, parameters, messages):

        in_fc = parameters[0].valueAsText
        out_fc = parameters[1].valueAsText

        max_area = toFloat(parameters[2].valueAsText)
        max_mbg_width = toFloat(parameters[3].valueAsText)
        max_equiv_width = toFloat(parameters[4].valueAsText)

        scale_mode = parameters[5].valueAsText

        scale_min_hits = parameters[6].value
        if scale_min_hits is None:
            scale_min_hits = 1
        scale_min_hits = int(scale_min_hits)

        min_ratio = toFloat(parameters[7].valueAsText)
        max_comp = toFloat(parameters[8].valueAsText)
        min_shape = toFloat(parameters[9].valueAsText)
        min_pa = toFloat(parameters[10].valueAsText)

        shape_mode = parameters[11].valueAsText

        shape_min_hits = parameters[12].value
        if shape_min_hits is None:
            shape_min_hits = 2
        shape_min_hits = int(shape_min_hits)

        only_flagged = parameters[13].value
        if only_flagged is None:
            only_flagged = True

        ok, text = checkProjectedMeter(in_fc)

        if not ok:
            addWarning(messages, text)

        scratch_gdb = arcpy.env.scratchGDB
        uid = uuid.uuid4().hex[:8]

        work_fc = os.path.join(
            scratch_gdb,
            "sliver_work_" + uid
        )

        mbg_fc = os.path.join(
            scratch_gdb,
            "sliver_mbg_" + uid
        )

        safeDelete(work_fc)
        safeDelete(mbg_fc)

        try:

            addMessage(
                messages,
                u"复制输入数据..."
            )

            arcpy.CopyFeatures_management(
                in_fc,
                work_fc
            )

            oid_field = arcpy.Describe(
                work_fc
            ).OIDFieldName

            addMessage(
                messages,
                u"计算最小外接矩形..."
            )

            arcpy.MinimumBoundingGeometry_management(
                in_features=work_fc,
                out_feature_class=mbg_fc,
                geometry_type="RECTANGLE_BY_AREA",
                group_option="NONE",
                group_field="",
                mbg_fields_option="MBG_FIELDS"
            )

            orig_field, width_field, length_field = \
                getMbgFields(mbg_fc)

            if (orig_field is None or
                    width_field is None or
                    length_field is None):

                raise Exception(
                    u"无法读取最小外接矩形的 "
                    u"ORIG_FID、MBG_Width、MBG_Length 字段。"
                )

            mbg_values = {}

            with arcpy.da.SearchCursor(
                    mbg_fc,
                    [
                        orig_field,
                        width_field,
                        length_field
                    ]) as cursor:

                for orig_fid, width, length in cursor:

                    width = float(width or 0)
                    length = float(length or 0)

                    mbg_values[int(orig_fid)] = (
                        min(width, length),
                        max(width, length)
                    )

            fields_to_add = [
                ("SLV_AREA", "DOUBLE", None),
                ("SLV_PERIM", "DOUBLE", None),
                ("SLV_WIDTH", "DOUBLE", None),
                ("SLV_LEN", "DOUBLE", None),
                ("SLV_EQW", "DOUBLE", None),
                ("SLV_RATIO", "DOUBLE", None),
                ("SLV_COMP", "DOUBLE", None),
                ("SLV_SHAPE", "DOUBLE", None),
                ("SLV_PA", "DOUBLE", None),
                ("SLV_SC_H", "SHORT", None),
                ("SLV_SH_H", "SHORT", None),
                ("SLV_FLAG", "SHORT", None),
                ("SLV_REASON", "TEXT", 250)
            ]

            for field_name, field_type, field_length \
                    in fields_to_add:

                ensureField(
                    work_fc,
                    field_name,
                    field_type,
                    field_length
                )

            cursor_fields = [
                oid_field,
                "SHAPE@AREA",
                "SHAPE@LENGTH",
                "SLV_AREA",
                "SLV_PERIM",
                "SLV_WIDTH",
                "SLV_LEN",
                "SLV_EQW",
                "SLV_RATIO",
                "SLV_COMP",
                "SLV_SHAPE",
                "SLV_PA",
                "SLV_SC_H",
                "SLV_SH_H",
                "SLV_FLAG",
                "SLV_REASON"
            ]

            scale_enabled_count = 0

            for value in [
                    max_area,
                    max_mbg_width,
                    max_equiv_width]:

                if value is not None:
                    scale_enabled_count += 1

            shape_enabled_count = 0

            for value in [
                    min_ratio,
                    max_comp,
                    min_shape,
                    min_pa]:

                if value is not None:
                    shape_enabled_count += 1

            flagged_count = 0

            addMessage(
                messages,
                u"计算尺度指标和形状指标..."
            )

            with arcpy.da.UpdateCursor(
                    work_fc,
                    cursor_fields) as cursor:

                for row in cursor:

                    oid_value = int(row[0])

                    area = float(row[1] or 0)
                    perimeter = float(row[2] or 0)

                    width, length = mbg_values.get(
                        oid_value,
                        (0.0, 0.0)
                    )

                    if perimeter > 0:
                        equiv_width = (
                            2.0 * area / perimeter
                        )
                    else:
                        equiv_width = 999999.0

                    if width > 0:
                        ratio = length / width
                    else:
                        ratio = 999999.0

                    if perimeter > 0:
                        compactness = (
                            4.0 * math.pi * area /
                            (perimeter * perimeter)
                        )
                    else:
                        compactness = 0.0

                    if area > 0:

                        shape_index = (
                            perimeter /
                            (2.0 * math.sqrt(
                                math.pi * area
                            ))
                        )

                        pa_ratio = (
                            perimeter * perimeter /
                            area
                        )

                    else:
                        shape_index = 999999.0
                        pa_ratio = 999999.0

                    # -----------------------
                    # 第一层：尺度条件
                    # -----------------------

                    scale_checks = []
                    scale_reasons = []

                    if max_area is not None:

                        hit = area <= max_area
                        scale_checks.append(hit)

                        if hit:
                            scale_reasons.append(u"面积")

                    if max_mbg_width is not None:

                        hit = width <= max_mbg_width
                        scale_checks.append(hit)

                        if hit:
                            scale_reasons.append(
                                u"外接矩形宽度"
                            )

                    if max_equiv_width is not None:

                        hit = equiv_width <= max_equiv_width
                        scale_checks.append(hit)

                        if hit:
                            scale_reasons.append(
                                u"等效平均宽度"
                            )

                    scale_hits = 0

                    for item in scale_checks:
                        if item:
                            scale_hits += 1

                    if scale_mode == u"全部满足":

                        scale_pass = (
                            len(scale_checks) > 0 and
                            scale_hits == len(scale_checks)
                        )

                    elif scale_mode == u"至少满足N项":

                        n = max(
                            1,
                            min(
                                scale_min_hits,
                                scale_enabled_count
                            )
                        )

                        scale_pass = (
                            scale_hits >= n
                        )

                    else:

                        scale_pass = (
                            scale_hits >= 1
                        )

                    # -----------------------
                    # 第二层：形状条件
                    # -----------------------

                    shape_checks = []
                    shape_reasons = []

                    if min_ratio is not None:

                        hit = ratio >= min_ratio
                        shape_checks.append(hit)

                        if hit:
                            shape_reasons.append(
                                u"长宽比"
                            )

                    if max_comp is not None:

                        hit = compactness <= max_comp
                        shape_checks.append(hit)

                        if hit:
                            shape_reasons.append(
                                u"紧凑度"
                            )

                    if min_shape is not None:

                        hit = shape_index >= min_shape
                        shape_checks.append(hit)

                        if hit:
                            shape_reasons.append(
                                u"形状指数"
                            )

                    if min_pa is not None:

                        hit = pa_ratio >= min_pa
                        shape_checks.append(hit)

                        if hit:
                            shape_reasons.append(
                                u"周长面积比"
                            )

                    shape_hits = 0

                    for item in shape_checks:
                        if item:
                            shape_hits += 1

                    if shape_mode == u"全部满足":

                        shape_pass = (
                            len(shape_checks) > 0 and
                            shape_hits == len(shape_checks)
                        )

                    elif shape_mode == u"任意满足":

                        shape_pass = (
                            shape_hits >= 1
                        )

                    elif shape_mode == u"至少满足N项":

                        n = max(
                            1,
                            min(
                                shape_min_hits,
                                shape_enabled_count
                            )
                        )

                        shape_pass = (
                            shape_hits >= n
                        )

                    else:
                        # 默认：至少满足2项
                        n = max(
                            1,
                            min(
                                2,
                                shape_enabled_count
                            )
                        )

                        shape_pass = (
                            shape_hits >= n
                        )

                    # -----------------------
                    # 最终判定
                    # -----------------------

                    flag = (
                        scale_pass and
                        shape_pass
                    )

                    if flag:
                        flagged_count += 1

                    reasons = []

                    if scale_reasons:
                        reasons.append(
                            u"尺度:" +
                            u"、".join(scale_reasons)
                        )

                    if shape_reasons:
                        reasons.append(
                            u"形状:" +
                            u"、".join(shape_reasons)
                        )

                    row[3] = area
                    row[4] = perimeter
                    row[5] = width
                    row[6] = length
                    row[7] = equiv_width
                    row[8] = ratio
                    row[9] = compactness
                    row[10] = shape_index
                    row[11] = pa_ratio
                    row[12] = scale_hits
                    row[13] = shape_hits
                    row[14] = 1 if flag else 0
                    row[15] = u"；".join(reasons)

                    cursor.updateRow(row)

            addMessage(
                messages,
                u"识别疑似狭长细碎图斑：%s 个" %
                flagged_count
            )

            if only_flagged:

                temp_layer = (
                    "sliver_layer_" + uid
                )

                arcpy.MakeFeatureLayer_management(
                    work_fc,
                    temp_layer,
                    "SLV_FLAG = 1"
                )

                arcpy.CopyFeatures_management(
                    temp_layer,
                    out_fc
                )

                arcpy.Delete_management(
                    temp_layer
                )

            else:

                arcpy.CopyFeatures_management(
                    work_fc,
                    out_fc
                )

            addMessage(
                messages,
                u"查找完成。"
            )

        finally:
            safeDelete(work_fc)
            safeDelete(mbg_fc)


# ============================================================
# 工具2：合并相邻狭长细碎图斑
# ============================================================

class MergeSliverPolygons(object):

    def __init__(self):
        self.label = u"2-合并提取的狭长细碎图斑"
        self.description = (
            u"输入原始 DLTB 和已经提取出的狭长细碎图斑，"
            u"自动匹配其在原始 DLTB 中对应的图斑，"
            u"再按属性、面积、公共边界等条件合并到相邻图斑，"
            u"最终输出修改后的完整 DLTB。"
        )
        self.canRunInBackground = False

    def getParameterInfo(self):

        p0 = arcpy.Parameter(
            displayName=u"原始面图层（DLTB）",
            name="original_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        p0.filter.list = ["Polygon"]

        p1 = arcpy.Parameter(
            displayName=u"已提取的狭长细碎图斑",
            name="sliver_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        p1.filter.list = ["Polygon"]

        p2 = arcpy.Parameter(
            displayName=u"输出修改后的 DLTB",
            name="out_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")

        p3 = arcpy.Parameter(
            displayName=u"目标相邻图斑 SQL 条件（可选）",
            name="target_where",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        p4 = arcpy.Parameter(
            displayName=u"要求属性相同的字段（可多选）",
            name="same_fields",
            datatype="Field",
            parameterType="Optional",
            direction="Input",
            multiValue=True)
        p4.parameterDependencies = [p0.name]

        p5 = arcpy.Parameter(
            displayName=u"目标图斑面积下限（平方米）",
            name="target_min_area",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p5.value = 1000.0

        p6 = arcpy.Parameter(
            displayName=u"目标图斑面积上限（平方米）",
            name="target_max_area",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")

        p7 = arcpy.Parameter(
            displayName=u"最小公共边界长度（米）",
            name="min_shared_length",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p7.value = 1.0

        p8 = arcpy.Parameter(
            displayName=u"合并目标优先规则",
            name="priority_rule",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        p8.filter.type = "ValueList"
        p8.filter.list = [
            u"公共边界最长",
            u"目标面积最大",
            u"目标面积最小"
        ]
        p8.value = u"公共边界最长"

        p9 = arcpy.Parameter(
            displayName=u"狭长图斑与原始图斑最小重叠比例（%）",
            name="min_overlap_percent",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        p9.value = 80.0

        p10 = arcpy.Parameter(
            displayName=u"允许合并到其他狭长细碎图斑",
            name="allow_sliver_target",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        p10.value = False

        return [
            p0, p1, p2, p3, p4,
            p5, p6, p7, p8, p9, p10
        ]

    def isLicensed(self):
        return True

    def updateMessages(self, parameters):

        if parameters[0].valueAsText:

            ok, msg_text = checkProjectedMeter(
                parameters[0].valueAsText
            )

            if not ok:
                parameters[0].setWarningMessage(msg_text)

        if parameters[1].valueAsText:

            try:
                desc = arcpy.Describe(
                    parameters[1].valueAsText
                )

                if desc.shapeType != "Polygon":
                    parameters[1].setErrorMessage(
                        u"狭长细碎图斑必须为面要素。"
                    )

            except Exception:
                pass

        if parameters[9].value is not None:

            try:
                value = float(parameters[9].value)

                if value <= 0 or value > 100:
                    parameters[9].setErrorMessage(
                        u"重叠比例应大于 0 且不超过 100。"
                    )

            except Exception:
                pass

    def execute(self, parameters, messages):

        original_fc = parameters[0].valueAsText
        sliver_fc = parameters[1].valueAsText
        out_fc = parameters[2].valueAsText

        target_where = parameters[3].valueAsText

        same_fields = parseMultiValue(
            parameters[4].valueAsText
        )
        target_min_area = toFloat(
            parameters[5].valueAsText
        )

        target_max_area = toFloat(
            parameters[6].valueAsText
        )

        min_shared_length = toFloat(
            parameters[7].valueAsText
        )

        if min_shared_length is None:
            min_shared_length = 0.0

        priority_rule = parameters[8].valueAsText

        min_overlap_percent = toFloat(
            parameters[9].valueAsText
        )

        if min_overlap_percent is None:
            min_overlap_percent = 80.0

        allow_sliver_target = parameters[10].value

        if allow_sliver_target is None:
            allow_sliver_target = False

        scratch_gdb = arcpy.env.scratchGDB
        uid = uuid.uuid4().hex[:8]

        work_fc = os.path.join(
            scratch_gdb,
            "merge_original_" + uid
        )

        sliver_work_fc = os.path.join(
            scratch_gdb,
            "merge_sliver_" + uid
        )

        intersect_fc = os.path.join(
            scratch_gdb,
            "merge_match_" + uid
        )

        neighbor_table = os.path.join(
            scratch_gdb,
            "merge_neighbor_" + uid
        )

        safeDelete(work_fc)
        safeDelete(sliver_work_fc)
        safeDelete(intersect_fc)
        safeDelete(neighbor_table)

        try:

            # ==================================================
            # 1. 复制原始数据与狭长图斑
            # ==================================================

            addMessage(
                messages,
                u"复制原始 DLTB..."
            )

            arcpy.CopyFeatures_management(
                original_fc,
                work_fc
            )

            addMessage(
                messages,
                u"复制已提取的狭长细碎图斑..."
            )

            arcpy.CopyFeatures_management(
                sliver_fc,
                sliver_work_fc
            )

            original_oid = arcpy.Describe(
                work_fc
            ).OIDFieldName

            sliver_oid = arcpy.Describe(
                sliver_work_fc
            ).OIDFieldName

            ensureField(
                work_fc,
                "TMP_MRGID",
                "LONG"
            )

            ensureField(
                sliver_work_fc,
                "TMP_SLVID",
                "LONG"
            )

            arcpy.CalculateField_management(
                work_fc,
                "TMP_MRGID",
                "!%s!" % original_oid,
                "PYTHON_9.3"
            )

            arcpy.CalculateField_management(
                sliver_work_fc,
                "TMP_SLVID",
                "!%s!" % sliver_oid,
                "PYTHON_9.3"
            )

            # ==================================================
            # 2. 将提取的狭长图斑匹配回原始 DLTB
            # ==================================================

            addMessage(
                messages,
                u"匹配狭长细碎图斑与原始 DLTB..."
            )

            sliver_area = {}

            with arcpy.da.SearchCursor(
                    sliver_work_fc,
                    [
                        "TMP_SLVID",
                        "SHAPE@AREA"
                    ]) as cursor:

                for sliver_id, area in cursor:

                    sliver_area[
                        int(sliver_id)
                    ] = float(area or 0)

            # 使用面相交面积匹配。
            # 对从原始 DLTB 中提取出来的图斑，
            # 正确原始图斑通常具有接近 100% 的重叠面积。
            arcpy.Intersect_analysis(
                in_features=[
                    sliver_work_fc,
                    work_fc
                ],
                out_feature_class=intersect_fc,
                join_attributes="ALL",
                cluster_tolerance="",
                output_type="INPUT"
            )

            match_area = {}

            with arcpy.da.SearchCursor(
                    intersect_fc,
                    [
                        "TMP_SLVID",
                        "TMP_MRGID",
                        "SHAPE@AREA"
                    ]) as cursor:

                for sliver_id, original_id, area in cursor:

                    if sliver_id is None or original_id is None:
                        continue

                    sliver_id = int(sliver_id)
                    original_id = int(original_id)
                    area = float(area or 0)

                    key = (
                        sliver_id,
                        original_id
                    )

                    if key not in match_area:
                        match_area[key] = 0.0

                    match_area[key] += area

            best_match = {}

            for key in match_area:

                sliver_id = key[0]
                original_id = key[1]
                area = match_area[key]

                if (sliver_id not in best_match or
                        area > best_match[sliver_id][1]):

                    best_match[sliver_id] = (
                        original_id,
                        area
                    )

            candidate_ids = set()
            unmatched_slivers = []

            for sliver_id in sliver_area:

                if sliver_id not in best_match:

                    unmatched_slivers.append(
                        sliver_id
                    )

                    continue

                original_id, overlap_area = \
                    best_match[sliver_id]

                source_area = sliver_area[
                    sliver_id
                ]

                if source_area > 0:

                    overlap_percent = (
                        overlap_area /
                        source_area *
                        100.0
                    )

                else:
                    overlap_percent = 0.0

                if overlap_percent >= min_overlap_percent:

                    candidate_ids.add(
                        original_id
                    )

                else:

                    unmatched_slivers.append(
                        sliver_id
                    )

            addMessage(
                messages,
                u"输入狭长细碎图斑：%s 个" %
                len(sliver_area)
            )

            addMessage(
                messages,
                u"成功匹配原始 DLTB 图斑：%s 个" %
                len(candidate_ids)
            )

            if len(unmatched_slivers) > 0:

                addWarning(
                    messages,
                    u"有 %s 个狭长图斑未达到 %.2f%% 的最小重叠比例，"
                    u"本次不参与合并。" %
                    (
                        len(unmatched_slivers),
                        min_overlap_percent
                    )
                )

            if len(candidate_ids) == 0:

                raise Exception(
                    u"没有狭长细碎图斑能够匹配到原始 DLTB。"
                    u"请确认两个输入数据空间位置一致，"
                    u"或适当降低最小重叠比例。"
                )

            # ==================================================
            # 3. 原始 DLTB 属性和面积缓存
            # ==================================================

            info = {}

            read_fields = [
                "TMP_MRGID",
                "SHAPE@AREA"
            ] + same_fields

            with arcpy.da.SearchCursor(
                    work_fc,
                    read_fields) as cursor:

                for row in cursor:

                    feature_id = int(row[0])

                    info[feature_id] = {
                        "area": float(row[1] or 0),
                        "attrs": tuple(row[2:])
                    }

            # ==================================================
            # 4. 确定允许作为合并目标的图斑
            # ==================================================

            target_ids = set()

            target_layer = (
                "target_layer_" + uid
            )

            if target_where:

                try:

                    arcpy.MakeFeatureLayer_management(
                        work_fc,
                        target_layer,
                        target_where
                    )

                except Exception:

                    raise Exception(
                        u"目标相邻图斑 SQL 条件无效：%s" %
                        target_where
                    )

            else:

                arcpy.MakeFeatureLayer_management(
                    work_fc,
                    target_layer
                )

            with arcpy.da.SearchCursor(
                    target_layer,
                    [
                        "TMP_MRGID",
                        "SHAPE@AREA"
                    ]) as cursor:

                for feature_id, area in cursor:

                    feature_id = int(feature_id)
                    area = float(area or 0)

                    if (not allow_sliver_target and
                            feature_id in candidate_ids):
                        continue

                    if (target_min_area is not None and
                            area < target_min_area):
                        continue

                    if (target_max_area is not None and
                            area > target_max_area):
                        continue

                    target_ids.add(
                        feature_id
                    )

            arcpy.Delete_management(
                target_layer
            )

            addMessage(
                messages,
                u"可作为合并目标的图斑：%s 个" %
                len(target_ids)
            )

            # ==================================================
            # 5. 计算原始 DLTB 邻接关系
            # ==================================================

            addMessage(
                messages,
                u"计算狭长图斑与相邻图斑的公共边界..."
            )

            arcpy.PolygonNeighbors_analysis(
                in_features=work_fc,
                out_table=neighbor_table,
                in_fields="TMP_MRGID",
                area_overlap="NO_AREA_OVERLAP",
                both_sides="BOTH_SIDES"
            )

            src_field, nbr_field, length_field = \
                getNeighborFields(
                    neighbor_table
                )

            if (src_field is None or
                    nbr_field is None or
                    length_field is None):

                raise Exception(
                    u"无法识别 Polygon Neighbors 输出字段。"
                )

            candidate_options = {}

            with arcpy.da.SearchCursor(
                    neighbor_table,
                    [
                        src_field,
                        nbr_field,
                        length_field
                    ]) as cursor:

                for src_id, nbr_id, shared_length in cursor:

                    if src_id is None or nbr_id is None:
                        continue

                    src_id = int(src_id)
                    nbr_id = int(nbr_id)

                    shared_length = float(
                        shared_length or 0
                    )

                    if src_id not in candidate_ids:
                        continue

                    if nbr_id not in target_ids:
                        continue

                    if shared_length < min_shared_length:
                        continue

                    if same_fields:

                        if (info[src_id]["attrs"] !=
                                info[nbr_id]["attrs"]):

                            continue

                    if src_id not in candidate_options:

                        candidate_options[
                            src_id
                        ] = []

                    candidate_options[
                        src_id
                    ].append(
                        (
                            nbr_id,
                            shared_length,
                            info[nbr_id]["area"]
                        )
                    )

            # ==================================================
            # 6. 每个狭长图斑选择唯一合并目标
            # ==================================================

            merge_mapping = {}

            for src_id in candidate_options:

                options = candidate_options[
                    src_id
                ]

                if not options:
                    continue

                if priority_rule == u"公共边界最长":

                    options.sort(
                        key=lambda x: (
                            x[1],
                            x[2]
                        ),
                        reverse=True
                    )

                elif priority_rule == u"目标面积最大":

                    options.sort(
                        key=lambda x: (
                            x[2],
                            x[1]
                        ),
                        reverse=True
                    )

                else:

                    options.sort(
                        key=lambda x: (
                            x[2],
                            -x[1]
                        )
                    )

                merge_mapping[
                    src_id
                ] = options[0][0]

            addMessage(
                messages,
                u"成功找到合并目标的狭长图斑：%s 个" %
                len(merge_mapping)
            )

            no_target_count = (
                len(candidate_ids) -
                len(merge_mapping)
            )

            if no_target_count > 0:

                addWarning(
                    messages,
                    u"有 %s 个狭长图斑未找到满足条件的相邻目标，"
                    u"将保留原状。" %
                    no_target_count
                )

            if len(merge_mapping) == 0:

                try:
                    arcpy.DeleteField_management(
                        work_fc,
                        ["TMP_MRGID"]
                    )
                except Exception:
                    pass

                arcpy.CopyFeatures_management(
                    work_fc,
                    out_fc
                )

                addWarning(
                    messages,
                    u"没有图斑满足合并条件，已输出未修改的原始 DLTB。"
                )

                return

            # ==================================================
            # 7. 几何合并
            # ==================================================

            geometry_dict = {}

            with arcpy.da.SearchCursor(
                    work_fc,
                    [
                        "TMP_MRGID",
                        "SHAPE@"
                    ]) as cursor:

                for feature_id, geometry in cursor:

                    geometry_dict[
                        int(feature_id)
                    ] = geometry

            target_sources = {}

            for src_id in merge_mapping:

                target_id = merge_mapping[
                    src_id
                ]

                if target_id not in target_sources:

                    target_sources[
                        target_id
                    ] = []

                target_sources[
                    target_id
                ].append(
                    src_id
                )

            merged_geometries = {}

            for target_id in target_sources:

                merged_geometry = \
                    geometry_dict[
                        target_id
                    ]

                for src_id in target_sources[
                        target_id]:

                    merged_geometry = \
                        merged_geometry.union(
                            geometry_dict[
                                src_id
                            ]
                        )

                merged_geometries[
                    target_id
                ] = merged_geometry

            addMessage(
                messages,
                u"更新目标图斑几何..."
            )

            with arcpy.da.UpdateCursor(
                    work_fc,
                    [
                        "TMP_MRGID",
                        "SHAPE@"
                    ]) as cursor:

                for row in cursor:

                    feature_id = int(
                        row[0]
                    )

                    if feature_id in \
                            merged_geometries:

                        row[1] = \
                            merged_geometries[
                                feature_id
                            ]

                        cursor.updateRow(
                            row
                        )

            # ==================================================
            # 8. 删除已经被并入邻斑的原狭长图斑
            # ==================================================

            delete_ids = set(
                merge_mapping.keys()
            )

            with arcpy.da.UpdateCursor(
                    work_fc,
                    ["TMP_MRGID"]) as cursor:

                for row in cursor:

                    if int(row[0]) in delete_ids:
                        cursor.deleteRow()

            try:

                arcpy.DeleteField_management(
                    work_fc,
                    ["TMP_MRGID"]
                )

            except Exception:
                pass

            # ==================================================
            # 9. 输出完整修改结果
            # ==================================================

            arcpy.CopyFeatures_management(
                work_fc,
                out_fc
            )

            addMessage(
                messages,
                u"处理完成。"
            )

            addMessage(
                messages,
                u"已合并狭长细碎图斑：%s 个" %
                len(merge_mapping)
            )

            addMessage(
                messages,
                u"保留未合并狭长图斑：%s 个" %
                no_target_count
            )

            addMessage(
                messages,
                u"输出为修改后的完整原始 DLTB。"
            )

        finally:

            safeDelete(
                work_fc
            )

            safeDelete(
                sliver_work_fc
            )

            safeDelete(
                intersect_fc
            )

            safeDelete(
                neighbor_table
            )
