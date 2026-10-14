# Files and working folders

Relative filenames are resolved from the session's working directory. The current directory is shown in the status bar and by `pwd`. Opening a do-file does not change it automatically.

## Finding the extracted test pack

For the reported Windows example, start with:

```stata
cd "C:/Users/connor.baird/Downloads/StatBridge-Test-Pack"
ls
findfile "test_analysis.do"
```

`ls` shows the entries directly inside the folder. If Windows extraction created a second nested `StatBridge-Test-Pack` folder, it appears as a directory. `findfile` searches subfolders and, when it finds exactly one file, prints a `cd` command for the containing folder. Run that printed command, then:

```stata
do "test_analysis.do"
```

The application does not automatically run a file found by searching, or choose one of multiple matching files.

## Commands

| Command | Behaviour |
| --- | --- |
| `pwd` | Print the working directory |
| `ls` or `dir` | List this directory, folders first, with sizes and local modification dates |
| `ls "*.do"` | List matching entries in this directory |
| `ls "Test Pack"` | List a different directory without changing the working directory |
| `ls "Test Pack/*.dta"` | Match filenames inside that directory |
| `ls -a` or `ls, all` | Include dot-prefixed entries |
| `ls -lh` | Accepted shell-style flags; detailed, human-readable output is already the default |
| `cd "folder"` or `chdir "folder"` | Change the session working directory |
| `cd ..` | Move to the parent directory |
| `cd ~` | Move to the current user's home directory |
| `cd -` | Return to the preceding working directory |
| `cd` | Print the current directory |
| `mkdir "new folder"` | Create one directory |
| `mkdir "results/tables", parents` | Also create missing parent directories |
| `findfile "test_analysis.do"` | Search this directory and up to four subfolder levels |
| `findfile "*.do", depth(8)` | Search to the selected depth, from 0 to 12 |

Quote paths containing spaces or commas. Windows accepts both forward slashes and native backslashes. These commands use Python file APIs, not a shell. They do not change the Python process's working directory or the dataset.

`ls` shows at most 1,000 matching entries and scans at most 20,000. `findfile` has the same entry/match caps, does not follow directory symlinks, and reports inaccessible folders or truncation. Narrow the working directory or pattern when a limit is reported. `findfile` searches filenames, not file contents. A zero-result search within its bounds returns r(601).

`ls` records the shown count in r(N) and the cap indicator in r(truncated). `findfile` also records r(skipped); when exactly one file is found, r(fn) contains its absolute path. These are StatBridge results. In particular, StatBridge's `findfile` searches local subfolders and does not implement Stata's ado-path search; the compatibility notice states this difference.

## Folder controls

- **File > Choose working folder**, also on the toolbar, opens a folder chooser and runs an auditable `cd` command.
- **File > Use do-file folder** changes to the folder containing the currently opened or saved do-file. This is useful when a dataset and do-file were supplied together.
- **File > List working folder** runs `ls`.

You can open the supplied do-file through File > Open do-file, select File > Use do-file folder, then press Ctrl+D to run it. Save current data before running a script that contains `clear` or `use ..., clear`.

## Path completion

Tab completes local paths after `cd`, `chdir`, `ls`, `dir`, `do`, `run`, `use`, `save` and `mkdir`. Folder commands offer directories; do/run offer directories and `.do` files; use/save offer directories and `.dta` files. Completion quotes paths automatically. When completing a directory, the cursor stays just before the closing quote, so you can continue into it. Text after the filename, such as `, clear`, is preserved.

Path completion considers at most 5,000 entries and shows up to 200 matches. It does not expand wildcards or macro values into filesystem searches. Use `ls`/`findfile` when you need explicit results or a bounded recursive search. Other file-taking command forms retain their existing completion behaviour.
