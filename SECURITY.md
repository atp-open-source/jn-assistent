# Sikkerhedspolitik

## Understøttede versioner

Så længe `jn-assistent` er pre-1.0, modtager kun `main`-grenen
sikkerhedsrettelser. Når vi rammer 1.0, udfyldes tabellen nedenfor med
de understøttede minor-versioner.

| Version | Understøttet |
|---------|--------------|
| `main`  | ✅           |
| `< 1.0` | ❌ (brug `main`) |

## Rapportering af sikkerhedshuller

**Rapportér ikke sikkerhedshuller via offentlige GitHub-issues,
-diskussioner eller pull requests.**

Brug i stedet én af følgende kanaler:

1. **Anbefalet:** opret en
   [GitHub Security Advisory](https://github.com/atp-open-source/jn-assistent/security/advisories/new).
   Rapporten forbliver privat, indtil vi udgiver en rettelse.
2. Send en mail til vedligeholderne på `movj@atp.dk` med emnet
   `[SECURITY] jn-assistent` og en tydelig beskrivelse af problemet,
   reproduktionstrin samt berørt version eller commit.

Vi tilstræber at:

- Kvittere for modtagelsen inden for **3 arbejdsdage**.
- Give en første vurdering inden for **10 arbejdsdage**.
- Koordinere offentliggørelsen og udgive en rettet version så hurtigt
  som muligt. Rapportøren krediteres, medmindre vedkommende ønsker at
  være anonym.

## Omfang

I scope:

- Kode i dette repository (`audio_streamer/`, `leverance/`,
  `aiservice/`, `fe/`).
- Build- og release-tooling i `.github/workflows/`.

Uden for scope:

- Sikkerhedshuller i tredjeparts Azure-tjenester eller
  telefoniplatforme.
- Problemer, der kræver fysisk adgang til en kunderådgivers
  arbejdsstation.

## Anbefalinger til drift

- Commit aldrig secrets — brug Azure Key Vault eller GitHub Actions
  secrets.
- Brug managed identities / `DefaultAzureCredential` i produktion.
- Rotér `LEVERANCE_PASSWORD` og eventuelle Azure service
  principal-secrets efter den frekvens, din organisation foreskriver.
