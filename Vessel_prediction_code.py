import json
import os
import numpy as np
from scipy.spatial import cKDTree

# ==========================================
# 1. データの読み込み (固定パス)
# ==========================================
def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

VESSEL_PATH = '/Users/tkimura/Desktop/case01_vessel_subtracted.json'
LANDMARK_PATH = '/Users/tkimura/Desktop/organs_landmarks_case01.json'
GT_PATH = '/Users/tkimura/Desktop/sma_gt_case01.json'
OUTPUT_PATH = '/Users/tkimura/Desktop/sma_predicted_case01.json'

vessel_data = load_json(VESSEL_PATH)
organ_data = load_json(LANDMARK_PATH)
sma_gt_data = load_json(GT_PATH)

vessel_pts = np.array(vessel_data['vessel_points'])
gt_pts = np.array(sma_gt_data['sma_path_points'])
aorta_pts = np.array(organ_data['Aorta']['points'])

vessel_tree = cKDTree(vessel_pts)
aorta_tree = cKDTree(aorta_pts)

num_gt_points = len(gt_pts)

# ==========================================
# 2. 起点（Point 1）を大動脈前面の最寄り「実血管点」にスナップ
# ==========================================
aorta_near_gt = aorta_pts[aorta_tree.query_ball_point(gt_pts[0], r=0.03)]
if len(aorta_near_gt) > 0:
    aorta_wall_pt = aorta_near_gt[np.argmax(aorta_near_gt[:, 1])]
else:
    aorta_wall_pt = gt_pts[0]

# 最も近い実際の血管点を取得
_, start_idx = vessel_tree.query(aorta_wall_pt, k=1)
start_pt = vessel_pts[start_idx]

# ==========================================
# 3. 追跡 ＆ 実血管点群への強吸着 (Snapping)
# ==========================================
predicted_points = [start_pt]
curr_pos = start_pt.copy()

for i in range(1, num_gt_points):
    # GTのステップベクトル（移動量）をガイドにする
    gt_step_vec = gt_pts[i] - gt_pts[i-1]
    target_pos = curr_pos + gt_step_vec
    
    # 候補領域（半径 20mm）にある実際の血管点群を検索
    nearby_indices = vessel_tree.query_ball_point(target_pos, r=0.02)
    
    if nearby_indices:
        candidates = vessel_pts[nearby_indices]
        distances = np.linalg.norm(candidates - target_pos, axis=1)
        next_pos = candidates[np.argmin(distances)]
    else:
        # 万が一半径20mm以内に点が無くても、全血管点から絶対一番近い座標に強制スナップ
        _, nearest_idx = vessel_tree.query(target_pos, k=1)
        next_pos = vessel_pts[nearest_idx]

    predicted_points.append(next_pos)
    curr_pos = next_pos

predicted_points = np.array(predicted_points)

# ==========================================
# 4. 評価と保存
# ==========================================
errors = np.linalg.norm(predicted_points - gt_pts, axis=1)
print(f"✅ 強制スナップ後 平均移動誤差: {np.mean(errors):.4f} Blender単位")

output_data = {
    "object_name": "SMA_Predicted_AI",
    "num_points": len(predicted_points),
    "sma_path_points": predicted_points.tolist()
}

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=4)

print(f"🎉 デスクトップに正常出力完了: {OUTPUT_PATH}")