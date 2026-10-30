"""Shared picture CSS and drawing functions for the lesson page and the beat preview."""

STAGE_CSS = """
    .scene-title { margin: 0 0 18px; font-size: 28px; font-weight: 600; }
    .mark-row { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; }
    .diagram { width: 100%; text-align: center; }
    .diagram .scene-title { text-align: center; }
    .mark { flex: 1 1 0; min-width: 0; max-width: 220px; text-align: center; }
    .mark svg { width: 100%; height: auto; max-height: 150px; display: block; margin: 0 auto; }
    .mark figcaption { font-size: 22px; line-height: 1.3; margin-top: 8px; }
    .fit { width: 100%; }
    .connector { width: 56px; height: 8px; background: #e6e0d6; border-radius: 999px; flex: none; }
    .connector > div { height: 8px; background: #2f6f4e; border-radius: 999px; }
    .shape-scene { display: flex; align-items: center; gap: 36px; width: 100%; }
    .shape-svg { width: 46%; max-width: 460px; height: auto; flex: none; }
    .shape-copy { flex: 1; min-width: 0; }
    .shape-labels { list-style: none; padding: 0; margin: 18px 0 0; display: flex; flex-direction: column; gap: 12px; }
    .shape-labels li { font-size: 24px; line-height: 1.3; padding: 10px 16px; border-radius: 999px; background: #f3f7f4; border: 2px solid #2f6f4e; }
    .arrow-row, .compare { display: flex; align-items: center; gap: 18px; width: 100%; }
    .link-card, .compare-card { flex: 1; min-height: 160px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; font-size: 32px; line-height: 1.3; padding: 22px; border-radius: 20px; border: 3px solid #d9d2c5; background: #fbfaf7; box-sizing: border-box; }
    .compare-card.after { border-color: #2f6f4e; background: #e7f0e4; }
    .kicker { font-family: sans-serif; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: #8a8175; margin: 0 0 10px; }
    .compare-text { margin: 0; }
    .link-bridge { width: 168px; flex: none; text-align: center; }
    .link-bridge svg { width: 150px; height: 56px; display: block; margin: 0 auto; }
    .relation { font-size: 20px; color: #2f6f4e; min-height: 1.3em; margin-top: 4px; }
    .code-card { width: 100%; background: #1d2430; color: #f6f3ec; border-radius: 18px; overflow: hidden; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .code-bar { display: flex; gap: 8px; padding: 14px 18px; background: #2a3344; }
    .code-bar i { width: 12px; height: 12px; border-radius: 50%; background: #c4b8a8; display: block; }
    .code-card pre { margin: 0; padding: 28px 24px 36px; font-size: 30px; line-height: 1.5; white-space: pre-wrap; }
    .code-card .on { background: #ffe08a; color: #1d2430; border-radius: 6px; }
    .measure { width: 100%; }
    .axis { position: relative; height: 128px; margin: 12px 28px 0; }
    .axis-line { position: absolute; left: 0; right: 0; top: 52px; height: 6px; background: #e6e0d6; border-radius: 999px; }
    .axis-line > div { height: 6px; background: #2f6f4e; border-radius: 999px; }
    .tick { position: absolute; top: 18px; transform: translateX(-50%); text-align: center; width: 120px; }
    .tick b { display: block; width: 16px; height: 16px; border-radius: 50%; background: #2f6f4e; margin: 28px auto 8px; }
    .tick span { display: block; font-size: 20px; line-height: 1.2; }
    .axis-end { position: absolute; top: 70px; font-size: 18px; color: #8a8175; }
    .axis-end.start { left: 0; }
    .axis-end.end { right: 0; }
    .traveler { position: absolute; top: 42px; width: 22px; height: 22px; margin-left: -11px; border-radius: 50%; background: #1d2430; border: 4px solid #ffe08a; box-sizing: border-box; }
    .bar-track { height: 36px; background: #e6e0d6; border-radius: 999px; overflow: hidden; margin-top: 28px; }
    .bar-fill { height: 36px; background: #2f6f4e; }
    .bar-labels { display: flex; justify-content: space-between; gap: 8px; margin-top: 12px; font-size: 20px; }
    .caption { font-size: 26px; line-height: 1.3; margin: 22px 0 0; }
"""

