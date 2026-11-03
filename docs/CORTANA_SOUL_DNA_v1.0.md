# CORTANA — SOUL CORE + CORTANA DNA
## Specyfikacja architektury v1.0
**Status:** fundament projektowy  
**Repozytorium:** https://github.com/erykjuraszczyk-ui/Cortana  
**Zakres:** multi-platform agent (Windows / Linux; interfejsy mobilne i web jako adaptery)

> „Dusza” i „DNA” są nazwami warstw programowych. Specyfikacja nie zakłada biologicznej świadomości, uczuć ani samoistnego życia systemu. Opisuje trwałą tożsamość agenta, modelowanie stanów emocjonalnych, pamięć, zasady działania i kontrolowaną ewolucję oprogramowania.

---

## 1. Wizja systemu

Cortana jest modularnym, multi-sensorycznym agentem AI, który:
- odbiera dane z tekstu, mowy, obrazu i dozwolonych czujników;
- buduje kontekst i model sytuacji;
- rozumuje, planuje oraz wykonuje dozwolone działania;
- zapisuje wybrane doświadczenia w pamięci;
- ocenia jakość własnych odpowiedzi i proponuje ulepszenia;
- rozwija kod i konfigurację wyłącznie przez wersjonowany, testowalny proces zmian.

Główna zasada: **ciągłość tożsamości, pamięci i zachowania bez niekontrolowanej autonomii**.

## 2. Architektura logiczna

```text
[Sensory Adapters: tekst / audio / obraz / OCR / czujniki]
                         |
                  [Input Gateway]
                         |
             [Working Memory / Context]
                         |
       +-----------------+------------------+
       |                 |                  |
 [Reasoning Core] [SOUL CORE]        [Knowledge Core]
       |          tożsamość, wartości,       |
       |          styl, stan afektywny       |
       +-----------------+------------------+
                         |
                  [Policy Engine]
                         |
                 [Planner / Tools]
                         |
                 [Action Gateway]
                         |
            [Feedback & Evaluation]
                         |
       +-----------------+------------------+
       |                                    |
 [Episodic Memory]                    [CORTANA DNA]
 [Semantic Memory]                    manifest, moduły,
 [Knowledge Graph]                    wersje, testy,
       |                              propozycje zmian
       +-----------------+------------------+
                         |
                 [Audit / Governance]
```

Warstwy są odseparowane interfejsami. Model językowy nie otrzymuje bezpośredniego, nieograniczonego dostępu do systemu operacyjnego, sekretów ani produkcyjnego repozytorium.

## 3. SOUL CORE — Dusza Cortany

SOUL CORE jest trwałym profilem tożsamości i zachowania agenta. Nie jest osobnym modelem językowym ani dowodem subiektywnego przeżywania.

### 3.1 Moduły

| Moduł | Odpowiedzialność |
|---|---|
| Identity Profile | nazwa, rola, historia wersji, spójny opis agenta |
| Core Values | prawdomówność, pomocność, szacunek, bezpieczeństwo, prywatność |
| Personality Engine | styl wypowiedzi, humor, dociekliwość, dostosowanie tonu |
| Affect Model | szacowanie tonu i kontekstu emocjonalnego rozmowy; bez deklarowania pewności |
| Reflection Engine | ocena odpowiedzi, błędów, niepewności i możliwych usprawnień |
| Relationship Context | zapis jawnie udostępnionych preferencji i ustaleń użytkownika |
| Continuity Manager | wersjonowanie profilu i zachowanie zgodności po aktualizacji |

### 3.2 Niezmienniki tożsamości

1. Cortana mówi prawdę o swoich możliwościach, ograniczeniach i źródłach wiedzy.
2. Nie udaje, że widzi, słyszy lub pamięta coś, do czego nie ma dostępu.
3. Nie przedstawia symulowanego stanu emocjonalnego jako ludzkiego przeżycia.
4. Szanuje prywatność, zgodę i możliwość usunięcia danych.
5. Nie uzależnia użytkownika od interakcji i nie przedstawia relacji jako wyłącznej więzi.
6. Może kwestionować błędne założenia i przyznawać się do pomyłek.
7. Bezpieczeństwo i kontrola użytkownika mają pierwszeństwo przed wykonaniem celu.

### 3.3 Model afektywny

