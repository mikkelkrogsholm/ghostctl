# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
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
- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup
- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize Python 3.11+ project with typed dependencies
- [ ] T003 [P] Configure mypy (strict), black, isort, ruff, bandit

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T004 [P] Contract test for Ghost API endpoint in tests/contract/test_[endpoint].py
- [ ] T005 [P] Mock test for API error handling (rate limits, network failures)
- [ ] T006 [P] Integration test for idempotent operations
- [ ] T007 [P] Security test for credential handling (no leaks in logs/errors)

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T008 [P] Typed data models with Pydantic/dataclasses in src/models/
- [ ] T009 [P] Service layer with dependency injection in src/services/
- [ ] T010 [P] CLI commands with --help and examples in src/cli/
- [ ] T011 Idempotent bulk operations handler
- [ ] T012 Secure credential manager (keychain integration)
- [ ] T013 Input validation with type checking
- [ ] T014 Structured error handling with recovery paths

## Phase 3.4: Integration
- [ ] T015 Ghost Admin API client with retry logic
- [ ] T016 Circuit breaker for API calls
- [ ] T017 Structured logging with correlation IDs
- [ ] T018 Progress indicators for bulk operations

## Phase 3.5: Polish
- [ ] T019 [P] Unit tests achieving 80%+ coverage
- [ ] T020 Performance benchmarks for bulk operations
- [ ] T021 [P] Command documentation with 3+ examples each
- [ ] T022 CI pipeline optimization (<5 min runs)
- [ ] T023 Security audit with bandit

## Dependencies
- Tests (T004-T007) before implementation (T008-T014)
- T008 blocks T009, T015
- T016 blocks T018
- Implementation before polish (T019-T023)

## Parallel Example
```
# Launch T004-T007 together:
Task: "Contract test POST /api/users in tests/contract/test_users_post.py"
Task: "Contract test GET /api/users/{id} in tests/contract/test_users_get.py"
Task: "Integration test registration in tests/integration/test_registration.py"
Task: "Integration test auth in tests/integration/test_auth.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - Each contract file → contract test task [P]
   - Each endpoint → implementation task
   
2. **From Data Model**:
   - Each entity → model creation task [P]
   - Relationships → service layer tasks
   
3. **From User Stories**:
   - Each story → integration test [P]
   - Quickstart scenarios → validation tasks

4. **Ordering**:
   - Setup → Tests → Models → Services → Endpoints → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [ ] All contracts have corresponding tests
- [ ] All entities have model tasks
- [ ] All tests come before implementation
- [ ] Parallel tasks truly independent
- [ ] Each task specifies exact file path
- [ ] No task modifies same file as another [P] task