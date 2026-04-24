import time

from flask import Response, jsonify, request
from flask import current_app as flask_app

from leverance.components.business.jn.jn_config_business_component import (
    JNConfigBusinessComponent,
)
from leverance.components.business.jn.jn_controller_business_component import (
    JNControllerBusinessComponent,
)
from leverance.components.business.jn.jn_model_business_component import (
    JNModelBusinessComponent,
)
from leverance.components.business.jn.jn_notat_business_component import (
    JNNotatBusinessComponent,
)
from leverance.components.business.jn.jn_notat_feedback_business_component import (
    JNNotatFeedbackBusinessComponent,
)
from leverance.components.business.jn.jn_prompts_business_component import (
    JNPromptsBusinessComponent,
)
from leverance.components.business.jn.jn_samtale_business_component import (
    JNSamtaleBusinessComponent,
)
from leverance.components.business.jn.jn_storage_account_business_component import (
    JNStorageAccountBusinessComponent,
)
from leverance.components.interaction.webservice.blueprints.jn import bp

#####################################################################################
### Routes for API'et der bliver kaldt af JN
#####################################################################################


@bp.route("/fetch_status", methods=["GET"])
def fetch_status() -> tuple[Response | str, int]:
    """
    Metoden bliver kaldt når ovenstående URL bliver kaldt med en HTTP GET. Henter
    kr_initialer og returnerer en HTTP 400 hvis noget mangler.
    Herefter kaldes status-køen i Azure Queue for kunderådgiveren og status for seneste
    opkald returneres herfra.
    """
    try:
        kr_initialer = request.args.get("kr_initialer")

        if not kr_initialer:
            return jsonify(msg="kr_initialer mangler"), 400

    except Exception as e:
        # Svarer med http statuskode 400, hvis anmodningen fejler
        flask_app.logger.exception(f"Dårlig anmodning. Fejl: {e!s}")
        return jsonify(msg="Dårlig anmodning"), 400

    status = JNNotatBusinessComponent(
        request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
    ).hent_opkald_status(
        kr_initialer=kr_initialer,
    )

    # Pak respons fra komponenten ind i et JSON objekt
    data = {
        "Status": status,
    }
    return jsonify(data), 200


@bp.route("/get_notat", methods=["GET"])
def get_notat() -> tuple[Response | str, int]:
    """
    Metoden bliver kaldt når ovenstående URL bliver kaldt med en HTTP GET. Givet
    kunderådgivers initialer hentes nyeste notat fra tabellen jn.notat på
    kunderådgiver. Gives et call-id hentes notatet tilknyttet dette frem for det nyeste.
    Hvis et notat findes for de givne inputs returneres dette med en statuskode 200.
    Ellers returneres en statuskode 204 sammen med en fejlbesked.
    """
    # Hent kr_initialer fra GET anmodning
    if "kr_initialer" not in request.args:
        return jsonify(msg="400 - kr_initialer skal gives med"), 400
    kr_initialer = request.args.get("kr_initialer")

    # Hent call-id
    call_id = request.args.get("call_id")

    notat, fetched_call_id, status_kode = JNNotatBusinessComponent(
        request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
    ).hent_notat(
        kr_initialer=kr_initialer,
        call_id=call_id,
    )

    # Hvis call-id oprindeligt var None, overskriv med call-id for nyeste notat
    call_id = call_id if call_id else fetched_call_id

    return jsonify({"notat": notat, "call_id": call_id}), status_kode


