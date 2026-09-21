"""Fusion 360 add-in for adding midpoint sketch points to selected curves."""

import traceback

import adsk.core
import adsk.fusion


_app = None
_ui = None
_handlers = []

CMD_ID = "JeroenVanWeeren_Midpoints_addMidpoint"
CMD_NAME = "Add Midpoints"
CMD_TOOLTIP = "Add a sketch point at the midpoint of selected lines, arcs, or splines."
PANEL_ID = "SketchModifyPanel"
RESOURCE_FOLDER = "resources"


_SUPPORTED_TYPES = {
    "SketchLine",
    "SketchArc",
    "SketchFittedSpline",
    "SketchControlPointSpline",
}


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        _remove_command()
        definition = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_TOOLTIP, RESOURCE_FOLDER
        )
        created = CommandCreatedHandler()
        definition.commandCreated.add(created)
        _handlers.append(created)

        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            control = panel.controls.addCommand(definition)
            control.isPromotedByDefault = True
            control.isPromoted = True
    except:  # noqa: E722
        if _ui:
            _ui.messageBox("Midpoints failed to start:\n{}".format(traceback.format_exc()))


def stop(context):
    try:
        _remove_command()
    except:  # noqa: E722
        if _ui:
            _ui.messageBox("Midpoints failed to stop:\n{}".format(traceback.format_exc()))


def _remove_command():
    panel = _ui.allToolbarPanels.itemById(PANEL_ID)
    if panel:
        control = panel.controls.itemById(CMD_ID)
        if control:
            control.deleteMe()

    definition = _ui.commandDefinitions.itemById(CMD_ID)
    if definition:
        definition.deleteMe()


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            command = args.command
            selection = command.commandInputs.addSelectionInput(
                "curveSelect",
                "Curves",
                "Select lines, arcs, or splines",
            )
            selection.setSelectionLimits(1, 0)
            selection.addSelectionFilter("SketchCurves")

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
                _ui.messageBox("Failed to create Midpoints command:\n{}".format(traceback.format_exc()))


class CommandValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            selection = args.inputs.itemById("curveSelect")
            args.areInputsValid = selection.selectionCount > 0 and all(
                _is_supported_curve(selection.selection(index).entity)
                for index in range(selection.selectionCount)
            )
        except:  # noqa: E722
            args.areInputsValid = False


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            selection = args.command.commandInputs.itemById("curveSelect")
            selected_curves = [
                selection.selection(index).entity
                for index in range(selection.selectionCount)
            ]
            created = []
            skipped = []

            for curve in selected_curves:
                if not _is_supported_curve(curve):
                    skipped.append(curve.objectType)
                    continue

                point = _add_midpoint(curve)
                if point:
                    created.append(point)
                else:
                    skipped.append(curve.objectType)

            _ui.activeSelections.clear()
            for point in created:
                _ui.activeSelections.add(point)

            if not created:
                _ui.messageBox("No supported sketch curves were selected.")
                return

            message = "Added {} midpoint point{}.".format(
                len(created), "" if len(created) == 1 else "s"
            )
            if skipped:
                message += " {} selection{} skipped.".format(
                    len(skipped), "" if len(skipped) == 1 else "s"
                )
            _ui.messageBox(message)
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed to add midpoint points:\n{}".format(traceback.format_exc()))


class CommandDestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        pass


def _is_supported_curve(entity):
    return getattr(entity, "objectType", "").split("::")[-1] in _SUPPORTED_TYPES


def _add_midpoint(curve):
    sketch = getattr(curve, "parentSketch", None)
    if not sketch:
        return None

    midpoint = _evaluate_midpoint(curve)
    if midpoint is None:
        return None

    sketch_point = sketch.sketchPoints.add(midpoint)
    try:
        sketch.geometricConstraints.addMidPoint(sketch_point, curve)
    except:  # Some Fusion versions do not expose midpoint constraints for splines.
        sketch.geometricConstraints.addCoincident(sketch_point, curve)
    return sketch_point


def _evaluate_midpoint(curve):
    geometry = curve.geometry
    evaluator = geometry.evaluator
    result = evaluator.getParameterExtents()
    if not result[0]:
        return None

    start_parameter = result[1]
    end_parameter = result[2]
    midpoint_parameter = (start_parameter + end_parameter) / 2.0
    point_result = evaluator.getPointAtParameter(midpoint_parameter)
    if not point_result[0]:
        return None
    return point_result[1]
