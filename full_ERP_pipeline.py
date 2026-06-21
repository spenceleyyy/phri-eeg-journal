import pyxdf
import pandas as pd
import numpy as np
from pathlib import Path
import traceback

# -----------------------
# USER SETTINGS
# -----------------------

XDF_FOLDER = Path("/path/to")
TRIGGER_FOLDER = Path("/path/to")
OUTPUT_ROOT = Path("Batch_Output")

PARTICIPANTS = {
    ##"PHRIE01": 107,
    ##"PHRIE02": 115,
    ##"PHRIE03": 118,
    ##"PHRIE04": 118,
    ##"PHRIE05": 
    #"PHRIE06": 118,
    #"PHRIE07": 111.4,
    #"PHRIE08": 103,
    #"PHRIE09": 112.5,
    #"PHRIE10": 117.2,
    ##"PHRIE11": 
    #"PHRIE12": 105.3,
    "PHRIE13": 100.8,
    "PHRIE13_2": 100.8,
    #"PHRIE14": 110,
    #"PHRIE15": 111,
    #"PHRIE16": 106.1,
    #"PHRIE17": 118.2,
    "PHRIE18": 110.9,
    "PHRIE18_2": 110.9,
    #"PHRIE19": 102,
    #"PHRIE20": 115.6,
    #"PHRIE21": 101.4,
    #"PHRIE22": 112.7,
    #"PHRIE23": 103.4,
    #"PHRIE24": 106,
    #"PHRIE25": 116.5,
    #"PHRIE26": 116,
    #"PHRIE27": 104,
    #"PHRIE28": 116.5,
    #"PHRIE29": 106.2,
    #"PHRIE30": 116.2,
    #"PHRIE32": 113.0,
    #"PHRIE33": 118.1,
    #"PHRIE34": 109,
    #"PHRIE35": 113,
    #"PHRIE36": 105,
    "PHRIE37": 111.1,
    "PHRIE37_2": 111.1,
    #"PHRIE38": 117.6,
    #"PHRIE39": 113.1,
    #"PHRIE40": 109.5,
    #"PHRIE41": 111.5,
}

DEBUG_FIRST_TRIAL = False

RADIUS_M = 0.02
MAX_CLOSEST_DISTANCE_M = 0.12
MIN_GAP_SEC = 2.0


# -----------------------
# BASE ERP POSITIONS
# These are zero-offset positions at 103 cm table height (original trigger coordinates)
# -----------------------

BASE_TARGETS = {
    "ERP_1":     (0.725,  0.449, 0.398),
    "ERP_2":     (0.725,  0.271, 0.397),
    "ERP_3":     (0.725,  0.271, 0.669),
    "ERP_4_T1":  (0.725,  0.486, 0.684),
    "ERP_5_mid": (0.725,  0.233, 0.752),
    "ERP_6_mid": (0.725, -0.234, 0.752),
}

#
# Offset correction is handled globally through BASE_TABLE_HEIGHT_CM.
# No per-ERP Z corrections should be applied here.
Z_CORRECTIONS_M = {
    "ERP_1":     0.0000,
    "ERP_2":     0.0000,
    "ERP_3":     0.0000,
    "ERP_4_T1":  0.0000,
    "ERP_5_mid": 0.0000,
    "ERP_6_mid": 0.0000,
}

# -----------------------
# HELPERS
# -----------------------

def stream_id(s):
    name = s["info"].get("name", [""])[0]
    stype = s["info"].get("type", [""])[0]
    source_id = s["info"].get("source_id", [""])[0]
    return name, stype, source_id


def print_streams(streams, title):
    print(f"\n{title}")
    for i, s in enumerate(streams):
        name, stype, source_id = stream_id(s)
        samples = len(s["time_stamps"])
        shape = np.asarray(s.get("time_series", [])).shape
        first_ts = s["time_stamps"][0] if samples > 0 else np.nan
        last_ts = s["time_stamps"][-1] if samples > 0 else np.nan
        print(
            f"{i}: name={name}, type={stype}, source_id={source_id}, "
            f"samples={samples}, shape={shape}, first={first_ts}, last={last_ts}"
        )