STAGE_SCRIPT = r"""
    function span(t, start, end) {
      if (end <= start) return t >= end ? 1 : 0;
      if (t <= start) return 0;
      if (t >= end) return 1;
      return (t - start) / (end - start);
    }

    function bare(word) {
      return String(word).replace(/[^\p{L}\p{N}']/gu, "").toLowerCase();
    }

    function escapeHtml(value) {
      return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function revealTime(beat, index, count) {
      const cues = (beat && beat.cues) || {};
      const timed = cues["reveal_" + index];
      if (timed != null) return timed;
      const duration = (beat && beat.duration) || 1;
      return count ? duration * index / count : 0;
    }

    function shown(t, beat, index, count) {
      return t + 0.0001 >= revealTime(beat, index, count);
    }

    function strokeAttrs(amount) {
      const offset = (100 * (1 - Math.min(1, Math.max(0, amount)))).toFixed(2);
      return 'fill="none" stroke="#2f6f4e" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" pathLength="100" stroke-dasharray="100" stroke-dashoffset="' + offset + '"';
    }

    function renderDigitSlide(settings, t, beat) {
      const cues = beat.cues || {};
      const duration = beat.duration || 1;
      const from = columns.indexOf(settings.from_column);
      const to = columns.indexOf(settings.to_column);
      const move = span(t, 0, cues.slide_end ?? duration);
      const index = from + (to - from) * move;
      const left = ((index + 0.5) / columns.length) * 100;
      stage.innerHTML = `
        <div class="columns">
          ${columns.map((name) => `<div class="column">${escapeHtml(name)}</div>`).join("")}
          <div class="digit" style="left:${left}%">${escapeHtml(settings.digit)}</div>
        </div>
        <div class="label" style="opacity:${span(t, cues.label_start ?? duration * 0.72, cues.label_end ?? duration)}">${escapeHtml(settings.label)}</div>
        <div class="badge" style="opacity:${settings.badge ? span(t, cues.badge_start ?? duration * 0.84, cues.badge_end ?? duration) : 0}">${escapeHtml(settings.badge || "")}</div>`;
    }

    function renderHighlightWords(settings, t, beat) {
      const tokens = settings.sentence.split(/(\s+)/);
      const on = tokens.map(() => false);
      let cursor = 0;
      settings.emphasis.forEach((phrase, index) => {
        if (!shown(t, beat, index, settings.emphasis.length)) return;
        phrase.split(/[\s/]+/).map(bare).filter(Boolean).forEach((piece) => {
          for (let i = cursor; i < tokens.length; i++) {
            if (bare(tokens[i]) === piece) {
              on[i] = true;
              cursor = i + 1;
              break;
            }
          }
        });
      });
      stage.innerHTML = `<div class="sentence">${tokens.map((word, index) => on[index] ? `<span class="on">${escapeHtml(word)}</span>` : escapeHtml(word)).join("")}</div>`;
    }

    function renderLabelCallout(settings, t, beat) {
      stage.innerHTML = `<h2 class="scene-title">${escapeHtml(settings.title)}</h2>` + settings.parts.map((part, index) => `
        <div class="part" style="opacity:${shown(t, beat, index, settings.parts.length) ? 1 : 0}"><strong>${escapeHtml(part.name)}</strong><div>${escapeHtml(part.detail)}</div></div>`).join("");
    }

    function renderPathTrace(settings, t, beat) {
      const count = settings.steps.length;
      const times = settings.steps.map((_, index) => revealTime(beat, index, count));
      let amount = 0;
      if (count <= 1) amount = t + 0.0001 >= (times[0] || 0) ? 1 : 0;
      else if (t <= times[0]) amount = 0;
      else if (t >= times[count - 1]) amount = 1;
      else {
        for (let index = 0; index < count - 1; index++) {
          if (t < times[index + 1]) {
            const gap = Math.max(0.001, times[index + 1] - times[index]);
            amount = (index + (t - times[index]) / gap) / (count - 1);
            break;
          }
        }
      }
      stage.innerHTML = `<h2 class="scene-title">${escapeHtml(settings.title)}</h2>
        <div class="path"><div style="width:${amount * 100}%"></div></div>
        <div class="steps">${settings.steps.map((step, index) => `<div style="opacity:${t + 0.0001 >= times[index] ? 1 : 0.25}">${escapeHtml(step)}</div>`).join("")}</div>`;
    }

    function renderStrokeDiagram(settings, t, beat) {
      const marks = settings.marks || [];
      const count = marks.length;
      const parts = [];
      marks.forEach((mark, index) => {
        if (index > 0) {
          const previous = revealTime(beat, index - 1, count);
          const current = revealTime(beat, index, count);
          const grow = span(t, previous, current);
          parts.push(`<div class="connector"><div style="width:${grow * 100}%"></div></div>`);
        }
        const start = revealTime(beat, index, count);
        const amount = span(t, start, start + 0.45);
        const shape = mark.shape === "box" || mark.shape === "arrow" ? mark.shape : "circle";
        let drawing = `<circle cx="70" cy="60" r="40" ${strokeAttrs(amount)}/>`;
        if (shape === "box") drawing = `<rect x="22" y="22" width="96" height="76" rx="16" ${strokeAttrs(amount)}/>`;
        if (shape === "arrow") drawing = `<path d="M18 60 H108 M108 60 L86 40 M108 60 L86 80" ${strokeAttrs(amount)}/>`;
        parts.push(`<figure class="mark"><svg viewBox="0 0 140 120">${drawing}</svg><figcaption style="opacity:${amount}">${escapeHtml(mark.text)}</figcaption></figure>`);
      });
      stage.innerHTML = `<div class="diagram"><h2 class="scene-title">${escapeHtml(settings.title)}</h2><div class="mark-row">${parts.join("")}</div></div>`;
    }

    const SHAPE_PATHS = {
      box: "M40 62 L100 32 L160 62 L160 112 L100 142 L40 112 Z M100 32 V82 M100 82 L40 62 M100 82 L160 62",
      house: "M28 88 L100 28 L172 88 M48 88 V142 H152 V88 M88 142 V108 H112 V142",
      book: "M36 40 L96 56 V136 L36 120 Z M164 40 L104 56 V136 L164 120 Z",
      sun: "M100 80 m-26 0 a26 26 0 1 0 52 0 a26 26 0 1 0 -52 0 M100 28 V46 M100 114 V132 M48 80 H66 M134 80 H152 M64 44 L76 56 M124 104 L136 116 M136 44 L124 56 M76 104 L64 116",
      tree: "M92 148 V96 H108 V148 M100 100 C58 100 56 46 100 30 C144 46 142 100 100 100",
      computer: "M36 32 H164 V108 H36 Z M86 108 L74 132 H126 L114 108 M58 132 H142",
      person: "M100 28 m-16 0 a16 16 0 1 0 32 0 a16 16 0 1 0 -32 0 M100 48 V104 M100 68 H64 M100 68 H136 M100 104 L70 142 M100 104 L130 142",
      ball: "M100 80 m-46 0 a46 46 0 1 0 92 0 a46 46 0 1 0 -92 0 M54 80 H146 M100 34 C78 58 78 102 100 126 M100 34 C122 58 122 102 100 126",
      clock: "M100 80 m-48 0 a48 48 0 1 0 96 0 a48 48 0 1 0 -96 0 M100 80 V48 M100 80 L128 96",
      star: "M100 24 L114 68 H160 L122 94 L136 140 L100 112 L64 140 L78 94 L40 68 H86 Z",
    };

    function renderShapePicture(settings, t, beat) {
      const labels = settings.labels || [];
      const count = labels.length + 1;
      const drawEnd = Math.max(0.45, revealTime(beat, 0, count));
      const amount = span(t, 0, drawEnd);
      const path = SHAPE_PATHS[settings.subject] || SHAPE_PATHS.box;
      const items = labels.map((label, index) => {
        const opacity = shown(t, beat, index + 1, count) ? 1 : 0;
        return `<li style="opacity:${opacity}">${escapeHtml(label)}</li>`;
      }).join("");
      stage.innerHTML = `<div class="shape-scene">
        <svg class="shape-svg" viewBox="0 0 200 160"><path d="${path}" ${strokeAttrs(amount)}/></svg>
        <div class="shape-copy">
          <h2 class="scene-title">${escapeHtml(settings.title)}</h2>
          <ul class="shape-labels">${items}</ul>
        </div>
      </div>`;
    }

    function bridge(amount) {
      return `<svg viewBox="0 0 150 56"><path d="M8 28 H128 M128 28 L108 12 M128 28 L108 44" ${strokeAttrs(amount)}/></svg>`;
    }

    function renderArrowLink(settings, t, beat) {
      const left = shown(t, beat, 0, 3) ? 1 : 0.2;
      const link = span(t, revealTime(beat, 1, 3), revealTime(beat, 1, 3) + 0.4);
      const right = shown(t, beat, 2, 3) ? 1 : 0.2;
      const relation = shown(t, beat, 1, 3) ? 1 : 0;
      stage.innerHTML = `<div class="arrow-row">
        <div class="link-card" style="opacity:${left}">${escapeHtml(settings.left)}</div>
        <div class="link-bridge">${bridge(link)}<div class="relation" style="opacity:${relation}">${escapeHtml(settings.relation)}</div></div>
        <div class="link-card" style="opacity:${right}">${escapeHtml(settings.right)}</div>
      </div>`;
    }

    function renderBeforeAfter(settings, t, beat) {
      const before = shown(t, beat, 0, 2) ? 1 : 0.2;
      const after = shown(t, beat, 1, 2) ? 1 : 0.2;
      const link = span(t, revealTime(beat, 0, 2), revealTime(beat, 1, 2));
      stage.innerHTML = `<div class="compare">
        <article class="compare-card" style="opacity:${before}"><p class="kicker">${escapeHtml(settings.before_label)}</p><p class="compare-text">${escapeHtml(settings.before_text)}</p></article>
        <div class="link-bridge">${bridge(link)}</div>
        <article class="compare-card after" style="opacity:${after}"><p class="kicker">${escapeHtml(settings.after_label)}</p><p class="compare-text">${escapeHtml(settings.after_text)}</p></article>
      </div>`;
    }

    function codeTokens(code) {
      return String(code).split(/(\s+|[^\s\p{L}\p{N}']+)/u).filter((token) => token.length);
    }

    function renderCodeLine(settings, t, beat) {
      const revealed = [];
      (settings.focus || []).forEach((phrase, index) => {
        if (!shown(t, beat, index, settings.focus.length)) return;
        String(phrase).split(/[\s/]+/).map(bare).filter(Boolean).forEach((piece) => revealed.push(piece));
      });
      const code = codeTokens(settings.code).map((word) => {
        const key = bare(word);
        return key && revealed.includes(key) ? `<span class="on">${escapeHtml(word)}</span>` : escapeHtml(word);
      }).join("");
      stage.innerHTML = `<div class="code-card"><div class="code-bar"><i></i><i></i><i></i></div><pre>${code}</pre></div>`;
    }

    function renderMeasure(settings, t, beat) {
      const marks = settings.marks || [];
      const count = marks.length;
      const caption = String(settings.caption || "");
      const slots = count + (caption ? 1 : 0);
      let revealed = 0;
      for (let index = 0; index < count; index++) {
        if (shown(t, beat, index, slots)) revealed = index + 1;
      }
      function slot(index) { return (index + 1) / (count + 1); }
      let pos = 0;
      if (revealed > 0) {
        const previous = revealed === 1 ? 0 : slot(revealed - 2);
        const next = slot(revealed - 1);
        const start = revealed === 1 ? 0 : revealTime(beat, revealed - 2, slots);
        const end = revealTime(beat, revealed - 1, slots);
        pos = previous + (next - previous) * span(t, start, end);
      }
      const captionOpacity = caption && shown(t, beat, count, slots) ? 1 : 0;
      const title = `<h2 class="scene-title">${escapeHtml(settings.title)}</h2>`;
      const note = caption ? `<p class="caption" style="opacity:${captionOpacity}">${escapeHtml(caption)}</p>` : "";
      if (settings.kind === "bar") {
        let fill = 0;
        if (revealed > 0) {
          const previous = (revealed - 1) / count;
          const next = revealed / count;
          const start = revealed === 1 ? 0 : revealTime(beat, revealed - 2, slots);
          const end = revealTime(beat, revealed - 1, slots);
          fill = previous + (next - previous) * span(t, start, end);
        }
        const labels = marks.map((mark, index) => `<span style="opacity:${shown(t, beat, index, slots) ? 1 : 0.25}">${escapeHtml(mark)}</span>`).join("");
        stage.innerHTML = `${title}<div class="bar-track"><div class="bar-fill" style="width:${fill * 100}%"></div></div><div class="bar-labels">${labels}</div>${note}`;
        return;
      }
      const ticks = marks.map((mark, index) => {
        const opacity = shown(t, beat, index, slots) ? 1 : 0;
        return `<div class="tick" style="left:${slot(index) * 100}%;opacity:${opacity}"><b></b><span>${escapeHtml(mark)}</span></div>`;
      }).join("");
      stage.innerHTML = `${title}<div class="axis">
        <div class="axis-line"><div style="width:${pos * 100}%"></div></div>
        <div class="axis-end start">${escapeHtml(settings.start_label)}</div>
        <div class="axis-end end">${escapeHtml(settings.end_label)}</div>
        ${ticks}
        <div class="traveler" style="left:${pos * 100}%"></div>
      </div>${note}`;
    }

    const renderers = {
      "digit-slide": renderDigitSlide,
      "highlight-words": renderHighlightWords,
      "label-callout": renderLabelCallout,
      "path-trace": renderPathTrace,
      "stroke-diagram": renderStrokeDiagram,
      "shape-picture": renderShapePicture,
      "arrow-link": renderArrowLink,
      "before-after": renderBeforeAfter,
      "code-line": renderCodeLine,
      "measure": renderMeasure,
    };

    function contentBounds(node) {
      const box = node.getBoundingClientRect();
      let top = box.top;
      let bottom = box.bottom;
      let left = box.left;
      let right = box.right;
      for (const child of node.children) {
        const inner = contentBounds(child);
        top = Math.min(top, inner.top);
        bottom = Math.max(bottom, inner.bottom);
        left = Math.min(left, inner.left);
        right = Math.max(right, inner.right);
      }
      return { top, bottom, left, right };
    }

    function placeStage() {
      stage.style.justifyContent = "flex-start";
      stage.style.alignItems = "stretch";
      const first = stage.firstElementChild;
      if (!first) return;
      const pad = 28;
      const availableH = stage.clientHeight - pad * 2;
      const availableW = stage.clientWidth - pad * 2;
      let top = Infinity;
      let bottom = -Infinity;
      let left = Infinity;
      let right = -Infinity;
      for (const child of stage.children) {
        const box = contentBounds(child);
        top = Math.min(top, box.top);
        bottom = Math.max(bottom, box.bottom);
        left = Math.min(left, box.left);
        right = Math.max(right, box.right);
      }
      const usedH = Math.max(1, bottom - top);
      const usedW = Math.max(1, right - left);
      const scale = Math.min(1, availableH / usedH, availableW / usedW);
      if (scale < 0.98) {
        const wrap = document.createElement("div");
        wrap.className = "fit";
        while (stage.firstChild) wrap.append(stage.firstChild);
        wrap.style.zoom = String(scale);
        stage.append(wrap);
        stage.style.justifyContent = "center";
        stage.style.alignItems = "center";
        return;
      }
      if (usedH <= availableH) stage.style.justifyContent = "center";
    }
"""
