import time
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask import Flask

from leverance.components.business.jn.jn_model_business_component import (
    JNModelBusinessComponent,
)


class TestJNModelBusinessComponent(unittest.TestCase):
    """
    Indeholder de forskellige tests for JNModelBusinessComponent
    """

    # Initialisér JN Modelkomponent med mocked _initialize_model
    @patch.object(JNModelBusinessComponent, "_initialize_model")
    def setUp(self, mock_initialize_model):
        # Mock Flask applikation
        self.flask_app = Flask(__name__)
        self.flask_app.config["SPARK_CONFIG"] = MagicMock()
        self.flask_app.config["SPARK_CONFIG"].NAME = "test_config"
        self.flask_app.logger = MagicMock()

        # Opret Flask applikationskontext
        self.app_context = self.flask_app.app_context()
        self.app_context.push()

        # Mock initialize_model
        mock_initialize_model.return_value = MagicMock()
        self.JNModel = JNModelBusinessComponent(request_uid=str(uuid4()), config_name=None)

    def tearDown(self):
        # Ryd Flask applikationskontext
        self.app_context.pop()

    # Globale variable
    prompt = "prompt"
    input = "input"
    temperature = 0.5
    max_tokens = 100
    call_id = "call_id"
    agent_id = "agent_id"

    @patch(
        "leverance.components.business.jn.jn_model_business_component.time.sleep",
    )
    def test_prompt_llm_max_retries(self, mock_sleep):
        """
        Der mockes en exception hver gang vi forsøger at kalde OpenAIAssistant. Det
        verificeres, at output fra _prompt_llm samt logging er som forventet,
        når max-retries overskrides.
        """

        # Mock OpenAIAssistant og sleep
        self.JNModel.llm.prompt.side_effect = Exception("Mocked Exception")
        mock_sleep.return_value = None

        with patch.object(self.JNModel.service_logger, "service_warning") as mock_log:
            results = self.JNModel._prompt_llm(
                llm=self.JNModel.llm,
                prompt=self.prompt,
                input=self.input,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                call_id=self.call_id,
            )

        # Forventet output
        expected_results = [
            "Det lykkedes ikke at generere et journalnotat",
            "",
            0,
            0,
            0,
        ]
        expected_logs = [
            f"Der opstod en fejl ved kald af LLM efter {i + 1} antal forsøg for call-id: {self.call_id}. Exception: {self.JNModel.llm.prompt.side_effect}"
            for i in range(self.JNModel.max_retries)
        ]

        for result, expected_result in zip(results, expected_results, strict=False):
            self.assertEqual(
                result,
                expected_result,
                f"Forventede: {expected_result}, men fik: {result}",
            )
        for i in range(self.JNModel.max_retries):
            self.assertEqual(
                expected_logs[i],
                mock_log.call_args_list[i][0][1],
                f"Forventede {expected_logs[i]}, men fik {mock_log.call_args_list[i][0][1]}",
            )
        self.assertEqual(
            self.JNModel.llm.prompt.call_count,
            self.JNModel.max_retries,
            "Forventede at antal kald var lig med max-retries",
        )

    def test_prompt_llm_break(self):
        """
        Der mockes en langsom exception når vi forsøger at kalde OpenAIAssistant, som
        overskrider den globale timeout-begrænsningen. Det verificeres, at loopet
        breakes korrekt, og dermed at output fra _prompt_llm samt logging er som forventet.
        """
        # Sæt timeout til 0.1 sekunder
        self.JNModel.global_timeout = 0.1

        # Mock OpenAIAssistant
        self.JNModel.llm.prompt.side_effect = Exception("Mocked Exception")

        with patch.object(self.JNModel.service_logger, "service_warning") as mock_log:
            results = self.JNModel._prompt_llm(
                llm=self.JNModel.llm,
                prompt=self.prompt,
                input=self.input,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                call_id=self.call_id,
            )

        # Forventet output
        expected_results = [
            "Det lykkedes ikke at generere et journalnotat",
            "",
            0,
            0,
            0,
        ]
        expected_log = f"LLM timeoutede efter {self.JNModel.global_timeout} sekunder for call-id: {self.call_id}"

        for result, expected_result in zip(results, expected_results, strict=False):
            self.assertEqual(
                result,
                expected_result,
                f"Forventede: {expected_result}, men fik: {result}",
            )
        self.assertEqual(
            mock_log.call_args[0][1],
            expected_log,
            f"Forventede {expected_log}, men fik {mock_log.call_args[0][1]}",
        )

        # Revert timeout til default (30 sekunder)
        self.JNModel.global_timeout = 30

    def test_prompt_llm_timeout(self):
        """
        OpenAIAssistant's (llm-objektet) prompt-metode mockes til at overstige
        timeout thresholden. Det verificeres, at output fra _prompt_llm samt
        logging er som forventet, når timeout overskrides.
        """
        # Sæt timeout til 0.1 sekunder
        self.JNModel.model_kald_timeout = 0.1

        # Mock llm.prompt med forsinkelse
        def delayed_prompt(messages, temperature, model, max_tokens, stream):
            time.sleep(0.2)

        self.JNModel.llm.prompt.side_effect = delayed_prompt

        with patch.object(self.JNModel.service_logger, "service_warning") as mock_log:
            results = self.JNModel._prompt_llm(
                llm=self.JNModel.llm,
                prompt=self.prompt,
                input=self.input,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                call_id=self.call_id,
            )

        # Forventet output
        expected_results = [
            "Det lykkedes ikke at generere et journalnotat",
            "",
            0,
            0,
            0,
        ]
        expected_log = f"LLM kald timeoutede efter {self.JNModel.model_kald_timeout} sekunder for call-id: {self.call_id}"

        for result, expected_result in zip(results, expected_results, strict=False):
            self.assertEqual(
                result,
                expected_result,
                f"Forventede: {expected_result}, men fik: {result}",
            )
        self.assertEqual(
            mock_log.call_args[0][1],
            expected_log,
            f"Forventede {expected_log}, men fik {mock_log.call_args[0][1]}",
        )

        # Revert timeout til default (20 sekunder)
        self.JNModel.model_kald_timeout = 20

    @patch(
        "leverance.components.business.jn.jn_model_business_component.JNModelBusinessComponent._prompt_llm"
    )
    @patch(
        "leverance.components.business.jn.jn_model_business_component.JNPromptsBusinessComponent"
    )
    @patch("leverance.components.business.jn.jn_model_business_component.JNConfigBusinessComponent")
    def test_predict(self, mock_jn_config, mock_jn_prompts, mock_prompt_llm):
        """
        Det testes at outputtet fra predict har det forventede format.
        Der gives en samtale som input i predict, og _prompt_llm mockes
        til at returnere et journalnotat i forventet json-format.
        Testen sikrer, at alle text-processing steps sker i korrekt rækkefølge.
        """

        # Mock JNConfigBusinessComponent hent_kr_konfiguration metode
        mock_jn_config.return_value.hent_kr_konfiguration.return_value = {
            "forretningsomraade": "pension"
        }

        # Mock JNPromptsBusinessComponent to return valid prompts
        mock_jn_prompts.return_value.hent_notat_prompts.return_value = (
            "Prompt til generering af notat",
            "gpt-4o",
            1,
            "Prompt til validering af notat",
            "gpt-4o-mini",
            2,
        )

        # Mock prompt_llm
        mock_prompt_llm.return_value = (
            '{\n  "oplysninger": "Dette er sætning 1.",\n  "status": "Dette er sætning 2."\n}',
            "finished",
            1,
            2,
            3,
        )

        # Definer variabler
        samtale = [{"speaker": "agent", "sentence": "Hej"}]
        speaker_mapping = {
            "agent": "Kunderådgiver",
            "caller": "Borger/fuldmagtshaver/hjælper",
        }

        # Kald predict
        (
            notat,
            formatted_samtale,
            results_dict,
            notat_prompt_id,
            notat_val_prompt_id,
            forretningsomraade,
        ) = self.JNModel.predict(samtale=samtale, call_id=self.call_id, agent_id=self.agent_id)

        # Forventet output
        forventet_notat = (
            "<strong>OPLYSNINGER</strong><br/>"
            "Dette er sætning 1.<br/>"
            "<br/><strong>VURDERING</strong><br/>"
            "-----<br/>"
            "<br/><strong>STATUS</strong><br/>"
            "Dette er sætning 2.<br/>"
            "<br/>#"
        )

        forventet_samtale = (
            "TRANSSKRIBERET SAMTALE MELLEM BORGER/FULDMAGTSHAVER/HJÆLPER OG KUNDERÅDGIVER: "
        )
        for sentence in samtale:
            forventet_samtale += f"\n{speaker_mapping[sentence['speaker']]}: {sentence['sentence']}"

        forventet_results_dict = {
            "response_notat": mock_prompt_llm.return_value[0],
            "finish_reason_notat": mock_prompt_llm.return_value[1],
            "tokens_used_notat": mock_prompt_llm.return_value[2],
            "prompt_tokens_used_notat": mock_prompt_llm.return_value[3],
            "generation_time_notat": mock_prompt_llm.return_value[4],
            "response_val_notat": mock_prompt_llm.return_value[0],
            "finish_reason_val_notat": mock_prompt_llm.return_value[1],
            "tokens_used_val_notat": mock_prompt_llm.return_value[2],
            "prompt_tokens_used_val_notat": mock_prompt_llm.return_value[3],
            "generation_time_val_notat": mock_prompt_llm.return_value[4],
            "call_id": self.call_id,
        }

        # Tjek output
        self.assertEqual(notat, forventet_notat, f"Forventede: {forventet_notat}, men fik: {notat}")
        self.assertEqual(
            formatted_samtale,
            forventet_samtale,
            f"Expected: {forventet_samtale}, but got: {formatted_samtale}",
        )
        self.assertEqual(
            results_dict,
            forventet_results_dict,
            f"Expected: {forventet_results_dict}, but got: {results_dict}",
        )

        self.assertEqual(
            notat_prompt_id,
            1,
            f"Forventede notat_prompt_id: 1, men fik: {notat_prompt_id}",
        )

        self.assertEqual(
            notat_val_prompt_id,
            2,
            f"Forventede notat_val_prompt_id: 2, men fik: {notat_val_prompt_id}",
        )

        self.assertEqual(
            forretningsomraade,
            "pension",
            f"Forventede forretningsomraade: pension, men fik: {forretningsomraade}",
        )

    @patch(
        "leverance.components.business.jn.jn_model_business_component.JNModelBusinessComponent._initialize_model",
    )
    @patch(
        "leverance.components.business.jn.jn_model_business_component.JNPromptsBusinessComponent"
    )
    @patch("leverance.components.business.jn.jn_model_business_component.JNConfigBusinessComponent")
    def test_predict_tom_samtale(self, mock_jn_config, mock_jn_prompts, mock_initialize_model):
        """
        Tester at korrekt fejlmeddelelse returneres, hvis samtalen er tom.
        """
        # Mock initialize_model
        mock_initialize_model.return_value = None

        # Mock JNConfigBusinessComponent's hent_kr_konfiguration method
        mock_jn_config.return_value.hent_kr_konfiguration.return_value = {
            "forretningsomraade": "pension"
        }

        # Mock JNPromptsBusinessComponent to return valid prompts
        mock_jn_prompts.return_value.hent_notat_prompts.return_value = (
            "Prompt til generering af notat",
            "gpt-4o",
            1,
            "Prompt til validering af notat",
            "gpt-4o-mini",
            2,
        )

        # Kald metoden
        output, _, _, notat_prompt_id, notat_val_prompt_id, forretningsomraade = (
            self.JNModel.predict(samtale=[], call_id=self.call_id, agent_id=self.agent_id)
        )

        # Forventet output
        forventet_output = (
            "Ingen samtale fundet. Journalnotat kan ikke genereres. Tjek lydindstillinger på PC."
        )
        self.assertEqual(
            output,
            forventet_output,
            f"Forventede: {forventet_output}, men fik: {output}",
        )

        self.assertIsNone(
            notat_prompt_id,
            f"Forventede at notat_prompt_id var None i fejlflow, men fik: {notat_prompt_id}",
        )

        self.assertIsNone(
            notat_val_prompt_id,
            f"Forventede at notat_val_prompt_id var None i fejlflow, men fik: {notat_val_prompt_id}",
        )

        self.assertEqual(
            forretningsomraade,
            "pension",
            f"Forventede forretningsomraade: pension, men fik: {forretningsomraade}",
        )
