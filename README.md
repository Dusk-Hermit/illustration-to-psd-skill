# Illustration to layered PSD

An agent skill and command-line workflow for repainting studies. It creates an editable PSD with eight ordered painting stages and a hidden raster reference from a flat RGB/RGBA illustration and a coarse material-outline recipe.

## Setup

- Clone this repository as `illustration-to-psd-skill` inside your agent's skills directory, or point your agent at [SKILL.md](SKILL.md).
- Use Python 3.11 or newer and install the dependencies with `python -m pip install -r requirements.txt`. The dependency versions below the specified upper bounds may vary between machines.
- Install a PhotoCraft CLI build that supports `convert --no-gpu input.ora output.psd`. Set `PHOTOCRAFT_CLI`, put the executable on PATH, or pass its location with `--photocraft`.

## Run

Make a [material recipe](recipe.md), then run:

```text
python scripts/study.py create --source "input.png" --recipe "recipe.json" --output "study.psd"
python scripts/study.py inspect "study.psd"
python scripts/study.py preview "study.psd" "review.png"
```

`create` verifies PSD dimensions, layer order, visibility, decoded pixels, and the merged composite before publishing the output. `inspect` reports layer coverage and decoded pixel hashes. Compare those hashes when checking repeated runs on the same environment. There is no requirement that the serialized PSD bytes match.

Store source images, generated PSDs, and image-specific recipes outside the skill repository.
