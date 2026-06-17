import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from camera_anim import add_keyframe, sample_camera_pose, delete_keyframe_at, sequence_end_frame

f = {"pos": (0.0, 0.0), "angle": 0.0, "height": 10.0, "format": "16:9", "keyframes": []}
f["pos"] = (0.0, 0.0); f["angle"] = 0.0; f["height"] = 10.0
add_keyframe(f, 0)
f["pos"] = (10.0, 0.0); f["angle"] = 1.0; f["height"] = 20.0
add_keyframe(f, 100)
# midpoint with smooth easing: smoothstep(0.5)=0.5 -> exactly halfway
pos, ang, h = sample_camera_pose(f, 50)
assert abs(pos[0] - 5.0) < 1e-6, pos
assert abs(h - 15.0) < 1e-6, h
# clamp before first / after last
assert sample_camera_pose(f, -10)[0][0] == 0.0
assert sample_camera_pose(f, 999)[0][0] == 10.0
# linear interp at quarter
f["keyframes"][1]["interp"] = "linear"
pos2, _, _ = sample_camera_pose(f, 25)
assert abs(pos2[0] - 2.5) < 1e-6, pos2
assert sequence_end_frame(f) == 100
# replace + delete
add_keyframe(f, 0); assert len(f["keyframes"]) == 2
delete_keyframe_at(f, 100); assert len(f["keyframes"]) == 1
print("OK")
