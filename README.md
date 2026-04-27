# Migaku Anki — `hughgramel` fork

> **What this fork adds:** automatic **wav2vec2 word-level alignment** on every Migaku audio clip. When the Migaku browser extension sends a card, this addon takes the (known) sentence text + the (already short, 6–10 s) audio clip, runs forced alignment in a background thread, and writes per-word `start`/`end` timings into a card field as JSON. Drop a small JS snippet into your card template and you get karaoke-style underlining of the active word as the audio plays — same UX as the langokee `Timestamp Sentence` model, but populated automatically from inside Migaku's normal capture flow instead of requiring a manual paste-text step.
>
> **Why this is interesting:** Migaku already has the sentence text and the trimmed audio. WhisperX's wav2vec2 alignment stage is the *reliable* part of ASR — it never invents words, only places known words against audio. On a 6–10 s clip this is **~1–3 s of CPU work** on Apple Silicon. So we get word timings essentially for free, asynchronously, after card creation. See **[Word Alignment (wav2vec2)](#word-alignment-wav2vec2)** below for full setup, the card-template snippet, language-detection behavior, and per-language notes (Chinese/Japanese/Korean align at character level — works fine, just produces one entry per character).
>
> **What's compatible:** all Migaku card types — Spanish, French, German, Italian, Portuguese, Dutch, Russian, Polish, Chinese Simplified, Chinese Traditional, Japanese, Korean, English, etc. The feature operates at the receiver level on the `sentence` + `sentenceAudio` fields, not on a specific note model. The language code drives which wav2vec2 model loads.
>
> **What did NOT change:** the original Migaku ↔ extension protocol, the existing card field mapping, the existing AnkiConnect endpoints, and every other addon feature. `wordTimings` is purely additive — disable it in settings and the addon behaves exactly like upstream.
>
> Branch: [`feat/wav2vec2-word-alignment`](https://github.com/hughgramel/Migaku-Anki-Addon-fork/tree/feat/wav2vec2-word-alignment). Upstream: [`migaku-official/Migaku-Anki-Addon`](https://github.com/migaku-official/Migaku-Anki-Addon).

---

Note: We renamed the pynput library to magicy in order to avoid Windows Real-time protection

## Docs

Some guidelines to work with this codebase:

For anything that uses the server created by the Migaku-Anki-Addon, the main entrance can be seen as the MigakuConnection object in `migaku_connection/__init__.py`.
In there is a handlers objects, which has all the endpoints, and which class they call.

The most important one is the ("/anki-connect", MigakuConnector) endpoint, which establishes the WebSocket connection to
the Migaku Extension.

The the Migkau extension sends a card, the `receive_card` endpoint is called.

## Development Setup

### Running the Add-on in Development Mode

To develop and test changes to the add-on locally, you can create a symlink to avoid copying files repeatedly.

#### Find Your Anki Add-ons Folder

**Mac:**

```bash
~/Library/Application Support/Anki2/addons21/
```

**Windows:**

```bash
%APPDATA%\Anki2\addons21\
```

**Linux:**

```bash
~/.local/share/Anki2/addons21/
```

#### Create a Development Symlink

**Important:** Remove the production add-on folder entirely (don't just rename it). Anki will process any folder in the addons directory, including backups.

**Mac/Linux:**

```bash
# Navigate to the addons folder
cd ~/Library/Application\ Support/Anki2/addons21/  # Mac
# or
cd ~/.local/share/Anki2/addons21/  # Linux

# Move the production add-on OUT of the addons folder entirely
mv 1846879528 ~/Desktop/1846879528.backup

# Create a symlink using the addon ID
# Replace /path/to/your/repo with your actual repo location
ln -s /path/to/your/repo/Migaku-Anki-Addon/src 1846879528
```

**Windows (Command Prompt as Administrator):**

```cmd
# Navigate to the addons folder
cd %APPDATA%\Anki2\addons21\

# Move the production add-on OUT of the addons folder entirely
move 1846879528 %USERPROFILE%\Desktop\1846879528.backup

# Create a symlink using the addon ID
# Replace C:\path\to\your\repo with your actual repo location
mklink /D 1846879528 C:\path\to\your\repo\Migaku-Anki-Addon\src
```

#### Enable Debug Logging

For better error visibility during development, you can run Anki from the terminal:

**Mac:**

```bash
/Applications/Anki.app/Contents/MacOS/launcher
```

**Windows:**

```cmd
# If Anki is in Program Files
"C:\Program Files\Anki\anki.exe"
```

**Linux:**

```bash
anki
```

**Logging**
You can also enable more verbose logging by adding this to the top of `src/__init__.py`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will output debug messages to the console when running Anki from the terminal.

#### Testing Changes

1. Make your code changes in the repository
2. Restart Anki to load the changes (no build step required)
3. Check the console output for logs and errors
4. Verify the add-on functionality

**Note:** Python changes are loaded directly by Anki - no compilation or build step is needed.

### Running Tests

The repository includes unit tests for syntax parsing functionality across all supported languages.

#### Prerequisites

- Node.js (v14 or higher)

#### Run Tests Manually

```bash
# Simple approach - no installation needed
node tests/syntax-parser.test.js
# or
./run-tests.sh

# Or with npm (optional)
npm test
```

#### Automatic Testing on Git Push

The repository uses a pre-push git hook to automatically run tests before every `git push`. If any tests fail, the push is rejected to prevent broken code from reaching the repository.

**First-time setup:**

```bash
./install-hooks.sh
```

This copies the hook from `hooks/pre-push` to `.git/hooks/pre-push` and makes it executable.

**Hook behavior:**

When you run `git push`, it will automatically run unit tests.

**Bypassing the hook (emergency only):**

```bash
git push --no-verify
```

⚠️ Use carefully! It's better to fix the tests than to push broken code.

**Troubleshooting:**

If the hook isn't running:

```bash
# Check if it exists and is executable
ls -la .git/hooks/pre-push

# Reinstall if needed
./install-hooks.sh
```

## Word Alignment (wav2vec2)

Optional feature: when a Migaku card lands, run **wav2vec2 forced alignment** on the sentence audio against the (known) sentence text and write per-word timings into a card field. Use the timings to underline the active word as the audio plays.

Alignment runs **asynchronously** in a background thread — card creation never blocks. ~1–3 s of CPU work per 6–10 s clip on Apple Silicon. First card per language downloads a ~400 MB wav2vec2 model from HuggingFace.

### One-time setup

1. **Install whisperx in a separate Python.** It is not bundled — torch is too large.
   ```bash
   # macOS / Linux (recommended)
   pipx install whisperx

   # Find the venv path:
   pipx environment --value PIPX_LOCAL_VENVS
   # → /Users/you/.local/pipx/venvs   (then append /whisperx/bin/python)
   ```
2. **Open Anki → Tools → Migaku → Settings/Help → "Word Alignment (wav2vec2)".**
3. Tick **Enable word alignment**.
4. Browse to the python from step 1 (e.g. `/Users/you/.local/pipx/venvs/whisperx/bin/python`).
5. Pick a default language (used when the Migaku payload doesn't carry one — see logging below).
6. Click **Test alignment setup**. A green confirmation means whisperx is reachable.

### Card type setup

In **Settings/Help → Field Settings** for your Migaku note type, add a field (e.g. `WordTimings`) and map it to the `wordTimings` data type. The field receives a JSON array on each card:

```json
[
  {"surface": "hola", "start": 0.12, "end": 0.41},
  {"surface": "mundo", "start": 0.42, "end": 0.78}
]
```

### Sample card template (highlight active word)

Drop into your card's **Front** template:

```html
<div id="ts-sentence">{{Sentence}}</div>
{{SentenceAudio}}
<script>
(function() {
  const raw = `{{WordTimings}}`.trim();
  if (!raw) return;
  let words; try { words = JSON.parse(raw); } catch { return; }
  const sentenceEl = document.getElementById('ts-sentence');
  const text = sentenceEl.textContent;
  // Naive: wrap each word in a span by surface order. Replace with your own
  // tokenizer for CJK or punctuation-heavy text.
  let cursor = 0;
  const html = words.map((w, i) => {
    const idx = text.indexOf(w.surface, cursor);
    if (idx < 0) return null;
    const lead = text.slice(cursor, idx);
    cursor = idx + w.surface.length;
    return lead + `<span data-i="${i}">${w.surface}</span>`;
  }).filter(Boolean).join('') + text.slice(cursor);
  sentenceEl.innerHTML = html;

  const audio = document.querySelector('audio');
  if (!audio) return;
  audio.addEventListener('timeupdate', () => {
    const t = audio.currentTime;
    sentenceEl.querySelectorAll('span[data-i]').forEach(s => {
      const w = words[+s.dataset.i];
      s.classList.toggle('active', t >= w.start && t <= w.end);
    });
  });
})();
</script>
<style>#ts-sentence .active { text-decoration: underline; text-decoration-thickness: 2px; }</style>
```

### Language detection

The addon walks the incoming Migaku payload for a language code under common keys (`language`, `lang`, `targetLanguage`, `sourceLanguage`, `languageCode`, `langCode`, `deck_language`, `deckLanguage`) at the top level and one level into nested dicts. If none match, it uses the **default language** from settings; if that's also unset, alignment is skipped.

Every received payload is logged at `INFO` to help discover Migaku's actual language key. View logs via **Tools → Migaku → Export Logs**, then grep for `[DEBUG-PAYLOAD]`.

### Troubleshooting

- **"whisperx not importable"** in the test probe — your selected Python doesn't have whisperx. Re-run `pipx install whisperx` and verify with `<that-python> -c "import whisperx"`.
- **First card stalls for 30–90 s** — first-run download of the wav2vec2 model for that language. Subsequent cards are fast.
- **Empty field after alignment** — check logs for `align:` lines. Common causes: language not detected, sentence audio not in Anki's media folder yet, sidecar timeout.
- **Windows** — whisperx on native Windows is rough. WSL2 with Linux pipx is the smoother path.

## Release Process

### Creating a New Release

1. **Update version and changelog:**
   - Update `CHANGELOG.md` with the new version number and changes
   - Commit the changes to your feature branch

2. **Merge to master:**

   ```bash
   git checkout master
   git pull origin master
   git merge your-feature-branch
   git push origin master
   ```

3. **Create and push a tag:**

   ```bash
   git tag 0.4.0  # Use the new version number
   git push origin 0.4.0
   ```

4. **GitHub Actions will automatically:**
   - Build the `.ankiaddon` file
   - Set the version in `src/version.py`
   - Create a GitHub release
   - Attach the built file to the release

### QA Testing a Release Candidate

**Step 1: Download the Test Build**

1. Go to https://github.com/migaku-official/Migaku-Anki-Addon/releases
2. Find the release version (e.g., 0.4.0)
3. Download `Migaku.ankiaddon`

**Step 2: Backup Current Production Version**

⚠️ **Important: Close Anki first before proceeding!**

**Mac:**

```bash
cd ~/Library/Application\ Support/Anki2/addons21/
mv 1846879528 ~/Desktop/1846879528.backup
```

**Windows:**

```cmd
cd %APPDATA%\Anki2\addons21\
move 1846879528 %USERPROFILE%\Desktop\1846879528.backup
```

**Linux:**

```bash
cd ~/.local/share/Anki2/addons21/
mv 1846879528 ~/Desktop/1846879528.backup
```

**Step 3: Install Test Version**

1. Open Anki
2. Go to **Tools → Add-ons**
3. Click **Install from file...**
4. Select the downloaded `Migaku.ankiaddon` file
5. Restart Anki

**Step 4: Test the Add-on**

- Verify all functionality works as expected
- Test new features mentioned in the changelog
- Check compatibility with current Anki version
- Test connection to Migaku Browser Extension

**Step 5: Restore Production Version (After Testing)**

```bash
# Close Anki first
cd [addons folder path from Step 2]
rm -rf 1846879528
mv ~/Desktop/1846879528.backup 1846879528
```

Then restart Anki.

### Publishing to AnkiWeb

After QA approval:

1. Go to https://ankiweb.net
2. Sign in with our AnkiWeb account `organization@migaku.com` (at time of writing, at least Saxon and Christo have access)
3. Go to our addon's page: https://ankiweb.net/shared/info/1846879528
4. Scroll down until you see the **Update** button (it's above Reviews. If you are logged in with an account with access you should see it)
5. Click **Update** 
6. Under Upload file, click **Choose file** to select the new `.addon` file (note: "branches" are way to distinguish which Anki versions an addon applies to. It can remain `Branch 2` unless this change is not compatible with the same Anki versions as our last addon version) (note: if **Choose file** button does not work, try a different browser like Safari)
7. Optionally, bump the max Anki version that this branch is compatible with
8. Optionally, update the description if needed (using `ankiweb.html`)

## Things that often break

- The `src/lib` folder contains dependencies, that are not included in Anki by default.
  If the extension suddenly starts failing on newer Anki versions (especially on macOS), you might have to create a new folder like `macos_314`,
  and add the new dependencies.

You'll also need to add the appropriate code in `sys_libraries.py` then, to load the new libraries on the right platform and Anki version.

- Support for new languages require adding a new folder in `src/languages` and modifying `src/languages/__init__.py` to include it.

## Ankiweb User Guide

Check out [here](./ankiweb.html).
