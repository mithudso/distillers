.PHONY: check test docs docs-check

check:
	python3 -m py_compile distill_offline.py scripts/*.py
	python3 -m unittest discover -s tests -v
	python3 scripts/generate_repo_docs.py --check

test:
	python3 -m unittest discover -s tests -v

docs:
	python3 scripts/generate_repo_docs.py

docs-check:
	python3 scripts/generate_repo_docs.py --check