@bp.route("/process_call", methods=["GET"])
def process_call() -> Response | tuple[Response, int]:
    """
    Metoden bliver kaldt, når call-id modtages fra transcriberen.
    Følgende sker, når metoden kaldes:

        1. Call-id hentes

        2. read_and_sort_messages metoden kaldes:

            i.  Beskederne (i json-format) med sætninger og start/end-call hentes.
                Der oprettes en Blob-klient, som læser indholdet af den blob, der
                relaterer sig til det pågældende call-id.
                Blobbens indhold opdeles i individuelle beskeder.

            ii.  Udtrækker call-id, agent-id, kø-id og cpr-nr fra beskederne.

            iii. Sorterer beskederne ud fra timestamp og samler beskederne til en samtale,
                 som forventes af modellen


        3. Den transskriberede samtale samt prompt sendes til ChatGPT, som genererer og validerer et
           journalnotat.

        4. Det genererede journalnotat gemmes i jn.notat tabellen.

        5. Der sendes "end-summary" til status-køen i Azure Queue Storage.

        6. Den transskriberede samtale gemmes i jn.samtale tabellen.

        7. Hvis modellen ikke har fejlet, evalueres og logges diagnosticering af det genererede
           journalnotat.
    """
    # Hent call-id fra anmodning
    call_id = request.args.get("call_id", type=str)

    if not call_id:
        flask_app.logger.error("Call-id findes ikke")
        return (
            jsonify(msg="400 - Dårlig anmodning, call-id mangler"),
            400,
        )

    try:
        start_total = time.time()

        # Initialisér Controller
        controller = JNControllerBusinessComponent(
            request.uid, config_name=flask_app.config["SPARK_config"]
        )

        # Processér beskeder og returnér variabler, som forventes af modellen
        service_logger = controller.service_logger
        start_read = time.time()
        agent_id, koe_id, cpr, samtale = controller.read_and_sort_messages(call_id)

        end_read = time.time()
        service_logger.service_info(
            controller,
            f"[Timing] read_and_sort_messages tog {end_read - start_read:.2f} sekunder",
            call_id=call_id,
            process_time=end_read - start_read,
        )

        # Initialisér model og generér journalnotat
        start_predict = time.time()
        model = JNModelBusinessComponent(request.uid, config_name=flask_app.config["SPARK_config"])
        (
            journalnotat,
            formatted_samtale,
            results_dict,
            notat_prompt_id,
            notat_val_prompt_id,
            forretningsomraade,
        ) = model.predict(samtale, call_id, agent_id)

        end_predict = time.time()
        service_logger.service_info(
            model,
            f"[Timing] model.predict tog {end_predict - start_predict:.2f} sekunder",
            call_id=call_id,
            process_time=end_predict - start_predict,
        )

        # Gem journalnotat
        start_save_notat = time.time()
        notat_component = JNNotatBusinessComponent(
            request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
        )
        notat_component.gem_notat(
            call_id=call_id,
            cpr=cpr,
            genererings_prompt_id=notat_prompt_id,
            validerings_prompt_id=notat_val_prompt_id,
            queue=koe_id,
            kr_initialer=agent_id,
            forretningsomraade=forretningsomraade,
            notat=journalnotat,
        )

        end_save_notat = time.time()
        service_logger.service_info(
            notat_component,
            f"[Timing] gem_notat tog {end_save_notat - start_save_notat:.2f} sekunder",
            call_id=call_id,
            process_time=end_save_notat - start_save_notat,
        )

        # Send end-summary
        start_notify = time.time()
        controller.azure_notify_status(agent_id, call_id, status="end-summary")

        end_notify = time.time()
        service_logger.service_info(
            controller,
            f"[Timing] notify_status tog {end_notify - start_notify:.2f} sekunder",
            call_id=call_id,
            process_time=end_notify - start_notify,
        )

        # Gem samtale mellem kunderådgiver og borger i jn.samtale
        start_save_samtale = time.time()
        samtale_component = JNSamtaleBusinessComponent(
            request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
        )
        samtale_component.gem_samtale(
            call_id=call_id,
            cpr=cpr,
            queue=koe_id,
            kr_initialer=agent_id,
            samtale=samtale,
        )

        end_save_samtale = time.time()
        service_logger.service_info(
            samtale_component,
            f"[Timing] gem_samtale tog {end_save_samtale - start_save_samtale:.2f} sekunder",
            call_id=call_id,
            process_time=end_save_samtale - start_save_samtale,
        )

        # Evaluér og log diagnosticering af det genererede journalnotat
        # OBS: Evaluering benyttes ikke lige nu. Kan være det skal bruges i Fase 3.
        # Den tages stilling til i US 685196, derfor er variablen eval sat til False.
        eval = False
        if model.har_fejlet is False and eval is True:
            start_eval = time.time()
            model.evaluate_model(call_id, results_dict, formatted_samtale)
            end_eval = time.time()
            service_logger.service_info(
                model,
                f"[Timing] evaluate_model tog {end_eval - start_eval:.2f} sekunder",
                call_id=call_id,
                process_time=end_eval - start_eval,
            )

        end_total = time.time()
        service_logger.service_info(
            controller,
            f"[Timing] TOTAL process_call tog {end_total - start_total:.2f} sekunder",
            call_id=call_id,
            process_time=end_total - start_total,
        )

        return jsonify(msg="Journalnotat dannet og gemt"), 200

    except Exception as e:
        service_logger.service_exception(controller, f"Der opstod en fejl i process_call: {e!s}")
        return jsonify(msg=f"Der opstod en fejl i process_call: {e!s}"), 500


@bp.route("/feedback", methods=["POST"])
def feedback() -> tuple[Response, int]:
    """
    Metoden bliver kaldt når ovenstående URL bliver kaldt med en HTTP POST. Metoden
    gemmer kunderådgivers feedback og feedback for det pågældende journalnotat.
    """
    try:
        # Hent data fra request
        data = request.get_json()
        call_id = data.get("call_id")
        agent_id = data.get("agent_id")
        feedback = data.get("feedback", "")
        rating = data.get("rating", -1)
        benyttet = data.get("benyttet")
    except Exception as e:
        flask_app.logger.exception(f"Fejl i hentning af feedback fra anmodning: {e!s}")
        return jsonify(msg="400 - Dårlig anmodning"), 400

    # Gem feedback i jn.notat_feedback
    status = JNNotatFeedbackBusinessComponent(
        request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
    ).gem_feedback(
        call_id=call_id,
        agent_id=agent_id,
        feedback=feedback,
        rating=rating,
        benyttet=benyttet,
    )
    if status == 0:
        return jsonify(msg="Feedback gemt"), 200
    else:
        return jsonify(msg="500 - Intern serverfejl"), 500


