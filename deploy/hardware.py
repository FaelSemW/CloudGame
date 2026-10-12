"""Read-only discovery of GPUs already dedicated to VFIO; never detaches a GPU."""
from pathlib import Path


def dedicated_gpus(root=Path('/sys/bus/pci/devices')):
    candidates = []
    if not root.is_dir(): return candidates
    for gpu in sorted(root.iterdir()):
        try:
            if not (gpu / 'class').read_text().strip().startswith('0x03'):
                continue
            if (gpu / 'driver').resolve().name != 'vfio-pci':
                continue
            functions = [p for p in root.iterdir() if p.name.rsplit('.', 1)[0] == gpu.name.rsplit('.', 1)[0]]
            devices = {p.name for p in functions}
            if all((p / 'driver').resolve().name == 'vfio-pci'
                   and (p / 'class').read_text().strip().startswith(('0x03', '0x0403'))
                   and (p / 'iommu_group/devices').is_dir()
                   and {d.name for d in (p / 'iommu_group/devices').iterdir()} <= devices
                   for p in functions):
                candidates.append({'devices': sorted(devices), 'vendor': (gpu / 'vendor').read_text().strip()})
        except OSError:
            continue
    return candidates