def find_robot_stream(streams):
    for i, s in enumerate(streams):
        name, stype, source_id = stream_id(s)
        if name == "UR10robot" or stype == "RobotPositions":
            return i, s
    raise ValueError("Could not find UR10robot / RobotPositions stream.")



def find_trigger_stream(streams):
    # Main corrected triggers appear to be in the stream named Trigger, not the empty actiCHampMarkers stream.
    for i, s in enumerate(streams):
        name, stype, source_id = stream_id(s)
        if name == "Trigger" and len(s["time_stamps"]) > 0:
            return i, s

    # Fallback: first non-empty marker/trigger stream.
    for i, s in enumerate(streams):
        name, stype, source_id = stream_id(s)
        if ("Marker" in stype or "Trigger" in stype or "Markers" in stype) and len(s["time_stamps"]) > 0:
            return i, s

    raise ValueError("Could not find a non-empty Trigger/Markers stream.")


# EEG stream selection
def find_eeg_stream(streams):
    # Prefer actiCHamp EEG streams.
    for i, s in enumerate(streams):
        name, stype, source_id = stream_id(s)
        if "actiCHamp" in name and stype == "EEG" and len(s["time_stamps"]) > 0:
            return i, s

    # Fallback: first non-empty EEG stream.
    for i, s in enumerate(streams):
        name, stype, source_id = stream_id(s)
        if stype == "EEG" and len(s["time_stamps"]) > 0:
            return i, s

    raise ValueError("Could not find a non-empty EEG stream.")




# -----------------------
# LOAD XDF ONCE WITH SYNCHRONIZED CLOCKS
# Robot positions and triggers will already share the same XDF time base.
# -----------------------

