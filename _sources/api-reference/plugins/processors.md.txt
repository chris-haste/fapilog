# Processors

Plugins that transform or filter log entries before they reach sinks.

## Contract

Implement `BaseProcessor.process(entry: dict) -> dict | None` (async). Return a modified entry to continue, or `None` to drop. Errors should be contained.

## Built-in processors

The core pipeline does not ship additional processors by default; processors are reserved for advanced transformations/filters when configured.

## Usage

Processors execute after enrichers/redactors and before queue/sink emission. Ensure they are non-blocking and idempotent.*** End Patch
