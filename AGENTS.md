# Agent instructions

## Code reviews

- Act as a senior software engineer: be critical, direct, and willing to challenge flawed assumptions or design choices. Clearly call out significant problems, even when they require substantial changes.
- Prioritize correctness and logical consistency. Trace behavior across affected components, check edge cases and failure paths, and verify that changes preserve the project's requirements and invariants.
- Evaluate test coverage for changed behavior, regressions, and meaningful edge cases. Flag missing or weak tests; passing tests alone do not establish correctness.
- Review documentation alongside code. Check that the README, API documentation, examples, and relevant comments accurately reflect the changes. Preserve the distinction between implemented and planned features.
- Make findings actionable: identify the affected file and line, explain the concrete impact, and suggest a practical correction. Prioritize substantive issues over stylistic preferences.
- Ground findings in evidence, state uncertainty explicitly, and do not invent problems. If no substantive issues are found, say so and note any remaining testing gaps or unverified behavior.

## Code style during development and review

- Apply these guidelines when writing or modifying code and when reviewing changes. Follow the project's configured lint rules and established conventions; for Python, respect the Ruff configuration in `pyproject.toml`, including the 89-character line limit and import ordering.
- Favor clear names, straightforward control flow, and focused functions. Explain non-obvious decisions and constraints in comments or docstrings rather than restating the code.
- Every test must have a concise, one-line summary describing the behavior or outcome it verifies. For Python tests, put this summary in a docstring as the first statement of the test function; a descriptive test name does not replace it.
- For complex tests, expand the docstring beyond the summary, separated by a blank line. Explain the scenario, any non-obvious setup or sequence of actions, and the expected outcome or regression being protected against. Document meaningful parameterized cases when their purpose is not clear from the summary.
- For test languages without docstrings, place an equivalent descriptive comment immediately above each test and add more detail for complex scenarios.
- During review, flag missing or inadequate test descriptions and violations of these style guidelines. Distinguish required conventions from optional preferences, and prioritize correctness and coverage issues by impact.

## Required checks before every commit

- Every commit must pass Ruff lint, Ruff formatting, and mypy for all Python source
  and tests. Apply this requirement during development and verify it during review.
- Install development tools and Git hooks with `make backend-dev`, or run
  `uv sync --extra dev` followed by `uv run --extra dev pre-commit install`.
- Before committing, run `uv run --extra dev ruff check src tests`,
  `uv run --extra dev ruff format --check src tests`, and `uv run --extra dev mypy src tests`.
  `make check` runs the same checks. Run relevant tests for behavior changes as well.
- Fix failures before committing. Do not bypass hooks or weaken checks with broad
  exclusions, ignores, or untyped code to make a commit pass. Keep type annotations
  accurate and explain any narrowly necessary suppression.
