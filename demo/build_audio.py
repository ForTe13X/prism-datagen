# -*- coding: utf-8 -*-
"""Generate per-scene neural TTS (edge-tts, gentle female voice), measure durations, and emit a synced
bilingual SRT, a single master.wav, and scenes.json (durations + action keys) for the Playwright walkthrough.

    python -m pip install edge-tts imageio-ffmpeg
    python build_audio.py            # → master.wav, subs.srt, scenes.json
"""
import json
import os
import subprocess
import wave

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "assets")
os.makedirs(A, exist_ok=True)

VOICE = "zh-CN-XiaoxiaoNeural"   # 温柔舒缓的女声
RATE = "-10%"                    # 稍慢一点,更柔和
SR = 24000
LEAD, GAP, TAIL = 0.8, 0.5, 1.8  # seconds: lead-in silence, inter-scene gap, end tail

# (action-key, Chinese narration, English subtitle)
SCENES = [
    ("intro", "prism-datagen,是一个确定性的跨源数据包生成器。它生成的,是带着已知因果真值的脏数据。",
     "prism-datagen is a deterministic cross-source data generator. What it makes is messy data that carries a known causal ground truth."),
    ("problem", "要评测一个跨源解析器,你既需要脏数据,又需要真值。真实数据没有真值标注,纯合成又太干净。这个工具,两者兼得。",
     "To evaluate a cross-source resolver you need messy data AND ground truth. Real data has no labels; pure synthetic is too clean. This tool gives you both."),
    ("overview", "一次生成,你拿到三种源:关系型的运单表、每个仓的吞吐量时序、还有港口新闻文本。",
     "One run gives you three sources: a relational shipments table, per-warehouse throughput time-series, and port-news text."),
    ("chain", "真值是一条跨源因果链:一条新闻事件,引起某个仓的吞吐量异常,进而让若干运单延误。它在生成之前,就被预先埋好。",
     "The ground truth is a cross-source causal chain: a news event causes a warehouse throughput anomaly, which delays certain shipments — embedded before generation."),
    ("truth_first", "关键在于:真值先建,所有观测再向它对齐。所以真值永远可恢复 —— 知道答案的 oracle 解法,恒为满分。",
     "The key: truth is authored first, then every observation is made consistent with it. So the truth is always recoverable — the oracle solver always scores a perfect one."),
    ("determinism", "整个过程完全确定性:相同的种子和旋钮,逐字节可复现。没有随机,没有时钟,只有 sha256。",
     "The whole process is fully deterministic: same seed and knobs, byte-for-byte reproducible. No random, no clock — just sha256."),
    ("dirt_up", "第一个旋钮,是脏度。把它拉高,观测开始被污染:别名改写、单位从公斤漂成磅、状态被置空、时间偏移、还有编码乱码。",
     "The first knob is dirtiness. Turn it up and observations get corrupted: aliased names, kilograms drifting to pounds, nulled statuses, time shifts, and mojibake."),
    ("corruption_map", "但每一处污染,都被记进 corruption_map,是可逆的 变体到规范 映射。而真值,一个字都没有动。",
     "But every corruption is logged into the corruption map as a reversible variant-to-canonical entry. And the truth — not one character changed."),
    ("link_sweep", "第二个旋钮,是显眼度:新闻把它命中哪些运单,暴露得多明显。从直接写出 id,一路降到只剩纯语义线索。",
     "The second knob is link-explicitness: how conspicuously the news reveals which shipments it hits — from literal ids down to pure semantic hints."),
    ("disc", "看判别力:显眼度一降,靠字面匹配的 naive 解法立刻崩到零;而做跨源联结的 linked 解法,仍然能恢复。这说明任务确实需要跨源推理。",
     "Watch the discriminability: as explicitness drops, the literal naive solver collapses to zero, while the cross-source linked solver still recovers. The task genuinely needs cross-source reasoning."),
    ("throughput", "每个仓一条吞吐量曲线;真值事件,会在它那一帧刻出一道异常凹陷 —— 这就是连接新闻与运单的中间证据。",
     "Each warehouse has a throughput curve; the true event carves an anomaly dip at its frame — the middle evidence linking news to shipments."),
    ("hover", "把鼠标悬到任意一条真值链上,它命中的仓、那道凹陷、和被延误的运单,会同时高亮 —— 一眼看清整条跨源链路。",
     "Hover any ground-truth chain and its warehouse, that dip, and the delayed shipments light up together — the whole cross-source path at a glance."),
    ("news_ships", "新闻里,真值事件标了星,干扰项被压暗,乱码和时移都打了标记;运单表里,延误的行会高亮,漂成磅的、被置空的,也一目了然。",
     "In the news, true events are starred, distractors dimmed, garble and time-shift flagged; in the shipments table, delayed rows glow, and pounds-drift and nulled status stand out."),
    ("seed", "换一个种子,就是另一个平行世界;换回来,分毫不差。这,就是确定性的意义。",
     "Change the seed and you get another parallel world; change it back and it's identical to the byte. That's what determinism buys you."),
    ("cli", "同一个生成器,也有命令行:一条命令,生成、评测、导出成 JSON、CSV,和可以直接查询的 SQLite;而核心,零依赖。",
     "The same generator has a CLI: one command to generate, evaluate, and export to JSON, CSV, and a directly-queryable SQLite — and the core has zero dependencies."),
    ("honest", "诚实的边界也要说清:分布是手设合成、没有做真实校准;这里的 linked,只是确定性的占位替身,真正的语义求解,留给未来的大模型。",
     "The honest limits, stated plainly: distributions are hand-set, not calibrated to real data; the linked solver here is a deterministic stand-in — real semantic solving is left to a future LLM."),
    ("outro", "确定性、真值始终可恢复、两个旋钮调难度、多模态物化。这,就是 prism-datagen。",
     "Deterministic, truth always recoverable, two knobs for difficulty, multi-modal export. This is prism-datagen."),
]


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_tts(mp3, zh):
    # edge-tts is an online service (speech.platform.bing.com) and intermittently drops the connection; it also
    # exits 0 while writing a 0-byte file on failure. Retry with backoff, checking the file actually has bytes.
    import time
    for attempt in range(8):
        try:
            if os.path.exists(mp3):
                os.remove(mp3)
            run("python", "-m", "edge_tts", "--voice", VOICE, f"--rate={RATE}", "--text", zh, "--write-media", mp3)
            if os.path.exists(mp3) and os.path.getsize(mp3) > 200:
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(min(20, 2.0 * (attempt + 1)))
    raise RuntimeError(f"edge-tts failed after retries for: {zh[:30]}...")


