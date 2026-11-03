"""Explicit, resumable guided setup; never grants permissions or starts audio."""
from dataclasses import replace

SETUP_VERSION = 1
STEPS = ('Welcome', 'Permissions', 'Microphone', 'Model and language', 'Practice', 'Ready')


def snapshot(config):
    return {'version': SETUP_VERSION, 'completed': config.onboarding_version >= SETUP_VERSION,
            'step': config.onboarding_step, 'steps': list(STEPS)}


def candidate(config, step, complete=False):
    if type(step) is not int or not 0 <= step < len(STEPS):
        raise ValueError('Choose a valid setup step.')
    if type(complete) is not bool:
        raise ValueError('Invalid setup completion state.')
    if complete and step != len(STEPS) - 1:
        raise ValueError('Finish the final setup page before marking setup complete.')
    return replace(config, onboarding_step=step,
                   onboarding_version=SETUP_VERSION if complete else config.onboarding_version)
