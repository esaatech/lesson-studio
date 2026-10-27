"""One page that plays a lesson: each beat's audio, then the checkpoint pause."""

import json
from pathlib import Path

from app.visuals.stage import STAGE_CSS, STAGE_SCRIPT

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    html, body {{ height: 100%; }}
    body {{ margin: 0; overflow: hidden; font-family: Georgia, serif; background: #f6f3ec; color: #1d2430; }}
    main {{ max-width: 880px; width: 100%; height: 100%; margin: 0 auto; padding: 20px 20px 12px; box-sizing: border-box; display: flex; flex-direction: column; min-height: 0; }}
    h1 {{ flex: none; font-size: 18px; font-weight: 600; margin: 0 0 8px; }}
    .stage {{ flex: none; width: 100%; aspect-ratio: 16 / 9; overflow: hidden; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; background: white; border-radius: 16px; padding: 28px; box-shadow: 0 8px 24px rgba(29, 36, 48, 0.06); }}
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
    .controls {{ flex: none; display: flex; align-items: center; gap: 12px; margin-top: 20px; font-family: sans-serif; font-size: 14px; }}
    button#play {{ font: inherit; padding: 8px 14px; border-radius: 999px; border: 0; background: #1d2430; color: white; }}
    label {{ flex: 1; }}
    input {{ width: 100%; }}
    .timeline {{ position: relative; flex: 1 1 auto; min-height: 0; overflow-y: auto; list-style: none; margin: 16px 0 0; padding: 0; font-family: sans-serif; }}
    .timeline button {{ display: flex; gap: 12px; width: 100%; text-align: left; padding: 10px 12px; border: 0; border-bottom: 1px solid #e6e0d6; background: transparent; color: inherit; font: inherit; cursor: pointer; }}
    .timeline button.on {{ background: #e7f0e4; }}
    .timeline .when {{ width: 52px; flex: none; color: #8a8175; }}
    body.capture {{ overflow: visible; height: auto; }}
    body.capture h1, body.capture .controls, body.capture .timeline {{ display: none; }}
    body.capture main {{ height: auto; min-height: 0; overflow: visible; display: block; padding: 0; }}
    body.capture .stage {{ width: 1280px; height: 720px; aspect-ratio: auto; flex: none; border-radius: 0; box-shadow: none; }}
    {stage_css}
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
    <ol class="timeline" id="timeline"></ol>
  </main>
  <script>
    const lesson = {lesson_json};
    const columns = ["tens", "ones", "tenths", "hundredths"];
    const stage = document.getElementById("stage");
    const slider = document.getElementById("slider");
    const readout = document.getElementById("readout");
    const play = document.getElementById("play");
    const timeline = document.getElementById("timeline");
    const beatButtons = {{}};
    const player = document.createElement("audio");
    player.preload = "auto";
    player.loop = false;
    document.body.append(player);
    let lessonTime = 0;
    let playing = false;
    let scrubbing = false;
    let lastTick = null;
    let playToken = 0;
    let shownBeat = "";

    function speakAt(time) {{
      const beat = beatAt(time);
      const local = Math.max(0, time - beat.start);
      const clip = beat.duration || 0;
      if (!beat.audio_file || local >= clip - 0.03) {{
        if (!player.paused) player.pause();
        return;
      }}
      // play() on an ended clip starts it again from the beginning.
      if (player.dataset.beat === beat.id && player.ended) return;
      if (player.dataset.beat !== beat.id) {{
        const token = ++playToken;
        let started = false;
        const start = () => {{
          if (started || token !== playToken || !playing) return;
          const at = Math.max(0, lessonTime - beat.start);
          if (at >= clip - 0.03) return;
          started = true;
          try {{ player.currentTime = at; }} catch (err) {{}}
          const pending = player.play();
          if (pending && pending.catch) pending.catch(() => {{}});
        }};
        player.dataset.beat = beat.id;
        player.addEventListener("loadedmetadata", start, {{ once: true }});
        player.src = beat.audio_file;
        return;
      }}
      if (player.paused) {{
        const pending = player.play();
        if (pending && pending.catch) pending.catch(() => {{}});
      }}
    }}

    for (const beat of lesson.beats) {{
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      const when = document.createElement("span");
      when.className = "when";
      when.textContent = beat.start.toFixed(1) + "s";
      const line = document.createElement("span");
      line.textContent = beat.text || beat.id;
      button.append(when, line);
      button.addEventListener("click", () => {{
        lessonTime = beat.start;
        lastTick = null;
        player.dataset.beat = "";
        paint(lessonTime);
        if (playing) speakAt(lessonTime);
      }});
      item.append(button);
      timeline.append(item);
      beatButtons[beat.id] = button;
    }}

    function clamp(value) {{
      return Math.min(1, Math.max(0, value));
    }}

    {stage_script}

    function beatAt(time) {{
      for (const beat of lesson.beats) {{
        const until = beat.end + (beat.pause_after || 0);
        if (time >= beat.start && time < until) return beat;
      }}
      return lesson.beats[lesson.beats.length - 1];
    }}

    function placeStage() {{
      stage.style.justifyContent = "flex-start";
      const first = stage.firstElementChild;
      const last = stage.lastElementChild;
      if (!first || !last) return;
      const used = last.getBoundingClientRect().bottom - first.getBoundingClientRect().top;
      const available = stage.clientHeight - 56;
      if (used <= available) stage.style.justifyContent = "center";
    }}

    function paint(time) {{
      const beat = beatAt(time);
      const local = Math.min(Math.max(0, time - beat.start), beat.duration || 0);
      renderers[beat.component](beat.settings, local, beat);
      placeStage();
      const held = time >= beat.end ? " · pause" : "";
      readout.textContent = time.toFixed(2) + "s / " + lesson.total_duration.toFixed(2) + "s · " + beat.id + held;
      for (const id of Object.keys(beatButtons)) beatButtons[id].classList.toggle("on", id === beat.id);
      const row = beatButtons[beat.id] && beatButtons[beat.id].parentElement;
      if (row && beat.id !== shownBeat) {{
        shownBeat = beat.id;
        const top = row.offsetTop;
        const bottom = top + row.offsetHeight;
        if (top < timeline.scrollTop || bottom > timeline.scrollTop + timeline.clientHeight) {{
          timeline.scrollTop = Math.max(0, top);
        }}
      }}
      slider.value = String(time);
      document.getElementById("title").textContent = lesson.id + " · " + beat.id;
    }}

    function stopAudio() {{
      player.pause();
    }}

    play.addEventListener("click", () => {{
      playing = !playing;
      play.textContent = playing ? "Pause" : "Play";
      if (!playing) stopAudio();
      if (playing && lessonTime >= lesson.total_duration - 0.05) lessonTime = 0;
      lastTick = null;
      if (playing) speakAt(lessonTime);
    }});

    slider.max = String(lesson.total_duration);
    slider.addEventListener("pointerdown", () => {{ scrubbing = true; stopAudio(); }});
    slider.addEventListener("pointerup", () => {{ scrubbing = false; lastTick = null; }});
    slider.addEventListener("input", () => {{
      lessonTime = Number(slider.value);
      player.dataset.beat = "";
      paint(lessonTime);
    }});

    function tick(now) {{
      if (playing && !scrubbing) {{
        const beat = beatAt(lessonTime);
        const local = lessonTime - beat.start;
        const clip = beat.duration || 0;
        const same = player.dataset.beat === beat.id;
        const ended = same && player.ended;
        const inSpeech = Boolean(beat.audio_file) && local < clip - 0.03 && !ended;
        if (inSpeech) {{
          speakAt(lessonTime);
          const heard = beat.start + (player.currentTime || 0);
          if (same && !player.paused && !player.ended && heard + 0.02 >= lessonTime && heard < beat.end) {{
            lessonTime = heard;
          }} else if (lastTick !== null) {{
            lessonTime += (now - lastTick) / 1000;
          }}
        }} else {{
          if (!player.paused) player.pause();
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
    beats = [_with_spoken_cues(beat) for beat in beats]
    payload = {"id": lesson_id, "total_duration": total_duration, "beats": beats}
    (directory / "lesson.json").write_text(json.dumps(payload, indent=2))
    lesson_json = json.dumps(payload).replace("<", "\\u003c")
    html = _PAGE.format(
        title=lesson_id,
        lesson_json=lesson_json,
        stage_css=STAGE_CSS,
        stage_script=STAGE_SCRIPT,
    )
    path = directory / "index.html"
    path.write_text(html)
    return path


def _with_spoken_cues(beat: dict) -> dict:
    words = beat.get("words") or []
    component = str(beat.get("component") or "")
    if not words or not component:
        return beat
    from app.visuals.cues import cues_for
    from app.visuals.schema import WordTime

    updated = dict(beat)
    updated["cues"] = cues_for(
        component,
        beat.get("settings") or {},
        [WordTime.model_validate(word) for word in words],
        beat.get("duration"),
    )
    return updated


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
