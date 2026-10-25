"""One page that plays a lesson: each beat's audio, then the checkpoint pause."""

import json
from pathlib import Path

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: Georgia, serif; background: #f6f3ec; color: #1d2430; }}
    main {{ max-width: 880px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1 {{ font-size: 18px; font-weight: 600; margin: 0 0 8px; }}
    .stage {{ min-height: 280px; background: white; border-radius: 16px; padding: 28px; box-shadow: 0 8px 24px rgba(29, 36, 48, 0.06); }}
    .columns {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; position: relative; min-height: 140px; }}
    .column {{ border-bottom: 2px solid #d9d2c5; text-align: center; padding-top: 72px; color: #8a8175; font-size: 13px; }}
    .digit {{ position: absolute; top: 8px; width: 64px; margin-left: -32px; text-align: center; font-size: 64px; line-height: 1; }}
    .label {{ margin-top: 24px; font-size: 28px; }}
    .badge {{ display: inline-block; margin-top: 12px; padding: 6px 10px; border-radius: 999px; background: #e7f0e4; }}
    .sentence {{ font-size: 32px; line-height: 1.4; }}
    .sentence span.on {{ background: #ffe08a; }}
    .part {{ margin-top: 12px; padding: 12px; border-left: 4px solid #2f6f4e; background: #f3f7f4; }}
    .path {{ height: 8px; background: #e6e0d6; border-radius: 999px; margin: 28px 0; }}
    .path > div {{ height: 8px; background: #2f6f4e; border-radius: 999px; }}
    .steps {{ display: flex; justify-content: space-between; gap: 8px; }}
    .controls {{ display: flex; align-items: center; gap: 12px; margin-top: 20px; font-family: sans-serif; font-size: 14px; }}
    button {{ font: inherit; padding: 8px 14px; border-radius: 999px; border: 0; background: #1d2430; color: white; }}
    label {{ flex: 1; }}
    input {{ width: 100%; }}
    body.capture h1, body.capture .controls {{ display: none; }}
    body.capture main {{ min-height: 100vh; display: flex; align-items: center; padding-top: 0; padding-bottom: 0; box-sizing: border-box; }}
    body.capture .stage {{ width: 100%; }}
  </style>
</head>
<body>
  <main>
    <h1 id="title"></h1>
    <div class="stage" id="stage"></div>
    <div class="controls">
      <button id="play" type="button">Play</button>
      <label>Time <output id="readout">0.00s</output>
        <input id="slider" type="range" min="0" step="0.01" value="0" />
      </label>
    </div>
  </main>
  <script>
    const lesson = {lesson_json};
    const columns = ["tens", "ones", "tenths", "hundredths"];
    const stage = document.getElementById("stage");
    const slider = document.getElementById("slider");
    const readout = document.getElementById("readout");
    const play = document.getElementById("play");
    const audios = {{}};
    let lessonTime = 0;
    let playing = false;
    let scrubbing = false;
    let active = null;
    let lastTick = null;

    for (const beat of lesson.beats) {{
      if (!beat.audio_file) continue;
      const audio = document.createElement("audio");
      audio.preload = "auto";
      audio.src = beat.audio_file;
      audios[beat.id] = audio;
    }}

    function clamp(value) {{
      return Math.min(1, Math.max(0, value));
    }}

    function span(t, start, end) {{
      if (end <= start) return t >= end ? 1 : 0;
      if (t <= start) return 0;
      if (t >= end) return 1;
      return (t - start) / (end - start);
    }}

    function renderDigitSlide(settings, t, beat) {{
      const cues = beat.cues || {{}};
      const duration = beat.duration || 1;
      const from = columns.indexOf(settings.from_column);
      const to = columns.indexOf(settings.to_column);
      const move = span(t, 0, cues.slide_end ?? duration);
      const index = from + (to - from) * move;
      const left = ((index + 0.5) / columns.length) * 100;
      stage.innerHTML = `
        <div class="columns">
          ${{columns.map((name) => `<div class="column">${{name}}</div>`).join("")}}
          <div class="digit" style="left:${{left}}%">${{settings.digit}}</div>
        </div>
        <div class="label" style="opacity:${{span(t, cues.label_start ?? duration * 0.72, cues.label_end ?? duration)}}">${{settings.label}}</div>
        <div class="badge" style="opacity:${{settings.badge ? span(t, cues.badge_start ?? duration * 0.84, cues.badge_end ?? duration) : 0}}">${{settings.badge || ""}}</div>`;
    }}

    function renderHighlightWords(settings, t, beat) {{
      const p = clamp(t / (beat.duration || 1));
      const shown = Math.floor(p * settings.emphasis.length + 0.0001);
      const emphasis = new Set(settings.emphasis.slice(0, shown).map((word) => word.replace(/[^\\p{{L}}\\p{{N}}']/gu, "")));
      const words = settings.sentence.split(/(\\s+)/);
      stage.innerHTML = `<div class="sentence">${{words.map((word) => {{
        const bare = word.replace(/[^\\p{{L}}\\p{{N}}']/gu, "");
        return emphasis.has(bare) ? `<span class="on">${{word}}</span>` : word;
      }}).join("")}}</div>`;
    }}

    function renderLabelCallout(settings, t, beat) {{
      const p = clamp(t / (beat.duration || 1));
      const shown = Math.floor(p * settings.parts.length + 0.0001);
      stage.innerHTML = `<h2>${{settings.title}}</h2>` + settings.parts.map((part, index) => `
        <div class="part" style="opacity:${{index < shown ? 1 : 0}}"><strong>${{part.name}}</strong><div>${{part.detail}}</div></div>`).join("");
    }}

    function renderPathTrace(settings, t, beat) {{
      const p = clamp(t / (beat.duration || 1));
      stage.innerHTML = `<h2>${{settings.title}}</h2>
        <div class="path"><div style="width:${{p * 100}}%"></div></div>
        <div class="steps">${{settings.steps.map((step, index) => `<div style="opacity:${{p >= index / (settings.steps.length - 1) ? 1 : 0.25}}">${{step}}</div>`).join("")}}</div>`;
    }}

    const renderers = {{
      "digit-slide": renderDigitSlide,
      "highlight-words": renderHighlightWords,
      "label-callout": renderLabelCallout,
      "path-trace": renderPathTrace,
    }};

    function beatAt(time) {{
      for (const beat of lesson.beats) {{
        const until = beat.end + (beat.pause_after || 0);
        if (time >= beat.start && time < until) return beat;
      }}
      return lesson.beats[lesson.beats.length - 1];
    }}

    function paint(time) {{
      const beat = beatAt(time);
      const local = Math.min(Math.max(0, time - beat.start), beat.duration || 0);
      renderers[beat.component](beat.settings, local, beat);
      const held = time >= beat.end ? " · pause" : "";
      readout.textContent = time.toFixed(2) + "s / " + lesson.total_duration.toFixed(2) + "s · " + beat.id + held;
      slider.value = String(time);
      document.getElementById("title").textContent = lesson.id + " · " + beat.id;
    }}

    function stopAudio() {{
      if (!active) return;
      active.pause();
      active = null;
    }}

    play.addEventListener("click", () => {{
      playing = !playing;
      play.textContent = playing ? "Pause" : "Play";
      if (!playing) stopAudio();
      if (playing && lessonTime >= lesson.total_duration - 0.05) lessonTime = 0;
      lastTick = null;
    }});

    slider.max = String(lesson.total_duration);
    slider.addEventListener("pointerdown", () => {{ scrubbing = true; stopAudio(); }});
    slider.addEventListener("pointerup", () => {{ scrubbing = false; lastTick = null; }});
    slider.addEventListener("input", () => {{
      lessonTime = Number(slider.value);
      paint(lessonTime);
    }});

    function tick(now) {{
      if (playing && !scrubbing) {{
        const beat = beatAt(lessonTime);
        const local = lessonTime - beat.start;
        const audio = audios[beat.id];
        const clip = audio && audio.duration ? audio.duration : beat.duration;
        const inSpeech = audio && local < Math.min(beat.duration, clip) - 0.03 && !audio.ended;
        if (inSpeech) {{
          if (active !== audio) {{
            stopAudio();
            active = audio;
            audio.currentTime = Math.max(0, local);
            audio.play();
          }}
          lessonTime = beat.start + audio.currentTime;
        }} else {{
          stopAudio();
          if (lastTick !== null) lessonTime += (now - lastTick) / 1000;
        }}
        if (lessonTime >= lesson.total_duration) {{
          lessonTime = lesson.total_duration;
          playing = false;
          play.textContent = "Play";
          stopAudio();
        }}
        paint(lessonTime);
      }}
      lastTick = now;
      requestAnimationFrame(tick);
    }}

    window.renderLessonFrame = (time) => {{
      playing = false;
      stopAudio();
      lessonTime = Number(time);
      paint(lessonTime);
    }};

    if (new URLSearchParams(location.search).get("capture") === "1") {{
      document.body.classList.add("capture");
    }}

    paint(0);
    requestAnimationFrame(tick);
  </script>
</body>
</html>
"""


def write_lesson_page(lesson_id: str, beats: list[dict], total_duration: float, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"id": lesson_id, "total_duration": total_duration, "beats": beats}
    (directory / "lesson.json").write_text(json.dumps(payload, indent=2))
    lesson_json = json.dumps(payload).replace("<", "\\u003c")
    html = _PAGE.format(title=lesson_id, lesson_json=lesson_json)
    path = directory / "index.html"
    path.write_text(html)
    return path


def load_lesson_record(directory: Path) -> dict:
    record = directory / "lesson.json"
    if record.is_file():
        return json.loads(record.read_text())
    html_path = directory / "index.html"
    html = html_path.read_text()
    marker = "const lesson = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    return json.loads(html[start:end])
