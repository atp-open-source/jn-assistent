import json


def parse_llm_json_response(response: str) -> dict:
    """
    Hjælpefunktion til at parse JSON-svar fra LLM.
    Håndterer markdown-kodeblokke og forsøger at extracte gyldig JSON.

    Args:
        response (str): Det rå svar fra LLM.

    Returns:
        dict: Det parsede JSON-svar som en dictionary.
    """
    # Hvis svaret indeholder markdown-kodeblokke, extract JSON
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()

    # Parse JSON-svar
    parsed_response = json.loads(response)

    return parsed_response
