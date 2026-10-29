"""Explicit CP1/VF1 selection; original enrollment assets remain unchanged."""
import hashlib
from pathlib import Path

MODELS = {
    'cp1/fixed98.onnx': '5012f8f3afd594943d37384524a8b596b1fc860c5f371058b783c396411396ac',
    'vf1/vad16_fixed.onnx': '2f9baaee7df0ff223225b6fcb176ad0ae33542c7ae83015d7f87351c5c32d84c',
}


def verify_candidates(core, window=1., rate=16000):
    if window != 1. or rate != 16000:
        raise ValueError('CP1/VF1 require one second and native frontend 16000 Hz')
    for name, expected in MODELS.items():
        path = Path(core)/'models'/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Candidate model does not match B delivery: '+name)
    return dict(selection='cp1_vf1', sample_rate=16000, embedding_shape=[1, 98, 80],
                vad_shape=[1, 576], vad_state_shape=[2, 1, 128], sha256=dict(MODELS),
                enrollment_model='int8-head.onnx', recognition_qualified=False)


def backend_options(role):
    # Each process only loads its own role. Enrollment/other windows keep original models.
    if role == 'front':
        return dict(vad_filename='vf1/vad16_fixed.onnx')
    if role == 'embed':
        return dict(model_filename='cp1/fixed98.onnx')
    raise ValueError('Unknown backend role')
