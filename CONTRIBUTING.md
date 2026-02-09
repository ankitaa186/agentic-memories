# Contributing to Agentic Memories

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/agentic-memories.git
   cd agentic-memories
   ```
3. **Set up** the development environment:
   ```bash
   make install
   cp env.example .env
   # Edit .env with your configuration
   ```
4. **Create a branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running Tests

```bash
make test-fast      # Unit tests only (fastest)
make test           # Unit + integration tests
make test-e2e       # End-to-end tests (requires Docker)
make test-coverage  # Tests with coverage report
```

### Code Quality

```bash
make lint           # Check linting with ruff
make lint FIX=1     # Auto-fix lint issues
make format         # Check formatting
make format FIX=1   # Auto-fix formatting
```

### Running Locally

```bash
make start          # Start Docker containers
make stop           # Stop Docker containers
make docker-logs    # View container logs
```

## Submitting Changes

1. **Ensure tests pass**: Run `make test` before submitting
2. **Ensure code quality**: Run `make lint` and `make format`
3. **Write clear commit messages**: Describe _what_ changed and _why_
4. **Push** your branch and open a **Pull Request** against `main`
5. **Describe your changes** in the PR description, including:
   - What the change does
   - How to test it
   - Any breaking changes

## Areas We Need Help

- **Testing**: LLM evaluation, performance benchmarks
- **Documentation**: Tutorials, examples, translations
- **UI/UX**: Web interface improvements
- **Cognitive Features**: Consolidation, forgetting, prediction algorithms
- **Security**: Encryption, consent management, auditing
- **Internationalization**: Multi-language support

## Code Style

- Python: We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Follow existing patterns in the codebase
- Keep changes focused — one feature or fix per PR

## Reporting Bugs

Open a [GitHub Issue](https://github.com/ankitaa186/agentic-memories/issues) with:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, Docker version)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
