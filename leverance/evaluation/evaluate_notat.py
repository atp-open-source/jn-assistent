import json, spacy
import os.path
from leverance.components.business.jn.jn_model_business_component import (
    JNModelBusinessComponent,
)
from jiwer import wer
import gc

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Forventet format for FILE_NAME_TEST_DATA - eksempel:
# {
#     "call_id_1": {
#         "endeligt_notat": "Her er et notat",
#         "samtale": [
#             {"speaker": "agent",
#              "sentence": "Hej"
#             },
#             {"speaker": "caller",
#              "sentence": "Hej"
#             }
#         ],
#         "daarligt_notat": "dårligt notat"
#     },
#     "call_id_2": {
#         "endeligt_notat": "Her er et andet notat",
#         "samtale": [
#             {"speaker": "agent",
#              "sentence": "Hej"
#             },
#             {"speaker": "caller",
#              "sentence": "Hej"
#             }
#         ],
#         "daarligt_notat": "dårligt notat"
#     }
# }
FILE_NAME_TEST_DATA = os.path.join(BASE_DIR, "data.json")

# Filnavn til gemte notater
FILE_NAME_NOTATER = os.path.join(BASE_DIR, "notater.json")


def get_min_max_mean(
    list: list[float],
) -> dict[str, float]:
    """
    Funktion til at finde min, max, mean af en liste
    """
    return {"min": min(list), "max": max(list), "mean": sum(list) / len(list)}


def remove_html_formatting(notat: str) -> str:
    """
    Fjerner html-formatering fra notat.
    """
    return (
        notat.replace("<br/><strong>VURDERING</strong><br/>-----<br/><br/>", "")
        .replace("<br/>", "\n")
        .replace("<strong>", "")
        .replace("</strong>", "")
        .strip()
    )


def generer_notater(
    model: JNModelBusinessComponent, prompt_strategy: str, eval_data: dict[str, dict]
) -> dict[str, dict[str, dict[str, str]]]:
    """
    Bruger JNModelBusinessComponent til at generere notater for test-samtaler med dens
    nuværende prompt-strategi samt scores for retningslinjer. For at teste forskellige
    prompt-strategier skal man ændre i predict-metoden i JNModelBusinessComponent
    og/eller de prompts, den bruger.

    Inputs:
        - model: modellen der kalder OpenAI og genererer notater.
        - prompt_strategy: navn på prompt-strategien, der testes. Gemmes sammen med \
            de genererede notater i en json-fil. Bruges ikke til andre formål, end at \
            man kan teste flere prompt-strategier uden at overskrive tidligere \
            resultater.
        - eval_data: dictionary med test-samtaler og guld-notater.
    Returns:
        - notater: dictionary med notater for hver test-samtale.
    """
    # Generer notater for test-samtaler med den prompt-strategi, der bruges af JNModelBusinessComponent
    notater = {prompt_strategy: {}}
    for call_id in eval_data.keys():
        notater[prompt_strategy][call_id] = {}
        notat, _, results_dict = model.predict(eval_data[call_id]["samtale"], "call_id")
        clean_notat = remove_html_formatting(notat)
        notater[prompt_strategy][call_id]["final_notat"] = clean_notat
        notater[prompt_strategy][call_id]["response_notat"] = results_dict[
            "response_notat"
        ]
        notater[prompt_strategy][call_id]["response_val_notat"] = results_dict[
            "response_val_notat"
        ]

    # Hvis der findes notater genereret med tidligere prompt-strategier, så indlæs dem
    if os.path.isfile(FILE_NAME_NOTATER):
        with open(FILE_NAME_NOTATER, "r") as json_file:
            tidligere_notater = json.load(json_file)
        tidligere_notater[prompt_strategy] = notater[prompt_strategy]
        notater = tidligere_notater

    with open(FILE_NAME_NOTATER, "w+") as json_file:
        json.dump(notater, json_file, indent=4)

    return notater


