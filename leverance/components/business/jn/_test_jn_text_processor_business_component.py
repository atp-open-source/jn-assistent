import unittest
from uuid import uuid4

from leverance.components.business.jn.jn_text_processor_business_component import (
    JNTextProcessorBusinessComponent,
)


class TestJNTextProcessorBusinessComponent(unittest.TestCase):
    """
    Indeholder tests for JNTextProcessorBusinessComponent
    """

    # Initialisér TextProcessor instans
    JNTextProcessor = JNTextProcessorBusinessComponent(str(uuid4()), config_name=None)

    def test_preprocess(self):
        """
        Tester at den transskriberede samtale bliver preprocesseret korrekt.
        """

        texts = [
            {"speaker": "agent", "sentence": "Kunderådgiver snakker."},
            {"speaker": "caller", "sentence": "Borger snakker."},
            {"speaker": "agent", "sentence": "Kunderådgiver snakker igen."},
        ]

        formatted_string = self.JNTextProcessor.preprocess(texts)

        expected_string = (
            "TRANSSKRIBERET SAMTALE MELLEM BORGER/FULDMAGTSHAVER/HJÆLPER OG KUNDERÅDGIVER: \n"
            "Kunderådgiver: Kunderådgiver snakker.\n"
            "Borger/fuldmagtshaver/hjælper: Borger snakker.\n"
            "Kunderådgiver: Kunderådgiver snakker igen."
        )

        self.assertEqual(
            formatted_string,
            expected_string,
            f"Forventede: {expected_string}, men fik: {formatted_string}",
        )

    def test_format_sentences(self):
        """
        Tester at newlines og ufærdige sætninger fjernes fra teksten. Testteksten er
        designet til at fremprovokere nogle af de problemer, som spaCy kan have svært
        ved at håndtere, når den skal splitte teksten.
        """

        text = (
            "Borger ringer angående en mail de har modtaget om efterregulering af boligstøtte fra 17 til 19."
            " Borger ønsker en forklaring på indholdet i mailen og er blevet bedt om at ringe til os."
            " Dette er første sætning fra d. 19. marts i år."
            " Borger er anden sætning som f.eks. kunne være fra 17 til 19."
            " Borger har bedt borger om at oplyse hvilket år de har arbejdet, og borger oplyser at de har boet på det sted fra 17 til 19, men har arbejdet hele 20."
            " Borger er usikker på præcis hvornår de startede med at arbejde."
            " Jeg undersøger sagen og oplyser, at der tidligere har været et tilgodehavende beløb på 11.676 kroner, som er blevet udbetalt til Mortens Nemme Konto."
            "\nDette er tredje sætning."
            "\n\nDette er fjerde sætning."
            "\n\n\nDette er femte sætning."
            " Og en sidste ufærdig sæ"
        )

        sentences = self.JNTextProcessor.format_sentences(text)

        expected_sentences = [
            "Borger ringer angående en mail de har modtaget om efterregulering af boligstøtte fra 17 til 19.",
            "Borger ønsker en forklaring på indholdet i mailen og er blevet bedt om at ringe til os.",
            "Dette er første sætning fra d. 19. marts i år.",
            "Borger er anden sætning som f.eks. kunne være fra 17 til 19.",
            "Borger har bedt borger om at oplyse hvilket år de har arbejdet, og borger oplyser at de har boet på det sted fra 17 til 19, men har arbejdet hele 20.",
            "Borger er usikker på præcis hvornår de startede med at arbejde.",
            "Jeg undersøger sagen og oplyser, at der tidligere har været et tilgodehavende beløb på 11.676 kroner, som er blevet udbetalt til Mortens Nemme Konto.",
            "Dette er tredje sætning.",
            "Dette er fjerde sætning.",
            "Dette er femte sætning.",
        ]

        self.assertEqual(
            sentences,
            expected_sentences,
            f"Forventede: {expected_sentences}, men fik: {sentences}",
        )

    def test_postprocess(self):
        """
        Tester at journalnotatet klargøres korrekt. Der indsættes et oplysningsnotat og
        et statusnotat, og det sikres, at outputtet bliver formateret korrekt.
        Journalnotatet for oplysninger er designet til at teste, at specifikke fraser
        fjernes jf. remove_sentence_with_phrase(), som bliver kaldt i "postprocess".
        """

        journalnotater = {
            "OPLYSNINGER": [
                "Dette er første sætning.",
                "Anden sætning foregår på dansk.",
                "Tredje sætning noterer på sagen.",
                "Fjerde sætning noterer.",
                "Femte sætning takker for hjælpen.",
                "Sjette sætning har takket for hjælpen.",
                "Syvende sætning er taknemmelig for hjælpen.",
                "Ottende sætning har ikke indgået en aftale.",
                "Niende sætning udtrykker taknemmelighed.",
                "Og tilbage har vi to sætninger.",
            ],
            "STATUS": [
                "Dette er den endelige status.",
                "Endnu en statussætning.",
            ],
        }

        html_str = {
            header: self.JNTextProcessor.postprocess(journalnotat, header)
            for header, journalnotat in journalnotater.items()
        }

        expected_html_strings = {
            "OPLYSNINGER": (
                "<strong>OPLYSNINGER</strong><br/>Dette er første sætning.<br/>Og tilbage har vi to sætninger.<br/>"
                "<br/><strong>VURDERING</strong><br/>-----<br/><br/>"
            ),
            "STATUS": "<strong>STATUS</strong><br/>Dette er den endelige status.<br/>Endnu en statussætning.<br/>",
        }

        for header, html_str in html_str.items():
            self.assertEqual(
                html_str,
                expected_html_strings[header],
                f"Forventede: {expected_html_strings[header]}, men fik: {html_str}",
            )

    def test_clean_notat(self):
        """
        Tester at citationstegn korrekt fjernes fra notatet.
        """
        # Test med citationstegn
        notat = "Den her borger er lidt 'craycray' hvis du spørger mig"
        expected_notat = "Den her borger er lidt craycray hvis du spørger mig"
        cleaned_notat = self.JNTextProcessor.clean_notat(notat)
        self.assertEqual(
            cleaned_notat,
            expected_notat,
            f"Expected: {expected_notat}, but got: {cleaned_notat}",
        )

        # Test uden citationstegn
        notat = "Den her borger er lidt craycray hvis du spørger mig"
        cleaned_notat = self.JNTextProcessor.clean_notat(notat)
        self.assertEqual(
            cleaned_notat,
            notat,
            f"Expected: {notat}, but got: {cleaned_notat}",
        )
