# PCAG Core Package

The `pcag` package is the core implementation of the Proof-Carrying Action Gateway (PCAG) system. It houses the microservices, core business logic, communication contracts, and pluggable architectures necessary to build a deterministic safety verification gateway for AI agents.

## Directory Structure

*   `apps/` - The core microservices that make up the PCAG system (Gateway, Safety Cluster, Policy Store, etc.).
*   `core/` - Shared business logic, database models, data transfer objects (Contracts), middleware, and utility functions.
*   `plugins/` - Implementations of specific interfaces for executors, sensors, and simulation backends, enabling easy extension to new physical assets.

## Purpose

The `pcag` package provides a robust, modular, and extensible foundation for evaluating and safely executing AI control commands. It separates concerns between the orchestration of the verification pipeline (`apps`), the underlying mathematical and deterministic logic (`core`), and the physical integration layer (`plugins`).

## Usage

You generally do not interact with the `pcag` package directly. Instead, you deploy the individual microservices within the `apps/` directory and manage them using the provided utility scripts in the `scripts/` directory.

## Related Files

*   `tests/` - The test suite for the `pcag` package components.
*   `config/` - YAML configuration files that dictate how the `pcag` microservices operate and interact.
