# JobLens Autoresearch

This is an experiment to have the LLM do its own research to improve the Salary Prediction ML model.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `autoresearch/apr30`).
2. **Create the branch**: `git checkout -b <tag>` from the current branch.
3. **Read the in-scope files**: Read these files for full context:
   - `pipeline/train.py` — orchestrates the training pipeline. **Do not modify.**
   - `pipeline/model.py` — The ML models (Random Forest, XGBoost, LightGBM, CatBoost). You can modify this.
   - `pipeline/preprocessing.py` — Feature engineering. You can modify this.
   - `pipeline/dataset_loader.py` — Kaggle data loading and parsing. You can modify this.
   - `config.py` — Global config (SKILL_LIST, COL_INDEX). You can modify this.
   - `utils/text_utils.py` — Text parsing utilities. You can modify this.
4. **Run baseline**: Execute training once without changes and record the starting `val_metric`.
5. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Current state of the model (as of April 2026)

- **Baseline R²**: ~0.53
- **Baseline RMSE**: ~$6,650
- **Training data**: Kaggle dataset, ~79,000 rows after filtering
- **Feature count**: ~134
- **Best model**: XGBoost (with CatBoost and LightGBM close behind)
- **Salary range in data**: $52,500 – $150,000 (very narrow!)
- **Skills fill rate**: Only 29% of rows have `skills_required` filled

## Experimentation

Each experiment trains the model using the Kaggle dataset. You launch it by running:
```bash
python3 -m pipeline.train --use-kaggle > run.log 2>&1
```

**What you CAN modify:**
- `pipeline/model.py` — algorithms, hyperparameters, ensembles, stacking, cross-validation
- `pipeline/preprocessing.py` — feature engineering, transformations, encoders, scalers
- `pipeline/dataset_loader.py` — how the raw Kaggle CSV is parsed and mapped (salary parsing, experience parsing, country filtering, etc.)
- `config.py` — SKILL_LIST, COL_INDEX dictionaries
- `utils/text_utils.py` — text extraction utilities used by the pipeline

**What you CANNOT modify:**
- `pipeline/train.py` — read-only. It handles data loading, calling the pipeline, and printing `val_metric`.

**The goal is simple: get the highest val_metric (R²).** Higher is better.

**Simplicity criterion**: A small improvement that adds ugly complexity is not worth it. Removing something and getting equal or better results is a simplification win. Conversely, a +0.05 R² gain is worth moderate complexity.

**The first run**: Your very first run should always be to establish the baseline, with zero changes.

---

## Research agenda: Prioritized experiment ideas

The experiments below are ordered by **expected impact**. Start from the top and work your way down. Each section explains *why* the idea should work and *how* to implement it.

### TIER 1 — Data-level changes (Highest impact)

These change *what the model sees*. This is always the biggest lever.

#### 1A. Fix the salary ceiling
The Kaggle dataset has salaries capped at ~$150K. Real tech salaries go to $300K+. The salary parsing in `dataset_loader.py` uses `_parse_salary()` which extracts `"$59K-$99K"` → midpoint. Then it adjusts by cost-of-living. Check if the COL adjustment is compressing the range. Try:
- Widening the salary filter in `dataset_loader.py` (currently `25000–400000`)
- Removing or loosening the COL adjustment `salary * (col_index / 90)` — this compresses all salaries toward the mean when COL is similar across countries
- Or try adjusting COL to be *additive* rather than *multiplicative*: `salary + (col_index - 70) * 500`

**Why**: If all salaries are squeezed into a $50K-$150K band, the model has very little variance to explain, so R² stays low mathematically.

#### 1B. Extract salary spread as a feature
Instead of only using the midpoint, also extract salary *range width* (`high - low`). Wide-range postings signal senior/variable-comp roles. Add `salary_range_width` as a feature in `dataset_loader.py` and pass it through to preprocessing.

