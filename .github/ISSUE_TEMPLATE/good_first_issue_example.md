---
name: Good First Issue — New Example
about: Add a new .ax example file
title: "[good first issue] Add example: "
labels: good first issue, documentation
---

## What to build

Create a new `.ax` file in the `examples/` directory that demonstrates a specific AXON capability.

## Suggested examples (pick one)

- [ ] **Sentiment analysis agent** — an agent that classifies text sentiment using a tool
- [ ] **Email summarizer** — an agent that summarizes emails with a RAG knowledge base
- [ ] **Code reviewer** — an agent that reviews code snippets and suggests improvements
- [ ] **Meeting scheduler** — a flow that coordinates between multiple agents to find a meeting time
- [ ] **Data validator** — a tool + agent combo that validates data against a schema
- [ ] **Translation pipeline** — a multi-agent flow that translates text through intermediate languages

## How to do it

1. Fork the repo and create a branch: `git checkout -b example/your-example-name`
2. Look at existing examples in `examples/` for patterns
3. Write your `.ax` file
4. Validate it: `axon syntax examples/your_example.ax && axon validate examples/your_example.ax`
5. Test it: `axon run examples/your_example.ax --mock`
6. Add a comment at the top explaining what the example demonstrates
7. Open a PR

## Need help?

- Read `examples/hello.ax` for the simplest example
- Read `examples/research_pipeline.ax` for a comprehensive example
- Join our Discord: [link]
- Ask in the issue — we'll help you get started!
