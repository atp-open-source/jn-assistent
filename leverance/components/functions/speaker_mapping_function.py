def speaker_mapping(speaker) -> str:
    """
    Laver en mapping af talere til deres respektive danske navne.
    """
    return {
        "agent": "Kunderådgiver",
        "caller": "Borger/fuldmagtshaver/hjælper",
    }[speaker]
