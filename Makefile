
SKILL_DIR  := printer
SKILL_NAME := $(notdir $(abspath $(SKILL_DIR)))
VERSION=1.0
SKILL_ZIP_NAME := $(SKILL_NAME).skill_v$(VERSION).zip
TARGET=pi@openclaw.local
CLAUDE_SKILLS_DIR := $(HOME)/.claude/skills

.PHONY: install  lint package clean

install:          ## Install all dependencies (dev + skill)
	(cd $(SKILL_DIR) && uv sync)

 
lint:             ## Check code style
	uv run ruff check $(SKILL_DIR)/scripts

package:          ## Build .skill zip
	rm -f *.skill *.zip
	(cd $(dir $(abspath $(SKILL_DIR))) && \
	 zip -r $(SKILL_ZIP_NAME) $(SKILL_NAME)/ -x *.venv*  -x *.zip  -x "*/__pycache__/*"  -x .pytest_cache -x *.lock -x *.DS_Store -x "*.git*" -x "*.python-version*")
	@echo "Created: $(SKILL_ZIP_NAME)"

clean:            ## Remove build artifacts
	rm -f *.skill *.zip
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
 
	rm -rf $(SKILL_DIR)/.venv  
	rm $(SKILL_DIR)/uv.lock	

deploy:
	scp  ${SKILL_ZIP_NAME} ${TARGET}:/home/pi/downloads
	  
deploy-claude:    ## Unzip skill into ~/.claude/skills/
	mkdir -p $(CLAUDE_SKILLS_DIR)
	rm -rf $(CLAUDE_SKILLS_DIR)/$(SKILL_NAME)
	unzip $(SKILL_ZIP_NAME) -d $(CLAUDE_SKILLS_DIR)
	@echo "Deployed to $(CLAUDE_SKILLS_DIR)/$(SKILL_NAME)"ls

help:             ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'