"""
FlattenCurveToPlane
--------------------
A Fusion 360 Add-In that lets you select a sketch line or spline and moves
every point of that curve onto a plane — either the curve's own sketch
plane, or another existing construction plane / planar face.

Why this is needed:
In a normal (2D) sketch, every point is already constrained to the sketch
plane. But in a 3D sketch, individual points can sit off-plane (non-zero
local Z, or off an arbitrary plane entirely). This add-in projects every
point of the selected curve straight onto the chosen plane.

Supported curve types:
  - SketchLine                (start + end point)
  - SketchFittedSpline        (fit points)
  - SketchControlPointSpline  (control points)
  - SketchFixedSpline         (control points, if editable)

Sketch points can also be selected directly.

Target planes:
  - "This curve's own sketch plane" — zeroes each point's sketch-local Z.
  - "An existing plane" — pick any construction plane or planar face;
    each point is projected (perpendicular drop) onto that plane.

Requires the curve to live in a 3D sketch (is3D). In a 2D sketch every
point is already pinned to that sketch's own plane, so there's nothing to
flatten there, and it can't hold points off an external plane either.

Install:
  1. Put this folder (FlattenCurveToPlane, containing this .py file and the
     matching .manifest file) somewhere permanent on disk.
  2. In Fusion 360: Utilities tab -> Add-Ins -> "Scripts and Add-Ins" ->
     Add-Ins tab -> green "+" -> select this folder.
  3. Run it once, or check "Run on Startup" to have it always available.
  4. A "Flatten to Plane" button appears in the Sketch Modify panel
     (Sketch environment must be active / a sketch must be open).

Use:
  1. Open / edit the sketch containing the 3D curve.
  2. Click "Flatten to Plane".
  3. Select the line or spline whose points you want to project.
  4. Choose "This curve's own sketch plane" or "An existing plane".
     If you pick the latter, select a construction plane or planar face.
  5. Click OK. The moved points are highlighted (selected) and a message
     box reports how many points were moved.
"""

import adsk.core
import adsk.fusion
import traceback

try:
    import debugpy
except ImportError:
    debugpy = None

_app = None
_ui = None
_handlers = []
_debugger_started = False

CMD_ID = "flattenCurveToPlaneCmd"
CMD_NAME = "Flatten to Plane"
CMD_TOOLTIP = "Move all points of the selected line or spline onto a plane."
PANEL_ID = "SketchModifyPanel"
RESOURCE_FOLDER = "resources"

OWN_PLANE_LABEL = "This curve's own sketch plane"
OTHER_PLANE_LABEL = "An existing plane"


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        _start_debugger()

        # Clean up any stale definition from a previous run/reload.
        existing_cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if existing_cmd_def:
            existing_cmd_def.deleteMe()

        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_TOOLTIP, RESOURCE_FOLDER
        )

        on_command_created = CommandCreatedHandler()
        cmd_def.commandCreated.add(on_command_created)
        _handlers.append(on_command_created)

        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            existing_control = panel.controls.itemById(CMD_ID)
            if existing_control:
                existing_control.deleteMe()
            control = panel.controls.addCommand(cmd_def)
            control.isPromotedByDefault = False

    except:  # noqa: E722
        if _ui:
            _ui.messageBox("FlattenCurveToPlane failed to start:\n{}".format(traceback.format_exc()))


def _start_debugger():
    global _debugger_started
    if debugpy is None or _debugger_started:
        return

    try:
        debugpy.listen(("127.0.0.1", 5678))
        _debugger_started = True
    except Exception:
        # A normal Fusion run should still work if debugpy is unavailable or
        # another copy of the add-in already owns the debug port.
        pass


