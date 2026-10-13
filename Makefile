.PHONY: install run test clean

install:
	pip install -r requirements.txt

run:
	python -m nemt_claims.run_pipeline

test:
	python -m pytest -q

clean:
	rm -rf data reports/*.png reports/*.md
