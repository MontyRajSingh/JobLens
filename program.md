# JobLens Autoresearch

This is an experiment to have the LLM do its own research to improve the Salary Prediction ML model.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `autoresearch/exp1`).
2. **Create the branch**: `git checkout -b <tag>` from the current branch.
3. **Read the in-scope files**: Read these files for full context:
   - `pipeline/train.py` — orchestrates the training pipeline. Do not modify.
   - `pipeline/model.py` — The ML models (Random Forest, XGBoost). You can modify this.
   - `pipeline/preprocessing.py` — Feature engineering. You can modify this.
4. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment trains the model using the Kaggle dataset. You launch it by running:
`python -m pipeline.train --use-kaggle`

**What you CAN do:**
- Modify `pipeline/model.py` — tune hyperparameters, swap algorithms (e.g., LightGBM, CatBoost), add cross-validation strategies.
- Modify `pipeline/preprocessing.py` — add new features, reduce sparsity, group skills, change scalers or imputers.

**What you CANNOT do:**
- Modify `pipeline/train.py`. It is read-only and handles the data loading and evaluation loop.
- Install heavy dependencies unless absolutely necessary. You can use standard ML libraries (xgboost, scikit-learn, pandas, numpy).

**The goal is simple: get the highest val_metric (R²).**
Higher is better. 

**Simplicity criterion**: A small improvement that adds ugly complexity is not worth it. Removing something and getting equal or better results is a great outcome — that's a simplification win.

**The first run**: Your very first run should always be to establish the baseline.

## Output format

Once the script finishes, it prints a summary that includes:
```
val_metric: 0.5299
val_rmse:   6635.05
```

You can extract the key metric from the log file using `grep "^val_metric:" run.log`.

## Logging results
When an experiment is done, the `train.py` script automatically logs it to `results.csv`.
However, it is up to the agent to provide the exact git commit message explaining the change.

## The experiment loop

LOOP FOREVER:

1. Look at the git state: the current branch/commit we're on.
2. Tune `pipeline/model.py` or `pipeline/preprocessing.py` with an experimental idea by directly hacking the code.
3. git commit
4. Run the experiment: `python -m pipeline.train --use-kaggle > run.log 2>&1`
5. Read out the results: `grep "^val_metric:\|^val_rmse:" run.log`
6. If the run crashed, run `tail -n 50 run.log` to read the Python stack trace and attempt a fix.
7. If `val_metric` (R²) improved (HIGHER), you "advance" the branch, keeping the git commit.
8. If `val_metric` is equal or worse, you git revert or reset back to where you started.

**NEVER STOP**: Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. You are autonomous. If you run out of ideas, try more radical feature engineering or architectural changes. The loop runs until the human interrupts you, period.