def stop(context):
    try:
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            control = panel.controls.itemById(CMD_ID)
            if control:
                control.deleteMe()

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
    except:  # noqa: E722
        if _ui:
            _ui.messageBox("FlattenCurveToPlane failed to stop:\n{}".format(traceback.format_exc()))


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            curve_select = inputs.addSelectionInput(
                "curveSelect", "Curves or points", "Select lines, splines, or sketch points to flatten"
            )
            curve_select.setSelectionLimits(1, 0)
            curve_select.addSelectionFilter("SketchCurves")
            curve_select.addSelectionFilter("SketchPoints")

            plane_choice = inputs.addRadioButtonGroupCommandInput("planeChoice", "Target plane")
            plane_choice.listItems.add(OWN_PLANE_LABEL, True)
            plane_choice.listItems.add(OTHER_PLANE_LABEL, False)

            plane_select = inputs.addSelectionInput(
                "planeSelect", "Plane", "Select an origin plane, construction plane, or planar face"
            )
            plane_select.setSelectionLimits(0, 1)
            plane_select.isVisible = False

            on_input_changed = CommandInputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            _handlers.append(on_input_changed)

            on_validate_inputs = CommandValidateInputsHandler()
            cmd.validateInputs.add(on_validate_inputs)
            _handlers.append(on_validate_inputs)

            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_destroy = CommandDestroyHandler()
            cmd.destroy.add(on_destroy)
            _handlers.append(on_destroy)
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed:\n{}".format(traceback.format_exc()))


class CommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            changed_input = args.input
            if changed_input.id != "planeChoice":
                return

            inputs = args.inputs
            plane_select = inputs.itemById("planeSelect")
            selected_item = changed_input.selectedItem

            plane_select.isVisible = bool(selected_item and selected_item.name == OTHER_PLANE_LABEL)
            if not plane_select.isVisible:
                plane_select.clearSelection()
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed:\n{}".format(traceback.format_exc()))


class CommandValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            curve_select = args.inputs.itemById("curveSelect")
            plane_choice = args.inputs.itemById("planeChoice")
            plane_select = args.inputs.itemById("planeSelect")
            has_curves = curve_select.selectionCount > 0
            needs_plane = (
                plane_choice.selectedItem
                and plane_choice.selectedItem.name == OTHER_PLANE_LABEL
            )
            has_valid_plane = False
            if plane_select.selectionCount > 0:
                plane_origin, plane_normal = _get_plane_origin_and_normal(
                    plane_select.selection(0).entity
                )
                has_valid_plane = plane_origin is not None and plane_normal is not None

            args.areInputsValid = has_curves and (not needs_plane or has_valid_plane)
        except:  # noqa: E722
            args.areInputsValid = False


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.command.commandInputs

            curve_select = inputs.itemById("curveSelect")
            selected_entities = [
                curve_select.selection(index).entity
                for index in range(curve_select.selectionCount)
            ]

            plane_choice = inputs.itemById("planeChoice")
            use_own_plane = plane_choice.selectedItem.name != OTHER_PLANE_LABEL

            plane_entity = None
            if not use_own_plane:
                plane_select = inputs.itemById("planeSelect")
                if plane_select.selectionCount == 0:
                    _ui.messageBox("Select a construction plane or planar face first.")
                    return
                plane_entity = plane_select.selection(0).entity

            points = _get_selected_points(selected_entities)
            if plane_entity is None:
                moved_points = _flatten_to_own_plane(points)
            else:
                plane_origin, plane_normal = _get_plane_origin_and_normal(plane_entity)
                if plane_origin is None:
                    _ui.messageBox("Couldn't read a flat plane from that selection.")
                    return
                moved_points = []
                for point in points:
                    moved_points.extend(
                        _flatten_to_world_plane(
                            point.parentSketch, [point], plane_origin, plane_normal
                        )
                    )

            _ui.activeSelections.clear()
            for point in moved_points:
                _ui.activeSelections.add(point)

            if moved_points:
                _ui.messageBox(
                    "Moved {} point{} onto the plane.".format(
                        len(moved_points), "" if len(moved_points) == 1 else "s"
                    )
                )
            else:
                _ui.messageBox("All selected curves were already on the plane.")
        except:  # noqa: E722
            if _ui:
                _ui.messageBox("Failed:\n{}".format(traceback.format_exc()))


class CommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        pass


