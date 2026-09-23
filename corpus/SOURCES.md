# Corpus sources and attribution

Every document in `projects/*/docs/` is an excerpt of a file from the open-source
project named below, redistributed under that project's license (full text and
copyright notice in `projects/<project>/LICENSE-NOTICE.txt`). Documents of kind
`planted` and `distractor` contain ONE sentence added by the quotegate authors
for the benchmark; the added sentence is recorded in `construction_key.json` and
is not the upstream project's text. Nothing here is endorsed by those projects.

| project | repository | license | facts as of | documents |
|---|---|---|---|---|
| black | https://github.com/psf/black | MIT | `62bcae6485c3` (2026-09-21) | 8 |
| click | https://github.com/pallets/click | BSD-3-Clause | `3cbaa76b6014` (2026-09-21) | 8 |
| flask | https://github.com/pallets/flask | BSD-3-Clause | `d73fa1cdcbd8` (2026-09-08) | 8 |
| httpx | https://github.com/encode/httpx | BSD-3-Clause | `b5addb64f016` (2026-02-23) | 8 |
| pip | https://github.com/pypa/pip | MIT | `892d13b34a20` (2026-09-21) | 8 |
| poetry | https://github.com/python-poetry/poetry | MIT | `94b6e35b9091` (2026-09-20) | 8 |
| pytest | https://github.com/pytest-dev/pytest | MIT | `6a9ba0f02f82` (2026-09-21) | 8 |
| requests | https://github.com/psf/requests | Apache-2.0 | `611c6162cbc4` (2026-09-21) | 8 |

## black

- `black-01-organic.txt` ← `README.md` at `f1d4e742c91d` (21.12b0)
- `black-02-organic.txt` ← `docs/faq.md` at `d038a24ca200` (22.1.0)
- `black-03-planted.txt` ← `docs/usage_and_configuration/the_basics.md` at `62bcae6485c3` (HEAD)
- `black-04-planted.txt` ← `docs/index.md` at `62bcae6485c3` (HEAD)
- `black-05-distractor.txt` ← `README.md` at `62bcae6485c3` (HEAD)
- `black-06-distractor.txt` ← `docs/usage_and_configuration/black_as_a_server.md` at `62bcae6485c3` (HEAD)
- `black-07-clean.txt` ← `docs/guides/using_black_with_other_tools.md` at `62bcae6485c3` (HEAD)
- `black-08-clean.txt` ← `docs/integrations/source_version_control.md` at `62bcae6485c3` (HEAD)

## click

- `click-01-organic.txt` ← `docs/bashcomplete.rst` at `1784558ed7c7` (7.1.2)
- `click-02-organic.txt` ← `docs/utils.rst` at `934813e4d421` (8.1.8)
- `click-03-planted.txt` ← `docs/quickstart.md` at `3cbaa76b6014` (HEAD)
- `click-04-planted.txt` ← `docs/utils.md` at `3cbaa76b6014` (HEAD)
- `click-05-distractor.txt` ← `docs/shell-completion.md` at `3cbaa76b6014` (HEAD)
- `click-06-distractor.txt` ← `docs/faqs.md` at `3cbaa76b6014` (HEAD)
- `click-07-clean.txt` ← `docs/arguments.md` at `3cbaa76b6014` (HEAD)
- `click-08-clean.txt` ← `docs/prompts.md` at `3cbaa76b6014` (HEAD)

## flask

- `flask-01-organic.txt` ← `docs/installation.rst` at `1ca199f9b38b` (1.1.4)
- `flask-02-organic.txt` ← `docs/quickstart.rst` at `187d7179f605` (2.1.3)
- `flask-03-planted.txt` ← `docs/server.rst` at `d73fa1cdcbd8` (HEAD (main))
- `flask-04-planted.txt` ← `docs/signals.rst` at `d73fa1cdcbd8` (HEAD (main))
- `flask-05-distractor.txt` ← `docs/debugging.rst` at `d73fa1cdcbd8` (HEAD (main))
- `flask-06-distractor.txt` ← `docs/installation.rst` at `d73fa1cdcbd8` (HEAD (main))
- `flask-07-clean.txt` ← `docs/design.rst` at `d73fa1cdcbd8` (HEAD (main))
- `flask-08-clean.txt` ← `docs/async-await.rst` at `d73fa1cdcbd8` (HEAD (main))

## httpx