def process_participant(participant_id, participant_table_height_cm):
    print(f"\n{'='*80}")
    print(f"Processing {participant_id}")
    print(f"{'='*80}")

    xdf_file = XDF_FOLDER / f"{participant_id}.xdf"
    corrected_trigger_csv = TRIGGER_FOLDER / f"{participant_id}.csv"

    if not xdf_file.exists():
        raise FileNotFoundError(f"Missing XDF file: {xdf_file}")

    if not corrected_trigger_csv.exists():
        raise FileNotFoundError(f"Missing corrected trigger CSV: {corrected_trigger_csv}")

    participant_output_dir = OUTPUT_ROOT / participant_id
    participant_output_dir.mkdir(parents=True, exist_ok=True)

    output_csv = participant_output_dir / f"{participant_id}_combined_corrected_and_erp_triggers_COMMON_TIME.csv"

    BASE_TABLE_HEIGHT_CM = 103.0

    streams, header = pyxdf.load_xdf(
        str(xdf_file),
        synchronize_clocks=True,
        dejitter_timestamps=False,
        handle_clock_resets=True,
        verbose=True
    )

    print_streams(streams, "Synchronized XDF streams:")

    robot_idx, robot_stream = find_robot_stream(streams)
    trigger_idx, trigger_stream = find_trigger_stream(streams)
    eeg_idx, eeg_stream = find_eeg_stream(streams)

    print(
        f"\nUsing robot stream: index {robot_idx}, "
        f"name={stream_id(robot_stream)[0]}, type={stream_id(robot_stream)[1]}"
    )
    print(
        f"Using trigger stream: index {trigger_idx}, "
        f"name={stream_id(trigger_stream)[0]}, type={stream_id(trigger_stream)[1]}"
    )
    print(
        f"Using EEG stream: index {eeg_idx}, "
        f"name={stream_id(eeg_stream)[0]}, type={stream_id(eeg_stream)[1]}"
    )

    eeg_ts = np.asarray(eeg_stream["time_stamps"], dtype=float)
    eeg_start_xdf_time = float(eeg_ts[0])

    try:
        eeg_srate = float(eeg_stream["info"]["nominal_srate"][0])
    except Exception:
        eeg_srate = 1.0 / float(np.median(np.diff(eeg_ts)))

    print("\nEEGLAB timing reference:")
    print(f"EEG start XDF time: {eeg_start_xdf_time}")
    print(f"EEG sampling rate: {eeg_srate}")

    # -----------------------
    # LOAD CORRECTED TRIGGER CSV
    # -----------------------

    corrected = pd.read_csv(str(corrected_trigger_csv))

    # -----------------------
    # FORMAT CORRECTED TRIGGERS
    # Corrected trigger CSV already uses XDF timestamps.
    # -----------------------

    corrected = corrected.rename(columns={
        "timestamp": "xdf_time",
        "raw_xdf_time": "xdf_time",
        "marker_id": "event_label",
        "Trigger": "event_label",
        "trigger": "event_label",
        "Marker": "event_label",
        "marker": "event_label",
    })

    if "xdf_time" not in corrected.columns:
        raise ValueError("Corrected trigger CSV must contain a timestamp/xdf_time column.")

    if "event_label" not in corrected.columns:
        corrected["event_label"] = [f"corrected_trigger_{i+1}" for i in range(len(corrected))]

    corrected_events = corrected[["xdf_time", "event_label"]].copy()
    corrected_events = corrected_events.dropna(subset=["xdf_time"])
    corrected_events["xdf_time"] = corrected_events["xdf_time"].astype(float)
    corrected_events["event_label"] = corrected_events["event_label"].astype(str)
    corrected_events["source"] = "corrected_trigger"
    corrected_events["raw_xdf_time"] = corrected_events["xdf_time"]
    corrected_events["unix_time"] = np.nan
    corrected_events["distance_m"] = np.nan
    corrected_events["seconds_from_eeg_start"] = corrected_events["xdf_time"] - eeg_start_xdf_time
    corrected_events["eeglab_latency"] = np.round(
        corrected_events["seconds_from_eeg_start"] * eeg_srate
    ).astype(int) + 1

    # Build robot trial windows from matching trigger pairs.
    ROBOT_LABELS = {"6", "7", "11", "12", "6.0", "7.0", "11.0", "12.0"}

    trial_windows = []

    for label in sorted(ROBOT_LABELS, key=lambda x: float(x)):
        events = corrected_events[
            corrected_events["event_label"].astype(str) == label
        ].sort_values("xdf_time")

        times = events["xdf_time"].tolist()

        for i in range(0, len(times) - 1, 2):
            trial_windows.append({
                "label": label,
                "start": float(times[i]),
                "stop": float(times[i + 1])
            })

    trial_windows = sorted(trial_windows, key=lambda x: x["start"])

    print("\nTrial windows:")
    for i, w in enumerate(trial_windows, start=1):
        print(
            f"Trial {i}: label={w['label']} start={w['start']:.3f} "
            f"stop={w['stop']:.3f} duration={w['stop'] - w['start']:.3f}s"
        )

    print(f"\nRobot trial windows found: {len(trial_windows)}")

    # -----------------------
    # EXTRACT ROBOT POSITION DATA DIRECTLY FROM XDF
    # UR10robot columns: 0=X, 1=Y, 2=Z, 3=Unix timestamp
    # -----------------------

    robot_ts = np.asarray(robot_stream["time_stamps"], dtype=float)
    robot_data = np.asarray(robot_stream["time_series"], dtype=float)

    if robot_data.ndim != 2 or robot_data.shape[1] < 3:
        raise ValueError("UR10robot stream must have at least 3 columns for X/Y/Z.")

    pos = pd.DataFrame({
        "xdf_time": robot_ts,
        "raw_robot_xdf_time": robot_ts,
        "X Position (m)": robot_data[:, 0],
        "Y Position (m)": robot_data[:, 1],
        "Z Position (m)": robot_data[:, 2],
    })

    if robot_data.shape[1] >= 4:
        pos["Timestamp"] = robot_data[:, 3]
    else:
        pos["Timestamp"] = np.nan

    print("\nRobot data extracted directly from XDF:")
    print(f"Robot samples: {len(pos)}")
    print(f"Robot XDF time range: {pos['xdf_time'].min()} to {pos['xdf_time'].max()}")
    print(f"Corrected trigger XDF time range: {corrected_events['xdf_time'].min()} to {corrected_events['xdf_time'].max()}")
    print(f"Current detection radius: {RADIUS_M:.4f} m")

    # -----------------------
    # APPLY TABLE HEIGHT OFFSET TO ERP TARGETS
    # -----------------------

    z_offset_m = (participant_table_height_cm - BASE_TABLE_HEIGHT_CM) / 100.0

    # Coordinates are only reliable to 3 decimals, so round adjusted targets
    # before matching against the robot trajectory.
    targets = {
        label: np.round(
            np.array([x, y, z + z_offset_m + Z_CORRECTIONS_M.get(label, 0.0)], dtype=float),
            3
        )
        for label, (x, y, z) in BASE_TARGETS.items()
    }

    print("\nTable height correction:")
    print(f"participant_id: {participant_id}")
    print(f"table height cm: {participant_table_height_cm}")
    print(f"z offset m: {z_offset_m:.4f}")

    print("\nAdjusted ERP targets:")
    for label, target in targets.items():
        print(
            f"{label}: x={target[0]:.4f}, y={target[1]:.4f}, z={target[2]:.4f} "
            f"(z correction={Z_CORRECTIONS_M.get(label, 0.0):+.4f})"
        )
    print("\nNOTE: ERP matching is running with NO candidate padding or distance expansion.")

    # -----------------------
    # GENERATE ROBOT POSITION ERP TRIGGERS ACROSS FULL ROBOT TRAJECTORY
    # -----------------------

    required_position_cols = [
        "X Position (m)",
        "Y Position (m)",
        "Z Position (m)",
    ]

    for col in required_position_cols:
        if col not in pos.columns:
            raise ValueError(f"Missing required position column: {col}")

    robot_events = []
    trial_summaries = []

    target_sequence = [
        "ERP_1",
        "ERP_2",
        "ERP_3",
        "ERP_4_T1",
        "ERP_5_mid",
        "ERP_6_mid",
    ]

    xyz = pos[required_position_cols].to_numpy(dtype=float)
    pos_times = pos["xdf_time"].to_numpy(dtype=float)

    for trial_idx, window in enumerate(trial_windows, start=1):

        start_t = window["start"]
        stop_t = window["stop"]

        window_mask = (pos_times >= start_t) & (pos_times <= stop_t)

        if not np.any(window_mask):
            continue

        window_indices = np.where(window_mask)[0]

        # Order-constrained matching:
        # For each ERP target, use all samples in the trial window as candidates.
        candidate_lists = []

        for label in target_sequence:
            target_xyz = targets[label]
            d_all = np.linalg.norm(xyz[window_indices] - target_xyz, axis=1)

            # No padding or radius expansion. Use the raw distances exactly as
            # observed in the robot trajectory.
            keep_local = np.arange(len(d_all))

            candidates = []
            for local_idx in keep_local:
                global_idx = int(window_indices[int(local_idx)])
                candidates.append({
                    "idx": global_idx,
                    "time": float(pos.iloc[global_idx]["xdf_time"]),
                    "distance": float(d_all[int(local_idx)]),
                })

            candidates = sorted(candidates, key=lambda c: c["time"])
            candidate_lists.append(candidates)

        dp = []
        back = []

        for k, candidates in enumerate(candidate_lists):
            dp_k = [np.inf] * len(candidates)
            back_k = [-1] * len(candidates)

            for j, cand in enumerate(candidates):
                cost = cand["distance"] ** 2

                if k == 0:
                    dp_k[j] = cost
                else:
                    best_prev_cost = np.inf
                    best_prev_idx = -1

                    for p, prev in enumerate(candidate_lists[k - 1]):
                        if prev["time"] <= cand["time"] and dp[k - 1][p] < best_prev_cost:
                            best_prev_cost = dp[k - 1][p]
                            best_prev_idx = p

                    if best_prev_idx >= 0:
                        dp_k[j] = best_prev_cost + cost
                        back_k[j] = best_prev_idx

            dp.append(dp_k)
            back.append(back_k)

        if len(dp[-1]) == 0 or not np.isfinite(np.min(dp[-1])):
            print(f"WARNING: Could not find ordered ERP path in trial {trial_idx}; skipping trial.")
            continue

        last_choice = int(np.argmin(dp[-1]))
        chosen = [None] * len(target_sequence)

        for k in range(len(target_sequence) - 1, -1, -1):
            chosen[k] = candidate_lists[k][last_choice]
            last_choice = back[k][last_choice]
            if k > 0 and last_choice < 0:
                print(f"WARNING: Broken backtrace in trial {trial_idx}; skipping trial.")
                chosen = None
                break

        if chosen is None:
            continue

        # --- REMOVE TRIAL QUALITY FILTER BLOCK ---
        # (was: skip trial if median distance exceeds TRIAL_QUALITY_MAX_MEDIAN_DISTANCE_M)
        # --- END REMOVE ---

        selected_times_for_order_check = []

        parent_label = str(window["label"]).replace(".0", "")

        for erp_number, (label, chosen_cand) in enumerate(zip(target_sequence, chosen), start=1):
            output_event_label = f"{parent_label}_{erp_number}"
            target_xyz = targets[label]
            best_idx = int(chosen_cand["idx"])
            best_distance = float(chosen_cand["distance"])
            selected_times_for_order_check.append((label, float(pos.iloc[best_idx]["xdf_time"])))

            actual_xyz = xyz[best_idx]
            diff_xyz = actual_xyz - target_xyz
            # Debug: print target vs actual coordinates for the first trial
            if DEBUG_FIRST_TRIAL and trial_idx == 1:
                print(
                    f"\n{label}"
                    f"\n  target: x={target_xyz[0]:.3f}, y={target_xyz[1]:.3f}, z={target_xyz[2]:.3f}"
                    f"\n  actual: x={actual_xyz[0]:.3f}, y={actual_xyz[1]:.3f}, z={actual_xyz[2]:.3f}"
                    f"\n  diff:   x={diff_xyz[0]:.3f}, y={diff_xyz[1]:.3f}, z={diff_xyz[2]:.3f}"
                    f"\n  dist:   {best_distance:.3f} m"
                )
            status = "accepted" if best_distance <= MAX_CLOSEST_DISTANCE_M else "too_far"

            trial_summaries.append({
                "sequence": trial_idx,
                "event_label": output_event_label,
                "erp_target_label": label,
                "parent_window_label": parent_label,
                "status": status,
                "closest_distance_m": best_distance,
                "xdf_time": float(pos.iloc[best_idx]["xdf_time"]),
                "seconds_from_eeg_start": float(pos.iloc[best_idx]["xdf_time"]) - eeg_start_xdf_time,
                "eeglab_latency": int(round((float(pos.iloc[best_idx]["xdf_time"]) - eeg_start_xdf_time) * eeg_srate)) + 1,
                "unix_time": float(pos.iloc[best_idx]["Timestamp"]),
                "target_x": float(target_xyz[0]),
                "target_y": float(target_xyz[1]),
                "target_z": float(target_xyz[2]),
                "actual_x": float(actual_xyz[0]),
                "actual_y": float(actual_xyz[1]),
                "actual_z": float(actual_xyz[2]),
                "diff_x": float(diff_xyz[0]),
                "diff_y": float(diff_xyz[1]),
                "diff_z": float(diff_xyz[2]),
            })

            if status != "accepted":
                print(
                    f"WARNING: Inserting {label} in trial {trial_idx} even though closest ordered distance "
                    f"{best_distance:.4f} m exceeds MAX_CLOSEST_DISTANCE_M={MAX_CLOSEST_DISTANCE_M:.4f}. "
                    f"Distance is diagnostic only."
                )

            robot_events.append({
                "xdf_time": float(pos.iloc[best_idx]["xdf_time"]),
                "raw_xdf_time": float(pos.iloc[best_idx]["raw_robot_xdf_time"]),
                "seconds_from_eeg_start": float(pos.iloc[best_idx]["xdf_time"]) - eeg_start_xdf_time,
                "eeglab_latency": int(round((float(pos.iloc[best_idx]["xdf_time"]) - eeg_start_xdf_time) * eeg_srate)) + 1,
                "event_label": output_event_label,
                "source": "robot_position",
                "unix_time": float(pos.iloc[best_idx]["Timestamp"]),
                "distance_m": best_distance,
                "sequence": trial_idx,
                "erp_target_label": label,
                "parent_window_label": parent_label,
            })

        ordered_times = [t for _, t in selected_times_for_order_check]
        if any(ordered_times[i] > ordered_times[i + 1] for i in range(len(ordered_times) - 1)):
            print(f"WARNING: ERP timestamp order mismatch in trial {trial_idx}: {selected_times_for_order_check}")

    trial_summaries_df = pd.DataFrame(trial_summaries)

    summary_csv = str(output_csv).replace(".csv", "_global_erp_detection_summary.csv")
    trial_summaries_df.to_csv(str(summary_csv), index=False)
    print(f"\nSaved trial detection summary: {summary_csv}")

    robot_events = pd.DataFrame(robot_events)
    if robot_events.empty:
        print("\nWARNING: No robot ERP events found.")
        robot_events = pd.DataFrame(columns=[
            "xdf_time", "raw_xdf_time", "seconds_from_eeg_start", "eeglab_latency",
            "event_label", "source", "unix_time", "distance_m",
            "sequence", "erp_target_label", "parent_window_label"
        ])
    else:
        print("\nRobot ERP events by label:")
        print(robot_events.groupby("event_label")["xdf_time"].count())

        print("\nClosest-distance summary by label:")
        print(robot_events.groupby("event_label")["distance_m"].agg(["min", "median", "max", "count"]))

        if not trial_summaries_df.empty:
            print("\nTarget-vs-actual median coordinate error by label:")
            print(
                trial_summaries_df.groupby("event_label")[["diff_x", "diff_y", "diff_z", "closest_distance_m"]]
                .median(numeric_only=True)
            )

    # -----------------------
    # COMBINE AND SAVE
    # -----------------------

    #
    # Add optional sequence/erp_target_label/parent_window_label columns to corrected events so concatenation is clean.
    corrected_events["sequence"] = np.nan
    corrected_events["erp_target_label"] = np.nan
    corrected_events["parent_window_label"] = np.nan

    combined_cols = [
        "xdf_time", "raw_xdf_time", "seconds_from_eeg_start", "eeglab_latency",
        "event_label", "source", "unix_time", "distance_m",
        "sequence", "erp_target_label", "parent_window_label"
    ]

    combined = pd.concat(
        [
            corrected_events[combined_cols],
            robot_events[combined_cols],
        ],
        ignore_index=True
    )

    combined = combined.sort_values("xdf_time").reset_index(drop=True)
    combined = combined[
        (combined["eeglab_latency"].notna()) &
        (combined["eeglab_latency"] >= 1) &
        (combined["eeglab_latency"] <= len(eeg_ts))
    ].reset_index(drop=True)
    combined.to_csv(str(output_csv), index=False)

    print(f"\nSaved combined event file: {output_csv}")
    print(f"Corrected trigger events: {len(corrected_events)}")
    print(f"Robot ERP events: {len(robot_events)}")
    print(f"Total events: {len(combined)}")

    print("\nCombined common-time ranges by source:")
    print(combined.groupby("source")["xdf_time"].agg(["min", "max", "count"]))

    print("\nFirst 40 combined events:")
    print(combined.head(40).to_string(index=False))


for participant_id, participant_table_height_cm in PARTICIPANTS.items():
    try:
        process_participant(participant_id, participant_table_height_cm)
    except Exception as e:
        print(f"\nERROR processing {participant_id}: {e}")
        traceback.print_exc()
        print("Skipping participant and continuing.")
