# demo — 讲解录屏与复现脚本

成品:**`prism-datagen-demo.mp4`**（≥3 分钟,edge-tts 舒缓女声中文讲解 + 精确打轴的中英双语字幕,展示 Web UI 全流程)。

## 复现三步

```bash
# 0) 依赖
python -m pip install edge-tts imageio-ffmpeg fastapi uvicorn
npm i playwright                         # 浏览器若未装:npx playwright install chromium
# 另需一个带 libass 的 ffmpeg(系统 ffmpeg 即可,字幕烧录用)

# 1) 生成讲解音轨 + 中英字幕(edge-tts zh-CN-XiaoxiaoNeural, rate -10%)
python build_audio.py                    # → master.wav, subs.srt, scenes.json

# 2) 录制 Playwright 走查(按 scenes.json 的分镜时长驱动 UI)
python ../server.py &                     # 先起 UI(127.0.0.1:8123)
node record.mjs                          # → video/*.webm

# 3) 混流:视频 + 音轨 + 烧录双语字幕
python mux.py                            # → prism-datagen-demo.mp4
```

## 构成

| 文件 | 作用 |
|---|---|
| `build_audio.py` | 分镜脚本(action-key + 中文旁白 + 英文字幕);逐镜 edge-tts、测时长、拼 `master.wav`、生成同步 `subs.srt` 与 `scenes.json` |
| `record.mjs` | 读 `scenes.json`,按每镜时长驱动 UI(拖旋钮、换种子、悬停真值链…),录成 webm |
| `mux.py` | ffmpeg 混流视频+音轨,并用 `subtitles` 滤镜烧录中英双语字幕 |
| `subs.srt` | 中英双语字幕(中文在上、英文在下),打轴与旁白逐镜对齐 |
| `scenes.json` | 每镜的 `dur`/`gap` 与 action-key —— 音画同步的单一事实源 |

字幕是**烧录**进画面的(硬字幕),无需外挂;`master.wav` 与视频等长,`mux.py -shortest` 对齐收尾。
确定性:UI 与生成器都是确定性的,所以同一套脚本每次录出的画面一致。
