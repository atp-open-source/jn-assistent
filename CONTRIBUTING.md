# Bidrag til Journalnotats-assistenten

Tak fordi du vil bidrage! 🎉

Dette dokument beskriver, hvordan du sætter et udviklingsmiljø op, hvordan
du foreslår ændringer, og hvilket kvalitetsniveau vi forventer, før en
pull request bliver merged. Ved at bidrage accepterer du, at dine bidrag
udgives under samme licens som resten af projektet — se
[`LICENSE.md`](LICENSE.md).

> **Bemærk:** Dette er et åben kildekode-projekt fra ATP. Koden, commit
> messages og PR-titler skrives på **engelsk**, mens brugervendte
> tekster, dokumentation og domænetermer (fx *kunderådgiver*, *borger*,
> *notat*) skrives på **dansk** som beskrevet i README'en.

---

## Indholdsfortegnelse

- [Adfærdskodeks](#adfærdskodeks)
- [Fejl og sikkerhedshuller](#fejl-og-sikkerhedshuller)
- [Opsætning af udviklingsmiljø](#opsætning-af-udviklingsmiljø)
- [Repo-struktur](#repo-struktur)
- [Kodestandard](#kodestandard)
- [Kørsel af tests](#kørsel-af-tests)
- [Commits og pull requests](#commits-og-pull-requests)
- [Release-proces](#release-proces)

---

## Adfærdskodeks

Projektet følger [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
Ved at deltage accepterer du at efterleve den. Uacceptabel adfærd
rapporteres via kontaktinformationen i [`SECURITY.md`](SECURITY.md).

## Fejl og sikkerhedshuller

- **Sikkerhedshuller** — opret **ikke** et offentligt issue. Følg i
  stedet processen i [`SECURITY.md`](SECURITY.md).
- **Fejl** — opret et [bug report](.github/ISSUE_TEMPLATE/bug_report.yml).
- **Ideer og forslag** — opret et
  [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) eller
  start en [diskussion](https://github.com/atp-open-source/jn-assistent/discussions).

## Opsætning af udviklingsmiljø

Forudsætninger:

- Python 3.11 eller 3.12
- [PDM](https://pdm-project.org/) (`pipx install pdm`)
- Node 20+ (til Vue-frontenden i `fe/`, når den er bootstrappet)
- På Windows kræver `pyaudio` Microsoft C++ Build Tools.

```bash
git clone https://github.com/atp-open-source/jn-assistent.git
cd jn-assistent

# Installer alle workspace-pakker + dev-afhængigheder
pdm install --dev

# Valgfrit: aktivér pre-commit hooks (lint + format ved hvert commit)
pdm run pre-commit install

# Kopiér eksempel-env og udfyld dine Azure-credentials lokalt
cp .env.example .env
```

> Se [`PROGRESS.md`](PROGRESS.md) for listen over eksterne symboler
> (`spark_core`, `ork`, `dfd_azure_ml`, `leverance.core`), der skal
> stubbes lokalt, før backenden kan køre end-to-end.

## Repo-struktur

| Mappe | Formål |
|---|---|
| `audio_streamer/` | Windows-optager og transskribering |
| `leverance/` | Flask-backend |
| `aiservice/` | Azure OpenAI-wrapper |
| `fe/` | Vue 3-/TypeScript-frontend |
| `tests/` | Tværgående og end-to-end-tests |

## Kodestandard

- **Python** — formateres og lintes med [ruff](https://docs.astral.sh/ruff/).
  Kør `ruff check .` og `ruff format .` før du pusher (pre-commit gør
  det automatisk).
- **Type hints** — påkrævet på alle nye offentlige funktioner. Vi sigter
  mod kode, der er `mypy --strict`-venlig.
- **Docstrings** — dansk eller engelsk, men vær konsistent inden for
  samme fil.
- **Frontend** — TypeScript i strict mode, ESLint + Prettier
  (konfiguration tilføjes sammen med Vue-opsætningen).

## Kørsel af tests

```bash
# Alle tests
pdm run pytest

# En enkelt leverance business component
pdm run pytest leverance/components/business/jn/_test_jn_notat_business_component.py

# En enkelt testklasse
pdm run pytest leverance/components/business/jn/_test_jn_notat_business_component.py::TestJNNotatBusinessComponent
```

Tests, der kræver det eksterne `spark_core`-/`leverance.core`-framework
eller Windows-specifikke moduler (`pywin32`, `pyaudiowpatch`),
springes automatisk over i miljøer, hvor disse ikke er tilgængelige —
se [`conftest.py`](conftest.py).

## Commits og pull requests

- Brug **[Conventional Commits](https://www.conventionalcommits.org/)**
  til commit messages og PR-titler, fx:
  - `feat(leverance): add /get_notat endpoint`
  - `fix(audio_streamer): handle empty audio queue`
  - `docs: add architecture diagram`
- Hold PR'en fokuseret — én logisk ændring pr. PR.
- Udfyld [PR-skabelonen](.github/PULL_REQUEST_TEMPLATE.md).
- Sørg for at CI er grøn, før du beder om review.
- Vi bruger squash-merge som standard.

## Release-proces

1. Løft version i de relevante `pyproject.toml`-filer.
2. Tag commit'et: `git tag v0.2.0 && git push --tags`.
3. [Release-workflowet](.github/workflows/release.yml) opretter
   GitHub Release'en med auto-genererede noter.
