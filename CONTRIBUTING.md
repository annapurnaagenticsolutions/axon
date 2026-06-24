# Contributing to AXON

Thank you for your interest in contributing to AXON! This document outlines the process for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/annapurna-agentics/axon.git`
3. Install in development mode: `python -m pip install -e ".[dev]"`
4. Run tests: `pytest`

## Development Workflow

1. Create a branch for your feature or fix: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests: `pytest`
4. Run syntax checks on examples: `axon syntax examples/hello.ax && axon validate examples/hello.ax`
5. Commit with a clear message describing what and why
6. Push to your fork and open a Pull Request

## Pull Request Guidelines

- Include a clear description of what your PR does and why
- Add or update tests for any new functionality
- Ensure all existing tests pass: `pytest`
- If adding a new `.ax` example, ensure it passes `axon syntax`, `axon validate`, and `axon smoke`
- Follow the existing code style

## Areas Where We Need Help

- **Language design feedback** — try AXON on real problems and tell us what's missing
- **New examples** — real-world `.ax` files that demonstrate AXON's capabilities
- **TypeScript compilation target** — improve the TS codegen quality
- **VS Code extension** — help improve the LSP and syntax highlighting
- **Documentation** — tutorials, guides, blog posts
- **Bug reports** — file issues for anything that doesn't work as expected

## Reporting Issues

When filing an issue, please include:
- AXON version: `axon version`
- Python version: `python --version`
- OS and platform
- Minimal `.ax` file that reproduces the issue
- Expected behavior vs actual behavior
- Full error output

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).
