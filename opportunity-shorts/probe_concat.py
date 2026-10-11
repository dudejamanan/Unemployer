"""Throwaway probe: does ffmpeg's concat demuxer honour the LAST file's duration?"""
import re
import subprocess
import tempfile
import os

d = tempfile.mkdtemp()
for name, color in (("a.png", "red"), ("b.png", "blue")):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c={color}:s=320x560", "-frames:v", "1", os.path.join(d, name)],
        check=True,
    )

concat = os.path.join(d, "c.txt")
with open(concat, "w") as f:
    f.write("file 'a.png'\nduration 2.0\nfile 'b.png'\nduration 3.0\n")

r = subprocess.run(
    ["ffmpeg", "-f", "concat", "-safe", "0", "-i", "c.txt", "-f", "null", "-"],
    cwd=d, capture_output=True, text=True,
)
m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
print(f"concat total = {sec} s (expected 5.0 if last duration honoured)")