@bp.route("/get_config", methods=["GET"])
def get_config() -> tuple[Response, int]:
    """
    Metoden kaldes når audiostreameren startes. Henter konfiguration for en specificeret
    kunderådgiver.
    """
    # Forsøg at udhente kr_initialer fra anmodning
    kr_initialer = request.args.get("kr_initialer", None)
    if not kr_initialer:
        return jsonify(msg="400 - Dårlig anmodning, kr_initialer skal gives med."), 400

    # Hent konfiguration for kunderådgiver
    try:
        konfiguration = JNConfigBusinessComponent(
            request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
        ).hent_kr_konfiguration(kr_initialer)
        return jsonify(konfiguration), 200
    except Exception as e:
        flask_app.logger.exception(
            f"Fejl i udhentning af konfiguration for kunderådgiver {kr_initialer}: {e!s}"
        )


@bp.route("/insert_config", methods=["POST"])
def insert_config() -> tuple[Response, int]:
    """
    Metode til at indsætte en ny konfiguration i jn.config tabellen for en kunderådgiver.
    """
    try:
        # Hent data fra request
        data = request.get_json()
        chatgpt_version = data.get("chatgpt_version")
        forretningsomraade = data.get("forretningsomraade")
        kr_initialer = data.get("kr_initialer")
        miljoe = data.get("miljoe")
        streamer_version = data.get("streamer_version")
        transcriber_version = data.get("transcriber_version")
        controller_version = data.get("controller_version")
    except Exception as e:
        flask_app.logger.exception(f"Fejl i hentning af konfiguration fra anmodning: {e!s}")
        return jsonify(msg="400 - Dårlig anmodning"), 400

    # Indsæt konfiguration for kunderådgiver
    msg, status = JNConfigBusinessComponent(
        request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
    ).indsaet_kr_konfiguration(
        chatgpt_version,
        controller_version,
        forretningsomraade,
        kr_initialer,
        miljoe,
        streamer_version,
        transcriber_version,
    )
    return jsonify(msg=msg), status


@bp.route("/delete_config", methods=["GET"])
def delete_config() -> tuple[Response, int]:
    """
    Metode til at slette konfiguration for en kunderådgiver i jn.config tabellen.
    """
    # Forsøg at hente kr_initialer fra anmodning
    try:
        kr_initialer = request.args.get("kr_initialer", None)
    except Exception as e:
        flask_app.logger.exception(f"Fejl i hentning af konfiguration fra anmodning: {e!s}")
        return jsonify(msg="400 - Dårlig anmodning, kr_initialer skal gives med."), 400

    # Slet konfiguration for kunderådgiver
    status, konfiguration = JNConfigBusinessComponent(
        request_uid=request.uid, config_name=flask_app.config["SPARK_config"]
    ).slet_kr_konfiguration(kr_initialer)
    if status == 0:
        return jsonify(konfiguration), 200
    else:
        return jsonify(msg="500 - Intern serverfejl"), 500


@bp.route("/sta_credentials", methods=["GET"])
def sta_credentials() -> tuple[Response | str, int]:
    """
    Metoden bliver kaldt når ovenstående URL bliver kaldt med en HTTP GET.
    Opretter et nyt token til storage account for JN ved at anvende JNStorageAccountBusinessComponent.
    """
    try:
        # Anvender JNStorageAccountBusinessComponent til at generere token
        token = JNStorageAccountBusinessComponent(
            request.uid, config_name=flask_app.config["SPARK_config"]
        ).get_token()
        return jsonify(token), 200
    except Exception as e:
        flask_app.logger.exception(f"Fejl ved generering af token: {e!s}")
        return jsonify(msg="500 - Intern serverfejl"), 500


@bp.route("/get_prompt", methods=["GET"])
def get_prompt() -> tuple[Response | str, int]:
    """
    Metoden henter prompt(s) for en angiven ordning.
    """
    # Hent parametre fra forespørgslen
    ordning = request.args.get("forretningsomraade", "pension")

    # Hent prompt fra business component
    try:
        prompt = JNPromptsBusinessComponent(
            request.uid, config_name=flask_app.config["SPARK_config"]
        ).hent_notat_prompts(ordning)
        return jsonify(prompt), 200
    except Exception as e:
        flask_app.logger.exception(f"Fejl ved hentning af prompt(s) for ordning {ordning}: {e!s}")
        return jsonify(msg="500 - Intern serverfejl"), 500
