# batch-crop

Crop a whole folder of images in one command. `batch-crop` cuts every image to
an aspect ratio, a fixed pixel size, an exact box, or a box in fractions of the
image, and writes the results to a separate folder. The originals are never
modified.

It needs Python 3.11 or newer and depends only on [Pillow](https://python-pillow.org/).

## Install

With [uv](https://docs.astral.sh/uv/), from the root of this repository (`_tools`):

```bash
uv tool install ./batch-crop
batch-crop --help
```

Or run it without installing, from inside `batch-crop/`:

```bash
uv run batch-crop --help
```

## Quick start

```bash
# Square crops of every image in photos/, centred, written to squares/
batch-crop photos -o squares -c aspect:1:1

# Preview first: prints each planned crop box, writes nothing
batch-crop photos -o squares -c aspect:1:1 --dry-run

# Walk subfolders too; the folder structure is kept under the output dir
batch-crop photos -o squares -c aspect:1:1 -r
```

More examples:

```bash
# 16:9 banners that keep the top of each picture, saved as WebP at quality 85
batch-crop photos -o banners -c aspect:16:9@top -f webp -q 85

# Exact 1200x630 thumbnails (crop to the ratio, then resize)
batch-crop photos -o social -c fill:1200x630

# Several crops per image in one pass: photo_sq.jpg and photo_tall.jpg
batch-crop photos -o out -c "aspect:1:1#sq" -c "aspect:4:5@top#tall"

# Only some files: quote the glob so the shell passes it through
batch-crop "photos/**/*.jpg" -o out -c rel:0.1,0.1,0.9,0.9

# Use a config file, overriding one setting from the command line
batch-crop --config crop.toml --format png
```

## Crop specs

A crop spec is `MODE:VALUE`, optionally followed by `@ANCHOR` and `#NAME`:

```
aspect:16:9@top#wide
└mode┘ └val┘└anchor┘└name┘
```

### Modes

| Mode | Value | What it does |
|------|-------|--------------|
| `aspect` | `W:H` or a ratio like `1.5` | Largest crop of that shape that fits the image. Nothing is resized. |
| `size` | `WxH` in pixels | A window of exactly that many pixels. An image smaller than the window fails; it is never upscaled. |
| `fill` | `WxH` in pixels | Crops to the W:H shape like `aspect`, then resizes to exactly W x H. Smaller images are scaled up. |
| `box` | `x1,y1,x2,y2` in pixels | That exact rectangle, measured from the top-left corner. Fails if the box runs past the image edge. |
| `rel` | `x1,y1,x2,y2` from 0 to 1 | A rectangle given as fractions of width and height, so `rel:0,0,0.5,1` is always the left half. Always at least 1 pixel. |

`aspect` and `rel` adapt to each image's size, so they suit folders of mixed
dimensions. `size` and `box` assume the images share a size.

### Anchors (`aspect`, `size`, `fill`)

The anchor chooses which part of the image the crop keeps. The default is
`center`. The names are `center`, `top`, `bottom`, `left`, `right`, `top-left`,
`top-right`, `bottom-left` and `bottom-right`.

For a focal point, give `fx,fy` as fractions of width and height:
`aspect:1:1@0.3,0.4` centres the crop on the point 30% across and 40% down.
When that would push the crop past an edge, the crop slides back inside the image.

### Names and output files

With one spec, `photos/cat.jpg` becomes `OUTPUT/cat.jpg`. A `#name` adds a
suffix, so `#thumb` writes `OUTPUT/cat_thumb.jpg`. When there are several specs,
any spec without a name is numbered (`cat_1.jpg`, `cat_2.jpg`). Names must be
unique and may use letters, digits, `-` and `_`.

## Options

| Flag | Meaning |
|------|---------|
| `INPUT` | A folder, a single image, or a quoted glob such as `"shots/*.png"` |
| `-o, --output DIR` | Where cropped files go. Created if missing. |
| `-c, --crop SPEC` | A crop spec. Repeat it for several outputs per image. |
| `--config FILE` | TOML config file. Any flag you pass overrides it. |
| `-f, --format` | `keep` (default: same format as the input), `jpeg`, `png` or `webp` |
| `-q, --quality N` | JPEG and WebP quality, 1-100 (default 90) |
| `-r, --recursive` | Also process subfolders when INPUT is a folder. With a glob, use `**` instead. |
| `-n, --dry-run` | Print every planned crop and output path, and write nothing. |
| `--overwrite` | Replace output files that already exist. |
| `--allow-input-dir` | Allow outputs where the input search looks, with a warning (see Safety). |

## Config file

Anything but `--dry-run` can live in a TOML file. Relative `input` and `output`
paths are resolved from the config file's own folder, so a project can keep its
crop settings next to its images.

```toml
input = "photos"          # folder, single file, or glob
output = "cropped"
format = "webp"           # keep | jpeg | png | webp
quality = 85              # 1-100, JPEG and WebP only
recursive = true
overwrite = false
allow_input_dir = false

# Each crop is a spec string or a table with mode, value, and optional anchor and name.
crop = [
  "aspect:1:1#square",
  { mode = "aspect", value = "16:9", anchor = "top", name = "wide" },
  { mode = "fill", value = "400x400", anchor = "0.5,0.3", name = "thumb" },
]
```

`--crop` on the command line replaces the file's `crop` list rather than adding
to it. Unknown keys, wrong value types and malformed specs stop the run with
exit code 2 before any image is touched.

## Safety

- **Inputs are never overwritten.** A planned output that resolves to an input
  file fails, even with `--overwrite`. The one exception is an earlier output
  of the same run, described under `--allow-input-dir` below.
- **Outputs never go where the input search looks.** Unless you pass
  `--allow-input-dir`, the run stops with exit code 2, before writing anything,
  if the output folder holds any input image, if an output would sit in the
  same folder as an input, or if the search is recursive and an output would
  land anywhere under its root:

  | Input | Output folder refused | Output folder allowed |
  |-------|-----------------------|-----------------------|
  | one file `photos/cat.jpg` | `photos` | `photos/cropped`, or any other folder |
  | folder `photos` | `photos` | `photos/cropped` (top-level images only) |
  | folder `photos` with `-r` | `photos` or any folder inside it | anything outside `photos` |
  | glob `"photos/*.jpg"` | `photos` | `photos/cropped` |
  | glob `"photos/**/*.jpg"` | `photos` or any folder inside it | anything outside `photos` |

  The reasoning: outputs copy the input layout, so `photos/a/x.jpg` becomes
  `OUTPUT/a/x.jpg`. A single file, a folder without `-r`, or a glob without
  `**` only finds files at one fixed depth below its folder. Outputs sit deeper
  than that whenever the output folder is inside the input folder, so a later
  identical run cannot find them. The only way to reach that depth is to write
  into the input folder itself, next to the originals, and that is refused.
  A recursive search or a `**` glob looks at every depth, so the whole tree is
  off limits.
- **What `--allow-input-dir` still protects.** For a placement the rule above
  would refuse, the run prints a warning and goes ahead. Then:
  - When the output folder is a subfolder of the input folder, nothing inside
    the output folder is ever read as an input.
  - When outputs land among the inputs (for example `-o` is the input folder
    itself), a file is skipped as an "earlier output" if its path is exactly
    what this run would write for another input. With `-c aspect:1:1#sq`,
    `a_sq.png` beside `a.png` is skipped, and so is `a_sq.webp` with `-f webp`.
    A rerun then replaces it only with `--overwrite`. `x_sq.png` with no `x.*`
    beside it is an ordinary image and is cropped.
  - The check knows only this run's specs and format. Outputs of an earlier
    run with other spec names or another format are cropped like any image, and
    a real photo that happens to carry exactly an output's name is skipped and
    can be replaced with `--overwrite`. Keep outputs in their own folder to
    avoid both.
- **Existing outputs are kept.** A file already at the output path fails with a
  message unless you pass `--overwrite`. Two inputs that would write the same
  output (say `a.png` and `a.bmp` both becoming `a.webp`) are caught, and only
  the first is written.
- Each file is written to a new, uniquely named hidden file
  (`.batch-crop-<random>.<ext>`) in the output folder and renamed into place.
  A failed write never leaves a half-written image at the output path, and
  cleanup only ever removes the temporary file this run created.

## What happens to each file

1. Hidden files and folders (names starting with `.`) are ignored.
2. Files that are not `.jpg`, `.jpeg`, `.png`, `.webp`, `.tif`, `.tiff`, `.bmp`
   or `.gif` are listed as skipped. Beside at least one image they do not
   affect the exit code. If the input yields no supported image at all (an
   empty folder, a glob that matches nothing, only unsupported or hidden
   files), the run stops with exit code 2.
3. The image is rotated upright according to its EXIF orientation tag, so
   phone photos are cropped the way they are displayed.
4. Every spec is checked before any output for that file is written. If one
   spec cannot be applied, that file fails, writes nothing and reserves no
   output names, and the batch moves on. If a write fails partway (a full disk,
   say), the outputs already written for that file stay on disk and stay
   reserved; the ones it never wrote remain free for later files.
5. The crop is saved. The ICC colour profile is kept unless the output needs a
   different colour space (for example CMYK to RGB for PNG), in which case it is
   dropped. Other metadata, such as EXIF and GPS, is never copied. Transparent
   images saved as JPEG are placed on white. Animated GIFs and multi-page TIFFs
   keep only their first frame.

After the run, a summary line reports how many files were written, failed and
skipped (unsupported, or earlier outputs), and each failure is listed again on
stderr.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Every supported image was cropped (or planned, with `--dry-run`) |
| 1 | At least one image failed. The others were still processed. |
| 2 | Bad arguments; a config file that is missing, unreadable, not UTF-8 or invalid; an input with no supported images; or an unsafe output folder. Nothing was written. |

## Development

```bash
cd tools/batch-crop
uv run pytest -q
```

The tests generate their own images with Pillow; no sample files are needed.

## Not included

- Automatic subject or face detection. Pick the region with an anchor or a
  focal point instead.
- Interactive, per-image cropping. Every image in a run gets the same specs.
