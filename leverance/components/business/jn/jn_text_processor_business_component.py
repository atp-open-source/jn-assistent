import re
from uuid import UUID
import nltk

from leverance.components.functions.speaker_mapping_function import speaker_mapping
from leverance.core.runners.service_runner import ServiceRunner


class JNTextProcessorBusinessComponent(ServiceRunner):
    """
    Denne Leverancekomponent indeholder metoder til at processere tekst, som bruges af
    modellen i JNModelBusinessComponent.
    """

    def __init__(self, request_uid: UUID, config_name=None) -> None:

        # Initialisér UID og servicenavn
        self.service_name = "jn"
        self.request_uid = request_uid
        super().__init__(self.service_name, self.request_uid, config_name=config_name)

        # Sørg for at NLTK punkt data er tilgængelig
        self._ensure_nltk_data()

        # Fraser der ikke skal med i det endelige journalnotat
        self.phrases = [
            r"foreg[a-zåæø]* på dansk",
            r"not[a-zåæø]* på sag[a-zåæø]*",
            r"notere[a-zåæø]*",
            r"takke[a-zåæø]* for",
            "er taknemmelig",
            r"ikke.*?indgået.*?aftale\b",
            "udtrykker taknemmelighed",
        ]

    def _ensure_nltk_data(self):
        """
        Sikrer at NLTK punkt data er tilgængelig for sætningssegmentering.
        """
        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            try:
                nltk.data.find("tokenizers/punkt")
            except LookupError:
                nltk.download("punkt", quiet=True)
                nltk.download("punkt_tab", quiet=True)

    def preprocess(self, samtale: list[dict[str, str]]) -> str:
        """
        Klargør samtalen mellem borger og kunderådgiver til input for modellen.
        """
        formatted_string = (
            "TRANSSKRIBERET SAMTALE MELLEM BORGER/FULDMAGTSHAVER/HJÆLPER OG KUNDERÅDGIVER: \n"
            + "\n".join(
                [
                    f"{speaker_mapping(entry['speaker'])}: {entry['sentence']}"
                    for entry in samtale
                ]
            )
        )

        return formatted_string

    def _refine_text(self, sentence: str) -> list[str]:
        """
        Tager én streng og splitter den, hvis strengen indeholder flere sætninger.
        Funktionen er designet til at håndtere strenge, som spaCy ikke har formået at
        splitte korrekt.
        """

        # Find sætningstop efterfulgt af mellemrum og stort bogstav
        pattern = re.compile(r"(?<=[.!?]) (?=[A-ZÆØÅ])")

        return pattern.split(sentence)

    def format_sentences(self, text: str) -> list[str]:
        """
        Tager en streng som input og formaterer den. Funktionen udfører følgende trin:
            1) Newlines fjernes.
            2) Strengen splittes i sætninger.
            3) Sidste sætning fjernes, hvis den ikke er afsluttet.
        """

        # Newline fjernes
        text = re.sub(r"\n+", " ", text)

        # Opdel tekst i sætninger med NLTK
        nltk_sentences = nltk.sent_tokenize(text, language="danish")

        # Anvend regex-baseret raffinering til edgecases
        refined_sentences = [
            part for sent in nltk_sentences for part in self._refine_text(sent)
        ]

        # Kombinér sætninger, der ikke afsluttes med punktum
        sentences = []
        for sentence in refined_sentences:
            if sentences and not sentences[-1].endswith("."):
                sentences[-1] += " " + sentence
            else:
                sentences.append(sentence)

        # Hvis der kun er én sætning, returneres den originale tekst
        if len(sentences) <= 1:
            return [text]

        # Fjern uafsluttede sætninger
        if not sentences[-1].endswith("."):
            sentences.pop()

        return sentences

    def _remove_sentence_with_phrase(
        self, sentences: list[str], phrases: list[str]
    ) -> list[str]:
        """
        Fjerner sætninger fra en tekst, der indeholder en af de angivne fraser.
        """

        # Mønster for uønskede fraser
        pattern = "|".join(phrases)

        # Filtrér sætninger, der indeholder de uønskede fraser
        return [sentence for sentence in sentences if not re.search(pattern, sentence)]

    def postprocess(self, journalnotat: list[str], header: str) -> str:
        """
        Validerer journalnotat og klargør til hjemmesiden ved at tilføje overskrifter
        og formatere til html.
        """

        # Fjern uønskede fraser fra journalnotat
        journalnotat = self._remove_sentence_with_phrase(
            journalnotat,
            self.phrases,
        )
        journalnotat = "".join([sentence + "<br/>" for sentence in journalnotat])

        # Formatér overskrift til ønsket html-format
        html_str = f"<strong>{header.upper()}</strong><br/>{journalnotat}"

        # Tilføj 'VURDERING' som overskrift efter 'OPLYSNINGER'
        if header == "OPLYSNINGER":
            html_str += f"<br/><strong>VURDERING</strong><br/>-----<br/><br/>"

        return html_str

    def clean_notat(self, notat: str) -> str:
        """
        Fjerner citationstegn fra notatet, så det kan gemmes i databasen
        uden der opstår fejl.
        """
        return re.sub(r'[\x00-\x1F"\'´`]+', "", notat)

    def add_stamp(self) -> str:
        """
         Tilføjer et stempel (#) til notatet, der angiver at det er genereret af JN.
        Dette er baseret på et ønske fra forretningen om, at man skal kunne skelne
        mellem notater genereret af JN og notater uden brug af JN.
        """
        stamp = "<br/>#"
        return stamp
