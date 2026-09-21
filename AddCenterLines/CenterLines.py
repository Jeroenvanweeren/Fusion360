"""Fusion 360 add-in for drawing radial centerlines on sketch curves and circles."""

import math
import traceback

import adsk.core
import adsk.fusion


_app = None
_ui = None
_handlers = []

CMD_ID = "centerLinesCmd"
LEGACY_CMD_ID = "addCenterLinesCmd"
CMD_NAME = "CenterLines"
CMD_TOOLTIP = "Draw constrained radial centerlines for a sketch curve or circle."
PANEL_ID = "SketchModifyPanel"
RESOURCE_FOLDER = "resources"
ALIGN_Y = "Align with Y axis"
ALIGN_X = "Align with X axis"
ALIGN_SKETCH_LINE = "Align with existing sketch line"
ALIGN_MODEL_AXIS = "Align with model axis"


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        _remove_command(LEGACY_CMD_ID)
        old_definition = _ui.commandDefinitions.itemById(CMD_ID)
        if old_definition:
            old_definition.deleteMe()

        definition = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_TOOLTIP, RESOURCE_FOLDER
        )
        created = CommandCreatedHandler()
        definition.commandCreated.add(created)
        _handlers.append(created)

        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            old_control = panel.controls.itemById(CMD_ID)
            if old_control:
                old_control.deleteMe()
            control = panel.controls.addCommand(definition)
            control.isPromotedByDefault = True
            control.isPromoted = True
    except:  # noqa: E722
        if _ui:
            _ui.messageBox("CenterLines failed to start:\n{}".format(traceback.format_exc()))


def stop(context):
    try:
        _remove_command(CMD_ID)
    except:  # noqa: E722
        if _ui:
            _ui.messageBox("CenterLines failed to stop:\n{}".format(traceback.format_exc()))


def _remove_command(command_id):
    panel = _ui.allToolbarPanels.itemById(PANEL_ID)
    if panel:
        control = panel.controls.itemById(command_id)
        if control:
            control.deleteMe()
    definition = _ui.commandDefinitions.itemById(command_id)
    if definition:
        definition.deleteMe()


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            command = args.command
            inputs = command.commandInputs

            selection = inputs.addSelectionInput(
                "curveSelect", "Curve or circle", "Select a sketch curve or circle"
            )
            selection.setSelectionLimits(1, 0)
            selection.addSelectionFilter("SketchLines")
            selection.addSelectionFilter("SketchCircles")

            line_type = inputs.addDropDownCommandInput(
                "lineType", "Line type", adsk.core.DropDownStyles.TextListDropDownStyle
            )
            line_type.listItems.add("Construction line", True)
            line_type.listItems.add("Center line", False)
            line_type.listItems.add("Normal line", False)

            count = inputs.addIntegerSpinnerCommandInput("lineCount", "Number of lines", 1, 360, 1, 4)
            extension = inputs.addIntegerSpinnerCommandInput(
                "extension", "Extension outside curve (%)", 0, 10000, 1, 0
            )
            extension.tooltip = "Percentage added beyond the selected curve"

            alignment = inputs.addDropDownCommandInput(
                "alignment", "Align first centerline", adsk.core.DropDownStyles.TextListDropDownStyle
            )
            alignment.listItems.add(ALIGN_Y, True)
            alignment.listItems.add(ALIGN_X, False)
            alignment.listItems.add(ALIGN_SKETCH_LINE, False)
            alignment.listItems.add(ALIGN_MODEL_AXIS, False)

            sketch_line_select = inputs.addSelectionInput(
                "alignmentSketchLine", "Sketch line", "Select a sketch line in the circle's sketch"
            )
            sketch_line_select.setSelectionLimits(0, 1)
            sketch_line_select.addSelectionFilter("SketchLines")

            model_axis_select = inputs.addSelectionInput(
                "alignmentModelAxis", "Model axis", "Select a construction axis in the same plane"
            )
            model_axis_select.setSelectionLimits(0, 1)
            sketch_line_select.isVisible = False
            model_axis_select.isVisible = False

            changed = CommandInputChangedHandler()
            command.inputChanged.add(changed)
            _handlers.append(changed)
            validate = CommandValidateInputsHandler()
            command.validateInputs.add(validate)
            _handlers.append(validate)
            execute = CommandExecuteHandler()
            command.execute.add(execute)
            _handlers.append(execute)
            destroy = CommandDestroyHandler()
            command.destroy.add(destroy)
            _handlers.append(destroy)
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed to create CenterLines command:\n{}".format(traceback.format_exc()))


class CommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id != "alignment":
                return
            sketch_line_select = args.inputs.itemById("alignmentSketchLine")
            model_axis_select = args.inputs.itemById("alignmentModelAxis")
            selected = args.input.selectedItem.name
            sketch_line_select.isVisible = selected == ALIGN_SKETCH_LINE
            model_axis_select.isVisible = selected == ALIGN_MODEL_AXIS
            if not sketch_line_select.isVisible:
                sketch_line_select.clearSelection()
            if not model_axis_select.isVisible:
                model_axis_select.clearSelection()
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed to update alignment options:\n{}".format(traceback.format_exc()))


class CommandValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            selection = args.inputs.itemById("curveSelect")
            extension = args.inputs.itemById("extension")
            alignment = args.inputs.itemById("alignment")
            valid_reference = True
            if alignment.selectedItem.name == ALIGN_SKETCH_LINE:
                valid_reference = args.inputs.itemById("alignmentSketchLine").selectionCount == 1
            elif alignment.selectedItem.name == ALIGN_MODEL_AXIS:
                valid_reference = args.inputs.itemById("alignmentModelAxis").selectionCount == 1
            if valid_reference and alignment.selectedItem.name in (ALIGN_SKETCH_LINE, ALIGN_MODEL_AXIS):
                curve = selection.selection(0).entity if selection.selectionCount else None
                reference_input = (
                    args.inputs.itemById("alignmentSketchLine")
                    if alignment.selectedItem.name == ALIGN_SKETCH_LINE
                    else args.inputs.itemById("alignmentModelAxis")
                )
                reference = reference_input.selection(0).entity
                valid_reference = bool(
                    curve
                    and _get_alignment_angle(curve.parentSketch, alignment.selectedItem.name, reference)
                    is not None
                )
            args.areInputsValid = selection.selectionCount > 0 and extension.value >= 0 and valid_reference
        except:  # noqa: E722
            args.areInputsValid = False


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            selection = inputs.itemById("curveSelect")
            line_type = inputs.itemById("lineType").selectedItem.name
            line_count = inputs.itemById("lineCount").value
            extension_percent = inputs.itemById("extension").value
            alignment = inputs.itemById("alignment").selectedItem.name
            alignment_reference = None
            if alignment == ALIGN_SKETCH_LINE:
                alignment_reference = inputs.itemById("alignmentSketchLine").selection(0).entity
            elif alignment == ALIGN_MODEL_AXIS:
                alignment_reference = inputs.itemById("alignmentModelAxis").selection(0).entity
            created = 0
            skipped = []

            for index in range(selection.selectionCount):
                entity = selection.selection(index).entity
                result = _add_centerlines(
                    entity, line_count, extension_percent, line_type, alignment, alignment_reference
                )
                if result:
                    created += result
                else:
                    skipped.append(entity.objectType)

            if created == 0:
                _ui.messageBox("No supported sketch curves were selected.")
            else:
                suffix = " Some selections were skipped." if skipped else ""
                _ui.messageBox("Created {} centerline{}{}.".format(
                    created, "" if created == 1 else "s", suffix
                ))
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed to add centerlines:\n{}".format(traceback.format_exc()))


class CommandDestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        pass


