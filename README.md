# Album plugin for distributed calls
Run an Album solution on many inputs with one command: `album run-distributed` turns file patterns such as `"*.tif"`
into one task per matching file and runs the tasks one after another or in parallel threads, on the machine where you
call it.

## Installation
1. [install Album](https://docs.album.solutions/en/latest/installation-instructions.html#)
2. Activate the album environment:
```
micromamba activate album
```
3. Install this plugin:
```
micromamba install album-distributed -c conda-forge
```
Or via pip:
```
pip install album-distributed
```
## Usage
In the examples, replace `solution.py` with the path of your solution file or folder, or with the
`group:name:version` coordinates of your solution.

First, list the tasks that would run - `--dry-run` does not run anything:
```
album run-distributed solution.py --input_data "*.tif" --dry-run
```
Then run them:
```
album run-distributed solution.py --input_data "*.tif" --install
```
Like `album run`, `run-distributed` runs installed solutions. `--install` installs the solution first if it is not
installed yet. Alternatively, install it once with `album install solution.py`.

- Put patterns in double quotes. Otherwise your shell replaces `*.tif` with the file names before Album sees the
  pattern.
- Spell out argument names in full: `--input_data "*.tif"` or `--input_data="*.tif"`.
- Use `/` in patterns, on Windows too.

## Use cases
Replace `input_data`, `output_data` and the other argument names with the arguments of your solution. Patterns use
the [`glob`](https://docs.python.org/3/library/glob.html) syntax.

### Process every file in a folder
```
album run-distributed solution.py --input_data "*.tif"
```

| Task | `--input_data` |
|------|----------------|
| 1    | `a.tif`        |
| 2    | `b.tif`        |

Other patterns:
- `"data/input*.tif"` - the files in the `data` folder whose names start with `input`
- `"**/*.tif"` - all `.tif` files in the current folder and its sub folders

### Write each result next to its input
```
album run-distributed solution.py --input_data "*.tif" --output_data "*_out.tif"
```

| Task | `--input_data` | `--output_data` |
|------|----------------|-----------------|
| 1    | `a.tif`        | `a_out.tif`     |
| 2    | `b.tif`        | `b_out.tif`     |

The `*` in `*_out.tif` is replaced with what the `*` in `*.tif` matched. If you run the command again, the
`*_out.tif` files are not used as inputs - all inputs are processed again and their results are overwritten.

### Write the results into another folder
```
album run-distributed solution.py --input_data "*.tif" --output_data "output/*.tif"
```

| Task | `--input_data` | `--output_data` |
|------|----------------|-----------------|
| 1    | `a.tif`        | `output/a.tif`  |
| 2    | `b.tif`        | `output/b.tif`  |

To keep the sub folders of the inputs, use `**` in both patterns:
```
album run-distributed solution.py --input_data "**/*.tif" --output_data "output/**/*.tif"
```

| Task | `--input_data` | `--output_data`  |
|------|----------------|------------------|
| 1    | `a.tif`        | `output/a.tif`   |
| 2    | `x/b.tif`      | `output/x/b.tif` |

`run-distributed` does not create the `output` folder - create it first, unless your solution does.

### Pair the files of two inputs
For example, process each image with its mask (`images/a.tif` with `masks/a_mask.tif`):
```
album run-distributed solution.py --image "images/*.tif" --mask "masks/*_mask.tif" --output_data "results/*.tif"
```

| Task | `--image`      | `--mask`           | `--output_data` |
|------|----------------|--------------------|-----------------|
| 1    | `images/a.tif` | `masks/a_mask.tif` | `results/a.tif` |
| 2    | `images/b.tif` | `masks/b_mask.tif` | `results/b.tif` |

The files are paired by name. Put the main input first: one task is generated for each file of the first pattern.

### Use the same value for every task
```
album run-distributed solution.py --input_data "*.tif" --model "models/model.pt"
```

| Task | `--input_data` | `--model`         |
|------|----------------|-------------------|
| 1    | `a.tif`        | `models/model.pt` |
| 2    | `b.tif`        | `models/model.pt` |

Arguments without a pattern are passed unchanged to every task.

### Run the tasks in parallel
```
album run-distributed solution.py --input_data "*.tif" --mode queue --threads 4
```
See [Modes](#modes).

## Modes
Choose how the tasks run with `--mode`:

| Mode              | How the tasks run                                                       | If a task fails                 |
|-------------------|-------------------------------------------------------------------------|---------------------------------|
| `basic` (default) | one after another, with the output of each task                         | the remaining tasks are not run |
| `queue`           | in parallel, in `--threads` worker threads (default: 3), without output | the other tasks still run       |

At the end, a summary lists the succeeded and failed tasks. If a task failed, the command exits with a non-zero
status.

All threads run on the machine where you call the command and use the same solution environment - choose `--threads`
by the CPU, memory and GPU resources each task needs.

## How patterns are matched
- Patterns work in arguments of type `file`, `directory` and `string`, and in arguments without a type.
- One task is generated for each file matched by the first pattern on the command line.
- In the other patterns, each wildcard is replaced with what the corresponding wildcard matched in that file; `**`
  keeps the sub folders.
- Existing files matched by the other patterns are paired with that file by name.
- If no task can be generated, a warning explains why. Check the tasks with `--dry-run`.