def score_notater(
    model: JNModelBusinessComponent,
    notater: dict[str, dict[str, dict[str, str]]],
    eval_data: dict[str, dict],
) -> None:
    """
    Udregner scores for de genererede test-notater. Der genereres i alt 7 scores:
        - score_retningslinjer_notat: score for overholdelse af retningslinjer i notat_prompt.txt.
        - score_retningslinjer_notat_val: score for overholdelse af retningslinjer i notat_val_prompt.txt.
        - score_hallucination: score for graden af hallucination i det genererede notat.
        - score_samtale_kvalitet: score for kvaliteten af den transskriberede samtalen.
        - score_kvalitet: score for kvaliteten af det genererede notat.
        - wer: Word Error Rate mellem guld-notat og det genererede notat.
        - sentence_similarity: Cosine similarity mellem guld-notat og det genererede notat.

    Hvert notat får en score på 1-5 for de 5 første evalueringsprompts, hvor 5 er bedst.
    Word Error Rate er en float mellem 0 og uendelig, hvor 0 er bedst.
    Sentence similarity er en float mellem 0 og 1, hvor 1 er bedst.

    Inputs:
        - model: modellen, der kalder OpenAI og genererer scores.
        - notater: dictionary med notater for hver test-samtale.
        - eval_data: dictionary med test-samtaler, guld-notater og dårlige notater.
    """

    # Indlæs prompts til at evaluere de genererede notater
    with open(
        os.path.join(BASE_DIR, "prompts", "kvalitet_prompt_offline.txt"), "r"
    ) as file:
        prompt_kvalitet = file.read()

    # Definer keys og labels for scores
    keys_and_labels = [
        ("response_notat_retningslinjer", "retningslinjer, notat_prompt"),
        ("response_val_notat_retningslinjer", "retningslinjer, notat_val_prompt"),
        ("response_hallucination", "hallucination"),
        ("samtale_kvalitet", "samtale_kvalitet"),
        ("score_kvalitet_offline", "notat_kvalitet"),
        ("wer", "Word Error Rate"),
        ("sentence_similarity", "Sentence Similarity"),
    ]
    # Generér scores for de generede notater
    for prompt_strategi in notater.keys():
        print(f"\nEvaluerer notater lavet med {prompt_strategi} prompt strategien.\n")
        for call_id in eval_data.keys():
            # Hvis der ikke findes et genereret notat på test-samtalen, så skip til næste test-samtale
            if call_id not in notater[prompt_strategi].keys():
                continue

            # Retningslinjer, hallucination og samtale_kvalitet
            formatted_samtale = model.text_processor.preprocess(
                eval_data[call_id]["samtale"]
            )
            results_dict = model.evaluate_model(
                call_id,
                notater[prompt_strategi][call_id],
                formatted_samtale=formatted_samtale,
            )

            # Kvalitet af det genererede notat
            notat = notater[prompt_strategi][call_id]["final_notat"]
            results_dict["score_kvalitet_offline"], _, _, _, _ = model._prompt_llm(
                model.llm,
                prompt_kvalitet.format(
                    samtale=eval_data[call_id]["samtale"],
                    guld_notat=eval_data[call_id]["endeligt_notat"],
                    daarligt_notat=eval_data[call_id]["daarligt_notat"],
                ),
                notat,
                model.temperature,
                model.max_tokens,
                call_id,
            )

            # Gem prompt_scores i eval_data
            for key, _ in keys_and_labels[:-2]:
                eval_data[call_id][key] = json.loads(results_dict[key])["score"]

            # Word Error Rate
            eval_data[call_id]["wer"] = wer(eval_data[call_id]["endeligt_notat"], notat)

            # Sentence similarity (cosine similarity)
            nlp = spacy.load("da_core_news_lg")
            eval_data[call_id]["sentence_similarity"] = nlp(
                eval_data[call_id]["endeligt_notat"]
            ).similarity(nlp(notat))

            # Fjerner spacy model fra memory
            del nlp
            gc.collect()

        for key, label in keys_and_labels:
            scores = [
                float(entry[key]) for entry in eval_data.values() if key in entry.keys()
            ]
            min_max_mean = get_min_max_mean(scores)
            print(f"Resultater for {label} \n{'='*25}")
            print(f"{key}:", min_max_mean, scores)


def main() -> None:
    # Initialisér model
    request_uid = "test"
    model = JNModelBusinessComponent(request_uid=request_uid)

    # Load test-samtaler + guld-notater
    with open(FILE_NAME_TEST_DATA, "r", encoding="utf-8") as json_file:
        eval_data = json.load(json_file)

    print("Genererer notater")
    notater = generer_notater(model, "baseline", eval_data)
    score_notater(model, notater, eval_data)


if __name__ == "__main__":
    main()