def _add_centerlines(entity, line_count, extension_percent, line_type, alignment, alignment_reference):
    sketch = getattr(entity, "parentSketch", None)
    if not sketch or not _is_supported_curve(entity):
        return 0

    center, radius = _curve_center_and_radius(entity)
    if center is None:
        return 0

    base_angle = _get_alignment_angle(sketch, alignment, alignment_reference)
    if base_angle is None:
        _ui.messageBox("The selected alignment reference is not in the circle's sketch plane.")
        return 0

    center_point = _get_center_point(sketch, entity, center)
    length = radius * (1.0 + extension_percent / 100.0)
    if length <= 0:
        return 0

    lines = sketch.sketchCurves.sketchLines
    centerlines = []
    made = 0
    for index in range(line_count):
        angle = base_angle + 2.0 * math.pi * index / line_count
        direction = adsk.core.Vector3D.create(math.cos(angle), math.sin(angle), 0)
        start = center.copy()
        end = center.copy()
        intersection = _curve_intersection(entity, center, direction, radius)
        if intersection is not None and extension_percent == 0:
            end = intersection.copy()
        else:
            end.translateBy(_scaled_vector(direction, length))
        line = lines.addByTwoPoints(start, end)
        centerlines.append(line)
        _set_line_type(line, line_type)
        _constrain_center(sketch, line, center_point)
        if intersection is not None:
            if extension_percent == 0:
                sketch.geometricConstraints.addCoincident(line.endSketchPoint, entity)
            else:
                intersection_point = sketch.sketchPoints.add(intersection)
                sketch.geometricConstraints.addCoincident(intersection_point, line)
                sketch.geometricConstraints.addCoincident(intersection_point, entity)
        made += 1

    if isinstance(entity, adsk.fusion.SketchCircle) and centerlines:
        _constrain_alignment(
            sketch, centerlines[0], alignment, alignment_reference, center, radius
        )
    _constrain_centerline_angles(sketch, centerlines, center, radius, base_angle)
    return made


def _curve_center_and_radius(entity):
    if isinstance(entity, adsk.fusion.SketchCircle):
        return entity.centerSketchPoint.geometry, entity.radius
    if isinstance(entity, adsk.fusion.SketchArc):
        return entity.centerSketchPoint.geometry, entity.radius

    evaluator = entity.geometry.evaluator
    ok, start_parameter, end_parameter = evaluator.getParameterExtents()
    if not ok:
        return None, 0
    ok, points = evaluator.getPointsAtParameters(
        [
            start_parameter,
            (start_parameter + end_parameter) / 2.0,
            end_parameter,
        ]
    )
    if not ok or len(points) != 3:
        return None, 0
    center = points[1]
    radius = max(center.distanceTo(points[0]), center.distanceTo(points[2]))
    return center, radius


def _is_supported_curve(entity):
    return isinstance(
        entity,
        (adsk.fusion.SketchLine, adsk.fusion.SketchArc, adsk.fusion.SketchCircle),
    )


def _get_center_point(sketch, entity, center):
    if isinstance(entity, (adsk.fusion.SketchArc, adsk.fusion.SketchCircle)):
        return entity.centerSketchPoint
    return sketch.sketchPoints.add(center)


def _get_alignment_angle(sketch, alignment, reference):
    if alignment == ALIGN_Y:
        return math.pi / 2.0
    if alignment == ALIGN_X:
        return 0.0
    if alignment == ALIGN_SKETCH_LINE:
        if not isinstance(reference, adsk.fusion.SketchLine) or reference.parentSketch != sketch:
            return None
        start = reference.geometry.startPoint
        end = reference.geometry.endPoint
        return math.atan2(end.y - start.y, end.x - start.x)
    if alignment == ALIGN_MODEL_AXIS:
        if not isinstance(reference, adsk.fusion.ConstructionAxis):
            return None
        origin = reference.geometry.origin
        direction = reference.geometry.direction
        first = sketch.modelToSketchSpace(origin)
        second = sketch.modelToSketchSpace(
            adsk.core.Point3D.create(
                origin.x + direction.x,
                origin.y + direction.y,
                origin.z + direction.z,
            )
        )
        if abs(first.z) > 1e-7 or abs(second.z) > 1e-7:
            return None
        return math.atan2(second.y - first.y, second.x - first.x)
    return None


