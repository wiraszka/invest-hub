import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge

# ── Config ─────────────────────────────────────────────────────────────────────

OUT_WEBM = "donut_loader_alpha.webm"
FRAME_DIR = Path("donut_frames")

VALUES = [60, 25, 15]
COLORS = ["#d4af37", "#c0c0c0", "#b87333"]

OUTER_R = 1.0
INNER_R = 0.62
WIDTH = OUTER_R - INNER_R

START_ANGLE = 90
N_FRAMES = 90
FPS = 30
DPI = 220

# ── Setup ──────────────────────────────────────────────────────────────────────

if FRAME_DIR.exists():
    shutil.rmtree(FRAME_DIR)
FRAME_DIR.mkdir(parents=True, exist_ok=True)

total = sum(VALUES)
slice_angles = [v / total * 360 for v in VALUES]

theta_starts = [START_ANGLE]
for a in slice_angles[:-1]:
    theta_starts.append(theta_starts[-1] + a)

theta_ends = [s + a for s, a in zip(theta_starts, slice_angles)]


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


# ── Render frames ──────────────────────────────────────────────────────────────

for frame in range(N_FRAMES):
    progress = frame / (N_FRAMES - 1)
    progress = ease_out_cubic(progress)

    fig, ax = plt.subplots(figsize=(5, 5), facecolor="none")
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    ax.patch.set_alpha(0)

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)

    for color, theta1, theta2_final in zip(COLORS, theta_starts, theta_ends):
        theta2 = theta1 + (theta2_final - theta1) * progress

        wedge = Wedge(
            center=(0, 0),
            r=OUTER_R,
            theta1=theta1,
            theta2=theta2,
            width=WIDTH,
            facecolor=color,
            edgecolor="none",
        )
        ax.add_patch(wedge)

    out_path = FRAME_DIR / f"frame_{frame:04d}.png"
    fig.savefig(
        out_path,
        dpi=DPI,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0,
    )
    plt.close(fig)

print(f"Rendered {N_FRAMES} frames to {FRAME_DIR.resolve()}")

first_frame = FRAME_DIR / "frame_0000.png"
mid_frame = FRAME_DIR / f"frame_{N_FRAMES // 2:04d}.png"
last_frame = FRAME_DIR / f"frame_{N_FRAMES - 1:04d}.png"

print("Check these files manually:")
print(first_frame.resolve())
print(mid_frame.resolve())
print(last_frame.resolve())

# ── Encode WebM ────────────────────────────────────────────────────────────────

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

cmd = [
    ffmpeg_exe,
    "-y",
    "-framerate",
    str(FPS),
    "-i",
    str(FRAME_DIR / "frame_%04d.png"),
    "-c:v",
    "libvpx-vp9",
    "-pix_fmt",
    "yuva420p",
    "-auto-alt-ref",
    "0",
    OUT_WEBM,
]

print("Running ffmpeg:")
print(" ".join(cmd))

result = subprocess.run(cmd, capture_output=True, text=True)

print("ffmpeg return code:", result.returncode)
if result.stdout:
    print("ffmpeg stdout:\n", result.stdout)
if result.stderr:
    print("ffmpeg stderr:\n", result.stderr)

if result.returncode == 0:
    print(f"Saved {Path(OUT_WEBM).resolve()}")
else:
    print("Encoding failed.")
