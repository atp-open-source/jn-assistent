# Vores load-test bruger CoRaL-datasættet som testdata
# @dataset{coral2024,
#   author    = {Dan Saattrup Nielsen, Sif Bernstorff Lehmann, Simon Leminen Madsen, Anders Jess Pedersen, Anna Katrine van Zee and Torben Blach},
#   title     = {CoRal: A Diverse Danish ASR Dataset Covering Dialects, Accents, Genders, and Age Groups},
#   year      = {2024},
#   url       = {https://hf.co/datasets/alexandrainst/coral},
# }

import os

import numpy as np
import scipy.io
from datasets import Audio, load_dataset


def save_coral_to_wav(
    path: str,
    name_prefix: str = "coral_audio",
    len_seconds: int = 30,
    silence=0,
    noise=0,
    hf_token: str | None = None,
    split: str = "test",
    n_take: int = 10,
    sampling_rate_hz: int = 16000,
) -> None:
    """
    Hjælpefunktion til at gemme lydfiler fra Coral-datasættet i WAV-format.

    Argumenter:
        path (str): Stien hvor lydfilerne skal gemmes.
        name_prefix (str): Præfiks for lydfilnavne.
        len_seconds (int): Længde i sekunder for de lydfiler der skal gemmes.
        silence (int): Antal sekunder stilhed der skal tilføjes mellem lydfilerne.
        noise (float): Støjniveau der skal tilføjes til lydfilerne (for at undgå perfekt stilhed)
        hf_token (str | None): Hugging Face token til adgang til datasættet.
        split (str): Datasæt split at bruge (f.eks. "train", "val", "test").
        n_take (int): Max antal samples at tage fra datasættet.
        sampling_rate_hz (int): Sampling rate i Hz for lydfilerne.
    """

    # Load dataset
    coral = load_dataset(
        "alexandrainst/coral",
        "read_aloud",
        split=split,
        streaming=True,
        token=hf_token,
    )

    coral = coral.cast_column("audio", Audio(sampling_rate=sampling_rate_hz))

    # Hent lydfiler
    samples = coral.take(n_take)

    # Saml alle lydfiler i et enkelt array med stilhed imellem hver lydfil, samt i
    # starten og slutningen
    audio = np.concatenate(
        [
            np.concatenate(
                [
                    np.zeros(
                        (int(silence * sampling_rate_hz),),
                        dtype=sample["audio"]["array"].dtype,
                    ),
                    sample["audio"]["array"],
                ]
            )
            for sample in samples
        ]
    )
    audio = np.concatenate(
        [
            audio,
            np.zeros((int(silence * sampling_rate_hz),), dtype=audio.dtype),
        ]
    )

    # Tilføj støj hvis angivet
    if noise > 0:
        np.random.seed(42)
        audio += np.random.normal(0, noise, audio.shape)

    # Klip audio til den ønskede længde og konvertér til int16
    audio_len = min(int(sampling_rate_hz * len_seconds), len(audio))
    audio_chunk = audio[:audio_len]
    audio_chunk = np.clip(audio_chunk, -1.0, 1.0)
    audio_chunk = (audio_chunk * np.iinfo(np.int16).max).astype(np.int16)

    # Opret sti hvis den ikke findes
    os.makedirs(path, exist_ok=True)

    # Gem til WAV-fil
    file_name = f"{name_prefix}_{len_seconds}.wav"
    file_path = os.path.join(path, file_name)
    scipy.io.wavfile.write(file_path, sampling_rate_hz, audio_chunk)
    print(f"Gemt {file_name}")


def main():
    save_coral_to_wav(
        path="audio",
        len_seconds=30,
        hf_token=os.getenv("HF_TOKEN"),
        split="test",
        n_take=10,
    )


if __name__ == "__main__":
    main()