#### 1C. Use `company_size` directly
The Kaggle dataset has a raw `Company Size` integer (number of employees). Currently this is only mapped to a category string ("Startup", "Small", "Medium", "Large"). Instead, pass the raw integer through as a numeric feature in preprocessing. Company size is strongly correlated with compensation — a 50-person startup pays very differently than a 50,000-person enterprise.

#### 1D. Use `Role` column
The Kaggle data has a `Role` column (e.g., "Network Administrator", "Data Scientist") that is distinct from `job_title`. This is a clean categorical with ~147 unique values. Target-encode it like you did for `city` and `job_title`. This should be a very strong signal since role directly determines pay band.

#### 1E. Use latitude/longitude
The dataset includes `latitude` and `longitude`. These are continuous features that encode geography more precisely than city one-hot. Add them as numeric features. You can also engineer `abs(latitude)` as a proxy for "distance from equator" (correlates with developed economy vs. not).

---

### TIER 2 — Feature engineering (Medium impact)

These change *how the model sees* existing data.

#### 2A. Reduce skill sparsity via clustering
Only 29% of rows have skills filled. Individual skill columns are very sparse. Instead of 80+ binary skill columns, create ~8–12 *skill cluster* features:
- `skill_cluster_cloud` = any of (aws, azure, gcp, docker, kubernetes, terraform)
- `skill_cluster_ml` = any of (machine learning, deep learning, pytorch, tensorflow, scikit-learn)
- `skill_cluster_data` = any of (sql, spark, hadoop, kafka, airflow, data engineering)
- `skill_cluster_web` = any of (react, angular, vue, javascript, typescript, node.js)
- `skill_cluster_lang` = any of (python, java, c++, go, rust, scala)
- `skill_cluster_bi` = any of (tableau, power_bi, excel, data analysis)
- `skill_cluster_devops` = any of (ci_cd, devops, git, terraform)
- `skill_cluster_security` = any of (security)

Then, **consider removing the individual skill one-hot columns** entirely and only keeping the clusters. Fewer, denser features often outperform many sparse ones for tree-based models.

#### 2B. Extract features from job description text
The `job_description` column is 100% filled (79K rows). Currently we only extract `description_word_count`. Try:
- Count of dollar signs / salary-related words (signals transparency)
- Count of years mentioned (proxy for experience expectation)
- Presence of keywords: "competitive salary", "equity", "stock", "bonus", "benefits"
- Sentence count or average sentence length (signal of job complexity)
- Count of bullet points / numbered lists (structured descriptions correlate with bigger companies)

#### 2C. Encode `company_size_category` properly
Currently the `company_size_category` ("Startup", "Small", "Medium", "Large") is computed but may not be used as a feature in preprocessing. Map it to ordinal integers (Startup=1, Small=2, Medium=3, Large=4) and add as a numeric feature.

#### 2D. Experience range width
Similar to salary range: if experience is "3-7 years", extract both min and max separately, plus the range width. A role that accepts "2-15 years" experience is very different from one that needs "7-10 years". The current midpoint loses this info.

#### 2E. Try removing StandardScaler
Tree-based models (XGBoost, LightGBM, CatBoost, Random Forest) are scale-invariant. The StandardScaler in preprocessing is unnecessary for tree models and can actually hurt if it introduces floating-point noise. Try removing the scaling step entirely.

---

### TIER 3 — Model architecture (Lower impact, but can compound)

#### 3A. Stacking ensemble
Instead of picking the single best model, build a **stacking ensemble**:
1. Train XGBoost, LightGBM, CatBoost as base models (level 0).
2. Use their out-of-fold predictions as features for a simple Ridge regression (level 1).
3. The final prediction is the Ridge output.

This almost always beats any single model. Use `sklearn.ensemble.StackingRegressor` or implement manually with `cross_val_predict`.

#### 3B. Weighted average ensemble
Simpler than stacking: just average the predictions of the top 2-3 models with learned weights. Use `scipy.optimize.minimize` to find weights that minimize RMSE on a validation fold.