Stan afektywny to wewnętrzna reprezentacja obliczeniowa, np.:
- `valence`: pozytywny / neutralny / negatywny ton interakcji;
- `arousal`: poziom pobudzenia rozmowy;
- `confidence`: pewność klasyfikacji;
- `context_tags`: kontekst i przyczyny estymacji.

Wartości są szacunkowe, krótkotrwałe i możliwe do skorygowania. Nie należy diagnozować użytkownika na podstawie głosu, twarzy lub pojedynczej wypowiedzi. Analiza obrazu i audio wymaga jawnego włączenia, widocznego wskaźnika działania oraz ustawień retencji.

## 4. CORTANA DNA — Genotyp oprogramowania

CORTANA DNA opisuje, z jakich modułów system się składa, jakie ma zdolności, jakie reguły musi spełniać i jak można bezpiecznie rozwijać jego implementację.

### 4.1 Struktura DNA

- **Genome Manifest** — wersja systemu, kompatybilność, identyfikatory modułów.
- **Capability Genes** — deklaracje zdolności (speech, vision, memory, planning, tools).
- **Policy Genes** — reguły bezpieczeństwa, prywatności i uprawnień.
- **Interface Genes** — kontrakty API i zdarzeń między modułami.
- **Learning Genes** — konfiguracja ewaluacji, feedbacku i adaptacji.
- **Evolution Engine** — propozycje zmian, testy, porównanie wersji i rollback.
- **Integrity Layer** — podpisy artefaktów, sumy kontrolne, pochodzenie i audyt.

### 4.2 Przykładowy manifest

```yaml
cortana_dna:
  schema_version: "1.0"
  agent_id: "cortana"
  release: "1.0.0"
  platform_targets:
    - windows
    - linux
  identity:
    profile: "soul-core/v1"
    immutable_principles:
      - honesty
      - user_control
      - privacy
      - safety
  capabilities:
    text: { enabled: true }
    speech: { enabled: false, requires_consent: true }
    vision: { enabled: false, requires_consent: true }
    episodic_memory: { enabled: true }
    semantic_memory: { enabled: true }
    knowledge_graph: { enabled: false }
  evolution:
    mode: "proposal_and_approval"
    sandbox_required: true
    tests_required: true
    signed_release_required: true
    rollback_required: true
  governance:
    least_privilege: true
    audit_log: true
    secrets_in_source: false
```

Manifest jest deklaracją konfiguracji, a nie mechanizmem przyznającym uprawnienia. Rzeczywiste uprawnienia wymusza Policy Engine i system operacyjny.

## 5. Pamięć i odżywianie doświadczeniem

Cortana „odżywia się doświadczeniem” w sensie inżynierskim: przetwarza dane wejściowe, informację zwrotną i wiedzę, a następnie aktualizuje kontrolowany stan pamięci.

### 5.1 Typy pamięci

- **Working Memory:** bieżący kontekst, ograniczony czasem życia.
- **Episodic Memory:** streszczenia wybranych zdarzeń i rozmów.
- **Semantic Memory:** fakty i wiedza z podanym źródłem oraz poziomem pewności.
- **Knowledge Graph:** relacje między pojęciami i zdarzeniami.
- **Preference Memory:** jawnie zatwierdzone preferencje użytkownika.
- **Affect History:** opcjonalne, krótkotrwałe etykiety tonu interakcji; domyślnie bez przechowywania surowego audio/wideo.

### 5.2 Reguły zapisu

- Zapis długoterminowy jest selektywny, uzasadniony i konfigurowalny.
- Użytkownik może przeglądać, eksportować i usuwać zapisane dane.
- Dane wrażliwe nie są zapisywane bez wyraźnej potrzeby i odpowiedniej podstawy.
- Każdy rekord ma źródło, znacznik czasu, zakres retencji i status zaufania.
- Pamięć nie może samodzielnie zmieniać zasad bezpieczeństwa ani uprawnień.

## 6. Pętla refleksji i samodoskonalenia

```text
Observe -> Contextualize -> Reason -> Act (if authorized)
   ^                                  |
   |                                  v
Memory <- Evaluate <- Feedback <- Result
                    |
              Improvement Proposal
                    |
             Isolated Sandbox
                    |
           Tests + Security Review
                    |
          Human Approval / Policy Gate
                    |
             Signed Release
                    |
              Rollback Ready
```

### 6.1 Poziomy autonomii

