# Context-aware completion

Completion is available in the **Command** field. Load a dataset first to get its variable names. Suggestions update after a command finishes, including data loading, renaming, dropping, editing, fitting and storing estimates. The do-file editor currently provides syntax highlighting and normal indentation; it does not use this completion engine.

| Input at the cursor | Suggestions |
| --- | --- |
| `regress income a` | Numeric variables starting with a |
| `summarize ` | Numeric variables from the loaded dataset |
| `encode reg` | String variables starting with reg |
| `generate log_income = ln(inc` | Variables/functions in an expression, including income |
| `count if reg` | Variables/functions for the condition |
| `regress income i.reg` | Numeric variables for a factor term |
| `generate change = L2.inc` | Numeric variables for the lagged expression |
| `regress income age [aw=wei` | Numeric variables and expression functions for the weight |
| `regress income age, vce(` | Supported covariance choices |
| `regress income age, vce(cluster reg` | Loaded variables starting with reg |
| `ttest income, by(reg` | Grouping variables starting with reg |
| `glm income age, family(po` | poisson |
| `display _b[inc` | Matching coefficient names from the active model |
| `estimates restore fi` | Matching stored estimate names |
| `set databackend po` | polars |

These examples assume matching variables/models exist. Numeric types do not establish that a variable is substantively suitable or has valid factor levels. Completion helps with syntax; the engine still validates the command and statistical assumptions remain the analyst's responsibility.

## Keys and editing

- **Tab:** insert a unique completion, extend a common prefix, or display choices. Tab again accepts the selected choice without executing the command.
- **Up/Down:** select within an open completion popup; otherwise recall command history.
- **Right/End at the end:** accept the grey inline suggestion.
- **Enter:** execute the command when the popup is closed. An open popup uses Enter to accept its selected completion.
- **Escape:** dismiss the popup.

Move the cursor into an existing token to complete that token. The rest of the identifier is replaced, text after it is retained, and the cursor stays immediately after the completed token. Already-present closing delimiters are not duplicated. Editing the command dismisses stale choices; press Tab again for the new context.

History can suggest full commands while entering a command name. Once an argument or option is being completed, suggestions come from the current syntax and session metadata, so historical arguments do not override current variable-type filtering. Up/Down history recall remains available.

## Scope

Rules cover StatBridge's implemented syntax, not every Stata/ado grammar. Aliases, quiet/capture prefixes, by/bysort prefixes, factor/interaction terms, composed time operators, supported weights and expression parentheses are recognised. Commas inside expressions and quotes do not start command options.

New variable names, free text, numeric option arguments and unimplemented syntax are not guessed. Local path completion is available for cd/chdir, ls/dir, do/run, use/save and mkdir; see NAVIGATION.md. Local/global macro names can be completed, including inside quoted paths. Completion does not run commands, read file contents, evaluate expressions or alter data. Variable completion uses session metadata; path completion reads a bounded local directory listing.
