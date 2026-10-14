# Results and appearance

## Regression tables

Regression commands now show a model summary followed by a coefficient table. Numeric columns are right aligned, rows are shaded, and confidence limits share a header showing the requested confidence level. P-values below 0.001 display as `<0.001`; other p-values use three decimal places. Coefficients, standard errors and limits use six decimals, with scientific notation for very small or large values. Statistics use two decimals and fit measures four. Missing results display as `.`.

This is display rounding only. Coefficients, covariance matrices, returned estimation results, predictions and downstream calculations retain their original numeric precision. Ratio output explains exponentiation and the delta-method standard errors; negative-binomial alpha remains untransformed.

`xtreg` distinguishes fixed-effects and random-effects models, and shows group count, minimum/average/maximum observations per group and within/between/overall R-squared. These describe the fitted estimation sample, even after storing/restoring a model. Panel values and inference follow linearmodels conventions; the existing PANEL notice documents differences from Stata.

The rich tables appear in the Results tab. **File > Save results**, text logs and batch runs use aligned plain text so they remain readable outside Qt. Copying a selection from the Results tab uses Qt's native rich-text clipboard behaviour; use Save results when you need an aligned plain-text transcript.

## Material dark mode

Click the sun/moon icon in the toolbar, or choose **Material dark mode** in the **Window** menu. The icon shows the theme you will switch to: a moon for dark mode and a sun for light mode. Charcoal surfaces, purple accents, rounded controls and contrasting text are applied to the desktop, data views, menus, editor highlighting, command suggestions and optional Learn panel. Already displayed results are recoloured immediately without rerunning commands. The setting is saved for the next session. Turn the same toggle off to return to light mode.

The theme uses Qt6 styling with no additional theme package. Native operating-system window borders and file dialogs follow system settings. Statistical graph artwork retains its plotting colours, including when exported.

Screenshots: `results-light.png` and `results-dark.png`.

## History and startup folder

The **Review** pane has a **Clear history** button and a **Remember history** checkbox. These controls are also available by right-clicking the pane or opening **Window > Command history**.

- **Clear history** removes current and saved command recall, including history-based inline suggestions. New commands start a fresh history. Results, do-files and logs are retained.
- **Remember history**, enabled by default, saves up to 1,000 commands between sessions. Unchecking it removes saved history immediately. The current session still has command recall; the next session starts with an empty Review pane.
- **File > Remember working folder between sessions**, enabled by default, restores the last valid working folder. Unchecking it removes the saved folder immediately, leaves the current session's folder unchanged, and starts future sessions in your home folder. Re-enable it to remember the folder again.

These preferences persist across restarts and updates. Theme and window layout preferences are independent of history and working-folder persistence.
