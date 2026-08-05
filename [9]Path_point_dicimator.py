bl_info = {
    "name": "Path Point Decimator",
    "author": "ChatGPT (Sora)",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > Path Tools",
    "description": "Decimate curve control points while keeping endpoints (Blender 4.x safe).",
    "category": "Object",
}

import bpy
from bpy.props import EnumProperty, IntProperty, FloatProperty
from mathutils import Vector


# -------------------------
# helpers
# -------------------------
def _curve_targets(context):
    sel = [o for o in context.selected_objects if o.type == "CURVE"]
    if sel:
        return sel
    ao = context.active_object
    if ao and ao.type == "CURVE":
        return [ao]
    return []


def _get_world_co_from_point(obj, p):
    # NURBS/POLY point: p.co is (x,y,z,w)
    # Bezier point: p.co is (x,y,z)
    co = p.co
    if len(co) == 4:
        v = Vector((co[0], co[1], co[2]))
    else:
        v = Vector(co)
    return obj.matrix_world @ v


def _compute_keep_indices_step(n, step):
    if n <= 2:
        return set(range(n))
    step = max(2, int(step))
    keep = {0, n - 1}
    for i in range(1, n - 1):
        if i % step == 0:
            keep.add(i)
    return keep


def _compute_keep_indices_distance(obj, pts, dist_thresh):
    n = len(pts)
    if n <= 2 or dist_thresh <= 0:
        return set(range(n))

    keep = [0]
    last = _get_world_co_from_point(obj, pts[0])

    for i in range(1, n - 1):
        cur = _get_world_co_from_point(obj, pts[i])
        if (cur - last).length >= dist_thresh:
            keep.append(i)
            last = cur

    keep.append(n - 1)
    return set(keep)


def _select_points_in_editmode(obj, spline_index, indices_to_select):
    """
    indices_to_select: set of indices within that spline to select (for deletion)
    """
    crv = obj.data
    sp = crv.splines[spline_index]

    # clear selection
    for s in crv.splines:
        if s.type == "BEZIER":
            for bp in s.bezier_points:
                bp.select_control_point = False
                bp.select_left_handle = False
                bp.select_right_handle = False
        else:
            for p in s.points:
                p.select = False

    # select targets
    if sp.type == "BEZIER":
        for i, bp in enumerate(sp.bezier_points):
            if i in indices_to_select:
                bp.select_control_point = True
                # ハンドルも一緒に選択（削除対象として自然）
                bp.select_left_handle = True
                bp.select_right_handle = True
    else:
        for i, p in enumerate(sp.points):
            if i in indices_to_select:
                p.select = True


def _delete_selected_points(context):
    # Curve edit delete
    bpy.ops.curve.delete(type='VERT')


# -------------------------
# operator
# -------------------------
class PATHDECIMATE_OT_decimate(bpy.types.Operator):
    bl_idname = "pathdecimate.decimate"
    bl_label = "Decimate Path Points"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = _curve_targets(context)
        if not objs:
            self.report({"WARNING"}, "No curve object selected (or active).")
            return {"CANCELLED"}

        scn = context.scene
        mode = scn.pathdec_mode
        step = scn.pathdec_step
        dist_thresh = scn.pathdec_distance

        # store original state
        prev_active = context.view_layer.objects.active
        prev_mode = prev_active.mode if prev_active else "OBJECT"

        total_removed = 0
        total_splines = 0

        # We must operate in Edit Mode on each curve object
        for obj in objs:
            context.view_layer.objects.active = obj

            # Ensure object mode first
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            # Enter edit mode
            bpy.ops.object.mode_set(mode="EDIT")

            crv = obj.data
            if not crv.splines:
                bpy.ops.object.mode_set(mode="OBJECT")
                continue

            # For each spline, compute deletion indices, select, delete
            for si, sp in enumerate(crv.splines):
                if sp.type == "BEZIER":
                    pts = sp.bezier_points
                else:
                    pts = sp.points

                n = len(pts)
                if n <= 2:
                    total_splines += 1
                    continue

                if mode == "STEP":
                    keep = _compute_keep_indices_step(n, step)
                else:
                    keep = _compute_keep_indices_distance(obj, pts, dist_thresh)

                delete_set = {i for i in range(n) if i not in keep}
                if delete_set:
                    _select_points_in_editmode(obj, si, delete_set)
                    _delete_selected_points(context)
                    total_removed += len(delete_set)

                total_splines += 1

            # back to object mode
            bpy.ops.object.mode_set(mode="OBJECT")
            crv.update()

        # restore previous active/mode
        if prev_active:
            context.view_layer.objects.active = prev_active
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass

        self.report(
            {"INFO"},
            f"Decimated {len(objs)} curve(s), {total_splines} spline(s). Removed ~{total_removed} point(s)."
        )
        return {"FINISHED"}


class PATHDECIMATE_PT_panel(bpy.types.Panel):
    bl_label = "Path Point Decimator"
    bl_idname = "PATHDECIMATE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Path Tools"

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        layout.label(text="Target: selected curve(s)")

        box = layout.box()
        box.prop(scn, "pathdec_mode", text="Mode")
        if scn.pathdec_mode == "STEP":
            box.prop(scn, "pathdec_step", text="Keep every Nth")
            box.label(text="Keeps start/end + indices % N == 0", icon="INFO")
        else:
            box.prop(scn, "pathdec_distance", text="Min distance")
            box.label(text="Keeps start/end + spaced points", icon="INFO")

        layout.separator()
        layout.operator("pathdecimate.decimate", icon="MOD_DECIM")


classes = (
    PATHDECIMATE_OT_decimate,
    PATHDECIMATE_PT_panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    S = bpy.types.Scene
    S.pathdec_mode = EnumProperty(
        name="Mode",
        items=[
            ("STEP", "Index Step", "Keep every Nth point (plus endpoints)"),
            ("DIST", "Distance", "Keep points spaced by minimum distance (plus endpoints)"),
        ],
        default="STEP",
    )
    S.pathdec_step = IntProperty(
        name="Keep every Nth",
        default=2,
        min=2,
        max=1000,
    )
    S.pathdec_distance = FloatProperty(
        name="Min distance",
        default=0.5,
        min=0.0,
        soft_max=10.0,
    )


def unregister():
    S = bpy.types.Scene
    for p in ("pathdec_mode", "pathdec_step", "pathdec_distance"):
        if hasattr(S, p):
            delattr(S, p)

    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
