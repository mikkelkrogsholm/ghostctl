# Tasks: Ghost CMS Management CLI (ghostctl)

**Input**: Design documents from `/specs/001-build-a-cli/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- Project structure follows plan.md: `ghostctl/` for source, `tests/` for tests
- All source files under `ghostctl/` package
- Test files mirror source structure under `tests/`

## Phase 3.1: Setup
- [X] T001 Create project directory structure: ghostctl/, tests/, .github/workflows/
- [X] T002 Create pyproject.toml with Poetry config for Python 3.11+ and dependencies
- [X] T003 [P] Configure development tools: setup.cfg for mypy --strict, .flake8, pyproject.toml sections for black, isort, ruff
- [X] T004 [P] Create .gitignore with Python patterns, .env exclusions, and IDE folders
- [X] T005 [P] Initialize pre-commit hooks configuration in .pre-commit-config.yaml

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests
- [X] T006 [P] Contract test for Posts API in tests/contract/test_posts_api.py (GET /posts, POST /posts, PUT /posts/{id}, DELETE /posts/{id})
- [X] T007 [P] Contract test for Images API in tests/contract/test_images_api.py (POST /images/upload)
- [X] T008 [P] Contract test for Themes API in tests/contract/test_themes_api.py (GET /themes, POST /themes/upload, PUT /themes/{name}/activate)
- [X] T009 [P] Contract test for Tags API in tests/contract/test_tags_api.py (GET /tags, POST /tags, PUT /tags/{id}, DELETE /tags/{id})

### Integration Tests
- [X] T010 [P] Integration test for configuration profiles in tests/integration/test_config_profiles.py
- [X] T011 [P] Integration test for JWT authentication in tests/integration/test_auth_flow.py
- [X] T012 [P] Integration test for retry mechanism in tests/integration/test_retry_logic.py
- [X] T013 [P] Integration test for output formats in tests/integration/test_output_formats.py
- [X] T014 [P] Integration test for bulk operations in tests/integration/test_bulk_operations.py
- [X] T015 [P] Integration test for dry-run mode in tests/integration/test_dry_run.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Infrastructure Modules
- [X] T016 Create ghostctl/__init__.py with version info
- [X] T017 Implement config.py with Profile model and TOML loading using tomllib
- [X] T018 Implement client.py with GhostClient class, JWT auth via PyJWT, and requests.Session
- [X] T019 Implement utils/auth.py with JWT token generation using PyJWT
- [X] T020 Implement utils/retry.py with exponential backoff and circuit breaker
- [X] T021 Implement render.py with output formatting (table via Rich, JSON, YAML)

### Data Models
- [X] T022 [P] Create models/__init__.py with base model exports
- [X] T023 [P] Implement models/post.py with Post and Page Pydantic models
- [X] T024 [P] Implement models/tag.py with Tag Pydantic model
- [X] T025 [P] Implement models/member.py with Member Pydantic model
- [X] T026 [P] Implement models/image.py with Image Pydantic model
- [X] T027 [P] Implement models/theme.py with Theme Pydantic model
- [X] T028 [P] Implement models/profile.py with Profile configuration model

### CLI Commands (Priority Resources)
- [X] T029 Create app.py with main Typer app and command registration
- [X] T030 Create cmds/__init__.py with command exports
- [X] T031 Implement cmds/posts.py with list, get, create, update, delete, publish commands
- [X] T032 Implement cmds/tags.py with list, get, create, update, delete commands
- [X] T033 Implement cmds/images.py with upload command supporting multipart/form-data
- [X] T034 Implement cmds/themes.py with list, upload, activate, rollback commands
- [X] T035 Implement cmds/config.py with init, validate, list-profiles commands

### Additional Commands (Second Priority)
- [X] T036 [P] Implement cmds/pages.py inheriting from posts.py logic
- [X] T037 [P] Implement cmds/members.py with CRUD and import commands
- [X] T038 [P] Implement cmds/export.py with export all/posts/members commands
- [X] T039 [P] Implement cmds/settings.py with get and update commands

## Phase 3.4: Integration

### API Client Integration
- [X] T040 Connect GhostClient to all command modules via dependency injection
- [X] T041 Implement pagination handling in client.py for list operations
- [X] T042 Add rate limiting awareness with X-RateLimit header parsing
- [X] T043 Implement progress bars using Rich for long operations

### Error Handling
- [X] T044 Create utils/exceptions.py with custom exception classes
- [X] T045 Implement structured error handling with user-friendly messages
- [X] T046 Add debug mode support with --debug flag showing full traces

### Configuration Features
- [X] T047 Implement environment variable override (GHOST_API_URL, GHOST_ADMIN_API_KEY)
- [X] T048 Add profile selection via --profile flag
- [X] T049 Implement secure credential storage warnings and best practices docs

## Phase 3.5: Polish

### Unit Tests
- [X] T050 [P] Unit tests for config.py in tests/unit/test_config.py
- [X] T051 [P] Unit tests for JWT generation in tests/unit/test_auth.py
- [X] T052 [P] Unit tests for retry logic in tests/unit/test_retry.py
- [X] T053 [P] Unit tests for output rendering in tests/unit/test_render.py
- [X] T054 [P] Unit tests for model validation in tests/unit/test_models.py

### Documentation
- [X] T055 [P] Create README.md with installation, quickstart, and examples
- [X] T056 [P] Generate CLI documentation from Typer help text
- [X] T057 [P] Create SECURITY.md with credential handling best practices

### CI/CD
- [X] T058 Create .github/workflows/ci.yml with lint, test, coverage steps
- [X] T059 Create Dockerfile with multi-stage build for slim runtime
- [X] T060 Create docker-compose.yml example with Ghost + ghostctl

### Performance & Security
- [ ] T061 Run performance benchmarks for bulk operations
- [ ] T062 Run security audit with bandit
- [ ] T063 Verify mypy strict mode passes on all modules

## Dependencies
- Setup tasks (T001-T005) must complete first
- Tests (T006-T015) before implementation (T016-T039)
- Infrastructure (T016-T021) before commands (T029-T039)
- Models (T022-T028) before commands that use them
- Core implementation before integration (T040-T049)
- Everything before polish phase (T050-T063)

## Parallel Execution Examples

### Launch contract tests together (after setup):
```
Task: "Contract test for Posts API in tests/contract/test_posts_api.py"
Task: "Contract test for Images API in tests/contract/test_images_api.py"
Task: "Contract test for Themes API in tests/contract/test_themes_api.py"
Task: "Contract test for Tags API in tests/contract/test_tags_api.py"
```

### Launch integration tests together:
```
Task: "Integration test for configuration profiles in tests/integration/test_config_profiles.py"
Task: "Integration test for JWT authentication in tests/integration/test_auth_flow.py"
Task: "Integration test for retry mechanism in tests/integration/test_retry_logic.py"
Task: "Integration test for output formats in tests/integration/test_output_formats.py"
```

### Launch model creation together:
```
Task: "Implement models/post.py with Post and Page Pydantic models"
Task: "Implement models/tag.py with Tag Pydantic model"
Task: "Implement models/member.py with Member Pydantic model"
Task: "Implement models/image.py with Image Pydantic model"
```

### Launch unit tests together:
```
Task: "Unit tests for config.py in tests/unit/test_config.py"
Task: "Unit tests for JWT generation in tests/unit/test_auth.py"
Task: "Unit tests for retry logic in tests/unit/test_retry.py"
Task: "Unit tests for output rendering in tests/unit/test_render.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing features (TDD)
- Commit after completing each task or task group
- Use type hints everywhere for mypy strict mode
- Follow constitution principles throughout

## Validation Checklist
✓ All 4 API contracts have corresponding test tasks
✓ All 11 entity types have model tasks (core ones priority)
✓ All priority endpoints have implementation tasks
✓ Tests come before implementation (TDD)
✓ Parallel tasks are truly independent files
✓ Each task specifies exact file path