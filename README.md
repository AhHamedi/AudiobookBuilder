<p align="center">
  <img src="https://raw.githubusercontent.com/AhHamedi/AudiobookBuilder/main/assets/hero.png" alt="Audio folders flowing into a chaptered audiobook" width="900">
</p>

<h1 align="center">AudiobookBuilder</h1>

<p align="center">
  Build chaptered <code>.m4b</code> audiobooks for Apple Books from folders of audio files.
</p>

<p align="center">
  <a href="https://github.com/AhHamedi/AudiobookBuilder/actions/workflows/ci.yml"><img src="https://github.com/AhHamedi/AudiobookBuilder/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/audiobook-builder/"><img src="https://img.shields.io/pypi/v/audiobook-builder" alt="PyPI version"></a>
  <a href="https://pypi.org/project/audiobook-builder/"><img src="https://img.shields.io/pypi/pyversions/audiobook-builder" alt="Python versions"></a>
  <a href="https://github.com/AhHamedi/AudiobookBuilder/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-57c7d4" alt="MIT license"></a>
</p>

AudiobookBuilder turns naturally ordered MP3, M4A, WAV, or FLAC tracks into one Apple Books-ready audiobook. It encodes AAC audio, writes a chapter for every source file, embeds useful metadata and optional cover art, and supports whole-series batch jobs.

<p align="center">
  <img src="https://raw.githubusercontent.com/AhHamedi/AudiobookBuilder/main/assets/demo.gif" alt="A real AudiobookBuilder terminal session converting three MP3 tracks into a chaptered M4B" width="900">
</p>

## Why it exists

A folder of narration tracks is not quite an audiobook. Apple Books expects an MPEG-4 audiobook container, consistent AAC audio, useful metadata, and chapter boundaries. AudiobookBuilder handles that assembly in one command without hiding the FFmpeg pipeline behind a fragile desktop wrapper.

### Highlights

- One chapter per source file, ordered with natural filename sorting
- AAC `.m4b` output optimized for Apple Books with `faststart`
- Title, author, album, genre, and optional JPEG/PNG cover art
- Exact duplicate detection before encoding
- Flat-folder and one-book-per-subfolder batch workflows
- Parallel batch encoding with safe temporary outputs
- Native Apple AudioToolbox AAC selection when FFmpeg provides it
- Dry runs and explicit overwrite controls

## Install

AudiobookBuilder supports macOS and Python 3.9 or newer.

```bash
brew install ffmpeg pipx
pipx ensurepath
pipx install audiobook-builder
```

Open a new terminal after `pipx ensurepath`, then confirm both tools are available:

```bash
audiobook-build --version
ffmpeg -version
```

To install the latest source directly from GitHub:

```bash
pipx install git+https://github.com/AhHamedi/AudiobookBuilder.git
```

## Quick start

Given a folder like this:

```text
The Long Way Home/
├── 01 Opening.mp3
├── 02 The Journey.mp3
└── 03 Homecoming.mp3
```

Run:

```bash
audiobook-build build "The Long Way Home" \
  --title "The Long Way Home" \
  --author "A. Narrator"
```

The default output is `The Long Way Home/The_Long_Way_Home.m4b`. Add it to Books by double-clicking the file or choosing **File → Add to Library**.

Add cover art or choose another destination when needed:

```bash
audiobook-build build "The Long Way Home" \
  --title "The Long Way Home" \
  --author "A. Narrator" \
  --cover cover.jpg \
  --out ~/Audiobooks/the-long-way-home.m4b
```

## Batch builds

### One subfolder per audiobook

```text
Library/
├── Book One/
│   ├── 01 Intro.mp3
│   └── 02 Chapter.mp3
└── Book Two/
    ├── 01 Intro.flac
    └── 02 Chapter.flac
```

```bash
audiobook-build batch Library \
  --one-subfolder-per-book \
  --author "A. Narrator"
```

### Numbered groups in one flat folder

Files beginning with the same number become one audiobook. This is useful when a series was exported into a single directory:

```text
01 Earthsea Book 1 01.mp3
01 Earthsea Book 1 02.mp3
02 Earthsea Book 2 01.mp3
02 Earthsea Book 2 02.mp3
```

```bash
audiobook-build batch Series --author "A. Narrator"
```

Batch output defaults to the parent of the input directory. Use `--out-dir`, `--jobs`, `--skip-existing`, or `--force` to control larger runs. Run with `--dry-run` first to inspect the grouping and output names without encoding.

## Command reference

```text
audiobook-build build DIRECTORY --author TEXT [OPTIONS]
  --title, -t TEXT       Audiobook title; inferred from the first filename
  --out, -o PATH         Output file; .m4b is added automatically
  --bitrate TEXT         AAC bitrate (default: 96k)
  --encoder TEXT         auto, aac, or aac_at (default: auto)
  --cover, -c FILE       JPEG or PNG artwork
  --dry-run              Inspect tracks without encoding
  --force, -f            Overwrite an existing output

audiobook-build batch ROOT --author TEXT [OPTIONS]
  --out-dir, -o PATH     Output directory; defaults to ROOT's parent
  --one-subfolder-per-book
                          Treat each immediate child directory as one book
  --title-template TEXT  Use {n} for the detected group or folder name
  --jobs, -j INTEGER     Parallel encodes; 0 selects automatically
  --skip-existing        Keep outputs that already exist
  --force, -f            Overwrite without prompting
  --cover FILE           Apply one cover to every output
  --dry-run              Show the batch plan without encoding
```

Run `audiobook-build COMMAND --help` for the authoritative option list.

## Verify an output

Inspect the container metadata and chapter boundaries with FFprobe:

```bash
ffprobe -v error \
  -show_entries format_tags=title,artist,genre:chapter=start_time,end_time:chapter_tags=title \
  -of json "The_Long_Way_Home.m4b"
```

A successful file reports AAC audio, the requested metadata, and one contiguous chapter per source track.

## How it works

1. Discover supported files in the selected folder and sort their names naturally.
2. Remove byte-for-byte duplicates while preserving the first occurrence.
3. Read each duration with FFprobe and generate FFMETADATA chapter boundaries.
4. Concatenate and encode the tracks to AAC in a temporary `.m4b`.
5. Attach optional cover art and atomically move the completed file into place.

All media processing is performed locally. AudiobookBuilder does not upload audio or contact an external service.

## Troubleshooting

**`ffmpeg and ffprobe were not found`**  
Install FFmpeg with `brew install ffmpeg`. If you keep custom binaries elsewhere, point AudiobookBuilder to their directory:

```bash
export AUDIOBOOK_FFMPEG_DIR="/path/to/ffmpeg/bin"
```

The directory must contain executable files named `ffmpeg` and `ffprobe`.

**The output title is not what I expected**  
Pass `--title` for a single book or `--title-template 'Series {n}'` for a batch.

**Books shows no cover**  
Use a JPEG or PNG file with `--cover`. Square artwork around 1400–3000 px is the most reliable choice.

**Encoding is using too much CPU**  
For a batch, reduce concurrency with `--jobs 1` or another explicit value.

## Limitations

- macOS and Apple Books are the supported v1 target.
- Input discovery is intentionally limited to immediate MP3, M4A, WAV, and FLAC files.
- MP4/MOV video extraction, DRM-protected media, tag-based track ordering, and cue sheets are not supported.
- Audio is re-encoded to AAC for consistent `.m4b` compatibility; this is not a lossless remuxer.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
```

See [CONTRIBUTING.md](https://github.com/AhHamedi/AudiobookBuilder/blob/main/CONTRIBUTING.md) for the complete contributor workflow and [CHANGELOG.md](https://github.com/AhHamedi/AudiobookBuilder/blob/main/CHANGELOG.md) for release history.

## License

AudiobookBuilder is available under the [MIT License](https://github.com/AhHamedi/AudiobookBuilder/blob/main/LICENSE).
