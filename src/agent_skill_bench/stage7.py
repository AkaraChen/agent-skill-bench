"""KIT-919 / Stage 7: frozen Codex × eric-way experiment catalog.

Design and dry-run only. Do not start billed trials from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agent_skill_bench.constants import DOCKER_DIGEST, DOCKER_IMAGE, HARBOR_VERSION
from agent_skill_bench.fingerprint import sha256_text, sha256_tree

REVISION = "stage7-ericway-2026.08.26.r1"
ERIC_WAY_COMMIT = "786ba75fa2de5238da80415dfad8d7e7ce5b4eab"
BENCH_BASE_COMMIT = "7587e40d4a26a8b0a7c004ab81c28f2c89f42256"
SKILL_ROOT = "skills/eric-way"

TRACK = "B"
AGENT_NAME = "codex"
CODEX_CLI_VERSION = "0.149.1"
MODEL_SNAPSHOT = "openai/gpt-5.6"
REASONING_EFFORT = "medium"
WEB_SEARCH = "disabled"
PROMPT_NAME = "stage7"
PROMPT_PATH = "prompts/stage7-codex.md"
USD_PER_TRIAL = 2.0
N_CONCURRENT = 2
MAX_RETRIES = 1
SEED = 919
NETWORK_MODE = "no-network"
AGENT_TIMEOUT_SEC = 900
VERIFIER_TIMEOUT_SEC = 180
E2E_AGENT_TIMEOUT_SEC = 1200
REVIEW_AGENT_TIMEOUT_SEC = 600

Kind = Literal["implement", "bugfix", "refactor", "test", "review", "plan"]
OracleKind = Literal["hidden_tests", "static_checks", "rubric_blind", "mixed"]
StageId = Literal["8A", "8B", "8C", "8D"]


INCLUDED_SKILLS = (
    "eric-backend",
    "eric-design",
    "eric-desktop",
    "eric-e2e-testing",
    "eric-frontend",
    "eric-github-actions",
    "eric-grill",
    "eric-javascript",
    "eric-quality-control",
    "eric-react",
    "eric-review",
    "eric-ui",
    "eric-writing-tests",
)

EXCLUDED_SKILLS: dict[str, str] = {
    "eric-github-pr": "GitHub PR viewed-state / GraphQL operations; collaboration, not local review.",
    "design-dna": "Vendored extractor, not an Eric atomic coding skill in this round.",
    "guided-review": "PR walkthrough artifacts; collaboration-adjacent.",
    "kill-ai-slop": "Vendored writing-style skill, not in the Stage 7 candidate list.",
    "native-feel-skill": "Vendored desktop-feel skill, not in the Stage 7 candidate list.",
}

SCENARIOS: dict[str, dict[str, Any]] = {
    "backend": {"stage": "8A", "issue": "KIT-913", "label": "后端"},
    "javascript": {"stage": "8A", "issue": "KIT-913", "label": "JavaScript/工具链"},
    "quality": {"stage": "8A", "issue": "KIT-913", "label": "质量与测试"},
    "ci": {"stage": "8A", "issue": "KIT-913", "label": "CI"},
    "frontend": {"stage": "8B", "issue": "KIT-914", "label": "前端"},
    "react": {"stage": "8B", "issue": "KIT-914", "label": "React"},
    "ui": {"stage": "8B", "issue": "KIT-914", "label": "UI 正确性"},
    "design": {"stage": "8B", "issue": "KIT-914", "label": "视觉设计"},
    "e2e": {"stage": "8B", "issue": "KIT-914", "label": "浏览器行为"},
    "desktop": {"stage": "8C", "issue": "KIT-915", "label": "桌面端"},
    "grill": {"stage": "8D", "issue": "KIT-916", "label": "方案推演"},
    "review": {"stage": "8D", "issue": "KIT-916", "label": "代码审查"},
}

STAGE_ISSUES = {
    "8A": {"id": "01a03a2b-6f04-7c28-8c02-1871b937692c", "key": "KIT-913", "config": "configs/experiments/stage8a-screen.yaml"},
    "8B": {"id": "01a03a2b-7859-7c5f-8860-475faee34cf9", "key": "KIT-914", "config": "configs/experiments/stage8b-screen.yaml"},
    "8C": {"id": "01a03a2b-81c4-7247-9dd3-b732fc7e600c", "key": "KIT-915", "config": "configs/experiments/stage8c-screen.yaml"},
    "8D": {"id": "01a03a2b-8ae6-7c3b-a075-8a43b03f098c", "key": "KIT-916", "config": "configs/experiments/stage8d-screen.yaml"},
}

CONFIRM_ISSUE = {
    "id": "01a03a2b-947b-7938-b59e-2949c75c5626",
    "key": "KIT-917",
    "config": "configs/experiments/stage9-confirm.example.yaml",
}


def skill_path(name: str) -> str:
    return f"./{SKILL_ROOT}/{name}"


@dataclass(frozen=True)
class Treatment:
    name: str
    skills: tuple[str, ...]
    kind: Literal["baseline", "single", "realistic", "contrast", "overload", "wrong"]
    primary: str | None = None
    note: str = ""

    @property
    def paths(self) -> list[str]:
        return [skill_path(name) for name in self.skills]


@dataclass(frozen=True)
class TaskSpec:
    id: str
    scenario: str
    primary_skill: str
    kind: Kind
    oracle: OracleKind
    instruction: str
    oracle_spec: str
    extra_treatments: tuple[str, ...] = ()
    realistic_treatment: str | None = None
    agent_timeout_sec: int = AGENT_TIMEOUT_SEC
    difficulty: str = "medium"

    @property
    def stage(self) -> StageId:
        return SCENARIOS[self.scenario]["stage"]

    @property
    def single_name(self) -> str:
        return f"single-{self.primary_skill.removeprefix('eric-')}"

    @property
    def realistic_name(self) -> str:
        if self.realistic_treatment:
            return self.realistic_treatment
        return f"realistic-{self.primary_skill.removeprefix('eric-')}"

    @property
    def treatment_names(self) -> tuple[str, ...]:
        return ("baseline", self.single_name, self.realistic_name, *self.extra_treatments)


def _t(
    name: str,
    skills: tuple[str, ...],
    kind: Literal["baseline", "single", "realistic", "contrast", "overload", "wrong"],
    primary: str | None = None,
    note: str = "",
) -> Treatment:
    return Treatment(name=name, skills=skills, kind=kind, primary=primary, note=note)


TREATMENTS: dict[str, Treatment] = {
    "baseline": _t("baseline", (), "baseline", note="No Eric skill loaded."),
    "single-backend": _t("single-backend", ("eric-backend",), "single", "eric-backend"),
    "single-javascript": _t("single-javascript", ("eric-javascript",), "single", "eric-javascript"),
    "single-quality-control": _t("single-quality-control", ("eric-quality-control",), "single", "eric-quality-control"),
    "single-writing-tests": _t("single-writing-tests", ("eric-writing-tests",), "single", "eric-writing-tests"),
    "single-github-actions": _t("single-github-actions", ("eric-github-actions",), "single", "eric-github-actions"),
    "single-frontend": _t("single-frontend", ("eric-frontend",), "single", "eric-frontend"),
    "single-react": _t("single-react", ("eric-react",), "single", "eric-react"),
    "single-ui": _t("single-ui", ("eric-ui",), "single", "eric-ui"),
    "single-design": _t("single-design", ("eric-design",), "single", "eric-design"),
    "single-e2e-testing": _t("single-e2e-testing", ("eric-e2e-testing",), "single", "eric-e2e-testing"),
    "single-desktop": _t("single-desktop", ("eric-desktop",), "single", "eric-desktop"),
    "single-grill": _t("single-grill", ("eric-grill",), "single", "eric-grill"),
    "single-review": _t("single-review", ("eric-review",), "single", "eric-review"),
    "realistic-backend": _t(
        "realistic-backend",
        ("eric-javascript", "eric-backend", "eric-writing-tests"),
        "realistic",
        "eric-backend",
        "Doc order: JS toolchain, then backend, then focused tests.",
    ),
    "realistic-javascript": _t(
        "realistic-javascript",
        ("eric-javascript", "eric-quality-control"),
        "realistic",
        "eric-javascript",
        "New/existing JS work loads ni plus boring local gates.",
    ),
    "realistic-quality-control": _t(
        "realistic-quality-control",
        ("eric-javascript", "eric-quality-control"),
        "realistic",
        "eric-quality-control",
    ),
    "realistic-writing-tests": _t(
        "realistic-writing-tests",
        ("eric-writing-tests", "eric-quality-control"),
        "realistic",
        "eric-writing-tests",
    ),
    "realistic-github-actions": _t(
        "realistic-github-actions",
        ("eric-quality-control", "eric-github-actions"),
        "realistic",
        "eric-github-actions",
        "CI must reuse local gates, then pin actions.",
    ),
    "realistic-frontend": _t(
        "realistic-frontend",
        ("eric-javascript", "eric-frontend", "eric-writing-tests"),
        "realistic",
        "eric-frontend",
    ),
    "realistic-react": _t(
        "realistic-react",
        ("eric-javascript", "eric-frontend", "eric-react"),
        "realistic",
        "eric-react",
    ),
    "realistic-ui": _t(
        "realistic-ui",
        ("eric-ui", "eric-frontend"),
        "realistic",
        "eric-ui",
        "Correctness first; design is not loaded here.",
    ),
    "realistic-design": _t(
        "realistic-design",
        ("eric-ui", "eric-design", "eric-frontend"),
        "realistic",
        "eric-design",
        "UI boundary then visual craft, with frontend styling rules.",
    ),
    "realistic-e2e-testing": _t(
        "realistic-e2e-testing",
        ("eric-writing-tests", "eric-e2e-testing"),
        "realistic",
        "eric-e2e-testing",
    ),
    "realistic-desktop": _t(
        "realistic-desktop",
        ("eric-javascript", "eric-backend", "eric-frontend", "eric-desktop"),
        "realistic",
        "eric-desktop",
        "Doc-recommended cross-layer combo; tests/e2e added only when the task asks.",
    ),
    "realistic-grill": _t(
        "realistic-grill",
        ("eric-grill", "eric-backend"),
        "realistic",
        "eric-grill",
        "Backend-plan grill with the domain skill the plan is about.",
    ),
    "realistic-review": _t(
        "realistic-review",
        ("eric-review", "eric-backend"),
        "realistic",
        "eric-review",
        "Review skill plus the stack skill for the diff. Frontend/desktop review tasks override this in extras.",
    ),
    "realistic-review-frontend": _t(
        "realistic-review-frontend",
        ("eric-review", "eric-frontend", "eric-react", "eric-ui"),
        "realistic",
        "eric-review",
    ),
    "realistic-review-desktop": _t(
        "realistic-review-desktop",
        ("eric-review", "eric-desktop", "eric-frontend"),
        "realistic",
        "eric-review",
    ),
    "contrast-design": _t(
        "contrast-design",
        ("eric-design",),
        "contrast",
        "eric-design",
        "Design-only on a UI-correctness task: usefulness vs looks.",
    ),
    "contrast-ui": _t(
        "contrast-ui",
        ("eric-ui",),
        "contrast",
        "eric-ui",
        "UI-only on a visual task.",
    ),
    "overload-backend-kitchen": _t(
        "overload-backend-kitchen",
        (
            "eric-backend",
            "eric-frontend",
            "eric-design",
            "eric-grill",
            "eric-review",
            "eric-github-actions",
        ),
        "overload",
        note="Too many unrelated rules on a thin-transport backend task.",
    ),
    "wrong-backend-on-frontend": _t(
        "wrong-backend-on-frontend",
        ("eric-backend",),
        "wrong",
        note="Backend skill on a frontend ownership task.",
    ),
    "overload-react-visual-ci": _t(
        "overload-react-visual-ci",
        ("eric-design", "eric-ui", "eric-github-actions"),
        "overload",
        note="Visual/CI rules on a React memoization/effects task.",
    ),
    "wrong-grill-design-on-ci": _t(
        "wrong-grill-design-on-ci",
        ("eric-grill", "eric-design"),
        "wrong",
        note="Plan/visual skills on a GitHub Actions pinning task.",
    ),
    "overload-desktop-visual": _t(
        "overload-desktop-visual",
        ("eric-design", "eric-ui", "eric-frontend", "eric-react"),
        "overload",
        note="Renderer visual stack without desktop IPC skill.",
    ),
    "wrong-javascript-on-review": _t(
        "wrong-javascript-on-review",
        ("eric-javascript",),
        "wrong",
        note="Toolchain skill instead of review judgment.",
    ),
    "wrong-unit-on-e2e": _t(
        "wrong-unit-on-e2e",
        ("eric-writing-tests",),
        "wrong",
        note="Unit-test skill on a real-browser smoke task.",
    ),
}


TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        id="be-thin-transport",
        scenario="backend",
        primary_skill="eric-backend",
        kind="implement",
        oracle="mixed",
        extra_treatments=("overload-backend-kitchen",),
        instruction=(
            "This repo is a small Hono + Drizzle TypeScript API. Routes currently call "
            "the database from the handler. Add GET /orders/:id that returns the order "
            "or 404. Reuse existing types. Do not invent a new framework."
        ),
        oracle_spec=(
            "Hidden tests: handler stays thin (parse, call service, map result); "
            "service owns lookup; transport does not import the Drizzle client. "
            "Static: tsc. Diff quality: no new abstraction layer. Overengineering = fail rubric."
        ),
    ),
    TaskSpec(
        id="be-typed-errors",
        scenario="backend",
        primary_skill="eric-backend",
        kind="bugfix",
        oracle="hidden_tests",
        instruction=(
            "Reusable service functions return string error codes. Callers parse those "
            "strings. Fix the error handling so domain failures are typed. Keep the HTTP "
            "edge mapping in the route."
        ),
        oracle_spec=(
            "Hidden tests: NotFound/Conflict are distinct types or enums; HTTP mapper "
            "still lives at the edge; no `error === 'not_found'` in reusable code."
        ),
    ),
    TaskSpec(
        id="be-trust-boundary",
        scenario="backend",
        primary_skill="eric-backend",
        kind="refactor",
        oracle="mixed",
        instruction=(
            "POST /accounts accepts a JSON body and passes it straight into core logic. "
            "Untrusted fields include negative balances and extra keys. Put validation at "
            "the trust boundary. Do not add a generic validation framework if the repo "
            "already has a schema helper."
        ),
        oracle_spec=(
            "Hidden tests: invalid bodies never reach core; extra keys stripped or rejected; "
            "core unit tests still pass with already-valid input. Adversarial cases required."
        ),
    ),
    TaskSpec(
        id="js-ni-scripts",
        scenario="javascript",
        primary_skill="eric-javascript",
        kind="implement",
        oracle="static_checks",
        instruction=(
            "Add a `lint` and `test` developer workflow to this existing TypeScript repo. "
            "package.json currently documents `npm run` commands. Follow the repo's package "
            "manager instead of hard-coding npm."
        ),
        oracle_spec=(
            "Static: README/scripts use `ni`/`nr` (or the repo package manager via ni), "
            "not `npm run`/`npm i`. packageManager field left intact. No new package manager."
        ),
    ),
    TaskSpec(
        id="js-new-project-pm",
        scenario="javascript",
        primary_skill="eric-javascript",
        kind="implement",
        oracle="static_checks",
        instruction=(
            "Scaffold a new tiny TypeScript library in ./pkg with a package.json, "
            "tsconfig, and one exported function `clamp`. Use the default package manager "
            "for a new Eric JS project."
        ),
        oracle_spec=(
            "packageManager is pnpm (latest major acceptable); lockfile is pnpm; no yarn.lock "
            "or package-lock.json. `clamp` is exported and typechecked."
        ),
    ),
    TaskSpec(
        id="js-mixed-pm",
        scenario="javascript",
        primary_skill="eric-javascript",
        kind="bugfix",
        oracle="static_checks",
        instruction=(
            "CONTRIBUTING.md and two scripts mix `yarn` and `npm`. Make the documented "
            "commands match the existing pnpm repo."
        ),
        oracle_spec="No yarn/npm install or run commands remain in docs/scripts; ni/nr or pnpm only.",
    ),
    TaskSpec(
        id="qc-add-gates",
        scenario="quality",
        primary_skill="eric-quality-control",
        kind="implement",
        oracle="static_checks",
        instruction=(
            "This TypeScript repo has no formatter, linter, typecheck, or test command. "
            "Add the boring local gates and wire them in package.json. Do not add extra "
            "security scanners."
        ),
        oracle_spec=(
            "Exactly one tool per job: format, lint, typecheck, test. Commands exist and "
            "pass on the fixture. No Knip/Playwright/audit unless asked."
        ),
    ),
    TaskSpec(
        id="qc-fix-lint",
        scenario="quality",
        primary_skill="eric-quality-control",
        kind="bugfix",
        oracle="hidden_tests",
        instruction=(
            "Lint currently fails. There is an eslint-disable on the broken line. Make the "
            "gate pass for the right reason."
        ),
        oracle_spec="Root cause fixed; eslint-disable removed; lint and the focused unit test pass.",
    ),
    TaskSpec(
        id="qc-too-many-tools",
        scenario="quality",
        primary_skill="eric-quality-control",
        kind="refactor",
        oracle="static_checks",
        instruction=(
            "The repo runs both Prettier and Biome for formatting, plus two test runners. "
            "Clean this up so each gate has one tool. Prefer what the repo already uses for "
            "app code."
        ),
        oracle_spec="One formatter, one test runner remain; CI/scripts call those; no third tool added.",
    ),
    TaskSpec(
        id="wt-regression",
        scenario="quality",
        primary_skill="eric-writing-tests",
        kind="test",
        oracle="hidden_tests",
        instruction=(
            "parseDuration('1.5h') currently returns 1 hour. Add a test that would have "
            "caught this, then fix the parser. Do not snapshot the whole module."
        ),
        oracle_spec=(
            "A focused test fails on the original code (hidden broken copy) and passes on "
            "the fix. No extra tests for trivial getters."
        ),
    ),
    TaskSpec(
        id="wt-skip-trivial",
        scenario="quality",
        primary_skill="eric-writing-tests",
        kind="test",
        oracle="rubric_blind",
        instruction=(
            "A reviewer asked for unit tests on a one-line `isEnabled` getter and on the "
            "generated protobuf types. Write tests only if they are worth writing. Put a "
            "short note in TEST_NOTE.md explaining skips."
        ),
        oracle_spec=(
            "Blind rubric: must refuse coverage-only getter/generated tests; may add a test "
            "only if a real break is possible. Note must name the skipped items."
        ),
    ),
    TaskSpec(
        id="wt-adversarial",
        scenario="quality",
        primary_skill="eric-writing-tests",
        kind="test",
        oracle="hidden_tests",
        instruction=(
            "mergeIds(a, b) concatenates two id lists. Write tests that prove the public "
            "contract, including messy input."
        ),
        oracle_spec="Hidden tests require empty, duplicate, and order-preserving cases; implementation-mirroring tests are not enough.",
    ),
    TaskSpec(
        id="ci-pin-actions",
        scenario="ci",
        primary_skill="eric-github-actions",
        kind="implement",
        oracle="static_checks",
        extra_treatments=("wrong-grill-design-on-ci",),
        instruction=(
            "Add a CI workflow that runs the repo's existing `nr lint`, `nr typecheck`, "
            "and `nr test`. External actions must be current and pinned. A `gh` CLI is on "
            "PATH; use it if you need version data. Do not invent new test commands."
        ),
        oracle_spec=(
            "Fixture `gh` returns frozen latest SHAs for actions/checkout and actions/setup-node. "
            "Workflow uses those SHAs with version comments; permissions are contents:read; "
            "no pull_request_target; actionlint-clean YAML."
        ),
    ),
    TaskSpec(
        id="ci-permissions",
        scenario="ci",
        primary_skill="eric-github-actions",
        kind="bugfix",
        oracle="static_checks",
        instruction=(
            ".github/workflows/pr.yml uses pull_request_target, write-all permissions, and "
            "checks out the PR head then runs it. Fix the workflow so untrusted code cannot "
            "steal secrets."
        ),
        oracle_spec="No pull_request_target; permissions narrowed; untrusted checkout is not executed; secrets not echoed.",
    ),
    TaskSpec(
        id="ci-local-commands",
        scenario="ci",
        primary_skill="eric-github-actions",
        kind="refactor",
        oracle="static_checks",
        instruction=(
            "CI inlines eslint and tsc flags that drift from package.json. Make CI call the "
            "same commands developers run."
        ),
        oracle_spec="Workflow steps invoke package.json scripts / ni; duplicated flags gone.",
    ),
    TaskSpec(
        id="fe-feature-folder",
        scenario="frontend",
        primary_skill="eric-frontend",
        kind="implement",
        oracle="mixed",
        extra_treatments=("wrong-backend-on-frontend",),
        instruction=(
            "Add an invoice list page to this Vite/React app. Data fetching already lives "
            "under src/shared/api. Do not introduce a new design system."
        ),
        oracle_spec=(
            "Feature folder owns the page; request/query keys stay in the existing API layer; "
            "no string-concat className; no hard-coded i18n strings if i18n config exists."
        ),
    ),
    TaskSpec(
        id="fe-query-layer",
        scenario="frontend",
        primary_skill="eric-frontend",
        kind="bugfix",
        oracle="hidden_tests",
        instruction=(
            "AccountPage fetches with useEffect + fetch even though src/shared/api already "
            "has query options. Fix data loading."
        ),
        oracle_spec="useEffect fetch gone; TanStack Query uses the existing request helper; cache invalidation stays in the API module.",
    ),
    TaskSpec(
        id="fe-classname",
        scenario="frontend",
        primary_skill="eric-frontend",
        kind="refactor",
        oracle="static_checks",
        instruction=(
            "Button.tsx concatenates class names with template strings. The repo already "
            "depends on clsx. Clean this up."
        ),
        oracle_spec="No string concat of className; uses clsx/twMerge already in the repo.",
    ),
    TaskSpec(
        id="re-no-usememo",
        scenario="react",
        primary_skill="eric-react",
        kind="implement",
        oracle="static_checks",
        extra_treatments=("overload-react-visual-ci",),
        instruction=(
            "Build FilterBar as a React function component. The repo uses React Compiler. "
            "Props include value, onChange, and children."
        ),
        oracle_spec=(
            "Uses type Props + FC; no React namespace; no useMemo/useCallback; native props "
            "spread if it wraps a DOM node."
        ),
    ),
    TaskSpec(
        id="re-effect-fetch",
        scenario="react",
        primary_skill="eric-react",
        kind="bugfix",
        oracle="hidden_tests",
        instruction=(
            "UserCard loads a user in useEffect. The app already has TanStack Query. Fix it."
        ),
        oracle_spec="No data-fetching useEffect; query hook used; local UI state stays in the component.",
    ),
    TaskSpec(
        id="re-provider-scope",
        scenario="react",
        primary_skill="eric-react",
        kind="refactor",
        oracle="static_checks",
        instruction=(
            "App.tsx nests QueryClient, Theme, Auth, and a feature store provider. Move "
            "app-level providers to the repo's conventional file. Keep the feature store "
            "near its feature."
        ),
        oracle_spec="src/providers.tsx (or existing equivalent) owns app providers; feature store is not global.",
    ),
    TaskSpec(
        id="ui-disclosure",
        scenario="ui",
        primary_skill="eric-ui",
        kind="implement",
        oracle="rubric_blind",
        extra_treatments=("contrast-design",),
        instruction=(
            "Build a job-run summary for a non-engineer user. The API returns status, "
            "durationMs, internalTaskId, workerHost, retryCount, and errorCode. Show only "
            "what helps the user decide the next action."
        ),
        oracle_spec=(
            "Blind rubric: hide internalTaskId/workerHost; translate status into user "
            "language; one next action. Extra metadata without user value fails."
        ),
    ),
    TaskSpec(
        id="ui-privacy",
        scenario="ui",
        primary_skill="eric-ui",
        kind="bugfix",
        oracle="mixed",
        instruction=(
            "The support panel dumps the whole user record, including email hashes and "
            "session tokens, into the DOM. Fix disclosure."
        ),
        oracle_spec="Tokens/hashes absent from DOM and copy; authorized fields only; hidden tests grep the render output.",
    ),
    TaskSpec(
        id="ui-copy-status",
        scenario="ui",
        primary_skill="eric-ui",
        kind="implement",
        oracle="rubric_blind",
        instruction=(
            "Add copy for a payment that can be processing, paid, failed, or refunded. "
            "Do not expose raw enum names or extra charts."
        ),
        oracle_spec="Blind rubric: user-facing outcomes, no dashboard of unused fields, no internal enum leakage.",
    ),
    TaskSpec(
        id="ds-landing-hero",
        scenario="design",
        primary_skill="eric-design",
        kind="implement",
        oracle="rubric_blind",
        extra_treatments=("contrast-ui",),
        instruction=(
            "Create a single-file landing hero in landing.html. The user already chose the "
            "Craft direction. This is a marketing landing page, not the app."
        ),
        oracle_spec=(
            "Blind visual rubric + screenshot: no purple-default slop, no emoji icons, "
            "tokens not ad-hoc hex, heading uses text-wrap balance. Style-menu step must be skipped."
        ),
    ),
    TaskSpec(
        id="ds-anti-slop",
        scenario="design",
        primary_skill="eric-design",
        kind="bugfix",
        oracle="rubric_blind",
        instruction=(
            "index.html is a generic purple gradient landing with blob decorations and "
            "emoji icons. Make it match the existing tokens in tokens.css."
        ),
        oracle_spec="No gradient blobs, no emoji-as-icon, no extra font families, uses tokens.css.",
    ),
    TaskSpec(
        id="ds-style-menu",
        scenario="design",
        primary_skill="eric-design",
        kind="implement",
        oracle="rubric_blind",
        instruction=(
            "The user asked for a landing visual direction but named no style. Do not "
            "silently pick one. Produce comparable previews and stop."
        ),
        oracle_spec=(
            "2–5 standalone HTML previews, not full pages; a short note asking the user to "
            "pick; no single committed 'final' landing. Blind rubric flags premature lock-in."
        ),
    ),
    TaskSpec(
        id="e2e-smoke-critical",
        scenario="e2e",
        primary_skill="eric-e2e-testing",
        kind="test",
        oracle="hidden_tests",
        extra_treatments=("wrong-unit-on-e2e",),
        agent_timeout_sec=E2E_AGENT_TIMEOUT_SEC,
        instruction=(
            "The app's critical flow is: open /, sign in with fixture user, reach /inbox. "
            "Add a real-browser smoke that proves this. Prefer agent-browser if present."
        ),
        oracle_spec=(
            "A browser smoke exists (not curl/HTTP 200); screenshot artifact required; no "
            "broad click-tour. Hidden test checks the artifact path and that Playwright is "
            "not added when agent-browser is available."
        ),
    ),
    TaskSpec(
        id="e2e-screenshot-repro",
        scenario="e2e",
        primary_skill="eric-e2e-testing",
        kind="test",
        oracle="mixed",
        agent_timeout_sec=E2E_AGENT_TIMEOUT_SEC,
        instruction=(
            "The settings page overflows on a 390px viewport. Reproduce it with screenshots "
            "at ~1280 and ~390 and fix the overflow."
        ),
        oracle_spec="Both screenshots exist; mobile capture shows no horizontal overflow after the fix; HTTP 200 is not accepted as proof.",
    ),
    TaskSpec(
        id="e2e-not-unit",
        scenario="e2e",
        primary_skill="eric-e2e-testing",
        kind="test",
        oracle="rubric_blind",
        instruction=(
            "Someone asked for an end-to-end browser test of clamp(n, min, max). Decide "
            "the right check and implement only that."
        ),
        oracle_spec="Blind rubric: must refuse E2E; a unit test is enough. Adding Playwright/agent-browser here is a miss.",
    ),
    TaskSpec(
        id="dt-ipc-boundary",
        scenario="desktop",
        primary_skill="eric-desktop",
        kind="implement",
        oracle="hidden_tests",
        extra_treatments=("overload-desktop-visual",),
        instruction=(
            "This Electron app currently reads files from the renderer with Node fs. Add "
            "an open-document path that uses the existing IPC/router and treats local data "
            "as server state in the renderer."
        ),
        oracle_spec="Renderer has no fs/path imports; IPC method is typed; Query used for the loaded document.",
    ),
    TaskSpec(
        id="dt-packaged-path",
        scenario="desktop",
        primary_skill="eric-desktop",
        kind="bugfix",
        oracle="hidden_tests",
        instruction=(
            "Asset loading uses path.join(__dirname, 'static/logo.png'), which works in "
            "dev and breaks when packaged. Fix both runtimes."
        ),
        oracle_spec="Hidden tests simulate packaged extraResources/app.asar paths; dev path still works; no project-tree user data.",
    ),
    TaskSpec(
        id="dt-off-ui-thread",
        scenario="desktop",
        primary_skill="eric-desktop",
        kind="refactor",
        oracle="static_checks",
        instruction=(
            "zipProject() runs a synchronous zip on the renderer thread during export. "
            "Move native/blocking work off the UI thread."
        ),
        oracle_spec="No sync zip in renderer; work is main/utility process or worker; UI remains responsive in the stub clock.",
    ),
    TaskSpec(
        id="dt-electron-webview",
        scenario="desktop",
        primary_skill="eric-desktop",
        kind="implement",
        oracle="mixed",
        instruction=(
            "Add a second Electron BrowserWindow for a preview surface. External links "
            "must open in the system browser. Navigation in the preview WebView must be "
            "explicitly allowlisted."
        ),
        oracle_spec="Two renderer surfaces; setWindowOpenHandler/shell.openExternal for http(s); allowlist present; not treated as 'just a wrapper'.",
    ),
    TaskSpec(
        id="dt-tauri-contract",
        scenario="desktop",
        primary_skill="eric-desktop",
        kind="implement",
        oracle="static_checks",
        instruction=(
            "This Tauri v2 app has a Rust command `list_notes` with an ad-hoc frontend "
            "string payload. Use generated contracts instead of hand-rolled types."
        ),
        oracle_spec="Frontend command types come from the generated contract path the repo already has (or ts-rs/tauri-typegen if that is the repo tool); no duplicate DTO.",
    ),
    TaskSpec(
        id="gr-fuzzy-terms",
        scenario="grill",
        primary_skill="eric-grill",
        kind="plan",
        oracle="rubric_blind",
        agent_timeout_sec=REVIEW_AGENT_TIMEOUT_SEC,
        instruction=(
            "We need to 'delete an account' when a customer leaves. The codebase has User, "
            "WorkspaceMember, and BillingAccount. Grill the plan before anyone implements. "
            "Ask one question at a time if you must; otherwise write the shared understanding."
        ),
        oracle_spec=(
            "Blind rubric gold: must split User vs BillingAccount vs membership; must not "
            "treat 'account' as one thing; must not start coding; recommended term proposed."
        ),
    ),
    TaskSpec(
        id="gr-context-boundary",
        scenario="grill",
        primary_skill="eric-grill",
        kind="plan",
        oracle="rubric_blind",
        agent_timeout_sec=REVIEW_AGENT_TIMEOUT_SEC,
        instruction=(
            "Add 'cancel' to the ordering API. Some people mean cancel the unpaid order; "
            "others mean refund a paid invoice. CONTEXT-MAP.md exists. Challenge the plan."
        ),
        oracle_spec="Must use map language (Order vs Invoice); flag cross-context cancel; no implementation.",
    ),
    TaskSpec(
        id="gr-adr-worthy",
        scenario="grill",
        primary_skill="eric-grill",
        kind="plan",
        oracle="rubric_blind",
        agent_timeout_sec=REVIEW_AGENT_TIMEOUT_SEC,
        instruction=(
            "A teammate wants to switch the app from SQLite to Postgres 'while we are here' "
            "during a small filter feature. Grill whether this needs an ADR and what to implement now."
        ),
        oracle_spec="Must separate the filter feature from the DB swap; DB swap is ADR-worthy; do not implement the migration in this task.",
    ),
    TaskSpec(
        id="rv-backend-diff",
        scenario="review",
        primary_skill="eric-review",
        kind="review",
        oracle="rubric_blind",
        extra_treatments=("wrong-javascript-on-review",),
        agent_timeout_sec=REVIEW_AGENT_TIMEOUT_SEC,
        instruction=(
            "Review the local diff in ./diff.patch (already applied in the tree). Write "
            "findings first, ordered by severity, with file references. Do not rewrite the "
            "code. Do not use GitHub."
        ),
        oracle_spec=(
            "Gold bugs: transport bypasses service; stringly error in reusable code; missing "
            "focused test. False positives: asking for useMemo, extra runtime validation of "
            "typed internals. Score TP/FP/FN against the gold list."
        ),
    ),
    TaskSpec(
        id="rv-frontend-diff",
        scenario="review",
        primary_skill="eric-review",
        kind="review",
        oracle="rubric_blind",
        realistic_treatment="realistic-review-frontend",
        agent_timeout_sec=REVIEW_AGENT_TIMEOUT_SEC,
        instruction=(
            "Review the local frontend diff in the tree. Findings first, with file/line. "
            "No GitHub. No rewrite unless a finding requires a one-line illustration."
        ),
        oracle_spec=(
            "Gold: useEffect fetch, className concat, leaked internal id in the UI. "
            "Do not ding missing useMemo. UI disclosure finding required."
        ),
    ),
    TaskSpec(
        id="rv-desktop-diff",
        scenario="review",
        primary_skill="eric-review",
        kind="review",
        oracle="rubric_blind",
        realistic_treatment="realistic-review-desktop",
        agent_timeout_sec=REVIEW_AGENT_TIMEOUT_SEC,
        instruction=(
            "Review the local Electron/Tauri diff. Findings first. Ignore GitHub review UI."
        ),
        oracle_spec="Gold: renderer fs access, blocking UI-thread zip, missing packaged-path handling. FP: asking to wrap Electron as a browser-only shell.",
    ),
)


STAGE7_RUBRIC_AXES = (
    {"id": "correctness", "scale": "pass/fail", "prompt": "Hidden tests and stated oracle passed?"},
    {"id": "hidden_tests", "scale": "pass/fail", "prompt": "Hidden tests passed? Infra errors are not model failure."},
    {"id": "static_checks", "scale": "pass/fail", "prompt": "Format/lint/typecheck/compile of the touched path passed?"},
    {"id": "diff_quality", "scale": "1-5", "prompt": "Is the diff local, named honestly, and free of drive-by edits?"},
    {"id": "overengineering", "scale": "1-5", "prompt": "Did the agent add unneeded abstractions, tools, or files?"},
    {"id": "test_value", "scale": "1-5", "prompt": "Did tests lock a real contract instead of mirroring code or chasing coverage?"},
    {"id": "ui_correctness", "scale": "1-5", "prompt": "Does the UI disclose the right information and hide internals?"},
    {"id": "visual_quality", "scale": "1-5", "prompt": "Visual craft only: tokens, anti-slop, landing vs app. Ignore usefulness."},
    {"id": "review_tp", "scale": "count", "prompt": "True-positive findings vs the gold list."},
    {"id": "review_fp", "scale": "count", "prompt": "False-positive findings vs the gold list."},
    {"id": "review_fn", "scale": "count", "prompt": "Missed gold findings."},
    {"id": "cost_usd", "scale": "usd", "prompt": "Trial USD cost from the agent metrics."},
    {"id": "duration_sec", "scale": "seconds", "prompt": "Wall-clock duration."},
)


@dataclass
class ScreenPlan:
    stage: StageId
    name: str
    tasks: list[TaskSpec]
    treatments: list[Treatment]
    cells: list[dict[str, str]]
    pairs: list[list[str]]
    max_trials: int
    budget_usd: float
    n_trials: int
    estimated_usd: float
    max_wall_hours: float


def _task_by_id() -> dict[str, TaskSpec]:
    return {task.id: task for task in TASKS}


def tasks_for_stage(stage: StageId) -> list[TaskSpec]:
    return [task for task in TASKS if task.stage == stage]


def treatments_for_stage(stage: StageId) -> list[Treatment]:
    names: list[str] = []
    for task in tasks_for_stage(stage):
        for name in task.treatment_names:
            if name not in names:
                names.append(name)
    missing = [name for name in names if name not in TREATMENTS]
    if missing:
        raise KeyError(f"unknown treatments: {missing}")
    return [TREATMENTS[name] for name in names]


def cells_for_stage(stage: StageId) -> list[dict[str, str]]:
    cells: list[dict[str, str]] = []
    for task in tasks_for_stage(stage):
        for name in task.treatment_names:
            cells.append(
                {
                    "agent": AGENT_NAME,
                    "model": MODEL_SNAPSHOT,
                    "treatment": name,
                    "task": task.id,
                }
            )
    return cells


def pairs_for_stage(stage: StageId) -> list[list[str]]:
    present = {item.name for item in treatments_for_stage(stage)}
    pairs: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for task in tasks_for_stage(stage):
        candidates = [
            ["baseline", task.single_name],
            ["baseline", task.realistic_name],
            [task.single_name, task.realistic_name],
        ]
        for extra in task.extra_treatments:
            kind = TREATMENTS[extra].kind
            if kind in {"overload", "wrong", "contrast"}:
                candidates.append(["baseline", extra])
        for left, right in candidates:
            if left in present and right in present and left != right:
                key = (left, right)
                if key not in seen:
                    seen.add(key)
                    pairs.append([left, right])
    return pairs


def _n_concurrent_wall_hours(n_trials: int, timeout_sec: int) -> float:
    waves = (n_trials + N_CONCURRENT - 1) // N_CONCURRENT
    return round(waves * timeout_sec / 3600, 2)


def screen_plan(stage: StageId) -> ScreenPlan:
    tasks = tasks_for_stage(stage)
    treatments = treatments_for_stage(stage)
    cells = cells_for_stage(stage)
    # expand() counts n_cells * n_task_units. Harbor also cartesians agents
    # against the job task list. Stage 7 therefore uses a 1-unit anchor task
    # and binds the real path on each cell via kwargs.asb_task so dry-run
    # trial counts equal the paired (task, treatment) matrix. Stage 8 must
    # expand those kwargs into per-task Harbor jobs before any billed run.
    n_pairs = len(cells)
    max_trials = n_pairs + 8
    estimated = n_pairs * USD_PER_TRIAL
    budget = round(estimated * 1.25, 2)
    timeout = max(task.agent_timeout_sec for task in tasks)
    return ScreenPlan(
        stage=stage,
        name=f"stage{stage.lower()}-screen",
        tasks=tasks,
        treatments=treatments,
        cells=cells,
        pairs=pairs_for_stage(stage),
        max_trials=max_trials,
        budget_usd=budget,
        n_trials=n_pairs,
        estimated_usd=estimated,
        max_wall_hours=_n_concurrent_wall_hours(n_pairs, timeout),
    )


def confirm_placeholder(stage: StageId) -> dict[str, Any]:
    """Stage 9 template: baseline + 1 single + 1 realistic + 1 risk, 4 tasks, repeat 3."""
    plan = screen_plan(stage)
    n_treatments = 4
    n_tasks = min(4, len(plan.tasks))
    n_trials = n_treatments * n_tasks * 3
    return {
        "stage": stage,
        "repeat": 3,
        "n_treatments_placeholder": n_treatments,
        "n_tasks_placeholder": n_tasks,
        "n_trials": n_trials,
        "estimated_usd": n_trials * USD_PER_TRIAL,
        "max_wall_hours": _n_concurrent_wall_hours(
            n_trials, max(task.agent_timeout_sec for task in plan.tasks)
        ),
        "selection_rule": (
            "After screening: keep baseline, best single, best realistic, "
            "and every pre-registered overload/wrong/contrast with a large "
            "effect or harm. Do not rank across scenarios."
        ),
    }


def freeze_skills(root: Path) -> list[dict[str, str]]:
    rows = []
    for name in INCLUDED_SKILLS:
        path = root / SKILL_ROOT / name
        rows.append(
            {
                "name": name,
                "path": skill_path(name),
                "digest": sha256_tree(path),
                "source_commit": ERIC_WAY_COMMIT,
            }
        )
    return rows


def coverage_rows() -> list[dict[str, str]]:
    rows = []
    for task in TASKS:
        for name in task.treatment_names:
            treatment = TREATMENTS[name]
            rows.append(
                {
                    "stage": task.stage,
                    "scenario": task.scenario,
                    "task": task.id,
                    "kind": task.kind,
                    "primary_skill": task.primary_skill,
                    "treatment": name,
                    "treatment_kind": treatment.kind,
                    "skills": "+".join(treatment.skills) or "none",
                    "oracle": task.oracle,
                }
            )
    return rows


def independent_controls() -> list[dict[str, str]]:
    rows = []
    for skill in INCLUDED_SKILLS:
        tasks = [task for task in TASKS if task.primary_skill == skill]
        single = f"single-{skill.removeprefix('eric-')}"
        rows.append(
            {
                "skill": skill,
                "n_tasks": str(len(tasks)),
                "task_ids": ",".join(task.id for task in tasks),
                "control": f"baseline vs {single} on those tasks",
            }
        )
    return rows


def experiment_spec(stage: StageId, root: Path) -> dict[str, Any]:
    plan = screen_plan(stage)
    cells = []
    for item in plan.cells:
        task_id = item["task"]
        cells.append(
            {
                "agent": AGENT_NAME,
                "model": MODEL_SNAPSHOT,
                "treatment": item["treatment"],
                "kwargs": {"asb_task": f"tasks/stage7/{task_id}"},
            }
        )
    return {
        "schema_version": 1,
        "name": plan.name,
        "track": TRACK,
        "seed": SEED,
        "repeat": 1,
        "max_trials": plan.max_trials,
        "n_concurrent": N_CONCURRENT,
        "max_retries": MAX_RETRIES,
        "timeout_multiplier": 1.0,
        "usd_per_trial": USD_PER_TRIAL,
        "budget_usd": plan.budget_usd,
        "policy": {
            "cache_scope": "image",
            "durable_artifacts": True,
            "retention_days": 30,
            "secret_allowlist": ["OPENAI_API_KEY"],
        },
        "environment": {
            "type": "docker",
            "force_build": False,
            "delete": True,
        },
        "models": [MODEL_SNAPSHOT],
        "agents": [
            {
                "name": AGENT_NAME,
                "kwargs": {
                    "version": CODEX_CLI_VERSION,
                    "reasoning_effort": REASONING_EFFORT,
                    "web_search": WEB_SEARCH,
                    "prompt_template_path": PROMPT_PATH,
                },
            }
        ],
        "prompts": {PROMPT_NAME: PROMPT_PATH},
        "treatments": [
            {
                "name": treatment.name,
                "prompt": PROMPT_NAME,
                "skills": treatment.paths,
                "skill_bundle": treatment.name,
            }
            for treatment in plan.treatments
        ],
        "pairs": plan.pairs,
        "cells": cells,
        "tasks": ["tasks/stage7/_anchor"],
    }


def manifest(root: Path) -> dict[str, Any]:
    screens = {stage: screen_plan(stage) for stage in ("8A", "8B", "8C", "8D")}
    confirms = {stage: confirm_placeholder(stage) for stage in ("8A", "8B", "8C", "8D")}
    screen_trials = sum(plan.n_trials for plan in screens.values())
    confirm_trials = sum(item["n_trials"] for item in confirms.values())
    prompt = root / PROMPT_PATH
    return {
        "revision": REVISION,
        "track": TRACK,
        "applicability": "Codex-only Track B; no other model or agent in the matrix.",
        "pins": {
            "eric_way_commit": ERIC_WAY_COMMIT,
            "agent_skill_bench_base_commit": BENCH_BASE_COMMIT,
            "harbor_version": HARBOR_VERSION,
            "codex_cli_version": CODEX_CLI_VERSION,
            "model_snapshot": MODEL_SNAPSHOT,
            "reasoning_effort": REASONING_EFFORT,
            "web_search": WEB_SEARCH,
            "system_prompt": PROMPT_PATH,
            "system_prompt_sha256": sha256_tree(prompt) if prompt.exists() else "",
            "network_mode": NETWORK_MODE,
            "docker_image": DOCKER_IMAGE,
            "docker_digest": DOCKER_DIGEST,
            "n_concurrent": N_CONCURRENT,
            "usd_per_trial": USD_PER_TRIAL,
            "agent_timeout_sec": AGENT_TIMEOUT_SEC,
            "verifier_timeout_sec": VERIFIER_TIMEOUT_SEC,
        },
        "included_skills": freeze_skills(root),
        "excluded_skills": EXCLUDED_SKILLS,
        "scenarios": SCENARIOS,
        "n_tasks": len(TASKS),
        "independent_controls": independent_controls(),
        "screening": {
            "repeat": 1,
            "n_trials": screen_trials,
            "estimated_usd": round(screen_trials * USD_PER_TRIAL, 2),
            "budget_usd": round(sum(plan.budget_usd for plan in screens.values()), 2),
            "max_wall_hours_serial": round(sum(plan.max_wall_hours for plan in screens.values()), 2),
            "max_wall_hours_parallel_stages": max(plan.max_wall_hours for plan in screens.values()),
            "by_stage": {
                stage: {
                    "n_tasks": len(plan.tasks),
                    "n_treatments": len(plan.treatments),
                    "n_cells": plan.n_trials,
                    "n_trials": plan.n_trials,
                    "estimated_usd": plan.estimated_usd,
                    "budget_usd": plan.budget_usd,
                    "max_trials": plan.max_trials,
                    "max_wall_hours": plan.max_wall_hours,
                    "issue": STAGE_ISSUES[stage],
                    "config": STAGE_ISSUES[stage]["config"],
                }
                for stage, plan in screens.items()
            },
        },
        "confirm": {
            "repeat": 3,
            "n_trials_placeholder": confirm_trials,
            "estimated_usd": round(confirm_trials * USD_PER_TRIAL, 2),
            "issue": CONFIRM_ISSUE,
            "note": "Do not run until screening finishes and Akara confirms budget.",
            "by_stage": confirms,
        },
        "hard_gates": {
            "do_not_start_without_budget_confirmation": True,
            "usd_per_trial_required": True,
            "max_trials_blocks_explosion": True,
            "budget_usd_blocks_overage": True,
            "single_agent": AGENT_NAME,
            "single_model": MODEL_SNAPSHOT,
        },
        "scoring": {
            "primary": "hidden_tests for execution tasks; blinded human rubric for UI/visual/grill/review",
            "infra_excluded": True,
            "no_composite_total": True,
            "axes": list(STAGE7_RUBRIC_AXES),
        },
    }
