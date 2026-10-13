# Album plugin for distributed calls 
This is an early version of enhancing album with calls for batch and distributed processing.

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
First, install a solution - replace `solution.py` with the path to your solution / solution folder or with the `group:name:version` coordinates of your solution.
```
album install solution.py
```
Now you can use the plugin:
```
album run-distributed solution.py
```
The plugin does two things:
1. It figures out if the input arguments match multiple tasks - in this case, it generates the different task arguments.
2. It runs all matching tasks, the mode for running these tasks can be chosen.  

Since the matching part can be tricky, please use the `--dry-run` argument to first print a list of matched tasks:
```
album run-distributed solution.py --dry-run
```

Always put patterns in quotes, as in the examples on this page. Otherwise your shell (e.g. bash or zsh) replaces the pattern with the matching file names before album sees it: `--input_data *.tif` becomes `--input_data a.tif b.tif c.tif`, which does not generate one task per file.
In the Windows Command Prompt (`cmd.exe`), single quotes are not removed - use double quotes (`"*.tif"`) there.

Arguments can be passed as `--input_data '*.tif'` or `--input_data='*.tif'`. Please spell out the full argument name - abbreviated argument names cannot be replaced with the matched values and result in an error.

On Windows, both `/` and `\` can be used as path separators in patterns, there is no need to replace the slashes in the examples on this page. Prefer `/`: it works in every shell, while `\` has to be quoted or escaped in Git Bash and other POSIX shells.

Please let us know if you run into issues.

## Matching input arguments
To generate multiple tasks, patterns in file name arguments can be used to match multiple files.

### Using patterns in a single argument

You should be able to use all [`glob`](https://docs.python.org/3/library/glob.html) features when using it in a single argument. Here are some examples:

In the following scenarios `solution.py` has an argument called `input_data`.

Match all `.tif` files in the current folder:
```
album run-distributed solution.py --input_data '*.tif'
```

Match all `.tif` files in a specific folder where the file name starts with `input`:
```
album run-distributed solution.py --input_data '/data/input*.tif'
```

Match all `.tif` files recursively, starting from the current folder:
```
album run-distributed solution.py --input_data '**/*.tif'
```

### Using patterns in multiple arguments

When using patterns in multiple arguments, this plugin will try to figure out the corresponding argument values based on which of the patterns match with existing files.
This is likely to fail in a bunch of situations - please use the `--dry-run` argument to test if the matched tasks correspond with your expectation.

In the following scenarios `solution.py` has two arguments called `input_data` and `output_data`.

Use all `.tif` files in the current folder and append `_out` to the file name for the output argument.
```
album run-distributed solution.py --input_data '*.tif' --output_data '*_out.tif'
```

Do the same thing recursively:
```
album run-distributed solution.py --input_data '**/*.tif' --output_data '**/*_out.tif'
```

Let the output argument values live in a different folder:
```
album run-distributed solution.py --input_data '*.tif' --output_data 'output/*.tif'
```

Since Album does not yet distinguish between input and output arguments, be aware that if the `output_data` argument in these scenarios matches existing files, the plugin will also try to generate corresponding `input_file` values. We will work on improving this.

## Modes
You can set the mode by using the `--mode` argument. The available modes are `basic` and `queue`:
```
album run-distributed solution.py --mode queue
```
By default, the plugin will use the `basic` mode. Other values for `--mode` are rejected with an error.

### Basic
In this mode, all tasks will be performed one after each other. The console output of each task will be printed.
The plugin stops at the first failing task.
### Queue
In this mode, a set of thread workers will be created to process tasks in parallel. The console output of each task will not be printed.
All tasks are processed, even if some of them fail.
You can control how many threads should be created with the `--threads` argument (default: 3, at least 1):
```
album run-distributed solution.py --mode queue --threads 16
```

## Exit status
After running the tasks, the plugin logs a summary with the number of succeeded, failed and not run tasks and lists the arguments of the failed tasks.
If a task failed, `album run-distributed` exits with a non-zero exit status:
- In `basic` mode, the remaining tasks are not run and the command fails with the error of the failing task.
- In `queue` mode, all tasks are processed first, then the command fails with `album command failed: N of M task(s) failed.`

With `--dry-run`, no task is run - the generated tasks are only listed.
