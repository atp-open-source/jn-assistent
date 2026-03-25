from uuid import uuid4

from flask import current_app as flask_app, jsonify
from flask import render_template
from flask import request
from flask import g

from leverance.components.business.jn.jn_notat_business_component import (
    JNNotatBusinessComponent,
)
from leverance.components.business.jn.jn_notat_feedback_business_component import (
    JNNotatFeedbackBusinessComponent,
)
from leverance.components.interaction.website.blueprints.jn import interaction_bp
from leverance.components.interaction.website.site_authentication import (
    auth_required,
    auth_required_site,
)

# Mapping af AD-grupper til ordninger
AD_GROUP_TO_ORDNING = {
    "JN_notatoverblik": ["alle_ordninger"],
    "Dataengineer_DFD": ["alle_ordninger"],
    "Dataanalyst_DFD": ["alle_ordninger"],
    "Kundeansvarlig_DFD": ["alle_ordninger"],
    "JN_notatoverblik_PEN": ["pension", "pension_test_1", "pension_test_2"],
    "JN_notatoverblik_FY": ["fy"],
    "JN_notatoverblik_BA": ["ba"],
    "JN_notatoverblik_BO": ["bo"],
}


def get_ordning_from_ad_groups(ad_groups):
    """
    Hjælpefunktion til at udlede ordninger baseret på AD-grupper.
    """
    # Normalisér input til liste af strings
    groups = ad_groups or []

    ordninger = []
    for g in groups:
        ordninger.extend(AD_GROUP_TO_ORDNING.get(g, []))
    return ordninger if ordninger else [""]


def fetch_notat_data(dagens_historik=True, ordning_list=None):
    """
    Henter data fra jn.notat og kombinerer med feedback fra jn.notat_feedback.
    """
    # Initialisér komponenter
    notatComponent = JNNotatBusinessComponent(
        request_uid=uuid4(), config_name=flask_app.config["SPARK_config"]
    )
    feedbackComponent = JNNotatFeedbackBusinessComponent(
        request_uid=uuid4(), config_name=flask_app.config["SPARK_config"]
    )

    # Hent notater
    notat_result = notatComponent.hent_alle_notater(
        dagens_historik=dagens_historik, ordning_list=ordning_list
    )
    notat_data = [
        {
            "call_id": row.call_id,
            "koe": row.queue,
            "kr_initialer": row.kr_initialer,
            "notat": row.notat,
            "ordning": row.ordning,
            "load_time": row.load_time,
        }
        for row in notat_result
    ]

    # Hent feedback
    feedback_result = feedbackComponent.hent_feedback()
    feedback_data = [
        {
            "call_id": row.call_id,
            "kr_initialer": row.agent_id,
            "feedback": row.feedback,
            "rating": row.rating,
            "benyttet": row.benyttet,
            "load_time": row.load_time,
        }
        for row in feedback_result
    ]

    # Kombinér notater og feedback
    for notat in notat_data:
        feedback_entry = next(
            (f for f in feedback_data if f["call_id"] == notat["call_id"]), None
        )
        if feedback_entry:
            notat["feedback"] = feedback_entry["feedback"]
            notat["rating"] = feedback_entry["rating"]
            notat["benyttet"] = feedback_entry["benyttet"]
        else:
            notat["feedback"] = None
            notat["rating"] = -1
            notat["benyttet"] = None

    return notat_data


@interaction_bp.route("/notat_oversigt", methods=["GET", "POST"])
@auth_required(
    ad_group=flask_app.config["JN_INTERACTION_READ_AD"],
    site_title=flask_app.config["JN_INTERACTION_TITLE"],
    app=flask_app,
)
def notat_oversigt():
    """
    Denne metode kaldes, når ovenstående URL tilgås med en HTTP GET eller HTTP POST.
    Den henter alle notater og renderer dem i 'forside.html.jinja' skabelonen.
    """
    ordning_list = ["alle_ordninger"]
    dagens_historik = request.args.get("dagens_historik", "true").lower() == "true"
    notat_data = fetch_notat_data(
        dagens_historik=dagens_historik, ordning_list=ordning_list
    )
    return render_template(
        "forside.html.jinja", args=notat_data, dagens_historik=dagens_historik
    )


@interaction_bp.route("/notat_oversigt_fe", methods=["GET", "POST"])
@auth_required_site(
    ad_group=flask_app.config["JN_NOTATER_READ_AD"],
    app=flask_app,
)
def notat_oversigt_fe():
    """
    Denne metode kaldes, når ovenstående URL tilgås med en HTTP GET eller HTTP POST.
    Den henter alle notater fra jn.notat og feedback fra jn.notat_feedback og returnerer dem som JSON.

    Notat_data er betinget af AD-grupperne for brugeren, dvs. kun notater for de ordninger,
    som brugeren har adgang til, returneres.
    """
    ad_groups = getattr(g, "ad_groups", [])
    ordning_list = get_ordning_from_ad_groups(ad_groups)
    dagens_historik = request.args.get("dagens_historik", "true").lower() == "true"
    notat_data = fetch_notat_data(
        dagens_historik=dagens_historik, ordning_list=ordning_list
    )
    response_data = {
        "notater": notat_data,
    }
    return jsonify(response_data)
