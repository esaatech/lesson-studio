# Studio handoff

This note is for the next agent. The same file is at the root of both repos. This copy is the studio service, `lesson-studio`. The teacher app is `/Users/joelivongbe/Documents/react/little-learners-tech`.

Last pushed commits, 30 Oct 2026:

- Studio `6af9db4` on `main`. Keep each spoken line short, on screen, and played to the end of the recording.
- Teacher app `48c1d7b` on `main`. Tell teachers a line is one breath and a question is a place to pause later.

Do not commit or push unless the user asks. Do not print `.env` values or API keys.

## What the product is

A teacher writes a short description of a lesson. Studio turns that into spoken lines, a picture for each line, and audio. The teacher approves the script, watches the lesson page, then exports an MP4 of that same page. The MP4 is not added to the course yet.

The teacher does not write beats, picture types, or timing. Those are backend rules. The field **What this lesson teaches** is a description of the title. The system instruction writes the lesson from that description, plus the course age, level, and notes.

A description a teacher would paste for a syllable lesson:

```
Students learn that a syllable is a part of a word they can clap. They listen to everyday words and count how many syllables each word has, from one syllable up to three.

They start with words of one syllable, such as cat, dog, sun, and book. Then they listen to words of two syllables, such as tiger, monkey, apple, and window, and they hear where the word breaks. After that they try words of three syllables, such as elephant, banana, and computer.

Students also learn that a longer word is not always the one with more syllables. They compare a short word and a longer word and decide which one has more claps. They practice counting the syllables in their own name and in a few words from the classroom.

By the end, students can listen to a new word, clap it, and say how many syllables it has.
```

The user had not generated that lesson yet when this note was written.

## How a lesson is made

Frontend: `src/services/lessonStudio.ts` builds the topic from the course title, age range, level, grade, course notes, lesson title, and the description. `src/components/teacher/studio/StudioSection.tsx` is the teacher UI.

Studio, in order:

1. `POST /v1/lessons` drafts the script. `app/script_draft.py`, prompt in `app/runtime_settings.py` `SCRIPT_DRAFTER_PROMPT`.
2. The teacher can edit a line. The checkbox label is **A place to pause later**. It sets `checkpoint` on that beat. It does not insert silence.
3. Approve runs audio, pictures, and one lesson page. Locally this happens inside the request because the queue env vars are empty. In the cloud, Cloud Tasks queues `studio-script` and `studio-render` do it.
4. Export records the saved `index.html`. It does not rebuild the page when that file already exists. Locally the recording runs in the API process. In the cloud, `EXPORT_JOB` starts the Cloud Run Job `lesson-studio-export`.

The page the teacher watches and the MP4 are the same HTML. Word times come from ElevenLabs. Pictures reveal on those spoken times, not on an even slice of the line.

## Rules the script and pictures follow

These were added because generated lessons were too long, lists ran off the bottom of the frame, shape rows ran off the right edge, and the last word of a line was cut off.

- One spoken line is one breath and one idea. A definition and an example are two lines. Draft text is capped at 220 characters. A script may have up to 24 lines (`app/script_draft.py`).
- After a finished thought, the model may add one spoken check with the class, or one flash question about what was just taught. The words are chosen for that age and that thought. Do not put sample questions in the prompt. The model copies them.
- `checkpoint` is true on a sentence that asks the student something. It is a mark for later. The lesson does not stop.
- A picture shows that one thing. Labels are one or two words. A list has at most four parts. A row of drawn shapes has at most three. If a picture is still too full, `placeStage` in `app/visuals/stage.py` scales it down with CSS `zoom` so the words stay whole. The frame is 16:9 and `overflow` is hidden.
- A line lasts as long as its MP3. `mp3_seconds` in `app/timing.py` reads the file. The next line starts when that recording ends. Word times still drive the picture. The old 0.15 second pad is only a fallback when the file cannot be measured. Do not go back to stopping at the last letter plus 0.15 seconds. That sliced the last sound.
- The old 2 second checkpoint pause is gone. `place_beats` always sets `pause_after` to 0. `checkpoint_pause_seconds` remains in settings so old config still loads, and the clock ignores it.

