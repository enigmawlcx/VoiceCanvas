# VoiceCanvas

VoiceCanvas is a macOS desktop application for personal use. It uses the MiniMax API for speech synthesis, voice cloning, and voice design, while providing usage reporting within the application. It brings configuration, text annotation, segment previews, full-text export, and voice management together in a local interface, making it suitable for everyday voice-over work on your own Mac.

## Core Features

- **工作台 (Workbench)**: The workbench supports editing source text, using AI to polish and annotate it, and manually adjusting `[emotion]` tags and `(interjection)` markers. It also supports segment previews, failed-segment markers and single-segment retry previews, full-text synthesis and export, effects, and automatic draft saving.
- **音色库 (Voice Library)**: Browse system voices; upload audio to clone a voice, with an optional clone prompt (reference text); design voices from text descriptions; and manage local notes for voices.
- **Usage reporting**: View daily or weekly trends, statistics broken down by feature, and call details. Filter by time range and feature, paginate results, export CSV files, and estimate costs based on configured unit prices.
- **Audio Formats**: Supports MP3, WAV, and FLAC.

## System Requirements

- macOS
- Python 3.13 or later
- Valid MiniMax API credentials

The application bundles ffmpeg through `imageio-ffmpeg`, so no separate system-level ffmpeg installation is required once the Python dependencies have been installed.

## Installation and Launch

Run the following commands in order from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

After launch, the native application window opens while the local service runs in the background on a random port.

## First-Time Setup

Before first use, complete the following settings on the **配置 (Settings)** page:

1. Enter the API Key, then click the separate **保存 (Save)** button next to it. The application stores the Key in macOS Keychain and displays only a masked value in the interface.
2. Set **默认模型 (Default Model)**, **默认格式 (Default Format)**, **默认采样率 (Default Sample Rate)**, **默认比特率 (Default Bitrate)**, **保存目录 (Save Directory)**, and API Base URL. Group ID is optional and should be entered only when required by the account or API; if you need cost estimates, you may also enter **每千字符单价 (Price per 1,000 Characters)** and **每千 Token 单价 (Price per 1,000 Tokens)**. Click **保存设置 (Save Settings)** when finished. The default audio save directory is `~/Music/VoiceCanvas`.
3. Click **测试连接 (Test Connection)** to confirm that the saved credentials, service address, and network connection work before going to **工作台 (Workbench)**. The connection test reads the saved configuration, so you must complete both save operations in the first two steps beforehand.

## Basic Workflow

1. Enter or paste the source text in **工作台 (Workbench)**, run **润色 (Polish)** as needed, then review and edit the generated `[emotion]` and `(interjection)` markers. Edited content is automatically saved as a draft.
2. Before synthesis, select **音色 (Voice)** and set **语速 (Speed)**, **音量 (Volume)**, Pitch, and the optional **音效器 (Voice Effects)**.
3. Click **解析分段 (Parse Segments)**, then preview each segment; if the result is unsatisfactory, continue editing the text, markers, or synthesis settings.
4. Click **整篇合成并导出 (Synthesize Full Text and Export)** to generate the finished audio.
5. If some segments fail to synthesize, the initially exported file contains only the successful segments. Clicking **重试 (Retry)** on a failed segment only synthesizes and plays that segment again; it does not add the retry result to the file already exported. To obtain a finished file containing every segment, click **整篇合成并导出 (Synthesize Full Text and Export)** again; all segments will then be regenerated.

Voice cloning and voice design are available in **音色库 (Voice Library)**; generated or saved voices can be selected in **工作台 (Workbench)**. The **报表 (Reports)** page records calls so you can review trends, details, and estimated costs.

## Audio Output

- MP3 supports 32, 64, 128, and 256 kbps, all using constant bitrate (CBR).
- The MP3 bitrate setting does not apply to WAV or FLAC.
- A fixed 1 second of silence is inserted between each pair of adjacent successfully synthesized segments; no extra silence is added at the beginning or end of the audio.
- The output format, sample rate, and bitrate are locked when a generation begins. Segment synthesis, failed-segment retries, and final concatenation within that generation reuse these settings to prevent inconsistent parameters within the same finished audio.

## Data and Privacy

- Application data is stored by default in `~/Library/Application Support/VoiceCanvas/`, including the configuration file and SQLite database.
- The API Key is stored in macOS Keychain and is not written in plaintext to the application data directory.
- Audio is output by default to `~/Music/VoiceCanvas`; this can be changed on the configuration page.
- On the first launch of a new version, the application attempts to migrate legacy VoiceMax data and credentials; if migration fails, it safely falls back to avoid overwriting usable data with incomplete migration results.

Local storage does not mean offline processing. Speech synthesis, voice cloning, voice design, and other features that require the MiniMax API send the data needed to complete each request to the API Base URL configured on the configuration page. Before submitting text or audio, confirm that the service address and its privacy policy meet your requirements.

## Testing

Run the following in an activated virtual environment:

```bash
pytest -v
```

The tests use `respx` to intercept MiniMax requests and do not consume real quota. GitHub Actions runs the complete test suite on macOS with Python 3.13 for every push to `main` and for pull requests.

## macOS Packaging

The packaging script first installs or updates build dependencies and runs the complete test suite, then generates the application for the specified architecture:

```bash
scripts/build_app.sh arm64
scripts/build_app.sh x86_64
```

The build artifact is located at `dist/<arch>/声绘魔法.app`. Building the x86_64 version requires Rosetta 2. `universal2` can be used only when the current Python interpreter and all dependencies provide universal2 support; otherwise, build the arm64 and x86_64 versions separately. Build directories and release artifacts are generated locally and are not tracked by Git.

## Project Structure

- `app/`: FastAPI routes, business services, and the SQLite data layer.
- `web/`: Native HTML, CSS, and JavaScript frontend assets.
- `tests/`: pytest tests.
- `scripts/`: Application icon generation and macOS packaging scripts.
- `docs/`: Design and maintenance documentation.

## Contributing and Security

- Before contributing, read [CONTRIBUTING.md](CONTRIBUTING.md).
- Privately report unresolved vulnerabilities according to [SECURITY.md](SECURITY.md); do not publicly disclose sensitive information.

## Open-Source License

This project is licensed under the [MIT License](LICENSE). The [Chinese translation](LICENSE.zh-CN.md) is for reference only; the English original controls.
