def _smoothstep(u):
    return u * u * (3.0 - 2.0 * u)


def add_keyframe(frame, t):
    t = int(t)
    kf = {"t": t, "pos": tuple(frame["pos"]), "angle": float(frame["angle"]),
          "height": float(frame["height"]), "interp": "smooth"}
    keys = [k for k in frame.get("keyframes", []) if k["t"] != t]
    keys.append(kf)
    keys.sort(key=lambda k: k["t"])
    frame["keyframes"] = keys


def delete_keyframe_at(frame, t):
    frame["keyframes"] = [k for k in frame.get("keyframes", []) if k["t"] != int(t)]


def sequence_end_frame(frame):
    keys = frame.get("keyframes", [])
    return keys[-1]["t"] if keys else 0


def sample_camera_pose(frame, t):
    keys = frame.get("keyframes", [])
    if not keys:
        return tuple(frame["pos"]), float(frame["angle"]), float(frame["height"])
    if len(keys) == 1 or t <= keys[0]["t"]:
        k = keys[0]; return tuple(k["pos"]), k["angle"], k["height"]
    if t >= keys[-1]["t"]:
        k = keys[-1]; return tuple(k["pos"]), k["angle"], k["height"]
    # find bracketing keys
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if a["t"] <= t <= b["t"]:
            span = (b["t"] - a["t"]) or 1
            u = (t - a["t"]) / span
            if b["interp"] == "smooth":
                u = _smoothstep(u)
            pos = (a["pos"][0] + (b["pos"][0] - a["pos"][0]) * u,
                   a["pos"][1] + (b["pos"][1] - a["pos"][1]) * u)
            ang = a["angle"] + (b["angle"] - a["angle"]) * u
            h = a["height"] + (b["height"] - a["height"]) * u
            return pos, ang, h
    k = keys[-1]; return tuple(k["pos"]), k["angle"], k["height"]


def apply_pose(frame, pose):
    pos, angle, height = pose
    frame["pos"] = pos; frame["angle"] = angle; frame["height"] = height
