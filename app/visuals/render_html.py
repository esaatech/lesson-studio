"""A single beat page. Audio time drives the frame, and the frame comes only from that time."""

import json
import shutil
from pathlib import Path

from app.visuals.schema import ResolvedVisual

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
    .digit {{ position: absolute; top: 8px; width: 64px; margin-left: -32px; text-align: center; font-size: 64px; line-height: 1; transition: none; }}
    .label, .badge, .part, .step {{ opacity: 0; }}
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
  </style>
</head>
<body>
  <main>
    <h1 id="title"></h1>
    <div class="stage" id="stage"></div>
    <div class="controls">
      <button id="play" type="button">Play</button>
      <label>Time <output id="readout">0.00s</output>
        <input id="slider" type="range" min="0" max="1" step="0.01" value="0" />
      </label>
    </div>
    <audio id="audio" preload="auto"></audio>
  </main>
  <script>
    const plan = {plan_json};
    const columns = ["tens", "ones", "tenths", "hundredths"];

    function clamp(p) {{
      return Math.min(1, Math.max(0, p));
    }}

    function span(t, start, end) {{
      if (end <= start) return t >= end ? 1 : 0;
      if (t <= start) return 0;
      if (t >= end) return 1;
      return (t - start) / (end - start);
    }}

    function renderDigitSlide(settings, t, beat) {{
      const view = beat || plan;
      const cues = view.cues || {{}};
      const duration = view.duration || 1;
      const slideEnd = cues.slide_end ?? duration;
      const from = columns.indexOf(settings.from_column);
      const to = columns.indexOf(settings.to_column);
      const move = span(t, 0, slideEnd);
      const index = from + (to - from) * move;
      const left = ((index + 0.5) / columns.length) * 100;
      const labelOpacity = span(t, cues.label_start ?? duration * 0.72, cues.label_end ?? duration);
      const badgeOpacity = settings.badge ? span(t, cues.badge_start ?? duration * 0.84, cues.badge_end ?? duration) : 0;
      stage.innerHTML = `
        <div class="columns">
          ${{columns.map((name) => `<div class="column">${{escapeHtml(name)}}</div>`).join("")}}
          <div class="digit" style="left:${{left}}%">${{escapeHtml(settings.digit)}}</div>
        </div>
        <div class="label" style="opacity:${{labelOpacity}}">${{escapeHtml(settings.label)}}</div>
        <div class="badge" style="opacity:${{badgeOpacity}}">${{escapeHtml(settings.badge)}}</div>`;
    }}

    function bare(word) {{
      return word.replace(/[^\\p{{L}}\\p{{N}}']/gu, "").toLowerCase();
    }}

    function escapeHtml(value) {{
      return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }}

    function revealTime(beat, index, count) {{
      const cues = beat.cues || {{}};
      const timed = cues["reveal_" + index];
      if (timed != null) return timed;
      return count ? (beat.duration || 1) * index / count : 0;
    }}

    function renderHighlightWords(settings, t, beat) {{
      const view = beat || plan;
      const tokens = settings.sentence.split(/(\\s+)/);
      const on = tokens.map(() => false);
      let cursor = 0;
      settings.emphasis.forEach((phrase, index) => {{
        if (t + 0.0001 < revealTime(view, index, settings.emphasis.length)) return;
        phrase.split(/[\\s/]+/).map(bare).filter(Boolean).forEach((piece) => {{
          for (let i = cursor; i < tokens.length; i++) {{
            if (bare(tokens[i]) === piece) {{
              on[i] = true;
              cursor = i + 1;
              break;
            }}
          }}
        }});
      }});
      stage.innerHTML = `<div class="sentence">${{tokens.map((word, index) => on[index] ? `<span class="on">${{escapeHtml(word)}}</span>` : escapeHtml(word)).join("")}}</div>`;
    }}

    function renderLabelCallout(settings, t, beat) {{
      const view = beat || plan;
      stage.innerHTML = `<h2>${{escapeHtml(settings.title)}}</h2>` + settings.parts.map((part, index) => `
        <div class="part" style="opacity:${{t + 0.0001 >= revealTime(view, index, settings.parts.length) ? 1 : 0}}">
          <strong>${{escapeHtml(part.name)}}</strong>
          <div>${{escapeHtml(part.detail)}}</div>
        </div>`).join("");
    }}

    function renderPathTrace(settings, t, beat) {{
      const view = beat || plan;
      const count = settings.steps.length;
      const times = settings.steps.map((_, index) => revealTime(view, index, count));
      let amount = 0;
      if (count <= 1) amount = t + 0.0001 >= (times[0] || 0) ? 1 : 0;
      else if (t <= times[0]) amount = 0;
      else if (t >= times[count - 1]) amount = 1;
      else {{
        for (let index = 0; index < count - 1; index++) {{
          if (t < times[index + 1]) {{
            const span = Math.max(0.001, times[index + 1] - times[index]);
            amount = (index + (t - times[index]) / span) / (count - 1);
            break;
          }}
        }}
      }}
      stage.innerHTML = `
        <h2>${{escapeHtml(settings.title)}}</h2>
        <div class="path"><div style="width:${{amount * 100}}%"></div></div>
        <div class="steps">${{settings.steps.map((step, index) => {{
          const opacity = t + 0.0001 >= times[index] ? 1 : 0.25;
          return `<div class="step" style="opacity:${{opacity}}">${{escapeHtml(step)}}</div>`;
        }}).join("")}}</div>`;
    }}

    const renderers = {{
      "digit-slide": renderDigitSlide,
      "highlight-words": renderHighlightWords,
      "label-callout": renderLabelCallout,
      "path-trace": renderPathTrace,
    }};

    const stage = document.getElementById("stage");
    const slider = document.getElementById("slider");
    const readout = document.getElementById("readout");
    const audio = document.getElementById("audio");
    const play = document.getElementById("play");
    const duration = plan.duration || 1;
    let scrubbing = false;
    document.getElementById("title").textContent = plan.id + " · " + plan.component;
    slider.max = String(duration);
    if (plan.audio_file) audio.src = plan.audio_file;
    else play.hidden = true;

    function phase(t) {{
      const cues = plan.cues || {{}};
      if (cues.label_start != null && t >= cues.label_start) return "label";
      if (cues.slide_end != null && t >= cues.slide_end) return "arrived";
      if (cues.slide_end != null) return "moving";
      return "";
    }}

    function frame(t) {{
      const value = Math.min(duration, Math.max(0, t));
      renderers[plan.component](plan.settings, value);
      const label = value.toFixed(2) + "s / " + duration.toFixed(2) + "s";
      const name = phase(value);
      readout.textContent = name ? label + " · " + name : label;
      slider.value = String(value);
    }}

    play.addEventListener("click", () => {{
      if (!audio.src) return;
      if (audio.paused) audio.play();
      else audio.pause();
    }});
    audio.addEventListener("play", () => {{ play.textContent = "Pause"; }});
    audio.addEventListener("pause", () => {{ play.textContent = "Play"; }});
    audio.addEventListener("ended", () => frame(duration));
    slider.addEventListener("pointerdown", () => {{ scrubbing = true; }});
    slider.addEventListener("pointerup", () => {{ scrubbing = false; }});
    slider.addEventListener("input", () => {{
      const t = Number(slider.value);
      if (audio.src) audio.currentTime = Math.min(t, audio.duration || t);
      frame(t);
    }});
    function tick() {{
      if (audio.src && !audio.paused && !scrubbing) frame(audio.currentTime);
      requestAnimationFrame(tick);
    }}
    tick();
    frame(0);
  </script>
</body>
</html>
"""


def write_visual_page(visual: ResolvedVisual, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    _copy_audio(visual, directory)
    plan_json = json.dumps(visual.model_dump()).replace("<", "\\u003c")
    html = _PAGE.format(title=visual.id, plan_json=plan_json)
    path = directory / f"{visual.id}.html"
    path.write_text(html)
    return path


def _copy_audio(visual: ResolvedVisual, directory: Path) -> None:
    if not visual.audio_file:
        return
    source = Path(visual.audio_file)
    if not source.is_file():
        visual.audio_file = ""
        return
    filename = f"{visual.id}.mp3"
    destination = directory / filename
    if source.resolve() != destination.resolve():
        shutil.copyfile(source, destination)
    visual.audio_file = filename