def flatten_curve_to_plane(curve_entity, plane_entity):
    """
    Moves every point that defines curve_entity onto a plane and returns the
    points that moved.

    If plane_entity is None, the curve's own parent-sketch plane is used
    (fast path: zero the sketch-local Z of each point). Otherwise every
    point is projected onto plane_entity (a ConstructionPlane or a planar
    BRepFace) in world space.
    """
    sketch = curve_entity.parentSketch

    points = _get_defining_points(curve_entity)
    if points is None:
        _ui.messageBox(
            "Unsupported curve type: {}\n"
            "This add-in supports lines and splines only.".format(curve_entity.objectType)
        )
        return []

    if plane_entity is None:
        moved_points = _flatten_to_own_plane(points)
    else:
        plane_origin, plane_normal = _get_plane_origin_and_normal(plane_entity)
        if plane_origin is None:
            _ui.messageBox("Couldn't read a flat plane from that selection.")
            return []
        moved_points = _flatten_to_world_plane(sketch, points, plane_origin, plane_normal)

    return moved_points


def _get_selected_points(selected_entities):
    """Expand selected curves and points into one de-duplicated point list."""
    points = []
    seen_tokens = set()
    for entity in selected_entities:
        if isinstance(entity, adsk.fusion.SketchPoint):
            entity_points = [entity]
        else:
            entity_points = _get_defining_points(entity) or []

        for point in entity_points:
            token = point.entityToken
            if token not in seen_tokens:
                seen_tokens.add(token)
                points.append(point)
    return points


def _flatten_to_own_plane(points):
    """Zeroes each point's sketch-local Z. Returns the list of points that moved."""
    moved_points = []
    for pt in points:
        local_pos = pt.geometry  # Point3D in sketch space (Z = out-of-plane offset)
        if abs(local_pos.z) > 1e-9:
            delta = adsk.core.Vector3D.create(0.0, 0.0, -local_pos.z)
            pt.move(delta)
            moved_points.append(pt)
    return moved_points


def _flatten_to_world_plane(sketch, points, plane_origin, plane_normal):
    """
    Projects each point onto an arbitrary plane (given in world/model
    space), then converts the resulting world position back into the
    sketch's local coordinate system to build the move delta.
    Returns the list of points that moved.
    """
    normal = plane_normal.copy()
    normal.normalize()

    moved_points = []
    for pt in points:
        local_pos = pt.geometry
        world_pos = sketch.sketchToModelSpace(local_pos)

        offset_vec = adsk.core.Vector3D.create(
            world_pos.x - plane_origin.x,
            world_pos.y - plane_origin.y,
            world_pos.z - plane_origin.z,
        )
        distance = offset_vec.dotProduct(normal)

        if abs(distance) <= 1e-9:
            continue

        drop = normal.copy()
        drop.scaleBy(-distance)
        new_world_pos = world_pos.copy()
        new_world_pos.translateBy(drop)

        new_local_pos = sketch.modelToSketchSpace(new_world_pos)

        delta = adsk.core.Vector3D.create(
            new_local_pos.x - local_pos.x,
            new_local_pos.y - local_pos.y,
            new_local_pos.z - local_pos.z,
        )
        pt.move(delta)
        moved_points.append(pt)

    return moved_points


def _get_plane_origin_and_normal(plane_entity):
    """
    Returns (Point3D origin, Vector3D normal) for a ConstructionPlane or a
    planar BRepFace, in world/model space, or (None, None) if unsupported.
    """
    if isinstance(plane_entity, adsk.fusion.ConstructionPlane):
        plane_geom = plane_entity.geometry
        return plane_geom.origin, plane_geom.normal

    if isinstance(plane_entity, adsk.fusion.BRepFace):
        plane_geom = adsk.core.Plane.cast(plane_entity.geometry)
        if plane_geom:
            return plane_geom.origin, plane_geom.normal

    return None, None


def _get_defining_points(curve_entity):
    """
    Returns the list of SketchPoint objects that define curve_entity's
    shape, or None if the type isn't handled.
    """
    if isinstance(curve_entity, adsk.fusion.SketchLine):
        return [curve_entity.startSketchPoint, curve_entity.endSketchPoint]

    if isinstance(curve_entity, adsk.fusion.SketchFittedSpline):
        return list(curve_entity.fitPoints)

    if isinstance(curve_entity, adsk.fusion.SketchControlPointSpline):
        return list(curve_entity.controlPoints)

    if isinstance(curve_entity, adsk.fusion.SketchFixedSpline):
        # Fixed splines are generally not user-editable point by point;
        # attempt controlPoints if exposed, otherwise bail out.
        try:
            return list(curve_entity.controlPoints)
        except AttributeError:
            return None

    return None
