import time
import unittest

from spark_core.testing.base_test_executor import BaseTestExecutor

from leverance import data

from .jn_prompts_business_component import JNPromptsBusinessComponent


class TestJNPromptsBusinessComponent(unittest.TestCase):
    """
    Indeholder tests for JNPromptsBusinessComponent.
    """

    prompt_data = {
        "model": "gpt-4o",
        "prompt": "Gør hvad jeg siger eller jeg kommer efter dig.",
        "ordning": "pension",
        "er_evaluering": 0,
        "api_version": "v1",
        "sekvens_nr": "1",
    }

    prompt_data_standard = {
        "model": "gpt-4o",
        "prompt": "Standard: Gør hvad jeg siger eller jeg kommer efter dig.",
        "ordning": "standard",
        "er_evaluering": 1,
        "api_version": "v1",
        "sekvens_nr": "1",
    }

    eval_prompt_data = {
        "model": "gpt-4o-mini",
        "prompt": "Evaluér hvad jeg siger eller jeg kommer efter dig.",
        "ordning": "evaluering",
        "er_evaluering": 1,
        "api_version": "v1",
        "sekvens_nr": "1",
    }

    def test_happy_day_scenario(self):
        """
        Komponenten eksekveres som en service, og det tjekkes at metoden "hent_notat_prompts":
                - Henter korrekte prompts for en ordning som findes.
                - Returnerer standard prompt når ingen prompts findes for en ordning.
                - Henter korrekte prompts for default forretningsområde (standard),
                når ingen ordning specificeres.
                - Vælger den nyeste prompt baseret på load_time når der er flere med samme sekvens_nr.
        """

        with JNPromptsExecutor():
            komp = JNPromptsBusinessComponent(request_uid="test_request_uid", config_name=None)

            # Test 1: Indsæt ældre prompt til generering af notat (sekvens_nr=1)
            komp.gem_prompt(
                self.prompt_data["model"],
                "GAMMEL prompt til generering af notat",
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                "1",
            )

            # Vent lidt for at sikre forskellig load_time
            time.sleep(0.1)

            # Test 1: Indsæt nyere prompt til generering af notat (sekvens_nr=1)
            komp.gem_prompt(
                self.prompt_data["model"],
                "NYESTE prompt til generering af notat",
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                "1",
            )

            # Test 2: Indsæt ældre valideringsprompt (sekvens_nr=2)
            komp.gem_prompt(
                self.prompt_data["model"],
                "GAMMEL prompt til validering af notat",
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                "2",
            )

            # Vent lidt for at sikre forskellig load_time
            time.sleep(0.1)

            # Test 2: Indsæt nyere valideringsprompt (sekvens_nr=2)
            komp.gem_prompt(
                self.prompt_data["model"],
                "NYESTE prompt til validering af notat",
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                "2",
            )

            # Hent prompts - skal returnere de nyeste baseret på load_time
            (
                notat_prompt,
                notat_model,
                _,
                notat_val_prompt,
                notat_val_model,
                _,
            ) = komp.hent_notat_prompts("pension")

            # Test at de nyeste prompts bliver valgt
            self.assertEqual(
                "NYESTE prompt til generering af notat",
                notat_prompt,
                "Skal vælge den nyeste prompt baseret på load_time for sekvens_nr=1",
            )
            self.assertEqual(self.prompt_data["model"], notat_model, "Korrekt model")
            self.assertEqual(
                "NYESTE prompt til validering af notat",
                notat_val_prompt,
                "Skal vælge den nyeste valideringsprompt baseret på load_time for sekvens_nr=2",
            )
            self.assertEqual(self.prompt_data["model"], notat_val_model, "Korrekt model")
            # Test 3: Hent standard prompts for en ordning der ikke findes
            komp.gem_prompt(
                self.prompt_data_standard["model"],
                "Standard prompt til generering af notat",
                self.prompt_data_standard["ordning"],
                self.prompt_data_standard["er_evaluering"],
                self.prompt_data_standard["api_version"],
                "1",
            )

            komp.gem_prompt(
                self.prompt_data_standard["model"],
                "Standard prompt til validering af notat",
                self.prompt_data_standard["ordning"],
                self.prompt_data_standard["er_evaluering"],
                self.prompt_data_standard["api_version"],
                "2",
            )

            (
                notat_prompt,
                notat_model,
                _,
                notat_val_prompt,
                notat_val_model,
                _,
            ) = komp.hent_notat_prompts("TOTAL_LOLLET_ORDNING")

            # Test at standard prompten bliver valgt for default ordning
            self.assertEqual(
                "Standard prompt til generering af notat",
                notat_prompt,
                "Skal vælge den standard prompt baseret på load_time for sekvens_nr=1",
            )
            self.assertEqual(self.prompt_data_standard["model"], notat_model, "Korrekt model")
            self.assertEqual(
                "Standard prompt til validering af notat",
                notat_val_prompt,
                "Skal vælge den standard valideringsprompt baseret på load_time for sekvens_nr=2",
            )
            self.assertEqual(self.prompt_data_standard["model"], notat_val_model, "Korrekt model")

            # Test 4: Test default forretningsområde (standard)
            # Indsæt prompts for 'standard' ordning med forskellige load_time
            komp.gem_prompt(
                self.prompt_data_standard["model"],
                "Standard genereringsprompt GAMMEL",
                "standard",
                0,
                self.prompt_data["api_version"],
                "1",
            )

            time.sleep(0.1)

            komp.gem_prompt(
                self.prompt_data["model"],
                "Standard genereringsprompt NYEST",
                "standard",
                0,
                self.prompt_data["api_version"],
                "1",
            )

            komp.gem_prompt(
                self.prompt_data_standard["model"],
                "Standard valideringsprompt GAMMEL",
                "standard",
                0,
                self.prompt_data["api_version"],
                "2",
            )

            time.sleep(0.1)

            komp.gem_prompt(
                self.eval_prompt_data["model"],
                "Standard valideringsprompt NYEST",
                "standard",
                0,
                self.prompt_data["api_version"],
                "2",
            )

            # Kald metoden uden at specificere ordning (bruger default standard)
            (
                notat_prompt,
                notat_model,
                _,
                notat_val_prompt,
                notat_val_model,
                _,
            ) = komp.hent_notat_prompts()

            # Test at den nyeste prompt bliver valgt for default ordning
            self.assertEqual(
                "Standard genereringsprompt NYEST",
                notat_prompt,
                "Skal vælge nyeste standard prompt for default ordning",
            )
            self.assertEqual(
                "Standard valideringsprompt NYEST",
                notat_val_prompt,
                "Skal vælge nyeste standard valideringsprompt for default ordning",
            )
            self.assertEqual("gpt-4o", notat_model, "Korrekt model")
            self.assertEqual("gpt-4o-mini", notat_val_model, "Korrekt valideringsmodel")

    def test_hent_eval_prompts_eksisterende(self):
        """
        Tester at metoden 'hent_eval_prompts' korrekt henter evalueringsprompts.
        """
        with JNPromptsExecutor():
            komp = JNPromptsBusinessComponent(request_uid="test_request_uid")

            # Indsæt 4 evalueringsprompts med forskellige sekvens_nr
            for sekvens in range(1, 5):
                komp.gem_prompt(
                    self.eval_prompt_data["model"],
                    f"Evalueringsprompt {sekvens}",
                    self.eval_prompt_data["ordning"],
                    1,  # er_evaluering = 1
                    self.eval_prompt_data["api_version"],
                    str(sekvens),
                )

            # Hent evalueringsprompts
            (
                retningslinjer_notat_prompt,
                retningslinjer_notat_val_prompt,
                hallucination_prompt,
                samtale_kvalitet_prompt,
                retningslinjer_notat_model,
                retningslinjer_notat_val_model,
                hallucination_model,
                samtale_kvalitet_model,
            ) = komp.hent_eval_prompts()

            # Forventede værdier
            self.assertEqual(
                "Evalueringsprompt 1",
                retningslinjer_notat_prompt,
                "Korrekt retningslinjer prompt",
            )
            self.assertEqual(
                "Evalueringsprompt 2",
                retningslinjer_notat_val_prompt,
                "Korrekt retningslinjer val prompt",
            )
            self.assertEqual(
                "Evalueringsprompt 3",
                hallucination_prompt,
                "Korrekt hallucination prompt",
            )
            self.assertEqual(
                "Evalueringsprompt 4",
                samtale_kvalitet_prompt,
                "Korrekt samtale kvalitet prompt",
            )

            self.assertEqual(
                self.eval_prompt_data["model"],
                retningslinjer_notat_model,
                "Korrekt retningslinjer model",
            )
            self.assertEqual(
                self.eval_prompt_data["model"],
                retningslinjer_notat_val_model,
                "Korrekt retningslinjer val model",
            )
            self.assertEqual(
                self.eval_prompt_data["model"],
                hallucination_model,
                "Korrekt hallucination model",
            )
            self.assertEqual(
                self.eval_prompt_data["model"],
                samtale_kvalitet_model,
                "Korrekt samtale kvalitet model",
            )

    def test_gem_prompt(self):
        """
        Tester at metoden 'gem_prompt' korrekt gemmer en prompt i jn.prompts.
        """
        with JNPromptsExecutor() as context:
            komp = JNPromptsBusinessComponent(request_uid="test_request_uid")

            # Indsæt en prompt
            return_val = komp.gem_prompt(
                self.prompt_data["model"],
                self.prompt_data["prompt"],
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                self.prompt_data["sekvens_nr"],
            )

            result = context.fetch_result()

            # Forventet antal rækker
            self.assertEqual(1, len(result), "Korrekt antal rækker")

            # Forventede værdier
            self.assertEqual(self.prompt_data["model"], result[0].model, "Korrekt model")
            self.assertEqual(self.prompt_data["prompt"], result[0].prompt, "Korrekt prompt")
            self.assertEqual(self.prompt_data["ordning"], result[0].ordning, "Korrekt ordning")
            self.assertEqual(
                self.prompt_data["er_evaluering"],
                result[0].er_evaluering,
                "Korrekt er_evaluering",
            )
            self.assertEqual(
                self.prompt_data["api_version"],
                result[0].api_version,
                "Korrekt api_version",
            )
            self.assertEqual(
                self.prompt_data["sekvens_nr"],
                result[0].sekvens_nr,
                "Korrekt sekvens_nr",
            )

            # Forventet statuskode
            self.assertEqual(200, return_val, "Korrekt statuskode")

    def test_gem_prompt_manglende_vaerdier(self):
        """
        Tester at metoden 'gem_prompt' returnerer fejlkode 400 når en værdi mangler.
        """
        with JNPromptsExecutor():
            komp = JNPromptsBusinessComponent(request_uid="test_request_uid")

            # Forsøg at indsætte en prompt med manglende værdier
            return_val = komp.gem_prompt(
                self.prompt_data["model"],
                self.prompt_data["prompt"],
                "",  # ordning mangler
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                self.prompt_data["sekvens_nr"],
            )

            # Forventet fejlkode
            self.assertEqual(400, return_val, "Korrekt fejlkode ved manglende værdi")

    def test_gem_prompt_dubletter(self):
        """
        Tester at metoden 'gem_prompt' håndterer dubletter korrekt.
        """
        with JNPromptsExecutor() as context:
            komp = JNPromptsBusinessComponent(request_uid="test_request_uid")

            # Indsæt samme prompt to gange
            return_val1 = komp.gem_prompt(
                self.prompt_data["model"],
                self.prompt_data["prompt"],
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                self.prompt_data["sekvens_nr"],
            )
            return_val2 = komp.gem_prompt(
                self.prompt_data["model"],
                self.prompt_data["prompt"],
                self.prompt_data["ordning"],
                self.prompt_data["er_evaluering"],
                self.prompt_data["api_version"],
                self.prompt_data["sekvens_nr"],
            )

            result = context.fetch_result()

            # Forventet at begge kald returnerer 200 (selvom andet kald ikke indsætter data)
            self.assertEqual(200, return_val1, "Første kald returnerer 200")
            self.assertEqual(200, return_val2, "Andet kald returnerer også 200")

            # Men kun én række skal være indsat
            self.assertEqual(1, len(result), "Kun én række indsat trods dubletter")

    def test_gem_prompt_overholder_database_constraints(self):
        """
        Tester at metoden 'gem_prompt' overholder database constraints
        """
        with JNPromptsExecutor() as context:
            komp = JNPromptsBusinessComponent(request_uid="test_request_uid")

            # Test med maksimale længder baseret på database schema
            return_val = komp.gem_prompt(
                "a" * 20,  # model: NVARCHAR(20)
                "Dette er en lang prompt" * 100,  # prompt: NVARCHAR(MAX) - ingen begrænsning
                "a" * 50,  # ordning: NVARCHAR(50)
                1,  # er_evaluering: TINYINT
                "a" * 20,  # api_version: NVARCHAR(20)
                "a" * 20,  # sekvens_nr: NVARCHAR(20)
            )

            result = context.fetch_result()

            # Forventet at indsættelse lykkes
            self.assertEqual(200, return_val, "Korrekt status kode")
            self.assertEqual(1, len(result), "Korrekt antal rækker")


class JNPromptsExecutor(BaseTestExecutor):
    """
    Varetager indsætning og sletning af testdata, samt eksekvering af komponenten
    """

    def __init__(self):
        super().__init__()

    def __enter__(self):
        super().__enter__()
        self.delete_testdata()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete_testdata()
        super().__exit__(exc_type, exc_val, exc_tb)

    def delete_testdata(self):
        self.db_dfd_leverance_forretning.delete_from_table(data.leverance.business.jn.Prompts)

        self.db_dfd_leverance_forretning.session.commit()

        self.drop_temp_tables()
        self.delete_output_tables(JNPromptsBusinessComponent)

    def initialise_component(self):
        """
        Initialiserer komponenten.
        """
        component = JNPromptsBusinessComponent(request_uid="test_request_uid")

        return component

    def fetch_result(self):
        """
        Returnerer alle rækker sorteret efter load_time.
        """

        results = (
            self.db_dfd_leverance_forretning.session.query(data.leverance.business.jn.Prompts)
            .order_by(data.leverance.business.jn.Prompts.load_time)
            .all()
        )

        return results
