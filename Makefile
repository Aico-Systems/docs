.PHONY: help dev build install export-connectors

# Use fnm to ensure correct Node version (Mintlify requires Node < 25)
FNM_SETUP = eval "$$(fnm env)" && fnm use 22

help:
	@echo "AICO Documentation - Available Commands:"
	@echo ""
	@echo "  make install           - Install dependencies"
	@echo "  make dev               - Start Mintlify dev server"
	@echo "  make build             - Build documentation for deployment"
	@echo "  make export-connectors - Export OpenAPI specs from connector services"

install:
	@$(FNM_SETUP) && npm install

dev:
	@$(FNM_SETUP) && npx mintlify dev

build:
	@$(FNM_SETUP) && npx mintlify build

export-connectors:
	@echo "Exporting OpenAPI specs from connector services..."
	@cd ../connectors && python3 scripts/export_openapi.py
