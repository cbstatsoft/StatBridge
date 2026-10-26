# Logos — optional English and formal-logic syntax

**Logos** is an opt-in second command language for StatBridge. It lets you express common statistical tasks in plain English and use logical predicates such as **∧ (and)**, **∨ (or)**, **¬ (not)**, **≥**, **≤** and **≠**. Logos translates these statements into the **same existing StatBridge commands and Python statistical backends**; it is not a separate estimator. Results match the corresponding supported Stata-style commands.

Logos is **local, deterministic and offline**. It is a **bounded grammar**, not a generative-AI interpreter, unrestricted English comprehension system or theorem prover. An instruction that does not match the documented grammar returns a syntax error without running an estimated or destructive substitute. Statements cannot execute Python or the shell.

## Selecting a command language

Stata-compatible syntax remains the default. Switch for the current session:

```stata
syntax logos
```

Switch back:

```stata
syntax stata
```

In the desktop application, use **Window → Command language → Logos — English / formal logic**. The selection is remembered for future desktop sessions, while a supplied `--syntax` command-line argument overrides the startup preference.

For an individual command, bypass the current mode:

```text
logos: regress income on education and experience
stata: regress income education experience
```

Both prefixes work even when the opposite language is active. Translated commands are shown in Results and recorded in the compatibility/audit ledger alongside the original statement. The data, estimation model and inference all belong to StatBridge, not Logos.

### Batch and terminal

```sh
statbridge --batch analysis.do --syntax logos
statbridge --terminal --syntax logos
```

You can also start either interface in Stata mode and execute `syntax logos`. Do-files are executed line by line with the current session mode. To use Stata's data setup, imports, `xtset`, `svy`, looping or other commands in Logos mode, explicitly prefix them with `stata:`.

## Grammar and examples

| Logos | Equivalent StatBridge syntax |
| --- | --- |
| `show variables` | `describe` |
| `describe dataset` | `describe` |
| `summarise income and education` | `summarize income education` |
| `average of income` | `mean income` |
| `count rows` | `count` |
| `count rows where age >= 18` | `count if age >= 18` |
| `∀ rows: age ≥ 0` | `assert age >= 0` (fails if contradicted) |
| `∃ row: income > 1000` | `logosexists income > 1000` (returns truth and number of matches) |
| `keep rows where age ≥ 18` | `keep if age >= 18` |
| `drop rows where missing(income)` | `drop if missing(income)` |
| `list rows with income and education where age ≥ 18` | `list income education if age >= 18` |
| `regress income on education and experience` | `regress income education experience` |
| `fit linear model income ~ education + experience` | `regress income education experience` |
| `fit logistic model employed ~ education + age` | `logit employed education age` |
| `fit probit model employed ~ education` | `probit employed education` |
| `create eligible as age ≥ 18` | `generate eligible = age >= 18` |
| `let eligible := age ≥ 18` | `generate eligible = age >= 18` |
| `tabulate eligible` | `tabulate eligible` |
| `correlate education and experience` | `correlate education experience` |
| `histogram of income` | `histogram income` |
| `predict residuals as error` | `predict error, residuals` |
| `predict fitted values as fit` | `predict fit, xb` |
| `explain regress` | `help regress` |

Aliases include `summarize`/`summarise`, `mean of`/`average of`, and `such that`/`where`. Variables must be named exactly as in the dataset, with unambiguous separators (spaces, `and`, commas, or `+` in formulas). Quoted literal strings are kept unchanged.

## Predicate/formal-logic support

Use parentheses when mixing AND/OR to make precedence explicit:

```text
count rows where (age ≥ 18) ∧ (income is not missing)
keep rows where (country = "Kenya") ∨ (country = "Uganda")
create target as (income at least 500) ∧ (employed = 1)
count observations such that ¬(age < 18)
```

Logical predicate mappings:

- `∧`, `and` → logical conjunction (`&`).
- `∨`, `or` → logical disjunction (`|`).
- `¬`, `not(...)` → negation (`!`).
- `≥`, `≤`, `≠` → `>=`, `<=`, `!=`.
- `∀ rows: P`, `every row satisfies P` → `assert P` (universal row truth; fails if false).
- `∃ row: P`, `there exists a row where P` → `logosexists P` (returns `r(exists)` and `r(N_matches)`; false is a valid result).
- `=`, `equals`, `is equal to` → equality comparison `==` **within a predicate**.
- `is missing`, `is not missing` → `missing(x)`, `!missing(x)`.
- `at least`, `at most`, `greater than`, `less than` → comparison operators.

StatBridge's existing safe expression parser ultimately validates and evaluates predicates. Quantifiers range **only over the rows of the currently loaded dataset**. There are **no nested or variable-domain quantifiers, theorem-proving tactics, type inference, free-text semantic disambiguation, arbitrary natural-language transformations, plugins, network requests or generated code execution**. For formal statistical model workflows beyond Logos's grammar, use `stata: ...`.

## Errors, audit and reproducibility

```text
syntax logos
regress income on education and experience
```

The Results pane displays the translated command and the selected backend. A command that Logos cannot parse is rejected before changing the dataset or fitting a model. Failures are recorded with the source statement and error; successful commands record their canonical translation. Unlike a chat-based language model, Logos always maps a supported statement to the same syntax, and its behaviour can be unit-tested.

Logos inherits StatBridge compatibility limits and backend inference; using natural language **does not certify results as Stata-identical**.

An executable example is provided in [examples/logos_workflow.do](../examples/logos_workflow.do).
