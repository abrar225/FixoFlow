"""
Fixoflow Command Line Interface
Provides commands to start the daemon, test dictation interactively, and inspect settings.
"""
from __future__ import annotations

import argparse
import logging
import sys

from fixoflow.config import FixoflowConfig
from fixoflow.core import FixoflowCoordinator


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_start(args):
    """Use the same single-instance application and floating controls as the DMG."""
    from fixoflow.desktop import main as app_main
    return app_main(["--background"])


def cmd_hub(args):
    """Open the shared application, rather than a second disconnected GUI."""
    from fixoflow.desktop import main as app_main
    return app_main([])


def cmd_record(args):
    """Interactive terminal record session (Press Enter to start, Enter to finish)."""
    config = FixoflowConfig.load()
    coordinator = FixoflowCoordinator(config, enable_overlay=False)

    print("\nFixoflow interactive dictation")
    input("Press [Enter] to start recording...")
    coordinator.start_recording()
    print("Recording. Speak naturally; press [Enter] again to stop.")
    input()

    print("Transcribing on the local Whisper model...")
    text = coordinator.stop_and_process(auto_paste=args.paste)

    print("\n" + "=" * 60)
    print("RESULT:")
    print(text)
    print("=" * 60)
    if not text:
        print(coordinator.last_error or "No transcript was produced.")
    elif not args.paste:
        print("Clipboard untouched (--no-paste).")
    elif coordinator.last_error:
        print(coordinator.last_error)
    else:
        print("Pasted at the cursor.")


def cmd_transcribe(args):
    """Transcribe an existing WAV/audio file."""
    import scipy.io.wavfile as wav
    import numpy as np

    config = FixoflowConfig.load()
    coordinator = FixoflowCoordinator(config, enable_overlay=False)

    print(f"Loading {args.file}...")
    sr, data = wav.read(args.file)
    if data.dtype == np.int16:
        audio = data.astype(np.float32) / 32768.0
    elif data.dtype == np.float32:
        audio = data
    else:
        audio = data.astype(np.float32)

    if len(audio.shape) > 1:
        audio = audio[:, 0]  # mono

    if sr != config.sample_rate:
        from scipy.signal import resample_poly
        audio = resample_poly(audio, config.sample_rate, sr).astype(np.float32)

    print("Transcribing...")
    raw = coordinator.stt.transcribe(audio)
    formatted = coordinator.learner.format_for_mode(raw, mode=config.mode, app_name="")
    effective_mode = coordinator.learner.effective_mode(config.mode, "")
    polished = coordinator.polisher.polish(formatted, app_context="", mode=effective_mode)

    print("\n" + "=" * 60)
    print("Raw:     ", raw)
    print("Polished:", polished)
    print("=" * 60)


def cmd_config(args):
    """View or modify configuration."""
    config = FixoflowConfig.load()
    if args.model:
        config.model_name = args.model
    if args.hotkey:
        from fixoflow.shortcuts import Shortcut
        config.hold_shortcut = Shortcut.from_text(args.hotkey).as_dict()
    if args.hands_free_shortcut:
        from fixoflow.shortcuts import Shortcut
        config.hands_free_shortcut = Shortcut.from_text(args.hands_free_shortcut).as_dict()
    if args.polisher:
        config.polishing_engine = args.polisher

    config.validate_product()
    config.save()
    print("Current Configuration:")
    for k, v in config.__dict__.items():
        print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(prog="fixoflow", description="Fixoflow: Zero-Loss Local Local Voice Dictation")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    subparsers = parser.add_subparsers(dest="command")

    # start
    subparsers.add_parser("start", help="Start background hotkey daemon")

    # record
    rec_parser = subparsers.add_parser("record", help="Interactive terminal dictation session")
    rec_parser.add_argument("--no-paste", dest="paste", action="store_false", default=True, help="Don't auto-paste")

    # transcribe
    tr_parser = subparsers.add_parser("transcribe", help="Transcribe an audio file")
    tr_parser.add_argument("file", help="Path to WAV audio file")

    # config
    cfg_parser = subparsers.add_parser("config", help="View or update configuration")
    cfg_parser.add_argument("--model", help="Whisper model (e.g. mlx-community/whisper-tiny, mlx-community/whisper-base)")
    cfg_parser.add_argument("--hold-shortcut", "--hotkey", dest="hotkey", help="Hold-to-talk keys, e.g. <ctrl>+<space>")
    cfg_parser.add_argument("--hands-free-shortcut", help="Toggle keys, e.g. <alt>+<space>")
    cfg_parser.add_argument("--polisher", choices=["rules", "none"], help="Polishing engine")

    # hub
    subparsers.add_parser("hub", help="Open Fixoflow Hub GUI dashboard")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "start":
        cmd_start(args)
    elif args.command == "hub":
        cmd_hub(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "transcribe":
        cmd_transcribe(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
