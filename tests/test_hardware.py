import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('hardware', Path(__file__).resolve().parents[1] / 'deploy/hardware.py')
hardware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardware)


@unittest.skipIf(os.name != 'posix', 'sysfs symlink policy exercised by Linux CI')
class HardwareDiscoveryTests(unittest.TestCase):
    def test_only_complete_prebound_iommu_group_is_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'devices'; root.mkdir()
            group = base / 'group/devices'; group.mkdir(parents=True)
            for name, kind in [('0000:01:00.0', '0x030000'), ('0000:01:00.1', '0x040300')]:
                device = root / name; device.mkdir()
                (device / 'class').write_text(kind)
                (device / 'vendor').write_text('0x1002')
                (device / 'driver').symlink_to(base / 'drivers/vfio-pci')
                (device / 'iommu_group').symlink_to(group.parent, target_is_directory=True)
                (group / name).symlink_to(device, target_is_directory=True)
            self.assertEqual(hardware.dedicated_gpus(root), [{'devices': ['0000:01:00.0', '0000:01:00.1'], 'vendor': '0x1002'}])
            # An unrelated IOMMU peer makes the entire candidate unsafe.
            (group / '0000:02:00.0').symlink_to(base / 'other-device')
            self.assertEqual(hardware.dedicated_gpus(root), [])
            (group / '0000:02:00.0').unlink()
            driver = root / '0000:01:00.0/driver'
            driver.unlink(); driver.symlink_to(base / 'drivers/amdgpu')
            self.assertEqual(hardware.dedicated_gpus(root), [])


if __name__ == '__main__':
    unittest.main()