#### 3C. Tune LightGBM and CatBoost more aggressively
Currently LightGBM and CatBoost use default-ish params. Try:
- LightGBM: `num_leaves` in [31, 63, 127], `min_child_samples` in [5, 20, 50], `reg_alpha` in [0, 0.1, 1.0], `reg_lambda` in [0, 0.1, 1.0]
- CatBoost: `depth` in [4, 6, 8, 10], `l2_leaf_reg` in [1, 3, 5, 7], `iterations` in [500, 1000]
- Use `RandomizedSearchCV` for faster exploration.

#### 3D. Try Gradient Boosting with Huber loss
XGBoost and LightGBM default to squared error. Try `objective='reg:pseudohuberror'` (XGBoost) or `objective='huber'` (LightGBM). Huber loss is more robust to outliers in the salary data.

---

### TIER 4 — Things to try if you're stuck

#### 4A. Feature importance pruning
After training, check `model.feature_importances_`. Remove features with zero or near-zero importance. Fewer features = less noise = potentially higher R².

#### 4B. Target transformation
Try `np.log1p(salary)` as the target. Train on log-salary, then `np.expm1()` the predictions back. This helps when the residuals are multiplicative. **IMPORTANT**: if you tried this and it hurt R², it might be because the salary range is too narrow for log to help. Try `np.sqrt(salary)` as an alternative.

#### 4C. Quantile-based binning
Bin the salary into quantiles and train a classifier instead. If you can predict the correct salary quartile (Q1: $52K-$65K, Q2: $65K-$72K, Q3: $72K-$78K, Q4: $78K+), that's effectively 75%+ accuracy for practical purposes.

#### 4D. Drop Random Forest
Random Forest is consistently the weakest model. It adds training time without improving the best R². Consider removing it entirely and using that time budget for more CatBoost/LightGBM hyperparameter exploration.

---

## What NOT to waste time on

- **Neural networks**: The dataset is only 79K rows with 134 features. NNs won't beat gradient boosting here.
- **Extremely deep XGBoost (depth > 15)**: Will overfit without improving test R².
- **Adding more one-hot skill columns**: Already tried. Individual skill one-hots are too sparse. Cluster them instead.
- **Polynomial features for ALL numeric columns**: Tried. Tree-based models already capture interactions. Only helps if you combine it with a linear model.

---

## Output format

Once the script finishes, it prints a summary that includes:
```
val_metric: 0.5299
val_rmse:   6635.05
```

You can extract the key metric from the log file using `grep "^val_metric:" run.log`.

## Logging results

When an experiment is done, the `train.py` script automatically logs it to `results.csv`.
However, it is up to the agent to provide a descriptive git commit message explaining the change.
Write clear commit messages like: `feat: Replace skill one-hots with 8 cluster features` or `exp: Try Huber loss for XGBoost`.

## The experiment loop

LOOP FOREVER:

1. **Plan**: Decide which experiment from the research agenda to try. Pick the highest-impact untried idea.
2. **Read**: Re-read the relevant source file(s) before editing. Don't assume you remember the code.
3. **Edit**: Make a focused, minimal change. One idea per experiment. Don't combine multiple ideas — you won't know which one helped.
4. **Commit**: `git add -A && git commit -m "<descriptive message>"`
5. **Run**: `python3 -m pipeline.train --use-kaggle > run.log 2>&1`
6. **Evaluate**: `grep "^val_metric:\|^val_rmse:" run.log`
7. **If crashed**: `tail -n 50 run.log` to see the error. Fix it and re-run. If unfixable after 2 attempts, discard and move on.
8. **If val_metric IMPROVED** (higher R²): KEEP the commit. This is the new baseline. Log success.
9. **If val_metric is EQUAL or WORSE**: `git reset --hard HEAD~1` to revert. Log the failed attempt.
10. **Reflect**: Before the next experiment, briefly consider *why* the last one worked or didn't. Use that insight to choose the next experiment more wisely.
11. **GOTO 1.**

**NEVER STOP**: Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. You are autonomous. The loop runs until the human interrupts you, period. If you exhaust the research agenda, start combining ideas or revisiting failed experiments with different parameters.