def _scaled_vector(vector, scale):
    result = vector.copy()
    result.scaleBy(scale)
    return result


def _set_line_type(line, line_type):
    if line_type == "Construction line":
        line.isConstruction = True
    elif line_type == "Center line":
        line.isConstruction = True
        line.isCenterLine = True


def _constrain_center(sketch, line, center_point):
    sketch.geometricConstraints.addCoincident(line.startSketchPoint, center_point)


def _constrain_alignment(sketch, line, alignment, reference, center, radius):
    if alignment == ALIGN_Y:
        sketch.geometricConstraints.addVertical(line)
    elif alignment == ALIGN_X:
        sketch.geometricConstraints.addHorizontal(line)
    elif alignment == ALIGN_SKETCH_LINE:
        sketch.geometricConstraints.addParallel(line, reference)
    elif alignment == ALIGN_MODEL_AXIS:
        origin = reference.geometry.origin
        direction = reference.geometry.direction
        first = sketch.modelToSketchSpace(origin)
        second = sketch.modelToSketchSpace(
            adsk.core.Point3D.create(
                origin.x + direction.x,
                origin.y + direction.y,
                origin.z + direction.z,
            )
        )
        axis_direction = adsk.core.Vector3D.create(
            second.x - first.x, second.y - first.y, 0
        )
        axis_direction.normalize()
        axis_start = center.copy()
        axis_end = center.copy()
        axis_start.translateBy(_scaled_vector(axis_direction, -radius))
        axis_end.translateBy(_scaled_vector(axis_direction, radius))
        axis_line = sketch.sketchCurves.sketchLines.addByTwoPoints(axis_start, axis_end)
        axis_line.isConstruction = True
        sketch.geometricConstraints.addParallel(line, axis_line)


def _constrain_centerline_angles(sketch, centerlines, center, radius, base_angle):
    if len(centerlines) < 2:
        return

    angle = 2.0 * math.pi / len(centerlines)
    # The final angle is implied by all preceding angles and would
    # over-constrain the shared center point.
    for index in range(len(centerlines) - 1):
        line = centerlines[index]
        next_line = centerlines[index + 1]
        label_angle = base_angle + angle * (index + 0.5)
        label_direction = adsk.core.Vector3D.create(
            math.cos(label_angle), math.sin(label_angle), 0
        )
        text_point = center.copy()
        text_point.translateBy(_scaled_vector(label_direction, radius * 0.5))
        sketch.sketchDimensions.addAngularDimension(line, next_line, text_point)


def _curve_intersection(entity, center, direction, radius):
    if isinstance(entity, adsk.fusion.SketchCircle):
        point = center.copy()
        point.translateBy(_scaled_vector(direction, radius))
        return point
    if not isinstance(entity, adsk.fusion.SketchArc):
        return None

    candidate = center.copy()
    candidate.translateBy(_scaled_vector(direction, radius))
    evaluator = entity.geometry.evaluator
    try:
        ok, parameter = evaluator.getParameterAtPoint(candidate)
        extents_ok, start_parameter, end_parameter = evaluator.getParameterExtents()
    except RuntimeError:
        return None

    if not extents_ok:
        return None
    if not ok:
        return None
    lower_bound = min(start_parameter, end_parameter)
    upper_bound = max(start_parameter, end_parameter)
    if parameter < lower_bound or parameter > upper_bound:
        return None

    # The radial candidate is already the exact point on the circle. Avoid
    # passing Fusion's arc parameter back through getPointAtParameter(); for
    # open arcs that returned parameter can be outside the valid arc domain.
    return candidate
