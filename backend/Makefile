.PHONY: dev gen-client

dev:
	uv run python -m app.main

gen-client:
	uv run python -m scripts.export_openapi
	cd ../frontend && bun run gen-client
