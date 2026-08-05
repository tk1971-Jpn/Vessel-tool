
import bpy
import json
from pathlib import Path
from mathutils import Vector, Matrix
import math

# ====== SETTINGS ======
# 生成された新しいJSONファイルのパスに書き換えてください
JSON_PATH = r"/Users/tkimura/Desktop/vessel_centerline_dual.json"
COLLECTION_NAME = "Centerlines_JSON"

MM_TO_BU = 0.02
ROT_X_DEG = -90.0

# 血管の肉付け設定（不要な場合は 0.0 にしてください）
BEVEL_DEPTH_MM = 0.6
BEVEL_RESOLUTION = 2

# ★カーブの滑らかさ（表示/レンダー）
CURVE_RES_U = 16

# ★NURBSの性質
NURBS_ORDER = 4          # 4が無難（制御点数が少ない線は自動で下がります）
USE_ENDPOINT = True      # 端点を通す（形が元の点列に綺麗に沿うようになります）
# ======================

def ensure_collection(name: str):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col

def safe_select_active(obj):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    obj.select_set(True)
    vl.objects.active = obj

def import_perfect_vessel_centerline(json_path: str):
    p = Path(json_path)
    if not p.exists():
        raise FileNotFoundError(f"JSON not found: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    polylines = data.get("polylines", [])
    if not polylines:
        raise ValueError("No 'polylines' found in JSON.")

    col = ensure_collection(COLLECTION_NAME)

    # 3Dカーブオブジェクトの初期設定
    curve_data = bpy.data.curves.new(name=p.stem, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = CURVE_RES_U
    curve_data.render_resolution_u = CURVE_RES_U

    # ベベル（厚み）の設定
    if BEVEL_DEPTH_MM and BEVEL_DEPTH_MM > 0:
        curve_data.bevel_depth = BEVEL_DEPTH_MM * MM_TO_BU
        curve_data.bevel_resolution = BEVEL_RESOLUTION

    obj = bpy.data.objects.new(name="vessel_centerline_perfect", object_data=curve_data)
    col.objects.link(obj)

    # 元のスクリプトと同一の回転行列（X軸-90度回転）
    Rx = Matrix.Rotation(math.radians(ROT_X_DEG), 4, 'X')

    n_added = 0
    for pl in polylines:
        # 新しいJupyter側で最適化した 'blender' 配列からデータを取得
        vessel_data = pl.get("blender", [])
        if vessel_data is None or len(vessel_data) < 2:
            continue

        # NURBSスプラインの新規作成と制御点の追加
        sp = curve_data.splines.new(type='NURBS')
        sp.points.add(len(vessel_data) - 1)

        # 頂点数に応じてNURBSのOrderを最適化（エラー防止）
        sp.order_u = min(NURBS_ORDER, len(vessel_data))  
        sp.use_endpoint_u = USE_ENDPOINT
        sp.resolution_u = CURVE_RES_U

        for i, node in enumerate(vessel_data):
            x, y, z = node["pos"]
            
            # 元のスクリプトと完全に一致するミリ単位のトランスフォーム
            v = Vector((x * MM_TO_BU, y * MM_TO_BU, z * MM_TO_BU))
            v = (Rx @ v.to_4d()).to_3d()
            
            # NURBSの座標(x, y, z, w) を設定。w(重み)は1.0固定
            sp.points[i].co = (v.x, v.y, v.z, 1.0)

        n_added += 1

    if n_added == 0:
        raise ValueError("No valid polylines imported.")

    # オブジェクト自体のトランスフォームをリセット（元の仕様通り）
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)

    safe_select_active(obj)

    print(f"[OK] Successfully imported splines: {n_added} (NURBS)")
    return obj

# ---- RUN ----
import_perfect_vessel_centerline(JSON_PATH)