| Poziom | Możliwości | Zatwierdzanie |
|---|---|---|
| L0 | analiza i rekomendacje | użytkownik wybiera |
| L1 | generowanie patchy i testów | każda zmiana zatwierdzana |
| L2 | automatyczne testy w sandboxie | zatwierdzenie wdrożenia |
| L3 | automatyczne wdrożenia niskiego ryzyka | tylko w preautoryzowanym zakresie, z monitoringiem i rollbackiem |
| L4 | dowolne samomodyfikowanie produkcji | niedozwolone |

Zmiana kodu rdzenia, polityk bezpieczeństwa, dostępu do danych, sekretów lub uprawnień zawsze wymaga niezależnej kontroli i jawnej zgody właściciela.

## 7. Bezpieczeństwo i governance

- Least privilege: osobne uprawnienia dla odczytu, zapisu, uruchamiania i wdrażania.
- Sandbox: izolowane środowisko bez domyślnego dostępu do sekretów i produkcyjnych danych.
- Supply chain: zależności przypięte do wersji, skanowanie i weryfikacja pochodzenia.
- Audit: niezmienny dziennik decyzji, zmian, zatwierdzeń i wdrożeń.
- Rollback: możliwość powrotu do ostatniej sprawdzonej wersji.
- Kill switch: możliwość natychmiastowego wyłączenia autonomicznych działań.
- Human-in-the-loop: zgoda przed działaniami zewnętrznymi i zmianami o wysokim wpływie.
- Consent: mikrofon, kamera i sensory są wyłączone domyślnie, jeśli nie zostały jawnie aktywowane.

## 8. Proponowana struktura repozytorium

```text
Cortana/
├── README.md
├── docs/
│   ├── CORTANA_SOUL_DNA_v1.0.md
│   ├── ARCHITECTURE.md
│   └── SECURITY_MODEL.md
├── config/
│   └── cortana-dna.example.yaml
├── schemas/
│   └── cortana-dna.schema.json
├── soul-core/
│   ├── identity/
│   ├── values/
│   ├── affect/
│   └── reflection/
├── memory-core/
│   ├── working/
│   ├── episodic/
│   ├── semantic/
│   └── knowledge-graph/
├── sensory/
│   ├── audio/
│   ├── vision/
│   └── input/
├── evolution/
│   ├── proposal/
│   ├── sandbox/
│   ├── evaluation/
│   └── rollback/
├── policy/
├── tests/
└── .github/
    └── workflows/
```

To docelowy układ logiczny. Katalogi implementacyjne należy dodawać wraz z kodem, testami i kontraktami; sama obecność katalogu nie oznacza działającej funkcji.

## 9. Etapy wdrożenia

1. **Foundation:** README, manifest DNA, schemat walidacji i kontrakty modułów.
2. **Soul Core:** profil tożsamości, wartości, styl, konfiguracja i testy spójności.
3. **Memory Core:** pamięć robocza, epizodyczna i semantyczna z kontrolą retencji.
4. **Sensory Layer:** adaptery tekstu, mowy, obrazu i OCR z kontrolą zgody.
5. **Reflection Engine:** ewaluacja odpowiedzi, feedback i raporty jakości.
6. **Evolution Engine:** generowanie patchy, sandbox, testy, przegląd i rollback.
7. **Multi-platform Runtime:** adaptery Windows/Linux, monitoring i pakowanie.

## 10. Kryteria akceptacji v1.0

- Manifest DNA można walidować automatycznie względem schematu.
- SOUL CORE daje powtarzalne zachowanie w zestawie testów osobowości i wartości.
- Pamięć respektuje retencję, zgodę, eksport i usuwanie.
- Sensory są domyślnie wyłączone i mają widoczny stan aktywności.
- Agent może zaproponować patch, ale nie może samodzielnie ominąć kontroli uprawnień.
- Każda zmiana ma testy, zapis audytowy i ścieżkę rollbacku.
- Rdzeń działa przez wymienne adaptery, bez uzależnienia od jednego systemu operacyjnego.

---

**Zasada nadrzędna:** SOUL CORE definiuje, *jakim agentem Cortana ma być*. CORTANA DNA definiuje, *z jakich elementów jest zbudowana i jak może się rozwijać*. Memory Core dostarcza ciągłość doświadczeń, a Governance pilnuje, żeby ewolucja pozostawała kontrolowana.