Picture types the model may choose: `digit-slide`, `highlight-words`, `label-callout`, `path-trace`, `stroke-diagram`, `shape-picture`, `arrow-link`, `before-after`, `code-line`, `measure`. Shapes it can draw: box, house, book, sun, tree, computer, person, ball, clock, star. Highlight is for when the point is the wording. Digit slide is only for a digit moving between place-value columns.

## What is not built

The user was clear about the next product step, and it is not in the code.

When a lesson is posted, the teacher adds a pause at a checkpoint line. The recording itself never pauses. At that pause an AI listens. If the student understands, the lesson continues. If the student has a question, the AI answers from the script. Do not put that silence back into the MP4 or the lesson clock.

Also later, and not started: dragging a sentence up or down on the page, and adding the downloaded MP4 to the course.

## Cloud

Project `esaasolution`, region `us-central1`.

- API service `lesson-studio-git`. Public URL `https://lesson-studio-git-578103433472.us-central1.run.app`. A push to studio `main` builds and deploys a new revision. Confirm the new revision still has `OUTPUT_DIR=/output`, `EXPORT_JOB=lesson-studio-export`, `EXPORT_JOB_PROJECT`, `EXPORT_JOB_LOCATION`, and the `sbty-studio` bucket mounted at `/output`. A source deploy has wiped those before.
- Job `lesson-studio-export` records the MP4. Its image does not rebuild when the API image rebuilds. After a change to export or page-drawing code, rebuild it from the studio repo with `gcloud builds submit --project=esaasolution --region=us-central1 --config=cloudbuild.export.yaml --timeout=1800`.
- The API service cannot record video itself. Timeout is 300 seconds and the API image has no Chromium or ffmpeg.
- Teacher app push to `main` publishes Firebase Hosting. Live origin includes `https://sbtyacedemy.com` (the domain is misspelled on purpose). CORS allows that host, the correctly spelled academy hosts, and `localhost:8080`.
- `gh` is not installed. Use `git` and `gcloud`.

Lessons rendered before the bucket mount can have files on the old instance disk. The job only sees files under `/output` on the bucket. Those older cloud lessons need to be made again.

## Local

The user starts the studio. Do not start or kill it unless they ask. Command is `python -m app` on `127.0.0.1:8001`, from this repo, with the poetry env. The frontend dev server is Vite on port 8080. The user often already has `npm run dev` running. A studio process keeps the old prompt and clock until it is started again. Restarting the frontend does not change a saved lesson page. Restarting the studio does not rewrite an existing `index.html`.

Generate the script again, then make the lesson again, to pick up prompt, timing, or picture changes. The teacher app only iframes the studio HTML.

Local `.env` leaves `EXPORT_JOB` empty, so a local export records in-process. Do not set the cloud job name in local `.env`.

Playwright browsers are in `$HOME/Library/Caches/ms-playwright`. The sandbox points `PLAYWRIGHT_BROWSERS_PATH` at a cache that has no browser. Poetry lives under `$HOME/Library/Caches/pypoetry/virtualenvs`. The studio venv is Python 3.13. System `python` may be 3.14 and has no pytest. Use `poetry run pytest`.

This repo is outside the Cursor workspace. Git and process commands here need an explicit `cd` and full permissions. `working_directory` is often ignored and the shell stays in this repo, which has caused a push to hit the wrong remote.

## Help Center

Teacher help lives in the teacher app: `src/tutorials/data/tutorialRegistry.ts` and `public/tutorials/content/`. Studio guide is `lesson-studio.md`. Picture FAQ is `lesson-studio-pictures-faq.md`. Update those when a teacher-facing behavior changes. The guide already says a line is one breath, the picture stays in the frame, a question is spoken, and **A place to pause later** is for when the lesson is posted. Do not document the AI listener as if it exists.

## While working

Auto-review sometimes blocks studio shell commands, including pytest and deploys that read env names. Retry with the exact block reason when the user should approve it. Do not print secret env values. The temp env file used for the job deploy was `/tmp/lesson-studio-export.env.yaml` and was removed.

Do not regenerate lessons with ElevenLabs unless the user asks. Do not force-push.