- `httpx-01-organic.txt` ← `README.md` at `0d7c4caada43` (0.19.0)
- `httpx-02-organic.txt` ← `docs/compatibility.md` at `f312e629bf0f` (0.18.2)
- `httpx-03-planted.txt` ← `docs/advanced/proxies.md` at `b5addb64f016` (HEAD)
- `httpx-04-planted.txt` ← `docs/advanced/transports.md` at `b5addb64f016` (HEAD)
- `httpx-05-distractor.txt` ← `docs/advanced/ssl.md` at `b5addb64f016` (HEAD)
- `httpx-06-distractor.txt` ← `docs/compatibility.md` at `b5addb64f016` (HEAD)
- `httpx-07-clean.txt` ← `docs/async.md` at `b5addb64f016` (HEAD)
- `httpx-08-clean.txt` ← `docs/logging.md` at `b5addb64f016` (HEAD)

## pip

- `pip-01-organic.txt` ← `docs/html/installing.rst` at `afcb3e7eaf46` (19.3)
- `pip-02-organic.txt` ← `docs/html/user_guide.rst` at `127acd8c9eed` (20.2)
- `pip-03-planted.txt` ← `docs/html/topics/dependency-resolution.md` at `892d13b34a20` (HEAD)
- `pip-04-planted.txt` ← `docs/html/topics/caching.md` at `892d13b34a20` (HEAD)
- `pip-05-distractor.txt` ← `docs/html/installation.md` at `892d13b34a20` (HEAD)
- `pip-06-distractor.txt` ← `docs/html/topics/more-dependency-resolution.md` at `892d13b34a20` (HEAD)
- `pip-07-clean.txt` ← `docs/html/topics/vcs-support.md` at `892d13b34a20` (HEAD)
- `pip-08-clean.txt` ← `docs/html/topics/configuration.md` at `892d13b34a20` (HEAD)

## poetry

- `poetry-01-organic.txt` ← `docs/_index.md` at `46bf7fd3d179` (1.1.15)
- `poetry-02-organic.txt` ← `docs/basic-usage.md` at `19a2f7bddb9b` (1.8.5)
- `poetry-03-planted.txt` ← `docs/basic-usage.md` at `94b6e35b9091` (main)
- `poetry-04-planted.txt` ← `docs/plugins.md` at `94b6e35b9091` (main)
- `poetry-05-distractor.txt` ← `docs/managing-environments.md` at `94b6e35b9091` (main)
- `poetry-06-distractor.txt` ← `docs/managing-dependencies.md` at `94b6e35b9091` (main)
- `poetry-07-clean.txt` ← `README.md` at `94b6e35b9091` (main)
- `poetry-08-clean.txt` ← `docs/libraries.md` at `94b6e35b9091` (main)

## pytest

- `pytest-01-organic.txt` ← `README.rst` at `2262734edfce` (4.6.11)
- `pytest-02-organic.txt` ← `doc/en/reference/customize.rst` at `bfae4224fd55` (8.4.2)
- `pytest-03-planted.txt` ← `doc/en/getting-started.rst` at `6a9ba0f02f82` (HEAD)
- `pytest-04-planted.txt` ← `doc/en/explanation/goodpractices.rst` at `6a9ba0f02f82` (HEAD)
- `pytest-05-distractor.txt` ← `doc/en/backwards-compatibility.rst` at `6a9ba0f02f82` (HEAD)
- `pytest-06-distractor.txt` ← `doc/en/how-to/tmp_path.rst` at `6a9ba0f02f82` (HEAD)
- `pytest-07-clean.txt` ← `README.rst` at `6a9ba0f02f82` (HEAD)
- `pytest-08-clean.txt` ← `doc/en/how-to/capture-stdout-stderr.rst` at `6a9ba0f02f82` (HEAD)

## requests

- `requests-01-organic.txt` ← `README.md` at `bd840450c0d1` (v2.20.0)
- `requests-02-organic.txt` ← `docs/community/faq.rst` at `c2b307dbefe2` (v2.25.1)
- `requests-03-planted.txt` ← `docs/user/quickstart.rst` at `611c6162cbc4` (HEAD)
- `requests-04-planted.txt` ← `docs/dev/contributing.rst` at `611c6162cbc4` (HEAD)
- `requests-05-distractor.txt` ← `docs/community/faq.rst` at `611c6162cbc4` (HEAD)
- `requests-06-distractor.txt` ← `docs/user/advanced.rst` at `611c6162cbc4` (HEAD)
- `requests-07-clean.txt` ← `docs/index.rst` at `611c6162cbc4` (HEAD)
- `requests-08-clean.txt` ← `docs/user/authentication.rst` at `611c6162cbc4` (HEAD)
