import concurrent.futures
import json
import os
import time
from typing import Any
from uuid import UUID

from flask import current_app as flask_app
from openai import AzureOpenAI

from aiservice.openai_assistant import OpenAIAssistant
from leverance.components.business.jn.jn_config_business_component import (
    JNConfigBusinessComponent,
)
from leverance.components.business.jn.jn_prompts_business_component import (
    JNPromptsBusinessComponent,
)
from leverance.components.business.jn.jn_text_processor_business_component import (
    JNTextProcessorBusinessComponent,
)
from leverance.components.functions.llm_helper import parse_llm_json_response
from leverance.core.common.azure_helper import (
    get_auth_based_on_env,
    get_openai_config_based_on_env,
)
from leverance.core.logger_adapter import ServiceLoggerAdapter
from leverance.core.runners.service_runner import ServiceRunner


class JNModelBusinessComponent(ServiceRunner):
    """
    Denne Leverancekomponent opretter journalnotater på baggrund af samtaler mellem
    borger og kunderådgiver vha. ChatGPT 4o.
    """

    def __init__(self, request_uid: UUID, config_name=None) -> None:
        # Initialisér UID og servicenavn
        self.service_name = "jn"
        self.request_uid = request_uid
        super().__init__(self.service_name, self.request_uid, config_name=config_name)

        # Logger
        self.service_logger = ServiceLoggerAdapter(self.app.log)

        # Sti til filen
        self.script_dir = os.path.dirname(__file__)

        # Defaultværdier
        self.default_forretningsomraade = "standard"
        self.evaluering_prompts_dir = "evaluering"

        # Initialisér modelkonfigurationer for OpenAI LLM-modellen
        self.temperature = 0.0
        self.max_tokens = 2000
        self.max_retries = 5
        self.global_timeout = 30
        self.model_kald_timeout = 20

        # Fejlnotatsbesked
        self.fejl_notat = "Det lykkedes ikke at generere et journalnotat"

        # Status for om flowet har fejlet
        self.har_fejlet = False

        # Initialisér model
        self.llm = self._initialize_model()

        # Initialisér text-processor
        self.text_processor = JNTextProcessorBusinessComponent(self.request_uid, config_name)

    def _initialize_model(self) -> AzureOpenAI:
        """
        Genererer api-nøgle til Azure OpenAI og initialiserer GPT 4o-modellen ud fra
        .env-filen.
        """

        # Hent akkreditiver og API-nøgler
        try:
            authentication = get_auth_based_on_env(
                self.app,
                tenant_key_name="JN_AZURE_IDENTITY_TENANT_ID",
                client_key_name="JN_AZURE_IDENTITY_CLIENT_ID",
                secret_key_name="JN_AZURE_IDENTITY_CLIENT_SECRET",
            )
            endpoint, version, deployment = get_openai_config_based_on_env(
                self.app,
                endpoint_key_name="JN_AZURE_OPENAI_API_ENDPOINT",
                version_key_name="JN_AZURE_OPENAI_API_VERSION",
                deployment_key_name="JN_AZURE_OPENAI_DEPLOYMENT_NAME",
            )

        except Exception as e:
            self.service_logger.service_warning(
                self, f"Fejl i indhentning af akkreditiver eller API-nøgler: {e}"
            )
            raise

        # Initialisér model
        try:
            llm = OpenAIAssistant(
                authentication,
                azure_open_ai_api_endpoint=endpoint,
                azure_open_ai_api_version=version,
                prompt_model_deployment_name=deployment,
            )
            return llm
        except Exception as e:
            self.service_logger.service_warning(self, f"Fejl i initialisering af model: {e}")
            raise

    def _prompt_llm(
        self,
        llm: OpenAIAssistant,
        prompt: str,
        input: str,
        temperature: float,
        max_tokens: int,
        call_id: str,
        model: str = "gpt-4o",
    ) -> tuple[str, str, int, int, float]:
        """
        Kalder modellen og returnerer et formatteret svar.

        Der returneres en fejl ved følgende scenarier:
                - Modellen fejler gentagne gange (max_retries)
                - Modellen tager længere tid på et enkelt kald end den angivne timeout
                  (20 sekunder pr. forsøg) til at generere et svar
                - Modellen tager længere tid end det angivne globale timeout (30 sekunder)
                  på tværs af forsøg.

        Ved både at have et timeout per kald og et global timeout for alle kald,
        sikrer vi os, at modellen får spurgt mere end én gang, hvis første kald tager
        lang tid.
        """

        # Forbered systembeskeder og brugerbeskeder
        input_list = [
            {"content": prompt, "role": "system"},
            {"content": input, "role": "user"},
        ]

        # Kald model
        current_time_spent = 0
        generation_timer_start = time.time()

        for i in range(self.max_retries):
            # Opdatér time spent
            current_time_spent = time.time() - generation_timer_start

            # Break hvis global timeout er overskredet
            if current_time_spent > self.global_timeout:
                self.service_logger.service_warning(
                    self,
                    f"LLM timeoutede efter {self.global_timeout} sekunder for call-id: {call_id}",
                )
                break

            # Kald model
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        llm.prompt,
                        messages=input_list,
                        temperature=temperature,
                        model=model,
                        max_tokens=max_tokens,
                        stream=False,
                    )
                    response = future.result(timeout=self.model_kald_timeout)
                    generation_timer_stop = time.time()
                    return (
                        response.choices[0].message.content,
                        response.choices[0].finish_reason,
                        response.usage.completion_tokens,
                        response.usage.prompt_tokens,
                        generation_timer_stop - generation_timer_start,
                    )
            except concurrent.futures.TimeoutError:
                self.service_logger.service_warning(
                    self,
                    f"LLM kald timeoutede efter {self.model_kald_timeout} sekunder for call-id: {call_id}",
                )
                self.har_fejlet = True
                return self.fejl_notat, "", 0, 0, 0
            except Exception as e:
                self.service_logger.service_warning(
                    self,
                    f"Der opstod en fejl ved kald af LLM efter {i + 1} antal forsøg for call-id: {call_id}. Exception: {e!s}",
                )
                time.sleep(0.5)

        # Returnér hvis max-retries er overskredet eller timeout er overskredet
        self.har_fejlet = True
        return self.fejl_notat, "", 0, 0, 0

    def predict(
        self, samtale: list[dict[str, str]], call_id: str, agent_id: str
    ) -> tuple[str, str, dict[str, Any], int | None, int | None, str]:
        """
        Metoden modtager en samtale som input, der indeholder hhv. 'speaker' og 'text'.
        Speaker er enten kunderådgiver eller borger, og text er det som speakeren har
        sagt. Outputtet er en streng med journalnotatet, som er genereret ud fra
        samtalen mellem borger og kunderådgiver. Modeloutputtet bliver efterfølgende
        postprocesseret til html-format til visning på hjemmesiden for kunderådgiver.

        Argumenter:
            samtale (list): Liste af ordbøger med 'speaker' og 'text'.
            call_id (str): Unikt ID for samtalen.
            agent_id (str): ID for kunderådgiveren, som har haft samtalen.

        Returnerer:
            notat (str): Genereret journalnotat i html-format.
            samtale (str): Samtalen som en enkelt streng.
            results_dict (dict): Dictionary med detaljer om modelkald og evalueringer.
            notat_prompt_id (int | None): ID for prompten brugt til at generere notatet.
            notat_val_prompt_id (int | None): ID for prompten brugt til at validere notatet.
            forretningsomraade (str): Forretningsområde for kunderådgiveren.
        """

        # Hent kunderådgiverens konfiguration for at indlæse prompts
        konfiguration = {}
        try:
            konfiguration = JNConfigBusinessComponent(
                request_uid=self.request_uid,
                config_name=flask_app.config["SPARK_CONFIG"].NAME,
            ).hent_kr_konfiguration(agent_id)
        except Exception:
            self.service_logger.service_warning(
                self,
                f"Kunne ikke hente konfiguration for kunderådgiver {agent_id}, bruger standardværdier.",
            )

        # Hent forretningsomraade fra konfigurationen eller brug defaultværdi
        forretningsomraade = konfiguration.get(
            "forretningsomraade", self.default_forretningsomraade
        )
        if forretningsomraade.strip() == "":
            self.service_logger.service_info(
                self,
                f"Forretningsområde er ikke angivet for kunderådgiver {agent_id}, bruger default forretningsområde '{self.default_forretningsomraade}'.",
            )
            forretningsomraade = self.default_forretningsomraade

        self.service_logger.service_info(
            self,
            f"Forretningsområde for kunderådgiver {agent_id} for call-id {call_id}: '{forretningsomraade}'",
        )

        # Hent prompts for det angivne forretningsområde
        try:
            (
                notat_prompt,
                notat_model,
                notat_prompt_id,
                notat_val_prompt,
                notat_val_model,
                notat_val_prompt_id,
            ) = JNPromptsBusinessComponent(
                request_uid=self.request_uid,
                config_name=flask_app.config["SPARK_CONFIG"].NAME,
            ).hent_notat_prompts(forretningsomraade)
        except Exception:
            self.service_logger.service_warning(
                self,
                f"Kunne ikke hente prompts for kunderådgiver {agent_id} i forretningsområde {forretningsomraade} for call-id {call_id}.",
            )
            self.har_fejlet = True
            return (
                f"Kunne ikke hente prompts for forretningsområde '{forretningsomraade}'. Journalnotat kan ikke genereres.",
                "",
                {},
                None,
                None,
                forretningsomraade,
            )

        # Initialisér dictionary til logging
        results_dict = {}

        # Check om samtalen er tom
        if not samtale:
            self.service_logger.service_warning(
                self,
                f"Fejl i generering af notat. Samtalen for call-id '{call_id}' er tom.",
            )
            self.har_fejlet = True
            return (
                "Ingen samtale fundet. Journalnotat kan ikke genereres. Tjek lydindstillinger på PC.",
                "",
                {},
                None,
                None,
                forretningsomraade,
            )

        # Konvertér fra liste til streng
        samtale = self.text_processor.preprocess(samtale)

        self.service_logger.service_info(
            self,
            json.dumps({"call_id": call_id, "samtale": samtale}),
        )

        # Justér notatprompten hvis forretningsområdet er pension_test_2
        # Hvis det besluttes at denne prompt ikke skal bruges, så skal dette
        # slettes igen.
        if forretningsomraade == "pension_test_2":
            # Beregn antal tokens i samtalen
            try:
                # Lazy import for at undgå unødvendig afhængighed hvis ikke brugt
                import tiktoken

                enc = tiktoken.encoding_for_model(notat_model)
                samtale_tokens = len(enc.encode(samtale))
            except Exception:
                samtale_tokens = 0
            # Indsæt antal tokens i prompten
            notat_prompt_fmt = notat_prompt.replace("[[samtale_tokens]]", str(samtale_tokens))
        else:
            notat_prompt_fmt = notat_prompt

        # Prompt modellen på hele samtalen
        (
            results_dict["response_notat"],
            results_dict["finish_reason_notat"],
            results_dict["tokens_used_notat"],
            results_dict["prompt_tokens_used_notat"],
            results_dict["generation_time_notat"],
        ) = self._prompt_llm(
            self.llm,
            notat_prompt_fmt,
            samtale,
            self.temperature,
            self.max_tokens,
            call_id,
            notat_model,
        )
        if self.har_fejlet is True:
            return (
                results_dict["response_notat"],
                "",
                {},
                None,
                None,
                forretningsomraade,
            )

        # Validér notatet
        (
            results_dict["response_val_notat"],
            results_dict["finish_reason_val_notat"],
            results_dict["tokens_used_val_notat"],
            results_dict["prompt_tokens_used_val_notat"],
            results_dict["generation_time_val_notat"],
        ) = self._prompt_llm(
            self.llm,
            notat_val_prompt,
            results_dict["response_notat"],
            self.temperature,
            self.max_tokens,
            call_id,
            notat_val_model,
        )

        # Tilføj call_id til results_dict for logging
        results_dict["call_id"] = call_id

        # Log tokens seperat fra notatet da vi gerne må gemme dem i mere end 2 måneder
        log_data_tokens = {
            "call_id": call_id,
            "tokens_used_notat": results_dict["tokens_used_notat"],
            "generation_time_notat": results_dict["generation_time_notat"],
            "tokens_used_val_notat": results_dict["tokens_used_val_notat"],
            "generation_time_val_notat": results_dict["generation_time_val_notat"],
        }
        self.service_logger.service_info(self, json.dumps(log_data_tokens, ensure_ascii=False))

        # Log notat og validerings notat seperat da vi ikke må gemme dem i mere end 2 måneder
        log_data_notat = {
            "call_id": call_id,
            "response_notat": results_dict["response_notat"],
            "response_val_notat": results_dict["response_val_notat"],
        }

        self.service_logger.service_info(self, json.dumps(log_data_notat, ensure_ascii=False))

        if self.har_fejlet is True:
            return (
                results_dict["response_val_notat"],
                "",
                {},
                None,
                None,
                forretningsomraade,
            )

        self.service_logger.service_info(
            self,
            f"Generering og validering af journalnotat med GPT for call-id: {call_id} tog {results_dict['generation_time_notat'] + results_dict['generation_time_val_notat']:.2f} sekunder",
        )

        # Forsøg at formatere notat
        try:
            notat_dict = parse_llm_json_response(results_dict["response_val_notat"])
        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"LLM'en genererede ikke journalnotatet i korrekt JSON-format for call-id: {call_id}. Exception: {e}, LLM output: {results_dict['response_val_notat']}",
            )
            self.har_fejlet = True
            return self.fejl_notat, "", {}, None, None, forretningsomraade

        # Formatér output
        response_opl = self.text_processor.format_sentences(notat_dict["oplysninger"])
        response_stat = self.text_processor.format_sentences(notat_dict["status"])

        # Formatér journalnotat til html som påkrævet for visning på hjemmesiden
        oplysninger = self.text_processor.postprocess(response_opl, "OPLYSNINGER")
        status = self.text_processor.postprocess(response_stat, "STATUS")
        stamp = self.text_processor.add_stamp()

        # Kombinér svar til endeligt journalnotat
        notat = oplysninger + status + stamp

        # Fjern uønskede tegn fra notatet
        notat_clean = self.text_processor.clean_notat(notat)

        return (
            notat_clean,
            samtale,
            results_dict,
            notat_prompt_id,
            notat_val_prompt_id,
            forretningsomraade,
        )

    def evaluate_model(
        self, call_id: str, results_dict: dict[str, Any], formatted_samtale: str
    ) -> dict[str, Any]:
        """
        Metode til at evaluere og logge diagnosticeringer af jouralnotatet.
        """
        # Hent evalueringsprompts fra jn.prompts
        try:
            (
                retningslinjer_notat_prompt,
                retningslinjer_notat_val_prompt,
                hallucination_prompt,
                samtale_kvalitet_prompt,
                retningslinjer_notat_model,
                retningslinjer_notat_val_model,
                hallucination_model,
                samtale_kvalitet_model,
            ) = JNPromptsBusinessComponent(
                request_uid=self.request_uid,
                config_name=flask_app.config["SPARK_CONFIG"].NAME,
            ).hent_eval_prompts()
        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"Kunne ikke hente evalueringsprompts for call-id: {call_id}: {e}",
            )

        # 1. Evaluér overholdelse af retningslinjer for response_notat
        response_notat_retningslinjer, _, _, _, _ = self._prompt_llm(
            self.llm,
            retningslinjer_notat_prompt.format(
                samtale=formatted_samtale,
                system_prompt=retningslinjer_notat_prompt,
            ),
            results_dict["response_notat"],
            self.temperature,
            self.max_tokens,
            call_id,
            model=retningslinjer_notat_model,
        )

        # Forsøg at parse JSON-svar
        try:
            results_dict["response_notat_retningslinjer"] = parse_llm_json_response(
                response_notat_retningslinjer
            )
        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"LLM'en genererede ikke evalueringen af retningslinjer for journalnotatet i korrekt JSON-format for call-id: {call_id}. Exception: {e}, LLM output: {response_notat_retningslinjer}",
            )
            self.har_fejlet = True
            return self.fejl_notat, "", {}

        # 2. Evaluér overholdelse af retningslinjer for response_val_notat
        (
            response_val_notat_retningslinjer,
            _,
            _,
            _,
            _,
        ) = self._prompt_llm(
            self.llm,
            retningslinjer_notat_val_prompt.format(
                samtale=formatted_samtale,
                system_prompt=retningslinjer_notat_val_prompt,
                journalnotat=results_dict["response_val_notat"],
            ),
            results_dict["response_val_notat"],
            self.temperature,
            self.max_tokens,
            call_id,
            model=retningslinjer_notat_val_model,
        )

        # Forsøg at parse JSON-svar
        try:
            results_dict["response_val_notat_retningslinjer"] = parse_llm_json_response(
                response_val_notat_retningslinjer
            )
        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"LLM'en genererede ikke evalueringen af retningslinjer for valideringen af journalnotatet i korrekt JSON-format for call-id: {call_id}. Exception: {e}, LLM output: {response_val_notat_retningslinjer}",
            )
            self.har_fejlet = True
            return self.fejl_notat, "", {}

        # 3. Evaluér for hallucinationer
        response_hallucination, _, _, _, _ = self._prompt_llm(
            self.llm,
            hallucination_prompt.format(
                samtale=formatted_samtale,
                system_prompt=hallucination_prompt,
            ),
            results_dict["response_val_notat"],
            self.temperature,
            self.max_tokens,
            call_id,
            model=hallucination_model,
        )

        # Forsøg at parse JSON-svar
        try:
            results_dict["response_hallucination"] = parse_llm_json_response(response_hallucination)
        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"LLM'en genererede ikke evalueringen af hallucinationer i journalnotatet i korrekt JSON-format for call-id: {call_id}. Exception: {e}, LLM output: {response_hallucination}",
            )
            self.har_fejlet = True
            return self.fejl_notat, "", {}

        # 4. Evaluér kvalitet af den transskriberede samtale
        samtale_kvalitet, _, _, _, _ = self._prompt_llm(
            self.llm,
            samtale_kvalitet_prompt,
            formatted_samtale,
            self.temperature,
            self.max_tokens,
            call_id,
            model=samtale_kvalitet_model,
        )

        # Forsøg at parse JSON-svar
        try:
            results_dict["samtale_kvalitet"] = parse_llm_json_response(samtale_kvalitet)
        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"LLM'en genererede ikke evalueringen af kvaliteten af den transskriberede samtale for journalnotatet i korrekt JSON-format for call-id: {call_id}. Exception: {e}, LLM output: {samtale_kvalitet}",
            )
            self.har_fejlet = True
            return self.fejl_notat, "", {}

        # Log evaluering plus diagnostics for det genererede journalnotat
        results_dict["call_id"] = call_id
        self.service_logger.service_info(self, json.dumps(results_dict, ensure_ascii=False))

        return results_dict
