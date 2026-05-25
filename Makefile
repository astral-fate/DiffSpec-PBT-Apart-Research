PYTHON ?= python

.PHONY: help install test eval demo live report clean

help:
	@echo "DiffSpec-PBT targets:"
	@echo "  make install   install package + test extras (editable)"
	@echo "  make test      run pytest suite"
	@echo "  make eval      run 10-task benchmark in fixture mode"
	@echo "  make live      run 10-task benchmark in live LLM mode (needs API keys)"
	@echo "  make demo      show one attack-pair contrast"
	@echo "  make report    build paper/main.pdf (pdflatex + bibtex)"
	@echo "  make clean     remove caches and build artefacts"

install:
	$(PYTHON) -m pip install -e ".[test]"

test:
	$(PYTHON) -m pytest -q

eval:
	$(PYTHON) -m evals.run_evals

live:
	$(PYTHON) -m diffspec.cli run --live

demo:
	$(PYTHON) -m evals.run_evals --task tokenizer_truncate 2>/dev/null || $(PYTHON) -m diffspec.cli run --task tokenizer_truncate

report:
	cd paper && pdflatex -interaction=nonstopmode main.tex
	cd paper && bibtex main || true
	cd paper && pdflatex -interaction=nonstopmode main.tex
	cd paper && pdflatex -interaction=nonstopmode main.tex
	@echo ""
	@echo "PDF written to paper/main.pdf"

clean:
	rm -rf __pycache__ src/diffspec/__pycache__ tests/__pycache__
	rm -rf evals/__pycache__ benchmark/*/__pycache__
	rm -rf .pytest_cache .hypothesis
	rm -f paper/main.aux paper/main.bbl paper/main.blg paper/main.log
	rm -f paper/main.out paper/main.toc paper/main.fdb_latexmk paper/main.fls
	rm -f paper/main.synctex.gz
