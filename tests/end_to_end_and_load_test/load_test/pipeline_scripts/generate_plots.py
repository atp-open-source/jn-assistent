import argparse
from json.tool import main
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def generate_plots(stats_history_path: Path, active_calls_path: Path, output_dir: Path):
    """
    Genererer plots fra CSV-filer med load test statistikker og aktive kald.
    Gemmer plots i det angivne output directory.

    Plots er opdelts efter endpoint-navn. For hvert endpoint genereres tre plots:
    1. Responstid over tid (50% og 95% percentiler)
    2. Kald pr. sekund og fejl pr. sekund over tid
    3. Antal brugere og aktive kald over tid (samme for alle endpoints)
    """

    # Load data
    stats_df = pd.read_csv(stats_history_path)
    active_calls_df = pd.read_csv(active_calls_path)
    stats_df["Timestamp"] = pd.to_datetime(stats_df["Timestamp"])
    active_calls_df["timestamp"] = pd.to_datetime(active_calls_df["timestamp"])
    start_timestamp = min(
        stats_df["Timestamp"].min(), active_calls_df["timestamp"].min()
    )
    stats_df["Timestamp"] = stats_df["Timestamp"] - start_timestamp
    active_calls_df["timestamp"] = active_calls_df["timestamp"] - start_timestamp

    # Sørg for at output directory eksisterer
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generér plots
    for name in stats_df["Name"].unique():
        df_name = stats_df[stats_df["Name"] == name]
        fig, ax = plt.subplots(1, 3, figsize=(27, 6))

        # Plot responstid
        ax[0].grid()
        ax[0].plot(df_name["Timestamp"], df_name["50%"], label="50%")
        ax[0].plot(df_name["Timestamp"], df_name["95%"], label="95%")
        ax[0].set_xlabel("Tid (s)")
        ax[0].set_ylabel("Responstid (ms)")
        ax[0].legend()
        ax[0].set_title("Responstid")

        # Plot kald og fejl pr. sekund
        ax[1].grid()
        ax[1].plot(
            df_name["Timestamp"], df_name["Requests/s"], label="Kald/s", color="orange"
        )
        ax[1].plot(
            df_name["Timestamp"], df_name["Failures/s"], label="Fejl/s", color="red"
        )
        ax[1].set_xlabel("Tid (s)")
        ax[1].set_ylabel("Kald/s")
        ax[1].legend()
        ax[1].set_title("Kald og fejl pr. sekund")

        # Plot brugere og aktive kald
        ax[2].grid()
        ax[2].plot(
            df_name["Timestamp"], df_name["User Count"], label="Brugere", color="green"
        )
        ax[2].plot(
            active_calls_df["timestamp"],
            active_calls_df["active_calls"],
            label="Aktive kald",
            color="purple",
        )
        ax[2].set_xlabel("Tid (s)")
        ax[2].set_ylabel("Brugere")
        ax[2].legend()
        ax[2].set_title("Antal brugere og aktive kald")

        # Sæt overskrift
        fig.suptitle(f"{name}")

        # Gem plots
        output_path = (
            output_dir
            / f"{name.replace('/', '_').replace(':', '_').replace(' ', '_')}_plots.png"
        )
        fig.savefig(output_path)


def _parse_args() -> tuple[Path, Path, Path]:
    """
    Parse kommandolinjeargumenter for stier til input CSV-filer og output directory.
    """

    parser = argparse.ArgumentParser(description="Generér plots fra load test output.")
    parser.add_argument(
        "-s",
        "--stats-history",
        type=Path,
        required=True,
        help="Sti til load test stats history CSV-fil.",
    )
    parser.add_argument(
        "-a",
        "--active-calls",
        type=Path,
        required=True,
        help="Sti til aktive kald history CSV-fil.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory til gemte plots. Oprettes hvis det ikke findes.",
    )
    args = parser.parse_args()
    return args.stats_history, args.active_calls, args.output_dir


def main() -> None:
    stats_history, active_calls, output_dir = _parse_args()
    generate_plots(stats_history, active_calls, output_dir)


if __name__ == "__main__":
    main()
