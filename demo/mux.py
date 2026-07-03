# -*- coding: utf-8 -*-
"""Mux the Playwright walkthrough (video/*.webm) with the narration (master.wav) and BURN the bilingual
subtitles (subs.srt) → prism-datagen-demo.mp4. Run from this demo/ directory (relative paths keep ffmpeg's
subtitles filter happy on Windows).

    python mux.py

Needs an ffmpeg with libass (the subtitles filter). The system ffmpeg (gyan.dev full build) has it;
imageio-ffmpeg's bundled binary may not, so we prefer a system ffmpeg on PATH.
"""
import glob
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

FF = shutil.which("ffmpeg")
if not FF:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
    print("WARN: using imageio-ffmpeg; if the subtitles filter fails, install a system ffmpeg with libass")

webms = sorted(glob.glob(os.path.join("video", "*.webm")))
if not webms:
    raise SystemExit("no walkthrough video found — run `node record.mjs` first")
video = webms[-1]
OUT = os.path.join(HERE, "prism-datagen-demo.mp4")

# bilingual subs: zh (line 1) larger on top of each cue, en (line 2) below; readable on the dark UI.
style = ("FontName=Microsoft YaHei,FontSize=17,PrimaryColour=&H00FFFFFF,"
         "OutlineColour=&HC0000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=26,Alignment=2")
vf = f"subtitles=subs.srt:force_style='{style}'"

cmd = [FF, "-y", "-i", video, "-i", "master.wav",
       "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-shortest", OUT]
print("muxing →", OUT)
subprocess.run(cmd, check=True)
# report duration
probe = subprocess.run([FF, "-i", OUT], capture_output=True, text=True)
for line in probe.stderr.splitlines():
    if "Duration" in line:
        print(line.strip())
print("done:", OUT)