def wav_dur(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def silence(path, secs):
    run(FF, "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{secs:.3f}", "-c:a", "pcm_s16le", path)


def srt_ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        s += 1; ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    srt, concat_lines = [], []
    sil_lead = os.path.join(A, "sil_lead.wav"); silence(sil_lead, LEAD)
    sil_gap = os.path.join(A, "sil_gap.wav"); silence(sil_gap, GAP)
    sil_tail = os.path.join(A, "sil_tail.wav"); silence(sil_tail, TAIL)

    scenes_out = []
    concat_lines.append(sil_lead)
    t = LEAD
    for i, (act, zh, en) in enumerate(SCENES):
        mp3 = os.path.join(A, f"s{i:02d}.mp3")
        wav = os.path.join(A, f"s{i:02d}.wav")
        # resumable: reuse an already-synthesized scene wav (survives a mid-run network drop on re-run)
        if not (os.path.exists(wav) and wav_dur(wav) > 0.3):
            run_tts(mp3, zh)
            run(FF, "-y", "-i", mp3, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", wav)
        d = wav_dur(wav)
        srt.append((len(srt) + 1, t, t + d, zh, en))
        scenes_out.append({"i": i, "act": act, "dur": round(d, 3), "gap": GAP})
        concat_lines.append(wav)
        if i < len(SCENES) - 1:
            concat_lines.append(sil_gap)
        t += d + (GAP if i < len(SCENES) - 1 else 0)
    concat_lines.append(sil_tail)
    total = t + TAIL

    listfile = os.path.join(A, "concat.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in concat_lines:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")
    master = os.path.join(HERE, "master.wav")
    run(FF, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c:a", "pcm_s16le", master)

    with open(os.path.join(HERE, "subs.srt"), "w", encoding="utf-8") as f:
        for idx, a, b, zh, en in srt:
            f.write(f"{idx}\n{srt_ts(a)} --> {srt_ts(b)}\n{zh}\n{en}\n\n")

    with open(os.path.join(HERE, "scenes.json"), "w", encoding="utf-8") as f:
        json.dump({"lead": LEAD, "tail": TAIL, "total": round(total, 3), "scenes": scenes_out}, f, ensure_ascii=False, indent=2)

    print(f"scenes={len(SCENES)} total_audio={total:.1f}s master={master}")


if __name__ == "__main__":
    main()
