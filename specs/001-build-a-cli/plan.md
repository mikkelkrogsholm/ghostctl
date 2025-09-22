
# Implementation Plan: Ghost CMS Management CLI (ghostctl)

**Branch**: `001-build-a-cli` | **Date**: 2025-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-build-a-cli/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Building a production-quality command-line interface tool called `ghostctl` to fully manage Ghost CMS blogs via the Admin API. The CLI will support all major Ghost resources (posts, pages, tags, members, themes, etc.) with comprehensive CRUD operations, bulk import/export capabilities, multiple configuration profiles, flexible output formats (table/JSON/YAML), and enterprise features like dry-run mode and idempotent operations. The implementation will use Python 3.11+ with Typer for CLI framework, Requests for HTTP, PyJWT for authentication, Pydantic for validation, and Rich for formatted output.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer (CLI), Requests (HTTP), PyJWT (Auth), Pydantic (Models), Rich (Tables), tomllib (Config), PyYAML (Output)
**Storage**: TOML configuration file (~/.ghostctl.toml) for profiles
**Testing**: pytest with pytest-mock for unit tests, pytest-integration for API tests
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows)
**Project Type**: single (CLI application)
**Performance Goals**: <500ms for single operations, <10s for bulk operations of 100 items
**Constraints**: Respect Ghost API rate limits (100 requests per minute), secure credential storage
**Scale/Scope**: Handle blogs with 10k+ posts/members, support 11 resource types, 45+ functional requirements

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Core Principle Compliance
- [x] **Reliability**: All operations idempotent, fault-tolerant with recovery paths
- [x] **CLI UX**: Clear feedback, progress indicators, actionable errors, --help with examples
- [x] **Type Safety**: Python 3.11+ with comprehensive type hints, mypy strict mode
- [x] **API Testing**: Exhaustive tests for all Ghost API interactions (mocks + integration)
- [x] **Security**: API keys secure, platform-appropriate credential storage documented
- [x] **Zero Magic**: All behaviors explicit, no hidden side effects, --debug transparency
- [x] **Documentation**: 3+ examples per command (basic, advanced, error recovery)
- [x] **Fast CI**: <5 min pipeline, parallel tests, caching, affected-only test runs

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
ghostctl/
├── __init__.py
├── app.py              # Typer app assembly
├── config.py           # Profile management
├── client.py           # JWT auth + HTTP client + retries
├── render.py           # Output formatting (table/json/yaml)
├── models/
│   ├── __init__.py
│   ├── post.py        # Pydantic models for posts/pages
│   ├── member.py      # Pydantic models for members
│   ├── tag.py         # Pydantic models for tags
│   └── ...            # Other resource models
├── cmds/
│   ├── __init__.py
│   ├── posts.py       # Post/Page commands
│   ├── tags.py        # Tag commands
│   ├── members.py     # Member commands
│   ├── newsletters.py # Newsletter commands
│   ├── tiers.py       # Tier commands
│   ├── offers.py      # Offer commands
│   ├── webhooks.py    # Webhook commands
│   ├── images.py      # Image upload commands
│   ├── themes.py      # Theme management commands
│   ├── settings.py    # Settings commands
│   └── export.py      # Export/Import commands
└── utils/
    ├── __init__.py
    ├── auth.py        # JWT generation
    └── retry.py       # Retry logic with backoff

tests/
├── unit/
├── integration/
└── fixtures/

# Additional project files
pyproject.toml          # Python project configuration
Dockerfile              # Slim runtime container
docker-compose.yml      # Example with Ghost + ghostctl
.github/
└── workflows/
    └── ci.yml          # GitHub Actions for lint+test
```

**Structure Decision**: Custom structure based on user requirements - CLI-focused with command modules

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Focus on priority resources first: posts, images, themes, tags
- Each API contract → contract test tasks [P]
- Each entity model → Pydantic model creation task [P]
- Each command group → CLI command implementation tasks
- Integration tests for critical user journeys

**Task Categories**:
1. **Setup** (3-4 tasks): Project init, dependencies, linting config
2. **Core Infrastructure** (5-6 tasks): Client, auth, config, render modules
3. **Contract Tests** (8-10 tasks): Test files for each API endpoint [P]
4. **Models** (8-10 tasks): Pydantic models for resources [P]
5. **Commands** (15-20 tasks): CLI commands for priority resources
6. **Integration** (5-6 tasks): End-to-end tests, Docker, CI/CD
7. **Polish** (3-4 tasks): Documentation, performance tests, security audit

**Ordering Strategy**:
- TDD order: Write failing tests before implementation
- Infrastructure before features: client.py before commands
- Models before commands that use them
- Priority resources first (posts, images, themes, tags)
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 50-60 numbered, ordered tasks in tasks.md covering priority features

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none required)

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
